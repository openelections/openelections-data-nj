"""Parse Cape May County's 2026 primary into a precinct CSV.

Sources (~/code/openelections-sources-nj/2026/primary/):
- "Cape May NJ 2026 Primary Summary Report.pdf" — Precinct Summary Report.
  One page (or page group) per precinct: a Statistics block on the first
  page, then two contest blocks per page, each a clean list of
  "Candidate Name N" lines followed by Write-In Totals / Total Votes Cast /
  Overvotes / Undervotes / Contest Totals keys. PRIMARY SOURCE for every
  row of the output CSV.
- "Cape May NJ 2026 Primary Statement of Vote.pdf" — Dominion Statement of
  Vote (Custom Table Report layout): a statistics table (label + 9 numbers
  + 4 turnout percentages per row, ending in a Totals row) and one contest
  per page with per-precinct rows plus "2ND CON ..." aggregate rows and a
  Totals row. VALIDATION SOURCE only: every row is checked against the
  Summary Report by label (falling back to value-vector accounting, since
  two Lower Township Ward 2 rows lost their district digit in the print)
  plus per-row arithmetic identities.

The output follows the 2026 precedents (Warren/Hunterdon): party tokens
REP/DEM, "No Petition Filed" candidates dropped, Write-ins rows written
even when zero, and Registered Voters / Ballots Cast / Blank Ballots Cast
pseudo-rows per precinct. Dominion prints contest totals and no vote-type
breakdowns, so `votes` is the single election-day total.
"""

import csv
import re
from itertools import combinations

import pdfplumber

SUMMARY_PDF = ("/Users/dwillis/code/openelections-sources-nj/2026/primary/"
               "Cape May NJ 2026 Primary Summary Report.pdf")
STATEMENT_PDF = ("/Users/dwillis/code/openelections-sources-nj/2026/primary/"
                 "Cape May NJ 2026 Primary Statement of Vote.pdf")
OUTPUT = "2026/counties/20260602__nj__primary__cape_may__precinct.csv"
COUNTY_CSV = "2026/20260602__nj__primary__county.csv"

US_HOUSE_DISTRICT = "2"   # Van Drew's 2nd congressional district

SUMMARY_HEADERS = (
    "Precinct Summary Report",
    "2026 Primary Election Cape May",
    "June 2, 2026 June 2, 2026",
)

# label -> key into the per-precinct statistics dict
STAT_PATTERNS = [
    (re.compile(r"^Registered Voters - Total (\d[\d,]*)$"), "reg_total"),
    (re.compile(r"^Registered Voters - REPUBLICAN (\d[\d,]*)$"), "reg_rep"),
    (re.compile(r"^Registered Voters - DEMOCRATIC (\d[\d,]*)$"), "reg_dem"),
    (re.compile(r"^Registered Voters - NONPARTISAN (\d[\d,]*)$"), "reg_np"),
    (re.compile(r"^Ballots Cast - Total (\d[\d,]*)$"), "cast_total"),
    (re.compile(r"^Ballots Cast - REPUBLICAN (\d[\d,]*)$"), "cast_rep"),
    (re.compile(r"^Ballots Cast - DEMOCRATIC (\d[\d,]*)$"), "cast_dem"),
    (re.compile(r"^Ballots Cast - NONPARTISAN (\d[\d,]*)$"), "cast_np"),
    (re.compile(r"^Ballots Cast - Blank (\d[\d,]*)$"), "cast_blank"),
]
STAT_KEYS = tuple(key for _, key in STAT_PATTERNS)

CONTEST_KEYS = {
    "Write-In Totals": "write_in",
    "Total Votes Cast": "cast",
    "Overvotes": "overvotes",
    "Undervotes": "undervotes",
    "Contest Totals": "contest_total",
}
CONTEST_KEY_RE = re.compile(
    r"^(Write-In Totals|Total Votes Cast|Overvotes|Undervotes"
    r"|Contest Totals) (\d+)$")
PRECINCT_RE = re.compile(r"^[A-Z].*\bDistrict \d+$")

# Statement of Vote stats-table integer column x-centers (from the first
# data row of page 1; the layout is identical on every stats page)
STAT_INT_CENTERS = (193.35, 235.35, 279.55, 319.35, 361.35, 405.55,
                    447.55, 491.8, 533.75)
STAT_INT_TOL = 12
# SoV row labels always end left of this x (a long 'Ward N District NN'
# label pushes its district digit out to x1 = 158.5; value columns start
# at x0 = 180)
LABEL_X_MAX = 165
VALIDATE_SUMMARY_KEYS = ("reg_total", "cast_total", "cast_rep", "cast_dem")

warnings = []


def warn(msg):
    warnings.append(msg)


# ------------------------------------------------------------------ offices

