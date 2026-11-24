"""Parse Hunterdon County's 2026 primary precinct-level report into a CSV.

Input:  ~/code/openelections-sources-nj/2026/primary/Hunterdon NJ 2026 Primary Official Results.pdf
Output: 2026/counties/20260602__nj__primary__hunterdon__precinct.csv

Same Dominion "Custom Table Report" design as Warren's 2026 report (see
src/nj_warren_2026_primary.py), with these differences:
  - The STATISTICS table has 13 columns: registered voters (total/Rep/Dem/
    Nonpartisan), ballots cast (total/Rep/Dem/Nonpartisan/blank) and four
    turnout percentages (ignored). Rows are validated on both identity sums
    (a few county rows don't balance -- see DISCREPANCIES.md).
  - Contest pages can carry up to three contests side by side (on pages
    26-29 the DEM Senate section starts alongside two REP municipal races).
    A row line carries numbers for any subset of the page's contests, so each
    contest is parsed from its own x-zone: party title, stacked candidate
    names, then Write-in and Contest Total columns. Per-contest columns are
    candidates..., Write-in, Contest Total (no Totals Cast / Overvotes /
    Undervotes columns like Warren's report has).
  - Contest titles are cut off on the right ("REP UNITED STATES HOUSE OF"),
    so the office comes from truncation-tolerant phrase matching, the U.S.
    House district comes from the official county CSV (which lists exactly
    one), and a municipal contest's town comes from the precinct labels it
    covers, the way the Ocean Clarity parser completes truncated names.
  - Precinct labels already match the repo's 2024 Hunterdon spelling, so no
    town remapping is needed.

Output conventions follow 2024/20241105__nj__general__hunterdon__precinct.csv
and the other 2026 files: DEM/REP parties, Registered Voters / Ballots Cast /
Blank Ballots Cast pseudo-offices, Write-ins pseudocandidate (this report has
no Under Votes column).
"""

import csv
import os
import re

import pdfplumber

SOURCE = (
    "/Users/dwillis/code/openelections-sources-nj/2026/primary/"
    "Hunterdon NJ 2026 Primary Official Results.pdf"
)
OUTPUT = "2026/counties/20260602__nj__primary__hunterdon__precinct.csv"
COUNTY_CSV = "2026/20260602__nj__primary__county.csv"
CROSSCHECK_OFFICES = {"U.S. Senate", "U.S. House"}

LABEL_COL_X1 = 175    # row-label words end left of here; value columns after
STATS_VALUE_X1 = 540  # integer stats columns end before the turnout % columns
COLUMN_TOL = 21       # a value within this of a column center belongs to it
NAME_CLUSTER_GAP = 20  # a "JR." between columns must not bridge two names

PARTIES = ("REP", "DEM")

# Truncation-tolerant office detection, searched in this priority order.
OFFICE_PATTERNS = (
    (r"UNITED STATES HOUSE", "U.S. House"),
    (r"UNITED STATES", "U.S. Senate"),  # Senate's title may cut at "STATES"
    (r"BOARD OF COUNTY", "County Commissioner"),
    (r"COUNTY CLERK", "County Clerk"),
    (r"TOWNSHIP COMMITTEE", "Township Committee"),
    (r"BOROUGH COUNCIL", "Borough Council"),
    (r"COMMON COUNCIL", "Common Council"),
    (r"CITY COUNCIL", "City Council"),
    (r"MAYOR", "Mayor"),
)
MUNICIPAL_OFFICES = {"Township Committee", "Borough Council",
                     "Common Council", "City Council", "Mayor"}
NON_TITLE_WORDS = {"Write-in", "Contest", "Totals", "Total", "VOTE", "FOR",
                   "COUNTYWIDE", "OFFICIAL", "RESULTS"}

