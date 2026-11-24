"""Parse the SOE Software page-per-sheet Excel exports into precinct CSVs.

Inputs:  ~/code/openelections-sources-nj/2026/primary/
           Middlesex NJ Primary Election 2026 Detail Report.xlsx
           Atlantic NJ primary.xlsx
           Somerset NJ 2026 Primary District Results.xlsx
           Monmouth NJ 2026 Primary District Detail.xls
Outputs: 2026/counties/20260602__nj__primary__<county>__precinct.csv

All four counties use the same vendor design: a "Table of Contents" sheet maps
page numbers to contest titles, and each remaining sheet is one report page.
A contest page holds a candidate-name row over columns of votes and a column
header row ("Precinct"/"County"/"District", "Registered Voters", then vote
types repeated per candidate), followed by one row per precinct and a
"Total:" row. Vote-type cells may read "protected" where the county
suppressed a count; those parse as 0. Middlesex has no per-precinct candidate
total, so its `votes` is the sum of the (unprotected) breakdown columns --
an undercount of the official totals; Somerset redacts even its per-county
"Total:" row.

County variations handled here:
  - Monmouth's export is Excel 2003 SpreadsheetML in a .xls file; the rest
    are .xlsx.
  - Middlesex/Atlantic carry per-candidate vote-type columns (Election Day,
    Early Voting, Vote by Mail, Provisional) and publish them as breakdown
    columns. Their "Registered Voters" page also reports Ballots Cast, which
    feeds both pseudo-rows.
  - Somerset/Monmouth only report a "Total Votes" column per candidate, so
    `votes` is that cell and no breakdown columns are published. Somerset has
    no Registered Voters page; it gets party-tagged Ballots Cast pseudo-rows
    from its two "BALLOTS CAST" pages instead. Monmouth's turnout page feeds
    both pseudo-rows, and its "FED Overseas" rows (district-wide military/
    UOCAVA votes) are dropped per the 2024 Monmouth precedent.
  - Middlesex keeps its "CD 6"/"CD 12" pseudo-precinct rows (district-wide
    mail ballots) and "<Town> Provisional" rows per the 2024 Middlesex file.

The crosscheck against 2026/20260602__nj__primary__county.csv reports the
(expected, suppressed-vote) gaps for Middlesex; Monmouth's reports the
dropped overseas votes.
"""

import csv
import os
import re
import warnings
import xml.etree.ElementTree as ET

import openpyxl

SOURCE_DIR = "/Users/dwillis/code/openelections-sources-nj/2026/primary"
OUTPUT_DIR = "2026/counties"
OUTPUT_PREFIX = "20260602__nj__primary"
COUNTY_CSV = "2026/20260602__nj__primary__county.csv"
CROSSCHECK_OFFICES = {"U.S. Senate", "U.S. House"}

BASE_HEADER = ["county", "precinct", "office", "district", "party",
               "candidate", "votes"]
BREAKDOWN_HEADER = ["early_voting", "election_day", "vote_by_mail",
                    "provisional"]

DROP_PRECINCT_RE = re.compile(r"FED Overseas|Overseas", re.I)

# ------------------------------------------------------------------ readers

def read_sheets_xlsx(path):
    """{sheet name: list of tuples} for a .xlsx workbook."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(path)
        return {ws.title: list(ws.iter_rows(values_only=True))
                for ws in wb.worksheets}


def read_sheets_ml(path):
    """{sheet name: list of tuples} for an Excel 2003 SpreadsheetML (.xls).

    Cells carry an ss:Index attribute when they skip empty columns; rows are
    expanded to a dense list aligned with the sheet's widest row.
    """
    ns = {"s": "urn:schemas-microsoft-com:office:spreadsheet"}
    qname = lambda t: "{%s}%s" % (ns["s"], t)
    tree = ET.parse(path)
    sheets = {}
    for ws in tree.getroot().findall(".//s:Worksheet", ns):
        rows = []
        for row in ws.findall("s:Table/s:Row", ns):
            values = []
            col = 1
            for c in row.findall("s:Cell", ns):
                idx = c.get(qname("Index"))
                if idx:
                    col = int(idx)
                data = c.find("s:Data", ns)
                while len(values) < col - 1:
                    values.append(None)
                values.append("" if data is None else (data.text or ""))
                col += 1
            rows.append(values)
        width = max((len(r) for r in rows), default=0)
        sheets[ws.get(qname("Name"))] = [
            r + [None] * (width - len(r)) for r in rows
        ]
    return sheets


# ------------------------------------------------------------- page parsing

def cell(value):
    """String form; 'protected' (a suppressed count) reads as None."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() == "protected" else text