def office_name(raw):
    """Map a Summary Report contest title (party prefix stripped) to the
    office name used in the output CSV."""
    raw = raw.strip()
    if raw in ("Memeber of the United States Senate",
               "Member of the United States Senate"):
        return "U.S. Senate"
    if raw == "Member of the House of Representatives":
        return "U.S. House"
    if raw == "County Sheriff":
        return "County Sheriff"
    if raw == "Member of the Board of County Commissioners":
        return "County Commissioner"
    m = re.match(r"^Member of (?:the )?Township Committee-Township of (.+)$", raw)
    if m:
        return f"{m.group(1)} Township Committee"
    m = re.match(r"^Member of (?:the )?Council-Township of (.+?)-Ward (\d+)$", raw)
    if m:
        return f"{m.group(1)} Township Council Ward {m.group(2)}"
    m = re.match(r"^Member of (?:the )?Council (\d)\S{0,2} Ward-City of (.+)$", raw)
    if m:
        return f"{m.group(2)} Council Ward {m.group(1)}"
    m = re.match(r"^Member of the Council-Borough of (.+)$", raw)
    if m:
        return f"{m.group(1)} Borough Council"
    m = re.match(r"^Mayor-(?:Borough|Township|City) of (.+)$", raw)
    if m:
        return f"{m.group(1)} Mayor"
    raise ValueError(f"unrecognized contest title: {raw!r}")


def norm(name):
    return re.sub(r"[.,\s]+", " ", name).strip().lower()


def norm_toks(name):
    """Token set with hyphens flattened — pdfplumber breaks hyphenated
    names differently on different lines (Blair- / Slemmer)."""
    return sorted(re.sub(r"[-]", " ", norm(name)).split())


def is_int(text):
    return text.replace(",", "").isdigit()


# ----------------------------------------------------------- summary report

def parse_summary():
    """Parse the Precinct Summary Report.

    Returns (precinct_stats, contests) where precinct_stats maps label ->
    stats dict and contests is a list of dicts with keys precinct, party,
    raw_office, candidates (list of (name, votes)), write_in, cast,
    overvotes, undervotes, contest_total, vote_for, page.
    """
    stats = {}
    contests = []
    precinct = None
    contest = None

    def close():
        nonlocal contest
        if contest is not None:
            contests.append(contest)
            contest = None

    with pdfplumber.open(SUMMARY_PDF) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith(SUMMARY_HEADERS):
                    continue
                if "Precinct Summary -" in line and "Page" in line:
                    continue  # page footer
                m = re.match(r"^(REP|DEM)-(.+)$", line)
                if m:
                    close()
                    contest = {
                        "precinct": precinct, "party": m.group(1),
                        "raw_office": m.group(2), "candidates": [],
                        "write_in": None, "cast": None, "overvotes": None,
                        "undervotes": None, "contest_total": None,
                        "vote_for": None, "page": page_no,
                    }
                    continue
                if contest is not None and line.startswith("Vote For"):
                    contest["vote_for"] = int(line.split()[-1])
                    continue
                if contest is not None and line == "TOTAL":
                    continue
                m = re.match(r"^(Write-In Totals|Total Votes Cast|Overvotes"
                             r"|Undervotes|Contest Totals) (\d+)$", line)
                if m:
                    contest[CONTEST_KEYS[m.group(1)]] = int(m.group(2))
                    continue
                if re.match(r"^[A-Z].*\bDistrict \d+$", line) \
                        or line.startswith("2ND CON"):
                    # a new page's label; the label itself never matches a
                    # candidate line because of this check's precedence.
                    # "2ND CON ..." rows are county-wide aggregates (FED
                    # Overseas-style), parsed but excluded from the output.
                    close()
                    precinct = line
                    stats.setdefault(precinct, {})
                    continue
                if contest is None:
                    if line.startswith("Voter Turnout"):
                        continue
                    for pat, key in STAT_PATTERNS:
                        m = pat.match(line)
                        if m:
                            if precinct is None:
                                raise ValueError(
                                    f"p{page_no}: statistics row before any "
                                    f"precinct label: {line!r}")
                            stats[precinct][key] = int(m.group(1).replace(",", ""))
                            break
                    else:
                        if line.startswith("Statistics"):
                            continue
                        if re.match(r"^[A-Z].*\bDistrict \d+$", line):
                            precinct = line
                            stats.setdefault(precinct, {})
                        else:
                            raise ValueError(
                                f"p{page_no}: unrecognized line: {line!r} "
                                f"(precinct={precinct!r})")
                    continue
                m = re.match(r"^(\D.*\S)\s+(\d+)$", line)
                if m:
                    contest["candidates"].append((m.group(1).strip(),
                                                  int(m.group(2))))
                    continue
                raise ValueError(
                    f"p{page_no}: unrecognized line: {line!r} "
                    f"(precinct={precinct!r})")
    close()
    return stats, contests