# Stacked candidate names occasionally read bottom-up; verified against the
# PDF's word coordinates.
# Stacked (often rotated) candidate names don't read in visual order; each
# fix maps the parser's assembled string to the name as printed on the
# report's column label, verified against the rendered page.
NAME_FIXES = {
    "Abuchowsk Abraham": "Abraham Abuchowski",
    "Alison Kavchok M.": "Alison M. Kavchok",
    "Blazakis Jason": "Jason Blazakis",
    "Booker Cory": "Cory Booker",
    "Caplan Jacob": "Jacob Caplan",
    "Castellano Mark": "Mark Castellano",
    "Celentano Robert": "Robert Celentano",
    "Christophe R Widuta": "Christopher Widuta",
    "Douglas Sloyer L.": "Douglas L. Sloyer",
    "Dougherty John": "John Dougherty",
    "Duane Young C.": "Duane C. Young",
    "Engelhard Susan D. T": "Susan D. Engelhardt",
    "Jeffrey Spencer J.": "Jeffrey J. Spencer",
    "Joseph Brosnan A.": "Joseph A. Brosnan",
    "Kashwick John": "John Kashwick",
    "Marcia Karrow A.": "Marcia A. Karrow",
    "Thomas Kean Jr. H.": "Thomas H. Kean Jr.",
    "Kathleen Klink E.": "Kathleen E. Klink",
    "Kearney Vincent": "Vincent Kearney",
    "Kimberly Stentz A.": "Kimberly A. Stentz",
    "Lance James": "James Lance",
    "Lebovics Robert S.": "Robert S. Lebovics",
    "Robert Lebovics S.": "Robert S. Lebovics",
    "Levitt Trent": "Trent Levitt",
    "Lipsen Aaron": "Aaron Lipsen",
    "Livingston Helen M.": "Helen M. Livingston",
    "Lockwood Susan D.": "Susan D. Lockwood",
    "Marlene Baldinger G.": "Marlene G. Baldinger",
    "Mark Wright E.": "Mark E. Wright",
    "Mary Melfi H.": "Mary H. Melfi",
    "Mccormick Caitlin Giles-": "Caitlin Giles-McCormick",
    "Mortara Robert": "Robert Mortara",
    "Mullay Brian": "Brian Mullay",
    "Murphy Justin": "Justin Murphy",
    "Natalie Ferry": "Natalie Ferry",
    "Nathalie Nelson S.": "Nathalie S. Nelson",
    "Nelson Judith": "Judith Nelson",
    "Norton David": "David Norton",
    "Pianka Adam": "Adam Pianka",
    "Porcello Lisa": "Lisa Porcello",
    "Rhoades Eric": "Eric Rhoades",
    "Richard Tabor": "Richard Tabor",
    "Robert Newland, Jr. D.": "Robert D. Newland, Jr.",
    "Shoolbraid Richard A.": "Richard A. Shoolbraid",
    "Sherlock Robert": "Robert Sherlock",
    "Schweikert Al": "Al Schweikert",
    "Sciarrino Jon": "Jon Sciarrino",
    "Stegman Steven": "Steven Stegman",
    "Tabor Richard": "Richard Tabor",
    "Tarby Alexa": "Alexa Tarby",
    "Thomas Davis G.": "Thomas G. Davis",
    "Taylor Russel": "Russel Taylor",
    "Thomas Mckee": "Thomas McKee",
    "Van Shaun Doren C.": "Shaun C. Van Doren",
    "James Kiernan P.": "James P. Kiernan",
    "Varela Brian": "Brian Varela",
}


def is_number(text):
    return bool(re.fullmatch(r"\d{1,3}(,\d{3})*", text))


