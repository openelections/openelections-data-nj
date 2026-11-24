"""Parse Burlington County's 2026 primary into a precinct CSV.

Sources (~/code/openelections-sources-nj/2026/primary/):
- "Burlington NJ 2026 Primary Statement of Votes Cast.pdf" (222 pp, landscape
  Dominion SOVC) — covers ONLY `US Senate (DEM|REP)`, and only the Mail-In
  and Provisional tabulators, aggregated by MUNICIPALITY (rows Mail-In /
  Provisional / "<Muni> - Total"; election-day and early-voting votes are
  not broken out below the county). PRIMARY SOURCE for the municipality-level
  U.S. Senate rows and for per-municipality Registered Voters / Ballots Cast.
- "Burlington NJ 2026 Primary Summary Report.pdf" (247 pp, portrait) —
  countywide election summary followed by per-tabulator blocks. PRIMARY
  SOURCE for the county committee races (per district, DEM only) and the
  municipal offices (municipality-wide); VALIDATION SOURCE for the SOVC
  (countywide mail+provisional vectors) and for the federal crosscheck.

Burlington publishes no district-level federal results, so U.S. House and
the countywide offices (County Commissioner / County Surrogate) are not in
the output, and the U.S. Senate municipality rows carry
`votes = mail + provisional` with the missing early-voting / election-day
votes documented in DISCREPANCIES.md. County-committee tabulators
"<Muni> N-M" (two machines in one district) are merged to district N.

SOVC layout (decoded): the section is a table of 40 municipalities (+ a
"Cumulative" pseudo-row) x candidates, printed in band/page order: each band
(a window of ~7-8 municipalities) gets a "main" page (a 2-table page: left
sub-table = Times Cast / Registered Voters for that window, right = the
contest's named-candidate + Total Votes columns), followed by pages of
write-in-candidate columns. EVERY page re-prints its band's municipality
window for that page's own columns. A window's last municipality often
overflows the page: some of its rows print at the bottom and the rest
(unlabeled) at the top of the next page of the same column group; the next
band's pages then start with that muni's remaining rows for their own
columns. Because consecutive main pages share the same contest columns,
merging a muni's values by column name across main pages reassembles every
block (validated by total == mail + provisional per column).
Column names are rotated (printed reversed) headers read bottom-to-top per
vertical line, lines left to right.

Output: 2026/counties/20260602__nj__primary__burlington__precinct.csv with
columns county,precinct,office,district,party,candidate,votes,mail,provisional
(the 2020 Burlington precedent's schema). Party tokens DEM/REP; write-in
columns collapse to a "Write-ins" candidate; "No Petition Filed" candidates
are dropped.
"""

import csv
import re
import sys
from collections import defaultdict

import pdfplumber

SOVC_PDF = ("/Users/dwillis/code/openelections-sources-nj/2026/primary/"
            "Burlington NJ 2026 Primary Statement of Votes Cast.pdf")
SUMMARY_PDF = ("/Users/dwillis/code/openelections-sources-nj/2026/primary/"
               "Burlington NJ 2026 Primary Summary Report.pdf")
OUTPUT = "2026/counties/20260602__nj__primary__burlington__precinct.csv"
COUNTY_CSV = "2026/20260602__nj__primary__county.csv"

# SOVC sections: party -> (first page, last page)
SOVC_SECTIONS = {"DEM": (7, 168), "REP": (169, 222)}

# left sub-table column x1 edges
EDGE_CAST = 178.0
EDGE_REG = 237.2

# Summary countywide anchors (page 1 turnout table): mail+provisional per
# party, for validating the SOVC municipality sums.
SUMMARY_MAIL_PROV = {
    "DEM": {"Cory Booker": 17559 + 233},
    "REP": {"Justin Murphy": 2094 + 42, "Robert S. Lebovics": 401 + 8,
            "Alex Zdan": 1337 + 18, "Richard Tabor": 401 + 12},
}