def validate_summary(stats, contests):
    """Arithmetic and completeness checks; returns problem count."""
    n_bad = 0
    for label, s in sorted(stats.items()):
        missing = [k for _, k in STAT_PATTERNS if k not in s]
        if missing:
            warn(f"stats {label}: missing {missing}")
            n_bad += 1
            continue
        if s["reg_total"] != s["reg_rep"] + s["reg_dem"] + s["reg_np"]:
            warn(f"stats {label}: registered {s['reg_total']} but "
                 f"{s['reg_rep']} + {s['reg_dem']} + {s['reg_np']}")
            n_bad += 1
        if s["cast_total"] != (s["cast_rep"] + s["cast_dem"]
                               + s["cast_np"] + s["cast_blank"]):
            warn(f"stats {label}: ballots {s['cast_total']} but "
                 f"{s['cast_rep']} + {s['cast_dem']} + {s['cast_np']} + "
                 f"{s['cast_blank']}")
            n_bad += 1
    for c in contests:
        pno = c["page"]
        office = office_name(c["raw_office"])
        no_pet = next((v for n, v in c["candidates"]
                       if n == "No Petition Filed"), 0)
        if no_pet:
            warn(f"p{pno} {c['precinct']}: No Petition Filed has "
                 f"{no_pet} votes")
        if c["cast"] is None:
            warn(f"p{pno} {c['precinct']} {c['party']} {office}: no "
                 f"'Total Votes Cast' found")
            n_bad += 1
            continue
        csum = sum(v for n, v in c["candidates"]
                   if n != "No Petition Filed") + (c["write_in"] or 0)
        if csum != c["cast"]:
            warn(f"p{pno} {c['precinct']} {c['party']} {office}: candidates "
                 f"sum {csum} != Total Votes Cast {c['cast']}")
            n_bad += 1
        if None not in (c["contest_total"], c["cast"], c["overvotes"],
                        c["undervotes"]) and c["contest_total"] != (
                c["cast"] + c["overvotes"] + c["undervotes"]):
            warn(f"p{pno} {c['precinct']} {c['party']} {office}: contest "
                 f"total {c['contest_total']} != {c['cast']} + "
                 f"{c['overvotes']} + {c['undervotes']}")
            n_bad += 1
        if c["vote_for"] == 1 and c["contest_total"] is not None:
            ballots = stats.get(c["precinct"], {}).get(
                "cast_rep" if c["party"] == "REP" else "cast_dem")
            if ballots is not None and c["contest_total"] != ballots:
                warn(f"p{pno} {c['precinct']} {c['party']} {office}: contest "
                     f"total {c['contest_total']} != party ballots {ballots}")
                n_bad += 1
    return n_bad


# -------------------------------------------------------- statement of vote

def to_lines(words, ytol=3):
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= ytol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return lines


def label_of(line_words):
    return " ".join(w["text"] for w in line_words if w["x1"] <= LABEL_X_MAX)


def assign_int_columns(nums):
    """Assign digit words to the 9 stats columns by x-center. Returns a
    list of 9 ints (blanks read as 0) or None if assignment is hopeless."""
    vals = [0] * 9
    for w in nums:
        center = (w["x0"] + w["x1"]) / 2
        best = min(range(9), key=lambda i: abs(STAT_INT_CENTERS[i] - center))
        if abs(STAT_INT_CENTERS[best] - center) > STAT_INT_TOL:
            return None
        if vals[best]:
            return None  # two words in one column
        vals[best] = int(w["text"].replace(",", ""))
    return vals


def check_stats_identity(tag, row):
    bad = 0
    if row["reg_total"] != row["reg_rep"] + row["reg_dem"] + row["reg_np"]:
        warn(f"{tag}: registered {row['reg_total']} but "
             f"{row['reg_rep']} + {row['reg_dem']} + {row['reg_np']}")
        bad += 1
    if row["cast_total"] != (row["cast_rep"] + row["cast_dem"]
                             + row["cast_np"] + row["cast_blank"]):
        warn(f"{tag}: ballots {row['cast_total']} but "
             f"{row['cast_rep']} + {row['cast_dem']} + {row['cast_np']} + "
             f"{row['cast_blank']}")
        bad += 1
    return bad


def vector(row_or_vals):
    return tuple(row_or_vals[k] for k in STAT_KEYS)