def value_of(value):
    """Integer vote count; 'protected'/blank read as 0."""
    c = cell(value)
    if not c:
        return 0
    return int(round(float(c)))


PRECINCT_LABELS = {"precinct", "precint", "county", "district"}


VOTE_LABEL_RE = re.compile(r"election day|mail|early|provisional"
                           r"|ballots cast|total votes|registered")


def find_header(rows):
    """(header row index, precinct-column index) of a page, or (None, None)."""
    for i, row in enumerate(rows):
        for j, c in enumerate(row[:4]):
            if c is not None and str(c).strip().lower() in PRECINCT_LABELS:
                return i, j
        # Some pages leave the leading label cell blank: the row holds only
        # vote-type column labels (e.g. Somerset's Republican BALLOTS CAST
        # page starts with ' ' where 'District' would be).
        labels = [str(c).strip().lower() if c is not None else ""
                  for c in row[:6]]
        nonempty = [label for label in labels if label]
        if len(nonempty) >= 2 and all(VOTE_LABEL_RE.search(label)
                                      for label in nonempty):
            return i, 0
    return None, None


def candidate_starts(candidate_row):
    """Columns holding a candidate name on the row above the column headers."""
    keep = ("ballots cast", "precinct", "precint", "county", "district",
            "registered", "voter turnout")
    names = []
    for j, c in enumerate(candidate_row):
        text = cell(c)
        if text and not text.lower().startswith(keep):
            names.append(j)
    return names


def group_columns(header, start, end):
    """{vote kind: column} for one candidate's group in [start, end)."""
    group = {}
    for j in range(start, end):
        label = cell(header[j]) if j < len(header) else None
        if not label:
            continue
        low = label.lower()
        if low == "election day":
            group["election_day"] = j
        elif "mail" in low:
            group["vote_by_mail"] = j
        elif "early" in low:
            group["early_voting"] = j
        elif "provisional" in low:
            group["provisional"] = j
        elif low == "total votes":
            group["total_votes"] = j
        elif low == "total":
            break
        else:
            raise ValueError(f"Unexpected column label {label!r}")
    return group


def parse_contest_rows(rows):
    """[(precinct, registered, {candidate: {"values": {...}, "total": v}})]
    for one contest page."""
    hdr_i, col0 = find_header(rows)
    if hdr_i is None:
        return None
    header = rows[hdr_i]
    registered_col = None
    for j, c in enumerate(header):
        label = (cell(c) or "").lower()
        if label.startswith("registered"):
            registered_col = j
            break
    starts = candidate_starts(rows[hdr_i - 1]) if hdr_i > 0 else []
    bounds = starts + [len(header)]
    groups = {start: group_columns(header, start, bounds[n + 1])
              for n, start in enumerate(starts)}
    # a plain turnout/ballots page has no candidate groups and its own
    # type columns
    plain = {}
    if not groups:
        for j, c in enumerate(header):
            label = (cell(c) or "").lower()
            if label == "election day":
                kind = "election_day"
            elif label == "ballots cast":
                kind = "ballots"
            elif "mail" in label:
                kind = "vote_by_mail"
            elif "early" in label:
                kind = "early_voting"
            elif label.startswith("provisional"):
                kind = "provisional"
            elif label == "total votes":
                kind = "total_votes"
            else:
                continue
            plain[kind] = j
    out = []
    for row in rows[hdr_i + 1:]:
        label = cell(row[col0])
        if not label or label.lower().rstrip(":") == "total":
            continue
        if DROP_PRECINCT_RE.search(label):
            continue
        registered = value_of(row[registered_col]) \
            if registered_col is not None else None
        candidates = {}
        for start, group in groups.items():
            name = cell(rows[hdr_i - 1][start])
            values = {kind: value_of(row[j]) for kind, j in group.items()
                      if kind != "total_votes"}
            total = value_of(row[group["total_votes"]]) \
                if "total_votes" in group else None
            candidates.setdefault(name, []).append(
                {"values": values, "total": total})
        plain_row = {kind: value_of(row[j]) for kind, j in plain.items()} \
            if plain else None
        out.append((label, registered, candidates, plain_row))
    return out