JUNK = {"DEM", "REP", "District", "Municipality", "Total"}
# page-1 countywide turnout table lines (name + counts + a percent column)
TURNOUT_RE = re.compile(
    r"^(?:Democratic |Republican |Total )?(?:Mail-In|Early Voting|"
    r"Election Day|Provisional|Total)"
    r"(?: \d{1,3}(?:,\d{3})*)* \d+\.\d+%$")
TITLE_RE = re.compile(r"^(.*) \((DEM|REP)\) \(Vote for (\d+)\)$")

# The Summary Report's write-in detail lists don't reconcile with their own
# aggregate "Write-in" row for these blocks — verified against the raw PDF
# text (the detail rows as printed sum short; not a parsing artifact). The
# missing votes appear nowhere in the source. (title, party) -> shortfall.
SUMMARY_WRITEIN_SHORT = {
    ("US Senate", "DEM"): 2,
    ("Delran Township Council - Ward 3", "DEM"): 1,
    ("Evesham Township - Township Council", "DEM"): 1,
    ("County Surrogate", "REP"): 18,
    ("Evesham Township - Mayor", "REP"): 2,
    ("Evesham Township - Township Council", "REP"): 2,
}
COMMITTEE_RE = re.compile(
    r"^(.*?\S) (\d+)(?:-\d+)?D? - County Committee \((Male|Female)\) "
    r"\((DEM|REP)\) \(Vote for 1\)$")


def is_int(text):
    return bool(re.fullmatch(r"\d{1,3}(,\d{3})*", text))


def as_int(text):
    return int(text.replace(",", ""))


def natkey(s):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]