def parse_statement_stats(pdf, stats):
    """Validate the SoV statistics table against Summary stats.

    Returns (aggregate rows keyed by label, totals-row dict). Precinct rows
    are matched by label; SoV rows whose district digit was dropped in the
    print are covered by the vector-multiset comparison."""
    aggregates = {}
    precinct_rows = []  # (label, values dict, page)
    totals_row = None
    for page_no, page in enumerate(pdf.pages, 1):
        words = page.extract_words()
        # rows are identified by content: real data rows have >=1 integer
        # value right of the label column (header words never do), and the
        # table stops at the Totals row. The header block's bottom edge
        # shifts between pages, so no fixed top threshold is used.
        n_pct = 0
        for line in to_lines(words):
            label = label_of(line)
            if label.startswith("Custom Table Report"):
                continue
            if not label:
                continue
            nums = [w for w in line if is_int(w["text"])
                    and w["x0"] >= LABEL_X_MAX and w["x1"] < 545]
            pcts = [w for w in line if w["text"].endswith("%")]
            if not nums and not pcts:
                continue
            vals = assign_int_columns(nums)
            if vals is None:
                warn(f"SoV stats p{page_no} {label!r}: {len(nums)} numbers, "
                     f"could not assign to the 9 columns")
                continue
            row = dict(zip(STAT_KEYS, vals))
            if pcts and len(pcts) != 4:
                warn(f"SoV stats p{page_no} {label!r}: {len(pcts)} pct cells")
            if label == "Totals":
                totals_row = row
                break
            if label in stats:
                precinct_rows.append((label, row, page_no))
            elif label.startswith("2ND CON"):
                aggregates[label] = row
            else:
                # a row whose district digit was dropped in the print
                # (two Lower Ward 2 rows): identify it by its full
                # 9-value vector against Summary rows not yet matched
                cands = [l for l in stats
                         if all(k in stats[l] for k in STAT_KEYS)
                         and vector(stats[l]) == vector(row)
                         and l not in {pl for pl, _, _ in precinct_rows}]
                if len(cands) == 1:
                    precinct_rows.append((cands[0], row, page_no))
                else:
                    warn(f"SoV stats p{page_no}: unrecognized label "
                         f"{label!r} (treated as aggregate)")
                    aggregates[f"{label} (p{page_no})"] = row
        if totals_row is not None:
            break
    for label, row, page_no in precinct_rows:
        check_stats_identity(f"SoV stats p{page_no} {label}", row)
    for label, row in aggregates.items():
        check_stats_identity(f"SoV stats aggregate {label}", row)
    if totals_row is None:
        warn("SoV stats: Totals row not found; stopping SoV validation")
        return aggregates, None
    check_stats_identity("SoV stats Totals", totals_row)
    for key in STAT_KEYS:
        s = sum(r[key] for _, r, _ in precinct_rows)
        a = sum(row[key] for row in aggregates.values())
        if s + a != totals_row[key]:
            warn(f"SoV stats Totals {key}: precincts {s} + aggregates {a} "
                 f"!= Totals {totals_row[key]}")
    # label-matched comparison + multiset comparison of full 9-vectors
    matched = 0
    for label, row, page_no in precinct_rows:
        s = stats.get(label)
        if s is None:
            continue
        matched += 1
        for key in VALIDATE_SUMMARY_KEYS:
            if s.get(key) != row[key]:
                warn(f"SoV stats {label}: {key} {row[key]} vs Summary "
                     f"{s.get(key)}")
    sov_vectors = sorted(vector(r) for _, r, _ in precinct_rows)
    sum_vectors = sorted(vector(stats[l]) for l in stats
                         if all(k in stats[l] for k in STAT_KEYS))
    if sov_vectors != sum_vectors:
        only_sov = sorted(v for v in set(sov_vectors)
                          if sum_vectors.count(v) < sov_vectors.count(v))[:2]
        only_sum = sorted(v for v in set(sum_vectors)
                          if sov_vectors.count(v) < sum_vectors.count(v))[:2]
        warn(f"SoV stats: precinct 9-vector multiset differs from Summary; "
             f"only-in-SoV {only_sov} only-in-Summary {only_sum}")
    if matched < len(precinct_rows):
        missed = [l for l, _, _ in precinct_rows if l not in stats]
        if missed:
            warn(f"SoV stats: {len(missed)} rows unmatched by label "
                 f"(expected if the district digit was dropped in the "
                 f"print): {missed}")
    return aggregates, totals_row


def cluster_x(words, gap=12):
    clusters = []
    for w in sorted(words, key=lambda w: w["x0"]):
        if clusters and w["x0"] - max(x["x1"] for x in clusters[-1]) <= gap:
            clusters[-1].append(w)
        else:
            clusters.append([w])
    return clusters


def contest_title_groups(line_words):
    """Split one title line into contest groups: a group starts at each
    word beginning with REP-/DEM- (titles of side-by-side contests sit too
    close together for a plain x-gap split). Returns (party, raw_office,
    x0, x1) per group, in x order."""
    groups = []
    for w in sorted(line_words, key=lambda w: w["x0"]):
        m = re.match(r"^(REP|DEM)-", w["text"])
        if m or not groups:
            if not m:
                warn(f"SoV contest: stray title word {w['text']!r} in "
                     f"{[x['text'] for x in line_words]}")
                continue
            groups.append([m.group(1), [w]])
        else:
            groups[-1][1].append(w)
    out = []
    for party, ws in groups:
        name = " ".join(w["text"] for w in ws)
        name = name[len(party) + 1:].strip()
        out.append((party, name,
                    min(w["x0"] for w in ws), max(w["x1"] for w in ws)))
    return out