def parse_turnout_page(rows):
    """[(precinct, registered-or-None, {kind: votes}-or-None, ballots-or-None)]
    from a Registered Voters page."""
    hdr_i, col0 = find_header(rows)
    if hdr_i is None:
        return []
    header = rows[hdr_i]
    registered_col = ballot_col = None
    for j, c in enumerate(header):
        label = (cell(c) or "").lower()
        if label.startswith("registered"):
            registered_col = j
        elif label == "ballots cast":
            ballot_col = j
    out = []
    for row in rows[hdr_i + 1:]:
        label = cell(row[col0])
        if not label or label.lower().rstrip(":") == "total":
            continue
        if DROP_PRECINCT_RE.search(label):
            continue
        registered = value_of(row[registered_col]) \
            if registered_col is not None else None
        ballots = value_of(row[ballot_col]) if ballot_col is not None else None
        types = {}
        for j, c in enumerate(header):
            low = (cell(c) or "").lower()
            if low in ("election day",) or "mail" in low \
                    or low == "early voting" or low.startswith("provisional"):
                if "registered" not in low and "ballots cast" not in low:
                    kind = ("vote_by_mail" if "mail" in low
                            else "election_day" if low == "election day"
                            else "early_voting" if "early" in low
                            else "provisional")
                    types[kind] = value_of(row[j])
        out.append((label, registered, types or None, ballots))
    return out


# --------------------------------------------------------- contest titles

HOUSE_RE = re.compile(r"house|congress|representative", re.I)
CD_RE = re.compile(r"CD\s*(\d+)", re.I)
DISTRICT_RE = re.compile(
    r"(\d+)(?:st|nd|rd|th)?\s+(?:Congressional\s+)?District", re.I)
BALLOTS_RE = re.compile(r"^BALLOTS CAST - (DEMOCRATIC|REPUBLICAN)\b", re.I)


def parse_contest(title):
    """(office, district, party) from a TOC contest title, or None to skip."""
    party = None
    m = re.match(r"^(DEM|REP)\b[ -]*", title.strip(), re.I)
    if m:
        party = m.group(1).upper()
        title = title[m.end():].strip()
    title = re.sub(r"\s*\(\s*vote\s+for\s+\d+\s*\)\s*$", "", title,
                   flags=re.I).strip()
    title = re.sub(r"\s*\(\s*\d+\s*\)\s*$", "", title).strip()
    if re.search(r"county committee", title, re.I):
        return None
    if re.fullmatch(r"u\.?\s?s\.?\s?senat(?:e|or)", title, flags=re.I):
        return "U.S. Senate", "", party
    if HOUSE_RE.search(title):
        dm = CD_RE.search(title) or DISTRICT_RE.search(title)
        if not dm:
            raise ValueError(f"House contest without district: {title!r}")
        return "U.S. House", dm.group(1), party
    return title, "", party


