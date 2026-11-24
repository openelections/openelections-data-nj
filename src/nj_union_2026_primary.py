"""Parse Union County's 2026 primary "District by District" Dominion PDF.

Source: "Union NJ 2026 Primary District by District Results.pdf" (1146 pages),
a Dominion Custom Table "District by District" export. Each election district
gets a section: a repeated header block ("District by District / 2026 Primary
Election June 2 / June 2, 2026 / <town>[ Ward n] District n"), a Statistics
block (Registered Voters and Ballots Cast for Total/Democrat/Republican),
then that district's DEM contests and REP contests. Sections span page
breaks, and header blocks can be split across pages (e.g. "District by
District" alone at a page bottom), so labels are matched by x0 position and
a "… District N" shape rather than page adjacency.

Contest blocks print a rotated "Machines / Machine" watermark inside the
Early Voting / Election Day columns just above the first candidate row; when
it collides with a data row, digits fuse into the rotated word ("Machi2n2e")
and breakdown cells get lost or split. The TOTAL column (right edge 238.1)
never collides, so `votes` is taken from the TOTAL column only and no
breakdown columns are published — the breakdowns are unrecoverable wherever
the rotated text overlaps.

Per-cell suppression: any withheld breakdown cell prints as "*". Candidate
TOTAL cells are supposed to be always printed; every candidate row and a
per-contest "Total Votes Cast" row are validated on that assumption.

Output: 2026/counties/20260602__nj__primary__union__precinct.csv with
Registered Voters and Ballots Cast pseudo rows per district. Municipal and
row offices keep their printed wording with the municipality compressed to
"<Town> <City|Twp|Boro>" (e.g. "Mayor Berkeley Heights Twp"); "Members of
County Committee <district label>" becomes "Members of County Committee".
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
PDF = Path("/Users/dwillis/code/openelections-sources-nj/2026/primary/"
           "Union NJ 2026 Primary District by District Results.pdf")
OUTPUT = BASE / "2026/counties/20260602__nj__primary__union__precinct.csv"
COUNTY_CSV = BASE / "2026/20260602__nj__primary__county.csv"

COL_EDGES = [238.1, 276.0, 313.1, 350.3, 397.8, 435.8]  # TOTAL..Overseas x1
COL_TOL = 7.0
LABEL_RE = re.compile(r"^(.+?)(?: (Ward \d+))? District (\d+)$")
MUNI_RE = re.compile(r"\b(City|Township|Borough|Town) of ")
HOUSE_RE = re.compile(r"House of Representatives (\d+)th Congressional")
SUFFIX = {"City": "City", "Township": "Twp", "Borough": "Boro", "Town": "Twp"}
MUNI_TYPES = "City|Township|Borough|Town"
MUNI_TOWNS = [
    "Berkeley Heights", "Scotch Plains", "Roselle Park", "New Providence",
    "Clark", "Cranford", "Elizabeth", "Fanwood", "Garwood", "Kenilworth",
    "Linden", "Mountainside", "Plainfield", "Rahway", "Roselle",
    "Springfield", "Summit", "Union", "Westfield", "Winfield",
]


def is_int(text):
    return (text and all(ch in "0123456789," for ch in text)
            and text.replace(",", "").isdigit())


def as_int(text):
    return int(text.replace(",", ""))


def natkey(s):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]


def name_key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def line_split(words, gap=8.0):
    """Cluster page words into visual lines (Dominion rows sit >= 12pt apart;
    a row's own tokens wobble up to ~5pt from its anchor)."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and w["top"] <= lines[-1]["top"] + gap:
            lines[-1]["words"].append(w)
        else:
            lines.append({"top": w["top"], "words": [w]})
    return lines


def line_text(line):
    return " ".join(w["text"] for w in sorted(line["words"], key=lambda w: w["x0"]))


def value_tokens(page):
    """Numeric / '*' tokens in the value area, for y-window queries."""
    toks = []
    for w in page.extract_words():
        if w["x0"] < 200:
            continue
        if w["text"] == "*" or is_int(w["text"]):
            toks.append(w)
    return toks


def cols_near(toks, top, lo=2.0, hi=9.0):
    """{col_index: text} for value tokens within [top-lo, top+hi].

    Value tokens sit between ~1pt above and ~8pt below the row's first word
    (rotated column-header words can shift the anchor), and rows are >= 12pt
    apart, so the default window only ever sees one row's tokens.
    """
    out = {}
    for w in toks:
        if not (top - lo <= w["top"] <= top + hi):
            continue
        for i, edge in enumerate(COL_EDGES):
            if abs(w["x1"] - edge) <= COL_TOL:
                prev = out.get(i)
                # a split number's neighbour token: keep any integer match
                if prev is None or (is_int(w["text"]) and not is_int(prev)) \
                        or prev == w["text"]:
                    out[i] = w["text"]
                break
    return out


def parse(pdf, problems):
    stats = {}
    contests = []
    cur_district = None
    cur = None
    pending_header = 0
    for pno, page in enumerate(pdf.pages, 1):
        toks = value_tokens(page)
        lines = line_split(page.extract_words())
        for line in lines:
            text = line_text(line)
            first_x0 = line["words"][0]["x0"]
            first = line["words"][0]["text"]

            # header block lines may straddle pages
            if text.startswith("District by District") and first_x0 < 73:
                pending_header = 3
                continue
            if pending_header:
                if text.startswith("2026 Primary Election June 2") and pending_header == 3:
                    pending_header = 2
                    continue
                if text.startswith("June 2, 2026") and pending_header == 2:
                    pending_header = 1
                    continue
                if pending_header == 1:
                    m = LABEL_RE.match(text)
                    ok = (first_x0 < 73
                          and (m or text.endswith("Overseas")))
                    if ok:
                        cur_district = text
                        pending_header = 0
                        continue
                pending_header = 0
            # district label on its own line (covers same-page headers too)
            if (first_x0 < 73 and first not in ("DEM", "REP")
                    and not text.startswith("Vote For")
                    and LABEL_RE.match(text) and "Total Votes Cast" not in text):
                cur_district = text
                continue

            ml = re.match(r"^(Registered Voters|Ballots Cast) - (Total|Democrat|Republican)\b",
                          text)
            x0_min = min(w["x0"] for w in line["words"])
            if cur_district and ml and x0_min < 73:
                vals = cols_near(toks, line["top"])
                key = ("reg_" if ml.group(1) == "Registered Voters" else "bc_") \
                    + ml.group(2).lower()
                if 0 not in vals:
                    problems.append("p%d: no value for %s %s" % (pno, cur_district, text))
                    continue
                stats.setdefault(cur_district, {})[key] = as_int(vals[0])
                if ml.group(1) == "Ballots Cast" and 2 in vals and any(
                        i not in vals for i in range(6)):
                    problems.append("p%d: partial Ballots Cast row for %s %s: %s"
                                    % (pno, cur_district, ml.group(2), vals))
                continue

            if first in ("DEM", "REP") and first_x0 < 73:
                cur = {"label": cur_district, "party": first,
                       "title": text.strip(), "candidates": {},
                       "order": [], "totals": None, "page": pno}
                contests.append(cur)
                continue
            if cur is None:
                continue
            if re.match(r"^Vote For \d+$", text):
                cur["vote_for"] = int(text.split()[-1])
                continue
            if re.match(r"^Total Votes Cast", text):
                cur["totals"] = cols_near(toks, line["top"])
                miss = [i for i in range(6) if i not in cur["totals"]]
                if miss:
                    problems.append("p%d: Total Votes Cast missing cols %s for %s %s"
                                    % (pno, miss, cur["party"], cur["title"]))
                cur = None
                continue
            if line["top"] > cur.get("header_top", 0) - 1 and 0 in cols_near(toks, line["top"]):
                name_words = [w["text"] for w in line["words"] if w["x1"] < 205]
                name = " ".join(name_words).strip()
                if not name:
                    # rotated "Machines/Machine" watermark merged with a real
                    # candidate row's tokens: the real row follows in the
                    # cluster with its name, this one has only values
                    continue
                if name == "Write-In Totals":
                    name = "Write-ins"
                cells = [cols_near(toks, line["top"]).get(i, "*") for i in range(6)]
                if name in cur["candidates"]:
                    problems.append("p%d: duplicate candidate %r in %s %s (%s)"
                                    % (pno, name, cur["party"], cur["title"],
                                       cur["label"]))
                else:
                    cur["candidates"][name] = cells
                    cur["order"].append(name)
        # end of page: a contest left open continues on the next page
    return stats, contests, cur


def to_office(title, problems):
    t = re.sub(r"^(DEM|REP)\s+", "", title).strip()
    m = HOUSE_RE.search(t)
    if m:
        return "U.S. House", m.group(1)
    if t == "United States Senator":
        return "U.S. Senate", ""
    if t == "Sheriff":
        return "Sheriff", ""
    if t == "County Clerk":
        return "County Clerk", ""
    if t == "County Surrogate":
        return "County Surrogate", ""
    if t.startswith("Members of County Committee"):
        return "Members of County Committee", ""
    if t == "Members of Board of County Commissioners":
        return "Members of the Board of County Commissioners", ""
    muni = re.search(r"\b(City|Township|Borough|Town) of ", t)
    if muni:
        after_txt = t[muni.end():]
        town = next((name for name in MUNI_TOWNS
                     if after_txt == name or after_txt.startswith(name + " ")
                     or after_txt.startswith(name + ",")), None)
        if town is None:
            problems.append("unmapped municipality in %r" % t)
            return t, ""
        idx = t.index(muni.group(0)) + len(muni.group(0))
        before = t[:idx - len(muni.group(0))].strip()
        suffix = SUFFIX[muni.group(1)]
        name = "%s %s %s" % (before, town, suffix)
        after = t[idx + len(town):].strip()
        if after:
            name += " (%s)" % after
        return name, ""
    problems.append("unmapped office title: %r" % t)
    return t, ""


def main():
    problems = []
    pdf = pdfplumber.open(str(PDF))
    stats, contests, cur = parse(pdf, problems)
    if cur is not None:
        problems.append("contest never closed: %s %s (%s)"
                        % (cur["party"], cur["title"], cur["label"]))

    # ---- integrity checks ----
    for cont in contests:
        if cont["label"] is None:
            problems.append("contest without district: %s" % cont["title"])
            continue
        if cont["totals"] is None:
            problems.append("no Total Votes Cast: %s %s (%s)"
                            % (cont["party"], cont["title"], cont["label"]))
            continue
        tvc = cont["totals"].get(0)
        if not tvc or tvc == "*" or not is_int(tvc):
            problems.append("bad Total Votes Cast: %s %s in %s" % (tvc, cont["title"], cont["label"]))
            continue
        s = 0
        for name, cells in cont["candidates"].items():
            if cells[0] == "*":
                problems.append("suppressed TOTAL cell: %s %s in %s (%s)"
                                % (cont["party"], name, cont["title"], cont["label"]))
                break
            s += as_int(cells[0])
        if s != as_int(tvc):
            problems.append("candidate sum %d != Total Votes Cast %s: %s %s (%s)"
                            % (s, tvc, cont["party"], cont["title"], cont["label"]))

    # ---- crosscheck vs official county file ----
    official = {}
    with open(COUNTY_CSV, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["county"] != "Union" or row["office"] not in ("U.S. Senate", "U.S. House"):
                continue
            key = (row["office"], row["district"], name_key(row["candidate"]))
            official[key] = official.get(key, 0) + int(row["votes"])
    sums = defaultdict(int)
    for cont in contests:
        office, dist = to_office(cont["title"], problems)
        if office not in ("U.S. Senate", "U.S. House"):
            continue
        for name, cells in cont["candidates"].items():
            if cells[0] == "*":
                continue
            sums[(office, dist, name_key(name))] += as_int(cells[0])
    for key in sorted(official, key=lambda k: (k[0], int(k[1] or 0), k[2])):
        got = sums.get(key, 0)
        want = official[key]
        if got != want:
            print("CROSSCHECK %s d%s %r: %d vs %d (delta %+d)"
                  % (key[0], key[1], key[2], got, want, got - want))
    for key in sums:
        if key not in official:
            print("extra in PDF: %s" % (key,))

    # ---- build output rows ----
    out = []
    for cont in contests:
        office, district = to_office(cont["title"], problems)
        for name in cont["order"]:
            cells = cont["candidates"][name]
            votes = 0 if cells[0] == "*" else as_int(cells[0])
            out.append({"precinct": cont["label"], "office": office,
                        "district": district, "party": cont["party"],
                        "candidate": name, "votes": votes})

    precincts = sorted(stats, key=natkey)
    for label in precincts:
        st = stats[label]
        reg = st.get("reg_total")
        bc = st.get("bc_total")
        if reg is None or bc is None:
            problems.append("incomplete stats for %r: %s" % (label, st))
            continue
        dem_rep = st.get("bc_democrat", 0) + st.get("bc_republican", 0)
        if dem_rep > bc:
            problems.append("Ballots Cast %d < DEM+REP %d in %r" % (bc, dem_rep, label))
        out.append({"precinct": label, "office": "Registered Voters", "district": "",
                    "party": "", "candidate": "", "votes": reg})
        out.append({"precinct": label, "office": "Ballots Cast", "district": "",
                    "party": "", "candidate": "", "votes": bc})

    out.sort(key=lambda r: (0 if r["office"] == "U.S. Senate" else
                            1 if r["office"] == "U.S. House" else 3,
                            r["office"], natkey(r["precinct"]),
                            int(r["district"]) if r["district"].isdigit() else 0,
                            0 if r["party"] == "REP" else 1))

    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(["county", "precinct", "office", "district", "party",
                      "candidate", "votes"])
        for r in out:
            wtr.writerow(["Union", r["precinct"], r["office"], r["district"],
                          r["party"], r["candidate"], r["votes"]])

    print("wrote %d rows to %s" % (len(out), OUTPUT))
    print("precincts: %d (stats for %d)" % (len({r["precinct"] for r in out}), len(stats)))
    print("problems: %d" % len(problems))
    for p in problems:
        print("  ", p)


if __name__ == "__main__":
    sys.exit(main())