def name_key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def lines_of(words, gap=5.0):
    """Cluster upright words into visual lines (rows sit >= 11pt apart;
    within-line tokens wobble up to ~4pt)."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and w["top"] <= lines[-1]["top"] + gap:
            lines[-1]["words"].append(w)
        else:
            lines.append({"top": w["top"], "words": [w]})
    return lines


def line_text(line):
    return " ".join(w["text"] for w in sorted(line["words"], key=lambda w: w["x0"]))


def cluster_edges(values, gap=30.0):
    edges = []
    for v in sorted(values):
        if edges and v - edges[-1][-1] <= gap:
            edges[-1].append(v)
        else:
            edges.append([v])
    return [round(sum(e) / len(e), 1) for e in edges]


def rotated_name(words, edge):
    """Read a SOVC rotated column header. Words print reversed; the
    vertical lines of one header stack left to right, and within a line
    the reading order is bottom to top."""
    mine = [w for w in words if not w["upright"]
            and edge - 48 <= w["x0"] <= edge - 1]
    if not mine:
        return ""
    vlines = []
    for w in sorted(mine, key=lambda w: w["x0"]):
        if vlines and abs(w["x0"] - vlines[-1][0]["x0"]) <= 4:
            vlines[-1].append(w)
        else:
            vlines.append([w])
    parts = []
    for line in vlines:
        parts.append(" ".join(w["text"][::-1]
                              for w in sorted(line, key=lambda w: -w["top"])))
    return " ".join(parts)


def classify_header(name, pno, problems):
    """Classify a rotated column header. Returns the column's display name
    for main-contest columns (party-named candidates and "Total Votes"),
    None for write-in detail columns and sub-table headers, and a problem
    for anything unrecognized."""
    if not name:
        return None
    n = name.replace("(DEM)", "").replace("(REP)", "").strip()
    if n in ("Times Cast", "Registered Voters"):
        return None
    if re.search(r"write.?in", n, re.I):
        return None
    if "(DEM)" in name or "(REP)" in name:
        return n
    if n == "Total Votes":
        return "Total Votes"
    problems.append("SOVC p%d: unclassified column header %r" % (pno, name))
    return None


# ------------------------------------------------------------------- SOVC

MUNI_SUFFIX_RE = re.compile(
    r"^(?:[A-Z][A-Za-z .'\-]*)?"
    r"(?:Township|Borough|City|Town)$")


def is_muni_label(label):
    return bool(MUNI_SUFFIX_RE.match(label)) or label == "Cumulative"


def parse_sovc(pdf, problems):
    """Parse both SOVC sections.

    Returns (munis, left, main, mtot, left_mtot) where
    - munis: ordered municipality labels seen in the section,
    - left[party][muni][kind] = {edge: n} from the Times Cast / Registered
      Voters sub-table (edges 178 = cast, 237.2 = registered; kind in
      mail/prov/total),
    - main[party][muni][colname] = {"mail": n, "prov": n, "total": n},
      merged across pages by column name (consecutive main pages share the
      same contest columns, so a block split across pages reassembles),
    - mtot[party][colname]: the countywide "Municipality - Total" vector,
    - left_mtot[party] = {edge: n}: the left sub-table's Municipality-Total.
    """
    munis = []
    left = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    left_mtot = defaultdict(dict)
    main = defaultdict(lambda: defaultdict(dict))
    mtot = defaultdict(dict)

    def add_muni(label):
        if label != "Cumulative" and label not in munis:
            munis.append(label)

    def assign_edge(w, edges):
        return min(edges, key=lambda c: abs(c - w["x1"]))

    for party, (p0, p1) in SOVC_SECTIONS.items():
        for pno in range(p0, p1 + 1):
            page = pdf.pages[pno - 1]
            words = page.extract_words(extra_attrs=["upright"])
            up = [w for w in words if w["upright"] and 60 < w["top"] < 600]
            nums = [w for w in up if is_int(w["text"])]
            if not nums:
                problems.append("SOVC p%d: no numeric tokens" % pno)
                continue
            edges = cluster_edges([w["x1"] for w in nums], gap=30.0)
            tables, cur = [], [edges[0]]
            for e in edges[1:]:
                if e - cur[-1] > 100:
                    tables.append(cur)
                    cur = [e]
                else:
                    cur.append(e)
            tables.append(cur)
            two = len(tables) == 2
            rotated = [w for w in words if not w["upright"]]
            vedges = tables[-1]
            colmap = {}
            for e in vedges:
                name = classify_header(rotated_name(rotated, e), pno, problems)
                if name:
                    colmap[e] = name
            if not colmap and not two:
                continue            # write-in detail page: nothing to record

            sides = ([("L", [w for w in up if w["x1"] < 300], tables[0], False),
                      ("R", [w for w in up if w["x1"] >= 300], vedges, True)]
                     if two else [("T", up, vedges, True)])

            for tag, ws, sedges, is_cand in sides:
                cur = None          # open block (muni label seen)
                pend = None         # wrapped-total muni awaiting its values
                buf = []            # unlabeled numeric rows (carry-over)

                def put(muni, kind, w):
                    val = as_int(w["text"])
                    e = assign_edge(w, sedges)
                    if is_cand:
                        col = colmap.get(e)
                        if col is None:
                            return  # write-in detail column
                        vec = main[party][muni].setdefault(col, {})
                        if kind in vec and vec[kind] != val:
                            problems.append(
                                "SOVC p%d: %s %r %s %s re-printed with a "
                                "different value (%d vs %d)"
                                % (pno, party, muni, col, kind, vec[kind],
                                   val))
                        vec[kind] = val
                    else:
                        left[party][muni][kind][e] = val

                def flush_total(muni, rows):
                    # rows = buffered carry-over rows + the total row, in
                    # print order; kinds fill up to mail/prov/total
                    kinds = ["mail", "prov", "total"][3 - len(rows):]
                    for kind, rowvals in zip(kinds, rows):
                        for w in rowvals:
                            put(muni, kind, w)

                for line in lines_of(ws):
                    toks = sorted(line["words"], key=lambda w: w["x0"])
                    ints = [w for w in toks if is_int(w["text"])]
                    texts = [w["text"] for w in toks]
                    first_int = min((toks.index(w) for w in ints),
                                    default=len(texts))
                    label = " ".join(texts[:first_int]).strip()
                    if label.startswith("Page:"):
                        continue
                    while label.startswith("Total "):
                        label = label[6:].strip()   # dangling wrap word

                    if not ints:
                        if label in ("", "District", "Municipality", "Total"):
                            continue
                        if label.endswith("- Total"):
                            pend = label[:-7].strip()
                            continue
                        if label.endswith("-"):
                            pend = label[:-1].strip()
                            continue
                        if label == "Cumulative":
                            cur = "Cumulative"
                            add_muni("Cumulative")
                            continue
                        if is_muni_label(label):
                            if buf or pend:
                                problems.append(
                                    "SOVC p%d: header %r with %s pending"
                                    % (pno, label,
                                       "buffered rows" if buf else "a wrap"))
                                buf, pend = [], None
                            cur = label
                            add_muni(label)
                            continue
                        problems.append("SOVC p%d: stray label line %r"
                                        % (pno, label))
                        continue

                    # numeric row
                    if label.endswith("- Total"):
                        muni = label[:-7].strip()
                    elif label.endswith("-"):
                        muni = label[:-1].strip()
                    else:
                        muni = None
                    if label == "Municipality - Total":
                        for w in ints:
                            e = assign_edge(w, sedges)
                            if is_cand:
                                col = colmap.get(e)
                                if col is None:
                                    continue    # write-in detail column
                                mtot[party][col] = as_int(w["text"])
                            else:
                                left_mtot[party][e] = as_int(w["text"])
                        continue
                    if muni is not None and \
                            not (is_muni_label(muni) or muni == "Cumulative"):
                        problems.append("SOVC p%d: unrecognized label %r"
                                        % (pno, label))
                        continue
                    if muni is not None:            # labelled total row
                        if pend is not None and pend != muni:
                            problems.append("SOVC p%d: total %r but wrap %r "
                                            "pending" % (pno, muni, pend))
                        flush_total(muni, buf + [ints])
                        buf, cur, pend = [], None, None
                    elif pend is not None:          # a wrapped total's values
                        flush_total(pend, buf + [ints])
                        muni, cur, pend, buf = pend, None, None, []
                    elif cur is not None:           # labelled Mail-In / Prov
                        kind = {"Mail-In": "mail", "Provisional": "prov"} \
                            .get(label)
                        if kind is None:
                            problems.append("SOVC p%d: numeric row %r with "
                                            "unexpected label under %r"
                                            % (pno, label, cur))
                            continue
                        for w in ints:
                            put(cur, kind, w)
                    else:                           # unlabeled carry-over
                        buf.append(ints)
                if pend is not None or buf:
                    problems.append("SOVC p%d: page ends with wrap %r / %d "
                                    "buffered rows" % (pno, pend, len(buf)))
    return munis, left, main, mtot, left_mtot


def validate_sovc(munis, left, main, mtot, left_mtot, problems):
    info = []
    for party in ("DEM", "REP"):
        # left sub-table identities
        for muni, rows in sorted(left[party].items()):
            if muni == "Cumulative":
                continue
            cast = rows.get("total", {}).get(EDGE_CAST)
            if cast is None:
                problems.append("SOVC left %s %r: no total row" % (party, muni))
                continue
            mail = rows.get("mail", {}).get(EDGE_CAST, 0)
            prov = rows.get("prov", {}).get(EDGE_CAST, 0)
            if mail + prov != cast:
                problems.append("SOVC left %s %r: cast %s != mail %s + prov %s"
                                % (party, muni, cast, mail, prov))
            regs = {rows.get(k, {}).get(EDGE_REG) for k in ("mail", "prov", "total")}
            regs.discard(None)
            if len(regs) > 1:
                problems.append("SOVC left %s %r: registered varies %s"
                                % (party, muni, regs))
        # main-column identities
        for muni in sorted(main[party]):
            for col, vec in sorted(main[party][muni].items()):
                if vec.get("total", 0) != vec.get("mail", 0) + vec.get("prov", 0):
                    problems.append("SOVC %s %r %s: total %s != mail %s + "
                                    "prov %s" % (party, muni, col,
                                                 vec.get("total"),
                                                 vec.get("mail"),
                                                 vec.get("prov")))
        # countywide: muni sum == Municipality-Total
        for col, want in sorted(mtot[party].items()):
            s = sum(main[party][m].get(col, {}).get("total", 0)
                    for m in main[party] if m != "Cumulative")
            if s != want:
                problems.append("SOVC %s %s: muni sum %d != Municipality-"
                                "Total %d" % (party, col, s, want))
        if left_mtot[party]:
            s = sum(left[party][m]["total"][EDGE_CAST]
                    for m in left[party]
                    if m != "Cumulative" and "total" in left[party][m])
            got = left_mtot[party].get(EDGE_CAST)
            if got is not None and s != got:
                problems.append("SOVC left %s: muni cast sum %d != "
                                "Municipality-Total %s" % (party, s, got))
    # Summary anchors: muni sum (mail+prov) per named candidate
    for party in ("DEM", "REP"):
        for name, want in SUMMARY_MAIL_PROV[party].items():
            got = sum(main[party][m][name]["mail"] + main[party][m][name]["prov"]
                      for m in main[party]
                      if m != "Cumulative" and name in main[party][m])
            info.append("anchor %s %s: SOVC mail+prov %d vs Summary %d %s"
                        % (party, name, got, want,
                           "OK" if got == want else "MISMATCH"))
    info.append("munis: %d (DEM left %d, REP left %d; DEM main %d, REP main %d)"
                % (len(munis), len(set(left["DEM"])), len(set(left["REP"])),
                   len(set(main["DEM"])), len(set(main["REP"]))))
    return info


# ---------------------------------------------------------------- Summary

def parse_summary(pdf, problems):
    """Parse the Summary Report's per-tabulator blocks.

    Returns (blocks, info) — blocks in file order, each:
    {title, party, vote_for, candidates: [(name, [m,e,ed,p,total])],
     writein: vec|None, total_votes: vec|None, times: vec|None, reg: int|None,
     details: [(name, vec)]}
    """
    blocks = []
    closed = []                 # blocks whose Total Votes has been seen
    cur = None
    pend = None                 # buffered (possibly wrapped) row
    after_sf = False            # the line after a wrapped "Summary for:" line

    def ints_of(tokens):
        return [as_int(t) for t in tokens if is_int(t)]

    def flush():
        nonlocal pend
        if pend is None:
            return
        name, marker, vals = pend
        pend = None
        if len(vals) < 5:
            problems.append("Summary %r: incomplete row %r %s"
                            % (cur["title"] if cur else closed[-1]["title"]
                               if closed else "?", name, vals))
            return
        vals = vals[:5]
        if marker == "DETAIL":
            owner = closed[-1] if closed else cur
            if owner is None:
                problems.append("Summary: write-in detail with no block: %r"
                                % name)
            else:
                owner["details"].append((name, vals))
        elif marker == "AGG":
            if cur is None:
                problems.append("Summary: aggregate Write-in with no block")
            else:
                cur["writein"] = vals
        else:
            if cur is None:
                problems.append("Summary: candidate row with no block: %r"
                                % name)
            else:
                cur["candidates"].append((name, vals))

    for pno, page in enumerate(pdf.pages, 1):
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("Page:"):
                continue
            m = TITLE_RE.match(line)
            if after_sf:
                after_sf = False
                if not TITLE_RE.match(line) and not ints_of(line.split()):
                    continue
            if m:
                flush()
                cur = {"title": m.group(1), "party": m.group(2),
                       "vote_for": int(m.group(3)), "candidates": [],
                       "writein": None, "total_votes": None, "times": None,
                       "reg": None, "details": []}
                blocks.append(cur)
                continue
            if cur is not None and line in ("DEM", "REP"):
                continue
            if line.startswith("Summary for:"):
                after_sf = True     # its tail wraps to the next line (p1)
            if line.startswith("Mail-In Early Voting") \
                    or line.startswith("Candidate Party") \
                    or line.startswith("Election Summary Report") \
                    or line.startswith("Closed Primary") \
                    or line.startswith("Burlington, NJ") \
                    or line.startswith("June 02, 2026") \
                    or line.startswith("Summary for:") \
                    or line.startswith("Elector Group") \
                    or line.startswith("Combined Party") \
                    or line.startswith("with Write Ins") \
                    or line.startswith("Voters Cast:") \
                    or TURNOUT_RE.match(line):
                # header/turnout junk — but flush a complete pending row
                flush()
                continue
            if line.startswith("Times Cast"):
                flush()
                if cur is None:
                    problems.append("Summary p%d: Times Cast with no block"
                                    % pno)
                    continue
                nums = ints_of(line.replace("/", " ").split())
                cur["times"] = nums[:5]
                if len(nums) >= 6:
                    cur["reg"] = nums[5]
                continue
            if line.startswith("Total Votes"):
                flush()
                if cur is None:
                    problems.append("Summary p%d: Total Votes with no block"
                                    % pno)
                    continue
                cur["total_votes"] = ints_of(line.split())[:5]
                closed.append(cur)
                cur = None
                continue
            # data row (candidate / aggregate / write-in detail), possibly
            # wrapped across lines
            toks = line.split()
            marker = None
            if "WRITE-IN" in toks:
                marker = "DETAIL"
                cut = toks.index("WRITE-IN")
            elif "(DEM)" in toks or "(REP)" in toks:
                marker = "CAND"
                cut = min(i for i, t in enumerate(toks)
                          if t in ("(DEM)", "(REP)"))
            elif "DEM" in toks or "REP" in toks:
                marker = "CAND"
                cut = min(i for i, t in enumerate(toks)
                          if t in ("DEM", "REP"))
            elif toks[0] == "Write-in":
                marker = "AGG"
                cut = 0
            if marker is None:
                # continuation of a wrapped row: a name's second line (no
                # integers), or the tail of a row's values (<5 ints yet)
                if pend is not None and not ints_of(toks):
                    pend[0] += " " + " ".join(t for t in toks if not t.endswith("%"))
                elif pend is not None and len(pend[2]) < 5:
                    pend[2].extend(ints_of(toks))
                else:
                    problems.append("Summary p%d: unrecognized line %r"
                                    % (pno, line))
                continue
            name = " ".join(toks[:cut])
            vals = ints_of(toks[cut + 1:])
            if pend is not None:
                if len(pend[2]) >= 5:
                    flush()
                else:
                    pend[2].extend(vals)
                    continue
            pend = [name, marker, vals]
    flush()
    return blocks


def validate_summary(blocks, problems):
    nbad = 0
    for b in blocks:
        if b["total_votes"] is None:
            problems.append("Summary block never closed: %r" % b["title"])
            continue
        s = [sum(v[i] for _, v in b["candidates"]) for i in range(5)]
        if b["writein"]:
            s = [s[i] + b["writein"][i] for i in range(5)]
        if s != b["total_votes"]:
            nbad += 1
            problems.append("Summary %r: candidate sum %s != total votes %s"
                            % (b["title"], s, b["total_votes"]))
        if b["writein"]:
            ds = sum(v[4] for _, v in b["details"])
            short = b["writein"][4] - ds
            if short and SUMMARY_WRITEIN_SHORT.get(
                    (b["title"], b["party"])) == short:
                problems.append("SOURCE: Summary %r (%s): write-in details "
                                "sum %d, aggregate %d (shortfall %d is in "
                                "the source)"
                                % (b["title"], b["party"], ds,
                                   b["writein"][4], short))
            elif ds != b["writein"][4]:
                nbad += 1
                problems.append("Summary %r: write-in detail sum %d != "
                                "aggregate %d" % (b["title"], ds,
                                                  b["writein"][4]))
    return nbad


# ----------------------------------------------------------------- output

SENATE_NAMED = {
    "DEM": ["Cory Booker"],
    "REP": ["Justin Murphy", "Robert S. Lebovics", "Alex Zdan",
            "Richard Tabor"],
}
MUNI_OF_TITLE_RE = re.compile(
    r"^(.+?\b(?:Township|Borough|City|Town))\b(.+)$")
COUNTYWIDE_TITLES = {"US Senate", "County Commissioner", "County Surrogate"}
OFFICE_ORDER = {"U.S. Senate": 0, "Registered Voters": 3, "Ballots Cast": 4}


def build_rows(left, main, blocks, problems):
    """Assemble output rows. Returns (rows, committee_munis, municipal_munis).

    U.S. Senate rows come from the SOVC (mail + provisional only — the SOVC
    breaks out no election-day/early-voting votes below the county); county
    committee and municipal rows come from the Summary blocks.
    """
    rows = []

    def add(precinct, office, district, party, candidate, votes, mail=None,
            prov=None):
        rows.append({"precinct": precinct, "office": office,
                     "district": district, "party": party,
                     "candidate": candidate, "votes": votes,
                     "mail": mail, "provisional": prov})

    # U.S. Senate per municipality
    for party in ("DEM", "REP"):
        named = SENATE_NAMED[party]
        for muni in sorted(main[party], key=natkey):
            if muni == "Cumulative":
                continue
            tv = main[party][muni].get("Total Votes", {})
            if not tv:
                problems.append("SOVC %s %r: no Total Votes column"
                                % (party, muni))
                continue
            ntot = nmail = nprov = 0
            complete = True
            for name in named:
                vec = main[party][muni].get(name)
                if vec is None:
                    problems.append("SOVC %s %r: missing column %r"
                                    % (party, muni, name))
                    complete = False
                    continue
                add(muni, "U.S. Senate", "", party, name, vec["total"],
                    vec["mail"], vec["prov"])
                ntot += vec["total"]
                nmail += vec["mail"]
                nprov += vec["prov"]
            if complete:
                add(muni, "U.S. Senate", "", party, "Write-ins",
                    tv["total"] - ntot, tv["mail"] - nmail,
                    tv["prov"] - nprov)

    committee_munis = set()
    municipal_munis = set()
    committee = {}      # (precinct, office, district, party, candidate) -> votes
    for b in blocks:
        line = "%s (%s) (Vote for %d)" % (b["title"], b["party"],
                                          b["vote_for"])
        cm = COMMITTEE_RE.match(line)
        if cm:
            muni, dist, gender = cm.group(1), cm.group(2), cm.group(3)
            muni = re.sub(r"^Mt ", "Mount ", muni)  # committee titles abbreviate
            committee_munis.add(muni)
            precinct = "%s District %d" % (muni, int(dist))
            office = "%s Member of County Committee" % gender
        elif b["title"] in COUNTYWIDE_TITLES \
                or b["title"].startswith("Member of Congress"):
            continue    # countywide offices: not in the output (see docstring)
        else:
            mm = MUNI_OF_TITLE_RE.match(b["title"])
            if mm is None:
                problems.append("unmapped municipal block title: %r"
                                % b["title"])
                continue
            muni = mm.group(1)
            office = mm.group(2).replace(" - ", " ").strip()
            municipal_munis.add(muni)
            precinct = muni

        def emit(name, votes):
            if cm:
                # a district's N-M tabulator blocks each carry the full
                # contest; merge them into one district-level row
                key = (precinct, office, str(int(dist)), b["party"], name)
                committee[key] = committee.get(key, 0) + votes
            else:
                add(precinct, office, "", b["party"], name, votes)

        for name, vec in b["candidates"]:
            if name == "No Petition Filed":
                continue
            emit(name, vec[4])
        if b["writein"]:
            emit("Write-ins", b["writein"][4])
    for (precinct, office, district, party, name), votes in committee.items():
        add(precinct, office, district, party, name, votes)

    # pseudo rows per municipality (SOVC left sub-table, mail+prov only)
    sovc_munis = set(left["DEM"]) | set(left["REP"])
    for muni in sorted(sovc_munis - {"Cumulative"}, key=natkey):
        reg = cast = mail = prov = 0
        ok = True
        for p in ("DEM", "REP"):
            sub = left[p].get(muni)
            if not sub:
                problems.append("SOVC %s %r: no left sub-table rows"
                                % (p, muni))
                ok = False
                continue
            rvals = {sub.get(k, {}).get(EDGE_REG) for k in ("mail", "prov",
                                                       "total")}
            rvals.discard(None)
            if not rvals:
                problems.append("SOVC %s %r: missing registered-voters cell"
                                % (p, muni))
                ok = False
                continue
            reg += next(iter(rvals))
            mail += sub.get("mail", {}).get(EDGE_CAST, 0)
            prov += sub.get("prov", {}).get(EDGE_CAST, 0)
            cast += sub.get("total", {}).get(EDGE_CAST, 0)
        if not ok:
            continue
        if cast != mail + prov:
            problems.append("SOVC %r: cast %d != mail %d + prov %d"
                            % (muni, cast, mail, prov))
        add(muni, "Registered Voters", "", "", "", reg)
        add(muni, "Ballots Cast", "", "", "", cast, mail, prov)

    for label, muniset in (("committee", committee_munis),
                           ("municipal", municipal_munis)):
        unknown = muniset - sovc_munis
        for muni in sorted(unknown):
            problems.append("%s municipality not in SOVC: %r" % (label, muni))

    rows.sort(key=lambda r: (
        OFFICE_ORDER.get(r["office"],
                         1 if "County Committee" in r["office"] else 2),
        r["office"], natkey(r["precinct"]),
        int(r["district"]) if r["district"].isdigit() else 0,
        r["party"], natkey(r["candidate"])))
    return rows, committee_munis, municipal_munis


def crosscheck(main, problems):
    """Compare SOVC U.S. Senate per-candidate sums (mail+prov only) with the
    official county CSV."""
    official = {}
    with open(COUNTY_CSV, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["county"] != "Burlington" or row["office"] != "U.S. Senate":
                continue
            key = name_key(row["candidate"])
            official[key] = official.get(key, 0) + int(row["votes"])
    sums = {}
    for party in ("DEM", "REP"):
        for name in SENATE_NAMED[party]:
            sums[name_key(name)] = sum(
                main[party][m].get(name, {}).get("total", 0)
                for m in main[party] if m != "Cumulative")
    for key in sorted(official):
        got = sums.get(key, 0)
        want = official[key]
        print("CROSSCHECK U.S. Senate %r: SOVC mail+prov %d vs official %d "
              "(delta %+d)" % (key, got, want, got - want))


# ------------------------------------------------------------------- main

def main():
    problems = []
    sovc = pdfplumber.open(SOVC_PDF)
    munis, left, main, mtot, left_mtot = parse_sovc(sovc, problems)
    info = validate_sovc(munis, left, main, mtot, left_mtot, problems)

    summ = pdfplumber.open(SUMMARY_PDF)
    blocks = parse_summary(summ, problems)
    nbad = validate_summary(blocks, problems)

    rows, committee_munis, municipal_munis = build_rows(
        left, main, blocks, problems)
    crosscheck(main, problems)

    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(["county", "precinct", "office", "district", "party",
                      "candidate", "votes", "mail", "provisional"])
        for r in rows:
            wtr.writerow(["Burlington", r["precinct"], r["office"],
                          r["district"], r["party"], r["candidate"],
                          r["votes"], r["mail"] if r["mail"] is not None
                          else "", r["provisional"]
                          if r["provisional"] is not None else ""])

    print("wrote %d rows to %s" % (len(rows), OUTPUT))
    print("munis: %d; committee munis: %d; municipal contests: %d"
          % (len(munis), len(committee_munis), len(municipal_munis)))
    for line in info:
        print("  " + line)
    print("Summary blocks: %d (%d failed internal identities)"
          % (len(blocks), nbad))
    print("problems: %d" % len(problems))
    for p in problems[:80]:
        print("  ", p)
    if len(problems) > 80:
        print("   ... %d more" % (len(problems) - 80))
    return 0


if __name__ == "__main__":
    sys.exit(main())