def load_toc(sheets):
    """{page number int: contest title} from a Table of Contents sheet."""
    out = {}
    for row in sheets.get("Table of Contents", []):
        if len(row) < 2:
            continue
        page, title = cell(row[0]), cell(row[1])
        if page is not None and title and re.fullmatch(r"\d+", page):
            out[int(page)] = title.strip()
    return out


def sheet_for_page(sheets, page):
    """A page's sheet; page 1 is the 'Registered Voters' sheet."""
    return (sheets.get(str(page), sheets.get(str(page).zfill(2)))
            or sheets.get("Registered Voters"))


# ------------------------------------------------------------------ profile

COUNTIES = [
    {"county": "Middlesex",
     "source": "Middlesex NJ Primary Election 2026 Detail Report.xlsx",
     "breakdown": True},
    {"county": "Atlantic", "source": "Atlantic NJ primary.xlsx",
     "breakdown": True},
    {"county": "Somerset", "source": "Somerset NJ 2026 Primary District "
                                     "Results.xlsx", "breakdown": False},
    {"county": "Monmouth", "source": "Monmouth NJ 2026 Primary District "
                                     "Detail.xls", "breakdown": False},
]


def collect(profile):
    """(contest rows, pseudo rows, warnings) for one county.

    Contest rows: (precinct, office, district, party, candidate, votes,
    breakdown) in TOC contest order. Pseudo rows: (precinct, office, party,
    votes, breakdown) for Registered Voters / Ballots Cast.
    """
    county = profile["county"]
    with_breakdown = profile["breakdown"]
    warnings_out = []
    path = os.path.join(SOURCE_DIR, profile["source"])
    sheets = (read_sheets_xlsx(path) if profile["source"].endswith(".xlsx")
              else read_sheets_ml(path))
    toc = load_toc(sheets)
    if not toc:
        raise ValueError(f"{county}: no Table of Contents entries found")

    pseudo_rows = []
    registered_seen = set()
    has_reg_voters = any(
        t.lower().startswith("registered voters") for t in toc.values())
    for page, title in toc.items():
        if title.lower().startswith("registered voters"):
            parsed = parse_turnout_page(sheet_for_page(sheets, page))
            if not parsed:
                # Somerset has no Registered Voters page (its TOC starts at
                # page 2); check a sheet named 'Registered Voters' too.
                parsed = parse_turnout_page(
                    sheets.get("Registered Voters", []))
            for label, registered, types, ballots in parsed:
                if label in registered_seen:
                    continue
                registered_seen.add(label)
                if registered is not None:
                    pseudo_rows.append((label, "Registered Voters", "",
                                        registered, None))
                if ballots is not None:
                    pseudo_rows.append((label, "Ballots Cast", "", ballots,
                                        types))
        elif BALLOTS_RE.match(title) and not has_reg_voters:
            party = BALLOTS_RE.match(title).group(1).upper()
            parsed = parse_contest_rows(sheet_for_page(sheets, page))
            if parsed is None:
                warnings_out.append(f"{county}: unparseable page {page}")
                continue
            for label, registered, candidates, plain in parsed:
                if not plain:
                    warnings_out.append(
                        f"{county}: no vote columns on page {page}")
                    continue
                total = plain.get("total_votes")
                votes = total if total is not None else \
                    sum(v for k, v in plain.items() if k != "total_votes")
                pseudo_rows.append((label, "Ballots Cast", party, votes,
                                    {k: plain[k] for k in
                                     ("early_voting", "election_day",
                                      "vote_by_mail", "provisional")
                                     if k in plain} or None))

    contest_rows = []
    for page in sorted(toc):
        title = toc[page]
        if title.lower().startswith("registered voters") \
                or BALLOTS_RE.match(title):
            continue
        parsed_title = parse_contest(title)
        if parsed_title is None:
            continue  # county committee seat
        office, district, party = parsed_title
        parsed = parse_contest_rows(sheet_for_page(sheets, page))
        if parsed is None:
            warnings_out.append(f"{county}: unparseable page {page} "
                                f"({title!r})")
            continue
        for label, registered, candidates, plain in parsed:
            if not candidates:
                warnings_out.append(
                    f"{county} p{page}: no candidates on row {label!r}")
                continue
            for name, entries in candidates.items():
                if name is None or name.lower() in ("no petition filed", ""):
                    continue
                for entry in entries:
                    if entry["total"] is not None and not with_breakdown:
                        votes = entry["total"]
                    else:
                        votes = sum(entry["values"].values())
                    contest_rows.append((label, office, district, party,
                                         name, votes, entry["values"]))
    return contest_rows, pseudo_rows, warnings_out