def is_fixed_col(name):
    """Header column that is not a candidate (write-in, cast, over/under,
    contest total)."""
    n = norm(name)
    n = n.replace("-", " ")
    return ("overvotes" in n or "undervotes" in n or "contest total" in n
            or "write in" in n or ("votes" in n and "cast" in n))


def block_ok(blk_names, cand_list):
    """True if a contiguous column block is one contest: fixed columns at
    the tail (TVC, Overvotes, Undervotes, Contest Total), one Write-in
    column, and every other column matching one of cand_list."""
    if len(blk_names) < 6:
        return False
    if "contest total" not in norm(blk_names[-1]):
        return False
    if "overvotes" not in norm(blk_names[-3]):
        return False
    if "undervotes" not in norm(blk_names[-2]):
        return False
    if len(blk_names) - len([n for n in blk_names if not is_fixed_col(n)]) != 5:
        return False
    for n in blk_names:
        if is_fixed_col(n):
            continue
        toks = norm_toks(n)
        if not any(norm_toks(c) == toks for c in cand_list):
            return False
    return True


def parse_statement_contests(pdf, contests):
    """Validate the SoV contest pages against the Summary contest rows.

    A SoV page can carry two contests side-by-side, so each page is split
    into horizontal bands at title lines; within a band the header words
    are clustered into columns and the columns are partitioned into one
    contiguous block per contest (block boundaries are pinned by the fixed
    tail of each contest: ... TVC, Overvotes, Undervotes, Contest Total).

    Contest titles can be truncated by the page edge (e.g. 'Member of the
    Township Committee-Township of' for several townships), so a title is
    mapped to the Summary office whose normalized name it equals or begins;
    truncated titles that stay ambiguous are resolved by which candidate
    office actually owns the page's precinct rows. Returns (aggregate rows
    keyed by (party, raw_office, label), candidate-column names keyed by
    (party, raw_office))."""
    by_key = {(c["precinct"], c["party"], c["raw_office"]): c
              for c in contests}
    summary_offices = sorted({(c["party"], c["raw_office"])
                              for c in contests})
    summary_cands = {}
    for c in contests:
        summary_cands.setdefault((c["party"], c["raw_office"]),
                                 [n for n, _ in c["candidates"]])

    def key_options(party, title):
        t = norm(title)
        return [k for k in summary_offices
                if k[0] == party and (norm(k[1]) == t
                                      or norm(k[1]).startswith(t))]

    # per-band sections awaiting key resolution
    parsed = []   # (party, title, options, blk_names,
                  #  [(label, vals, page_no, n_cand)])
    for page_no, page in enumerate(pdf.pages, 1):
        words = page.extract_words()
        lines = to_lines(words)
        title_idx = [i for i, l in enumerate(lines)
                     if any(w["text"].startswith(("REP-", "DEM-"))
                            for w in l)]
        if not title_idx:
            continue  # statistics pages before the contest pages
        bounds = title_idx + [len(lines)]
        for ti, tstart in enumerate(title_idx):
            band = lines[tstart + 1:bounds[ti + 1]]
            groups = contest_title_groups(lines[tstart])
            if not groups:
                continue
            vf_top = None
            data_tops = []
            for l in band:
                if line_text(l).startswith(("Custom Table Report", "Page ")):
                    continue
                if vf_top is None and any(w["text"] == "VOTE" for w in l):
                    vf_top = l[0]["top"]
                elif any(w["x0"] >= LABEL_X_MAX and is_int(w["text"])
                         for w in l):
                    data_tops.append(l[0]["top"])
            if vf_top is None or not data_tops:
                warn(f"SoV contest p{page_no}: no Vote-For line or no data "
                     f"rows ({[g[1] for g in groups]})")
                continue
            hdr_cap = min(data_tops) - 2
            hdr_words = [w for w in words
                         if vf_top < w["top"] < hdr_cap
                         and w["x0"] >= 170
                         and w["text"] not in ("VOTE", "FOR")
                         and not is_int(w["text"])]
            clusters = cluster_x(hdr_words, gap=12)
            col_names = [" ".join(w["text"] for w in
                                  sorted(cl, key=lambda w: (w["top"], w["x0"])))
                         for cl in clusters]
            centers = [sum(w["x0"] for w in cl) / len(cl) for cl in clusters]
            m, ng = len(col_names), len(groups)
            if m < 6 * ng:
                warn(f"SoV contest p{page_no}: {m} header columns too few "
                     f"for {ng} contest(s) {[g[1] for g in groups]}: "
                     f"{col_names}")
                continue
            options = [key_options(g[0], g[1]) or [None] for g in groups]
            unions = []
            for g, opts in zip(groups, options):
                names = set()
                for k in opts:
                    names.update(summary_cands.get(k, []))
                unions.append(list(names) or
                              list(summary_cands.get((g[0], g[1]), [])))
            # one contiguous column block per group; block_ok against the
            # union of the group's candidate offices
            valid = []
            for pts in combinations(range(1, m), ng - 1):
                blocks, prev = [], 0
                for pt in pts + (m,):
                    blocks.append(col_names[prev:pt])
                    prev = pt
                if all(block_ok(b, u) for b, u in zip(blocks, unions)):
                    valid.append(((0,) + pts + (m,), blocks))
            if len(valid) != 1:
                cand_lists = {g[1]: options[i] for i, g in enumerate(groups)}
                kind = "multiple" if len(valid) > 1 else "no"
                warn(f"SoV contest p{page_no}: {kind} column split(s) for "
                     f"{[g[1] for g in groups]}; columns {col_names}; "
                     f"offices {cand_lists}")
                continue
            splits, blocks = valid[0]
            # rows are shared between the two contests only in the sense of
            # layout: each row carries values in the block of the contest it
            # belongs to (the other block is simply not printed), except
            # Totals / 2ND CON rows which carry both blocks.
            band_rows = []
            for top in data_tops:
                lab = [w for w in words
                       if w["x1"] <= LABEL_X_MAX
                       and abs(w["top"] - top) <= 3]
                if not lab:
                    continue
                label = " ".join(w["text"] for w in sorted(
                    lab, key=lambda w: (w["top"], w["x0"])))
                colvals = [0] * m
                far = []
                for w in words:
                    if abs(w["top"] - top) > 3 or not is_int(w["text"]) \
                            or w["x0"] < LABEL_X_MAX:
                        continue
                    c = (w["x0"] + w["x1"]) / 2
                    j = min(range(m), key=lambda i: abs(centers[i] - c))
                    if abs(centers[j] - c) > 15:
                        far.append(w["text"])
                        continue
                    colvals[j] = int(w["text"].replace(",", ""))
                if far:
                    warn(f"SoV contest p{page_no} {label!r}: value(s) {far} "
                         f"far from any column")
                band_rows.append((label, colvals, page_no))
            for gi, (party, title, _, _) in enumerate(groups):
                blk = blocks[gi]
                n_cand = len(blk) - 5
                g_lo, g_hi = splits[gi], splits[gi + 1]
                rows = []
                for label, colvals, rpage in band_rows:
                    if label == "Totals" or label.startswith("2ND CON"):
                        owned = True
                    else:
                        nz = [any(v != 0 for v in
                                  colvals[splits[g]:splits[g + 1]])
                              for g in range(ng)]
                        if any(nz):
                            owned = nz[gi]
                        else:
                            owned = any(k is not None
                                        and (label, k[0], k[1]) in by_key
                                        for k in options[gi])
                    if not owned:
                        continue
                    rows.append((label, colvals[g_lo:g_hi], rpage, n_cand))
                parsed.append((party, title, options[gi], blk, rows))

    # resolve ambiguous titles by which candidate office owns the rows
    sections = {}
    names_by_key = {}
    for party, title, opts, blk, rows in parsed:
        key = None
        if len(opts) == 1:
            key = opts[0]
        else:
            scores = [(sum(1 for r in rows
                           if (r[0], party, k[1]) in by_key), k)
                      for k in opts]
            best = max(sc for sc, _ in scores)
            winners = [k for sc, k in scores if sc == best]
            if best and len(winners) == 1:
                key = winners[0]
            else:
                warn(f"SoV contest: cannot resolve title {party}-{title!r} "
                     f"to one of {opts} "
                     f"(row matches {[(sc, k[1]) for sc, k in scores]})")
        if key is None:
            continue
        if key in names_by_key and names_by_key[key] != blk:
            warn(f"SoV contest {party}-{key[1]}: inconsistent header "
                 f"columns {blk} vs {names_by_key[key]}")
        names_by_key[key] = blk
        sections.setdefault(key, []).extend(rows)

    # ---------------- per-contest validation against the Summary blocks
    aggregate_rows = {}
    for (party, raw_office), rows in sections.items():
        n_cand = rows[0][3]
        data = [r for r in rows if r[0] != "Totals"]
        totals = next((r for r in rows if r[0] == "Totals"), None)
        if len({r[3] for r in rows}) != 1:
            warn(f"SoV contest {party}-{raw_office}: inconsistent column "
                 f"counts across pages: {sorted({r[3] for r in rows})}")
        for label, vals, page_no, n_cand in data:
            cands_vals = vals[:n_cand]
            write_in, cast_v = vals[n_cand], vals[n_cand + 1]
            over, under = vals[n_cand + 2], vals[n_cand + 3]
            ctotal = vals[n_cand + 4]
            if cands_vals and cast_v != sum(cands_vals) + write_in:
                warn(f"SoV contest p{page_no} {party} {raw_office} "
                     f"{label!r}: candidates {cands_vals} + write-in "
                     f"{write_in} != Total Votes Cast {cast_v}")
            if ctotal != cast_v + over + under:
                warn(f"SoV contest p{page_no} {party} {raw_office} "
                     f"{label!r}: contest total {ctotal} != {cast_v} + "
                     f"{over} + {under}")
            if label.startswith("2ND CON"):
                agg = aggregate_rows.setdefault(
                    (party, raw_office, label), {
                        "cands": [0] * n_cand, "write_in": 0, "cast": 0,
                        "over": 0, "under": 0, "contest_total": 0})
                for i, v in enumerate(cands_vals):
                    agg["cands"][i] += v
                for field, v in (("write_in", write_in), ("cast", cast_v),
                                 ("over", over), ("under", under),
                                 ("contest_total", ctotal)):
                    agg[field] += v
                continue
            c = by_key.get((label, party, raw_office))
            if c is None:
                # the print loses the trailing district digit on two
                # Lower Township Ward 2 rows; fall back to a whole-vector
                # match against the summary blocks
                base = re.sub(r"\s*District\s*$", "", label)
                matches = []
                for k, blk in by_key.items():
                    if k[1] != party or k[2] != raw_office:
                        continue
                    if re.sub(r"\s*District\s*\d+$", "", k[0]) != base:
                        continue
                    if (sorted(v for _, v in blk["candidates"])
                            == sorted(cands_vals)
                            and (blk["write_in"] or 0) == write_in
                            and blk["cast"] == cast_v
                            and blk["contest_total"] == ctotal):
                        matches.append(k)
                if len(matches) == 1:
                    c = by_key[matches[0]]
                else:
                    warn(f"SoV contest p{page_no}: row {label!r} not in "
                         f"Summary for {party} {raw_office}")
                    continue
            names = names_by_key[(party, raw_office)]
            for i, v in enumerate(cands_vals):
                match = next((cv for cn, cv in c["candidates"]
                              if norm_toks(cn) == norm_toks(names[i])), None)
                if match is None:
                    warn(f"SoV contest p{page_no} {label}: candidate "
                         f"{names[i]!r} not among Summary "
                         f"{[cn for cn, _ in c['candidates']]}")
                    continue
                if match != v:
                    warn(f"SoV contest p{page_no} {label} {party} "
                         f"{raw_office}: {names[i]} {v} vs Summary {match}")
            if write_in != (c["write_in"] or 0):
                warn(f"SoV contest p{page_no} {label} {party} {raw_office}: "
                     f"write-in {write_in} vs Summary {c['write_in']}")
            if cast_v != c["cast"]:
                warn(f"SoV contest p{page_no} {label} {party} {raw_office}: "
                     f"Total Votes Cast {cast_v} vs Summary {c['cast']}")
            if ctotal != c["contest_total"]:
                warn(f"SoV contest p{page_no} {label} {party} {raw_office}: "
                     f"Contest Total {ctotal} vs Summary "
                     f"{c['contest_total']}")
        if totals is None:
            warn(f"SoV contest {party}-{raw_office}: no Totals row")
            continue
        col_names = names_by_key[(party, raw_office)]
        for i in range(n_cand):
            sum_v = sum(r[1][i] for r in data)
            if sum_v != totals[1][i]:
                warn(f"SoV contest {party} {raw_office} column "
                     f"{col_names[i]}: sum {sum_v} != Totals {totals[1][i]}")
        for field, i in (("write_in", n_cand), ("cast", n_cand + 1),
                         ("over", n_cand + 2), ("under", n_cand + 3),
                         ("contest_total", n_cand + 4)):
            sum_v = sum(r[1][i] for r in data)
            if sum_v != totals[1][i]:
                warn(f"SoV contest {party} {raw_office} {field}: sum "
                     f"{sum_v} != Totals {totals[1][i]}")
    return aggregate_rows, names_by_key