def to_lines(words, tol=2.0):
    """Group word dicts into visual lines by top coordinate."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


# ---------------------------------------------------------------- statistics

STATS_COLUMNS = 9  # reg total/rep/dem/np + cast total/rep/dem/np/blank


def parse_statistics(pdf):
    """({precinct label: stats dict}, warnings) until the Totals row."""
    stats = {}
    warnings = []
    for page in pdf.pages:
        done = False
        for line in to_lines(page.extract_words()):
            label_words = [w for w in line if w["x1"] < LABEL_COL_X1]
            numbers = [
                w for w in line
                if is_number(w["text"])
                and LABEL_COL_X1 <= w["x0"] < STATS_VALUE_X1
            ]
            # The Totals row's first number sometimes lands in its own
            # visual line, so test for the label before the column count.
            if not label_words or not numbers:
                continue
            label = " ".join(w["text"] for w in label_words)
            if label.startswith("Totals"):
                done = True
                break
            if len(numbers) != STATS_COLUMNS:
                continue
            values = [int(w["text"].replace(",", "")) for w in numbers]
            reg_total, reg_rep, reg_dem, reg_np = values[:4]
            cast_total, cast_rep, cast_dem, cast_np, blank = values[4:]
            if reg_total != reg_rep + reg_dem + reg_np:
                warnings.append(
                    f"{label}: registered {reg_total} but REP {reg_rep} + "
                    f"DEM {reg_dem} + NP {reg_np} = "
                    f"{reg_rep + reg_dem + reg_np}"
                )
            if cast_total != cast_rep + cast_dem + cast_np + blank:
                warnings.append(
                    f"{label}: ballots {cast_total} but REP {cast_rep} + DEM "
                    f"{cast_dem} + NP {cast_np} + blank {blank} = "
                    f"{cast_rep + cast_dem + cast_np + blank}"
                )
            stats[label] = {
                "registered": reg_total,
                "cast_total": cast_total,
                "cast_rep": cast_rep,
                "cast_dem": cast_dem,
                "blank": blank,
            }
        if done:
            break
    if not stats:
        raise ValueError("No statistics rows found")
    return stats, warnings


TOWNS = []  # filled in main() from the statistics labels


def town_of_label(label):
    prefix = label.rsplit(" District ", 1)[0]
    return prefix if prefix in TOWNS else None


# ------------------------------------------------------------ contest titles

def contest_office(title_words):
    """Office from one contest zone's title words (above the VOTE/FOR line).

    Titles are cut off on the right, so patterns are truncation-tolerant.
    """
    joined = " ".join(
        w["text"] for w in title_words if w["text"] not in NON_TITLE_WORDS
    ).upper()
    for pattern, office in OFFICE_PATTERNS:
        if re.search(rf"\b{pattern}\b", joined):
            return office
    raise ValueError(f"Unrecognized contest title: {joined!r}")


def house_district():
    """The congressional district listed for this county in the official CSV."""
    districts = set()
    with open(COUNTY_CSV) as f:
        for row in csv.DictReader(f):
            if row["county"] == "Hunterdon" and row["office"] == "U.S. House" \
                    and row["district"]:
                districts.add(str(int(row["district"])))
    if len(districts) != 1:
        raise ValueError(f"Expected one U.S. House district, got {districts}")
    return districts.pop()


# --------------------------------------------------------------- page parser

def parse_contest_pages(pdf, stats, warnings):
    """All contests, merged across pages, with per-row validation."""
    house_district_value = house_district()
    contests = {}
    unassigned_numbers = 0

    class Unit:
        def __init__(self, party, office, district, names):
            self.party = party
            self.office = office
            self.district = district
            self.names = names
            self.rows = []  # [(label, [values per column center])]

    def add(unit, label, values):
        for existing_label, existing in unit.rows:
            if existing_label == label:
                if existing != values:
                    raise ValueError(
                        f"{unit.party} {unit.office}: conflicting values for "
                        f"{label}"
                    )
                return
        unit.rows.append((label, values))

    for page_no, page in enumerate(pdf.pages, start=1):
        words = page.extract_words()
        ct_tops = [w["top"] for w in words if w["text"] == "Contest"]
        if not ct_tops:
            continue  # statistics page
        # The header zone ends above the page's first precinct data row;
        # page 4's own statistics rows also look like data rows, so anchor
        # on the first one below the contest headers.
        header_cap = next(
            (min(w["top"] for w in line)
             for line in to_lines(words)
             if min(w["top"] for w in line) > min(ct_tops)
             and " ".join(w["text"] for w in line
                          if w["x1"] < LABEL_COL_X1 and w["x0"] < 300) in stats),
            None)
        if header_cap is None:
            continue
        header_words = [w for w in words if w["top"] < header_cap - 5]
        # The top of the REP/DEM title tokens bounds the header block from
        # above: page 4's statistics rows sit below this top but above the
        # contest titles.
        title_top = min(w["top"] for w in header_words
                        if w["text"] in PARTIES and w["x0"] > LABEL_COL_X1)
        # Each contest's x-zone ends at its own 'Contest' (Contest Total)
        # column label: title words can cross a party token's boundary, but
        # nothing crosses the next contest's Contest Total column.
        ct_xs = sorted(w["x0"] for w in header_words if w["text"] == "Contest")
        if not ct_xs:
            continue
        zones = []
        prev_x = LABEL_COL_X1 - 15
        for ct_x in ct_xs:
            start, end = prev_x, ct_x + 5
            zone_words = [w for w in header_words if start < w["x0"] <= end]
            prev_x = ct_x
            vote_word = min((w for w in zone_words if w["text"] == "VOTE"),
                            key=lambda w: w["top"], default=None)
            if vote_word is None:
                raise ValueError(
                    f"p{page_no}: no VOTE label in zone {start:.0f}-{end:.0f}")
            vote_top = vote_word["top"]
            title_words = [w for w in zone_words
                           if title_top - 2 <= w["top"] < vote_top]
            party = next((w["text"] for w in title_words
                          if w["text"] in PARTIES), None)
            if party is None:
                raise ValueError(f"p{page_no}: zone at {start}-{end:.0f} "
                                 f"has no party token")
            raw_office = contest_office(title_words)
            if raw_office == "U.S. House":
                district = house_district_value
            elif raw_office in ("U.S. Senate", "County Clerk",
                                "County Commissioner"):
                district = ""
            else:
                district = ""  # resolved from row labels below
            unit = Unit(party, raw_office, district, None)
            unit._zone = zone_words
            unit._start, unit._end = start, end
            unit._raw_office = raw_office
            unit._vote_top = vote_top
            digits = [w for w in zone_words if w["text"].isdigit()
                      and abs(w["top"] - vote_top) <= 3]
            unit._vote_for = int(digits[-1]["text"]) if digits else 1
            zones.append(unit)

        # Column centers per zone: header name clusters + Write-in + Contest.
        for unit in zones:
            # Candidate names stack below the VOTE/FOR line and above the
            # first data row; suffix/initial lines sit lower still.
            name_words = [
                w for w in unit._zone
                if unit._vote_top < w["top"] < header_cap - 5
                and w["text"] not in NON_TITLE_WORDS
                and not w["text"].isdigit()
            ]
            xs = sorted(w["x0"] for w in name_words)
            clusters = []
            for x in xs:
                if clusters and x - clusters[-1][-1] <= NAME_CLUSTER_GAP:
                    clusters[-1].append(x)
                else:
                    clusters.append([x])
            centers = [sum(c) / len(c) for c in clusters]
            for label in ("Write-in", "Contest"):
                matches = [w["x0"] for w in unit._zone if w["text"] == label]
                if not matches:
                    raise ValueError(
                        f"p{page_no}: no {label!r} label in "
                        f"{unit._raw_office} zone"
                    )
                centers.append(sorted(matches)[0])
            unit._centers = centers
            names = []
            for center in centers[:-2]:
                stacked = sorted(
                    [w for w in name_words if abs(w["x0"] - center)
                     <= NAME_CLUSTER_GAP],
                    key=lambda w: w["top"])
                raw = " ".join(w["text"] for w in stacked)
                # NAME_FIXES keys are written in title case; the PDF prints
                # candidate names in caps.
                name = NAME_FIXES.get(raw.title(), raw.title())
                names.append("No Petition" if name.startswith("No Petition")
                             else name)
            # Column order is candidates..., Write-in, Contest Total.
            unit.names = names + ["Write-ins"]

        # Data rows: a line's numbers belong to whichever zone's columns
        # they land in.
        for line in to_lines(words):
            if min(w["top"] for w in line) < title_top:
                continue  # statistics rows above the contest block (page 4)
            label_words = [
                w for w in line if w["x1"] < LABEL_COL_X1 and w["x0"] < 300
            ]
            numbers = [
                w for w in line
                if is_number(w["text"]) and LABEL_COL_X1 <= w["x0"]
            ]
            if not label_words or not numbers:
                continue
            label = " ".join(w["text"] for w in label_words)
            if label.startswith(("Totals", "P26", "Page")):
                continue
            if label not in stats:
                raise ValueError(f"p{page_no}: unknown precinct {label!r}")
            for unit in zones:
                values = {}
                for w in numbers:
                    if not (unit._start <= w["x0"] < unit._end):
                        continue
                    nearest = min(unit._centers,
                                  key=lambda c: abs(w["x0"] - c))
                    if abs(w["x0"] - nearest) > COLUMN_TOL:
                        unassigned_numbers += 1
                        warnings.append(
                            f"p{page_no} {label}: {w['text']}@{w['x0']:.0f} "
                            f"> {COLUMN_TOL} from any {unit._raw_office} "
                            f"column {[f'{c:.0f}' for c in unit._centers]}"
                        )
                        continue
                    if nearest in values:
                        raise ValueError(
                            f"p{page_no} {label}: two values for column "
                            f"{nearest:.0f} in {unit._raw_office}"
                        )
                    values[nearest] = int(w["text"].replace(",", ""))
                if not values:
                    continue  # this contest's numbers are on another line
                if any(center not in values for center in unit._centers):
                    missing = [f"{c:.0f}" for c in unit._centers
                               if c not in values]
                    warnings.append(
                        f"p{page_no} {unit._raw_office} {label}: missing "
                        f"columns {missing}; row skipped"
                    )
                    continue
                ordered = [values[c] for c in unit._centers]
                add(unit, label, ordered)

        # Resolve municipal offices now that rows know their town.
        for unit in zones:
            if unit._raw_office in MUNICIPAL_OFFICES:
                towns_covered = {
                    label.rsplit(" District ", 1)[0] for label, _ in unit.rows
                }
                if not unit.rows:
                    # The contest starts here; its rows are on later pages.
                    unit.district, unit.office = "", unit._raw_office
                elif len(towns_covered) != 1:
                    warnings.append(
                        f"p{page_no}: {unit._raw_office} rows span towns "
                        f"{sorted(towns_covered)}"
                    )
                    unit.district, unit.office = "", unit._raw_office
                else:
                    town = towns_covered.pop()
                    suffix = {"Township Committee": "Township Committee",
                              "Borough Council": "Borough Council",
                              "Common Council": "Common Council",
                              "City Council": "Council",
                              "Mayor": "Mayor"}[unit._raw_office]
                    if unit._raw_office == "Township Committee":
                        unit.office = f"{town} Committee"
                    elif unit._raw_office == "Borough Council":
                        # "Bloomsbury Borough" + "Borough Council" would
                        # double the town type.
                        unit.office = (f"{town} Council" if
                                       town.endswith("Borough")
                                       else f"{town} Borough Council")
                    elif unit._raw_office == "Common Council":
                        unit.office = f"{town} Common Council"
                    else:
                        unit.office = f"{town} {suffix}"
                    unit.district = ""

        for unit in zones:
            if not unit.rows and unit._raw_office in MUNICIPAL_OFFICES:
                continue  # page carries the header but none of its rows
            key = (unit.party, unit.office, unit.district)
            if key not in contests:
                contests[key] = unit
            else:
                existing = contests[key]
                if existing.names != unit.names:
                    warnings.append(
                        f"{unit.party} {unit.office}: header names differ "
                        f"between pages ({existing.names} vs {unit.names})"
                    )
                for label, values in unit.rows:
                    add(existing, label, values)

    if unassigned_numbers:
        warnings.append(f"{unassigned_numbers} numbers matched no contest "
                        f"column and were ignored")

    validate_contests(contests, stats, warnings)
    return list(contests.values()), warnings


def validate_contests(contests, stats, warnings):
    """Cross-check every contest row against the statistics table."""
    all_labels = set(stats)
    for unit in contests.values():
        party = unit.party
        office = unit.office
        if "write" not in unit.names[-1].lower().replace(" ", ""):
            warnings.append(
                f"{party} {office}: last candidate is {unit.names[-1]!r}, "
                f"expected the Write-in column"
            )
        labels = [label for label, _ in unit.rows]
        countywide = office in ("U.S. Senate", "U.S. House", "County Clerk",
                                "County Commissioner")
        if countywide:
            if len(labels) != len(stats) or set(labels) != all_labels:
                missing = sorted(all_labels - set(labels))[:3]
                extra = sorted(set(labels) - all_labels)[:3]
                warnings.append(
                    f"{party} {office}: {len(labels)} rows (expected "
                    f"{len(stats)}); missing {missing}, extra {extra}"
                )
        else:
            towns = {label.rsplit(" District ", 1)[0] for label in labels}
            if len(towns) != 1 or None in towns:
                warnings.append(
                    f"{party} {office}: rows span towns {sorted(map(str, towns))}"
                )
            else:
                expected = sum(1 for s in stats
                               if s.rsplit(" District ", 1)[0] in towns)
                if len(labels) != expected:
                    warnings.append(
                        f"{party} {office}: {len(labels)} rows, expected "
                        f"{expected}"
                    )
        cast_key = "cast_rep" if party == "REP" else "cast_dem"
        for label, values in unit.rows:
            cands, write_in, total = values[:-2], values[-2], values[-1]
            if sum(cands) + write_in > total:
                warnings.append(
                    f"{party} {office} {label}: votes {sum(cands) + write_in} "
                    f"exceed contest total {total}"
                )
            ballots = stats[label].get(cast_key)
            # "VOTE FOR 2" contests total up to n per ballot, so only
            # single-seat contests must tie the party ballots cast.
            if ballots is not None and unit._vote_for == 1 and total != ballots:
                warnings.append(
                    f"{party} {office} {label}: contest total {total} vs "
                    f"{party.lower()} ballots cast {ballots} in statistics"
                )
            for name, votes in zip(unit.names[:-1], cands):
                if votes != 0 and name == "No Petition":
                    warnings.append(
                        f"{party} {office} {label}: {name} has {votes} votes"
                    )


# --------------------------------------------------------------- crosscheck

PARTY_NAMES = {"REP": "REPUBLICAN", "DEM": "DEMOCRATIC"}


def crosscheck(contests, warnings):
    if not os.path.exists(COUNTY_CSV):
        warnings.append(f"crosscheck: {COUNTY_CSV} missing; skipped")
        return
    official = {}
    with open(COUNTY_CSV) as f:
        for row in csv.DictReader(f):
            if row["county"] != "Hunterdon" \
                    or row["office"] not in CROSSCHECK_OFFICES:
                continue
            key = (row["office"], str(int(row["district"]))
                   if row["district"] else "",
                   PARTY_NAMES.get(row["party"], row["party"]).upper(),
                   row["candidate"].upper().replace(",", "")
                   .replace(".", "").strip())
            official[key] = int(row["votes"])
    tally = {}
    for unit in contests:
        if unit.office not in CROSSCHECK_OFFICES:
            continue
        for label, values in unit.rows:
            for name, votes in zip(unit.names[:-1], values[:-2]):
                if name == "No Petition":
                    continue
                key = (unit.office, unit.district,
                       PARTY_NAMES[unit.party].upper(),
                       name.upper().replace(",", "").replace(".", "").strip())
                tally[key] = tally.get(key, 0) + votes
    for key in sorted(set(official) | set(tally)):
        ours, theirs = tally.get(key), official.get(key)
        if ours != theirs:
            warnings.append(
                f"crosscheck {key[0]} d{key[1]} {key[3]}: precinct total "
                f"{ours} vs official {theirs}"
            )


# ------------------------------------------------------------------ writing

def write_csv(contests, stats):
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["county", "precinct", "office", "district", "party",
             "candidate", "votes"]
        )
        n_rows = 0
        for label, s in stats.items():
            writer.writerow(
                ["Hunterdon", label, "Registered Voters", "", "", "",
                 s["registered"]]
            )
            writer.writerow(
                ["Hunterdon", label, "Ballots Cast", "", "", "", s["cast_total"]]
            )
            writer.writerow(
                ["Hunterdon", label, "Blank Ballots Cast", "", "", "",
                 s["blank"]]
            )
            n_rows += 3
            for contest in contests:
                rows = dict(contest.rows)
                if label not in rows:
                    continue  # municipal contests only cover their town
                values = rows[label]
                candidates, write_in = values[:-2], values[-2]
                for name, votes in zip(contest.names[:-1], candidates):
                    if name == "No Petition":
                        continue
                    writer.writerow(
                        ["Hunterdon", label, contest.office,
                         contest.district, contest.party, name, votes]
                    )
                    n_rows += 1
                writer.writerow(
                    ["Hunterdon", label, contest.office, contest.district,
                     contest.party, "Write-ins", write_in]
                )
                n_rows += 1
    print(f"Wrote {n_rows} rows to {OUTPUT}")


def main():
    global TOWNS
    pdf = pdfplumber.open(SOURCE)
    stats, warnings = parse_statistics(pdf)
    TOWNS = sorted({label.rsplit(" District ", 1)[0] for label in stats})
    contests, more_warnings = parse_contest_pages(pdf, stats, warnings)
    if more_warnings is not warnings:
        warnings.extend(more_warnings)
    n_warnings = len(warnings)
    crosscheck(contests, warnings)
    for w in warnings:
        print("WARN:", w)
    if not warnings:
        print("no warnings")
    else:
        print(f"({n_warnings} parse warnings, "
              f"{len(warnings) - n_warnings} crosscheck mismatches)")
    print(f"{len(contests)} contests parsed:")
    for contest in sorted(contests, key=lambda c: (c.party, c.office)):
        print(f"  {contest.party} {contest.office!r} "
              f"({len(contest.rows)} rows): {contest.names}")
    write_csv(contests, stats)


if __name__ == "__main__":
    main()