# ------------------------------------------------------ output & validation

PARTY_NAMES = {"REP": "REPUBLICAN", "DEM": "DEMOCRATIC", "Democratic":
               "DEMOCRATIC", "Republican": "REPUBLICAN"}


def crosscheck(county, rows, warnings_out):
    """Compare U.S. Senate/House sums to the official county CSV."""
    if not os.path.exists(COUNTY_CSV):
        warnings_out.append("crosscheck: official county CSV missing")
        return
    official = {}
    with open(COUNTY_CSV) as f:
        for row in csv.DictReader(f):
            if row["county"] != county \
                    or row["office"] not in CROSSCHECK_OFFICES:
                continue
            key = (row["office"], str(int(row["district"]))
                   if row["district"] else "",
                   PARTY_NAMES.get(row["party"], row["party"]).upper(),
                   row["candidate"].upper().replace("-", " ")
                   .replace(".", "").replace(",", "")
                   .replace("  ", " ").strip())
            official[key] = int(row["votes"])
    tally = {}
    for precinct, office, district, party, candidate, votes, _ in rows:
        if office not in CROSSCHECK_OFFICES or \
                candidate.upper() in ("WRITE-IN", "WRITE IN"):
            continue
        key = (office, str(district),
               PARTY_NAMES.get(party, party or "").upper(),
               candidate.upper().replace("-", " ").replace(".", "")
               .replace(",", "").replace("  ", " ").strip())
        tally[key] = tally.get(key, 0) + votes
    for key in sorted(set(official) | set(tally)):
        ours, theirs = tally.get(key), official.get(key)
        if ours != theirs:
            warnings_out.append(
                f"{county} crosscheck {key[0]} d{key[1]} {key[3]}: precinct "
                f"total {ours} vs official {theirs}")


def write_csv(profile, pseudo_rows, contest_rows):
    county = profile["county"]
    header = BASE_HEADER + (BREAKDOWN_HEADER if profile["breakdown"] else [])
    output = os.path.join(OUTPUT_DIR,
                          f"{OUTPUT_PREFIX}__{county.lower()}__precinct.csv")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    n = 0
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for precinct, office, party, votes, breakdown in pseudo_rows:
            values = [breakdown.get(k, "") if breakdown else ""
                      for k in BREAKDOWN_HEADER] \
                if profile["breakdown"] else []
            writer.writerow([county, precinct, office, "", party, "", votes]
                            + values)
            n += 1
        for precinct, office, district, party, candidate, votes, breakdown \
                in contest_rows:
            values = [breakdown.get(k, "") for k in BREAKDOWN_HEADER] \
                if profile["breakdown"] else []
            writer.writerow([county, precinct, office, district, party,
                             candidate, votes] + values)
            n += 1
    print(f"Wrote {n} rows to {output}")


def main():
    for profile in COUNTIES:
        county = profile["county"]
        contest_rows, pseudo_rows, warnings_out = collect(profile)
        print(f"== {county}: {len(pseudo_rows)} turnout rows, "
              f"{len(contest_rows)} contest rows")
        crosscheck(county, contest_rows, warnings_out)
        for w in warnings_out:
            print("WARN:", w)
        if not warnings_out:
            print("   no warnings")
        write_csv(profile, pseudo_rows, contest_rows)


if __name__ == "__main__":
    main()