def line_text(line_words):
    return " ".join(w["text"] for w in line_words)


# --------------------------------------------------------------- crosscheck

def crosscheck(contests, aggregates, names_by_key):
    """Compare federal precinct sums against the official county file. The
    official file has no write-in rows, so write-in sums are reported as
    information; candidate deltas must be explained by the SoV aggregate
    ('2ND CON ...') rows or they are mismatches."""
    official = {}
    with open(COUNTY_CSV, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["county"] != "Cape May" or row["office"] not in (
                    "U.S. Senate", "U.S. House"):
                continue
            key = (row["office"], row["district"], row["party"],
                   norm(row["candidate"]))
            official[key] = official.get(key, 0) + int(row["votes"])
    party_names = {"REP": "Republican", "DEM": "Democratic"}
    mine = {}
    for c in contests:
        office = office_name(c["raw_office"])
        if office not in ("U.S. Senate", "U.S. House"):
            continue
        party = party_names[c["party"]]
        dist = US_HOUSE_DISTRICT if office == "U.S. House" else ""
        for name, votes in c["candidates"]:
            if name == "No Petition Filed":
                continue
            key = (office, dist, party, norm(name))
            mine[key] = mine.get(key, 0) + votes
        key = (office, dist, party, "write-ins")
        mine[key] = mine.get(key, 0) + (c["write_in"] or 0)
    agg_deltas = {}
    for (party_token, raw_office, _), agg in aggregates.items():
        office = office_name(raw_office)
        if office not in ("U.S. Senate", "U.S. House"):
            continue
        party = party_names[party_token]
        dist = US_HOUSE_DISTRICT if office == "U.S. House" else ""
        names = names_by_key[(party_token, raw_office)]
        for i, v in enumerate(agg["cands"]):
            if v:
                key = (office, dist, party, norm(names[i]))
                agg_deltas[key] = agg_deltas.get(key, 0) + v
        key = (office, dist, party, "write-ins")
        if agg["write_in"]:
            agg_deltas[key] = agg_deltas.get(key, 0) + agg["write_in"]
    n_bad = 0
    for key in sorted(set(official) | set(mine), key=repr):
        o, m = official.get(key, 0), mine.get(key, 0)
        if o == m:
            continue
        agg = agg_deltas.get(key, 0)
        if key[3] == "write-ins" and key not in official:
            print(f"  crosscheck note {key[0]} {key[2]} {key[3]}: precinct "
                  f"sum {m}; official county file has no write-in row")
            continue
        if o == m + agg and o:
            print(f"  crosscheck note {key[2]} {key[3]}: precinct sum {m} "
                  f"vs official {o}; delta {o - m} explained by the "
                  f"'2ND CON ...' aggregate rows")
        else:
            warn(f"crosscheck {key[0]} {key[2]} {key[3]}: precinct sum {m} "
                 f"vs official {o} (aggregate rows account for {agg})")
            n_bad += 1
    return n_bad


# ---------------------------------------------------------------- write CSV

OFFICE_RANK = {"U.S. Senate": 0, "U.S. House": 1}


def write_csv(contests, stats):
    contests = [c for c in contests
                if not c["precinct"].startswith("2ND CON")]

    def sort_key(c):
        office = office_name(c["raw_office"])
        dist_n = int(re.search(r"(\d+)$", c["precinct"]).group(1))
        return (OFFICE_RANK.get(office, 2), office, c["precinct"], dist_n,
                0 if c["party"] == "REP" else 1)
    contests_sorted = sorted(contests, key=sort_key)
    seen = set()
    for c in contests_sorted:
        k = (c["precinct"], office_name(c["raw_office"]), c["party"])
        if k in seen:
            raise ValueError(f"duplicate contest block: {k}")
        seen.add(k)
    rows = []
    for label in sorted(stats):
        if label.startswith("2ND CON"):
            continue  # Dominion aggregate pseudo-precincts
        s = stats[label]
        rows.append(["Cape May", label, "Registered Voters", "", "", "",
                     s["reg_total"]])
        rows.append(["Cape May", label, "Ballots Cast", "", "", "",
                     s["cast_total"]])
        rows.append(["Cape May", label, "Blank Ballots Cast", "", "", "",
                     s["cast_blank"]])
    n_contest = 0
    for c in contests_sorted:
        office = office_name(c["raw_office"])
        district = US_HOUSE_DISTRICT if office == "U.S. House" else ""
        for name, votes in c["candidates"]:
            if name == "No Petition Filed":
                continue
            rows.append(["Cape May", c["precinct"], office, district,
                         c["party"], name, votes])
            n_contest += 1
        rows.append(["Cape May", c["precinct"], office, district,
                     c["party"], "Write-ins", c["write_in"] or 0])
        n_contest += 1
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["county", "precinct", "office", "district", "party",
                         "candidate", "votes"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT}")
    print(f"  ({len(stats)} precincts x 3 pseudo-rows + {n_contest} contest "
          f"rows)")


# --------------------------------------------------------------------- main

def main():
    summary_stats, contests = parse_summary()
    n_bad = validate_summary(summary_stats, contests)
    print(f"Summary: {len(summary_stats)} precincts, {len(contests)} "
          f"contest blocks, {n_bad} validation problems")
    with pdfplumber.open(STATEMENT_PDF) as pdf:
        aggregates, _ = parse_statement_stats(pdf, summary_stats)
        agg_rows, names_by_key = parse_statement_contests(pdf, contests)
    n_x = crosscheck(contests, agg_rows, names_by_key)
    for w in warnings:
        print("WARN:", w)
    if not warnings:
        print("no warnings")
    print(f"crosscheck mismatches: {n_x}")
    write_csv(contests, summary_stats)


if __name__ == "__main__":
    main()