"""Parse Camden County's 2026 primary "Canvasser" Dominion PDF.

Source: "Camden NJ 2026_Primary_Canvasser.pdf" (286 pages, landscape 792x612,
header says "2025 Primary Election" but the data is the 2026 primary). It has
five sections:

- p2-47   Summary Results Report (portrait): one block per contest with
          county-level candidate totals, Write-In Totals, Total Votes Cast,
          Overvotes, Undervotes, Contest Totals. Titles start with DEM/REP
          and may wrap onto a second line before "Vote For N".
- p48     Rejected Vote report (ignored).
- p50-61  District Report STATISTICS: 387 rows (districts + one Provisional
          row per town + "Federal/State CD1 VBM" + county Totals) with 9
          numeric columns (registered voters total/DEM/REP/NP, ballots cast
          total/DEM/REP/NP/blank).
- p62-188 Primary Election Table Report: the contest tables. A page holds
          1-4 contest blocks side by side, each anchored on its "VOTE FOR N"
          line; a block's columns are its candidates plus a rotated
          "Write-in / Totals" column. Contests run across consecutive pages
          (headers repeat, rows continue), and a contest wider than the page
          (committee races with up to 24 candidates) is split into column
          slices, each slice repeating all row labels and carrying its own
          Totals cell per column. Closed contests keep "ghost" headers on
          later pages of their group with no value tokens, so they produce
          no extractable block.
- p190+   write-in detail / by-municipality reports (ignored).

Merging: page blocks are merged per VOTE anchor while a contest stays open
(overlapping row labels mean a column slice, whose per-label values are
concatenated; disjoint labels mean a continuation page, whose rows are
appended); a Totals row closes the contest. After that, adjacent same-anchor
contests with identical label sets are re-joined as slices when the combined
Totals vector matches exactly one unmatched Summary Report contest. That
match supplies the canonical title and candidate names; per-column rotated
headers are matched by name where possible.

Every column's row sums must equal its Totals cell.

Output: 2026/counties/20260602__nj__primary__camden__precinct.csv with
Registered Voters and Ballots Cast pseudo rows per statistics label (the
county "Totals" statistics row is excluded). Row labels (including
"<Town> Provisional" and "Federal/State CD1 VBM") are kept verbatim,
following the 2024 Camden general precedent. Municipal offices keep their
printed wording with the municipality compressed to "<Town> <Boro|Twp|City>"
(e.g. "Mayor Gloucester City"); ward-specific contests get a " (Ward N)"
suffix. "NO PETITION FILED" candidates are dropped.
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
PDF = Path("/Users/dwillis/code/openelections-sources-nj/2026/primary/"
           "Camden NJ 2026_Primary_Canvasser.pdf")
OUTPUT = BASE / "2026/counties/20260602__nj__primary__camden__precinct.csv"
COUNTY_CSV = BASE / "2026/20260602__nj__primary__county.csv"

SUMMARY_PAGES = range(2, 48)
STATS_PAGES = range(50, 62)
CONTEST_PAGES = range(62, 189)

STAT_EDGES = [213.5, 252.4, 291.3, 330.2, 369.1, 408.0, 446.8, 485.7, 524.6]
STAT_KEYS = ["reg_total", "reg_dem", "reg_rep", "reg_np",
             "bc_total", "bc_dem", "bc_rep", "bc_np", "bc_blank"]

TOWNS = {
    "Audubon": "Boro", "Audubon Park": "Boro", "Barrington": "Boro",
    "Bellmawr": "Boro", "Berlin Boro": "Boro", "Berlin Twp": "Twp",
    "Berlin": "Boro", "Brooklawn": "Boro", "Camden": "City",
    "Cherry Hill": "Twp", "Chesilhurst": "Boro", "Clementon": "Boro",
    "Collingswood": "Boro", "Gibbsboro": "Boro", "Gloucester City": "City",
    "Gloucester": "Twp", "Haddon Twp": "Twp", "Haddon Heights": "Boro",
    "Haddon": "Twp", "Haddonfield": "Boro", "Hi-Nella": "Boro",
    "Laurel Springs": "Boro", "Lawnside": "Boro", "Lindenwold": "Boro",
    "Magnolia": "Boro", "Merchantville": "Boro", "Mt. Ephraim": "Boro",
    "Mt Ephraim": "Boro",
    "Oaklyn": "Boro", "Pennsauken": "Twp", "Pine Hill": "Boro",
    "Pine Valley": "Boro", "Runnemede": "Boro", "Somerdale": "Boro",
    "Stratford": "Boro", "Tavistock": "Boro", "Voorhees": "Twp",
    "Waterford Twp": "Twp", "Waterford": "Twp", "Winslow Twp": "Twp",
    "Winslow": "Twp", "Woodlynne": "Boro",
}


def is_int(text):
    return bool(re.fullmatch(r"\d{1,3}(,\d{3})*", text))


def as_int(text):
    return int(text.replace(",", ""))


def natkey(s):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]


def name_key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def to_lines(words, tol=3.0):
    """Cluster words into visual lines by top coordinate."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and w["top"] <= lines[-1]["top"] + tol:
            lines[-1]["words"].append(w)
        else:
            lines.append({"top": w["top"], "words": [w]})
    return lines


def line_text(line):
    return " ".join(w["text"] for w in sorted(line["words"], key=lambda w: w["x0"]))


# ---------------------------------------------------------------- summary

def parse_summary(pdf, problems):
    contests = []
    cur = None
    for pno in SUMMARY_PAGES:
        page = pdf.pages[pno - 1]
        lines = to_lines(page.extract_words())
        for line in lines:
            text = line_text(line)
            m = re.match(r"^(DEM|REP) ", text)
            if m and cur is None:
                cur = {"party": m.group(1), "title": text.strip(),
                       "vote_for": None, "candidates": [], "writeins": None,
                       "tvc": None, "over": None, "under": None,
                       "contest_total": None}
                continue
            if cur is None:
                continue
            if re.match(r"^Vote For (\d+)$", text):
                cur["vote_for"] = int(text.split()[-1])
                continue
            label = " ".join(w["text"] for w in line["words"] if w["x0"] < 160)
            vals = [w["text"] for w in line["words"]
                    if is_int(w["text"]) and w["x1"] > 160]
            val = as_int(vals[0]) if vals else None
            if label.startswith("Write-In Totals"):
                cur["writeins"] = val
            elif label.startswith("Total Votes Cast"):
                cur["tvc"] = val
            elif label.startswith("Overvotes"):
                cur["over"] = val
            elif label.startswith("Undervotes"):
                cur["under"] = val
            elif label.startswith("Contest Totals"):
                cur["contest_total"] = val
            elif label.startswith("Precincts Reporting"):
                if cur["vote_for"] is None:
                    problems.append("summary p%d: %r has no Vote For"
                                    % (pno, cur["title"]))
                contests.append(cur)
                cur = None
            elif val is not None:
                cur["candidates"].append((label.strip(), val))
            elif not label.startswith("TOTAL") and label.strip():
                # wrapped title continuation line
                cur["title"] += " " + label.strip()
    if cur is not None:
        problems.append("summary: contest never closed: %s" % cur["title"])
    return contests


# -------------------------------------------------------------- statistics

def parse_statistics(pdf, problems):
    stats = {}
    for pno in STATS_PAGES:
        page = pdf.pages[pno - 1]
        words = [w for w in page.extract_words() if w["x0"] >= 40 and w["top"] <= 550]
        for line in to_lines(words):
            lab_words = [w for w in line["words"] if 44 <= w["x0"] and w["x1"] < 180]
            nums = [w for w in line["words"]
                    if is_int(w["text"]) and w["x0"] > 180]
            if not lab_words or not nums:
                continue
            label = " ".join(w["text"] for w in lab_words)
            vals = {}
            for w in nums:
                for i, edge in enumerate(STAT_EDGES):
                    if abs(w["x1"] - edge) <= 6:
                        vals[i] = w["text"]
                        break
                else:
                    problems.append("stats p%d: stray number %r in %r"
                                    % (pno, w["text"], label))
            if len(vals) != len(STAT_EDGES):
                problems.append("stats p%d: %r has %d of 9 values"
                                % (pno, label, len(vals)))
                continue
            if label in stats:
                problems.append("stats: duplicate label %r" % label)
            stats[label] = dict(zip(STAT_KEYS,
                                    (as_int(vals[i]) for i in range(9))))
    return stats


# ------------------------------------------------------------ contest pages

def cluster_edges(values, gap=6.0):
    edges = []
    for v in sorted(values):
        if edges and v - edges[-1][-1] <= gap:
            edges[-1].append(v)
        else:
            edges.append([v])
    return [sum(e) / len(e) for e in edges]


def clean_title_word(text):
    """Undo Dominion word fusions in block titles."""
    text = re.sub(r"(DEM|REP)$", "", text)          # "TownshipDEM"
    text = re.sub(r"(County)(Member)", r"\1 \2", text)  # "CountyMember"
    text = re.sub(r"(County)(Members)", r"\1 \2", text)
    return text


def page_blocks(page, pno, problems):
    """Extract contest blocks (with data rows) from one contest-table page.

    A page holds 1-4 contest blocks side by side. Block boundaries are the
    rotated "Write-in" columns: every contest block ends with one (except
    pre-write-in column slices of oversized contests, which have none).
    """
    words = [w for w in page.extract_words(extra_attrs=["upright"])
             if w["x0"] >= 40 and w["top"] <= 550]
    lines = to_lines(words)
    # data rows: label words on the left, numeric values in the table area
    rows = []
    for line in lines:
        lab = [w for w in line["words"] if 44 <= w["x0"] and w["x1"] < 172]
        nums = [w for w in line["words"] if is_int(w["text"]) and w["x0"] > 172]
        if lab and nums:
            rows.append({"label": " ".join(w["text"] for w in lab),
                         "top": line["top"], "nums": nums})
    if not rows:
        return []
    data_top = rows[0]["top"]

    all_nums = [w for line in lines for w in line["words"]
                if is_int(w["text"]) and w["x0"] > 172
                and w["top"] >= data_top - 4]
    edges = cluster_edges([w["x1"] for w in all_nums])

    # write-in columns: any rotated "Write-in" word above the data
    wi_bounds = [w["x1"] for w in words if not w["upright"]
                 and w["text"].startswith("Write-in") and w["top"] < data_top]

    # split columns into blocks at write-in columns
    groups, cur = [], []
    for e in edges:
        cur.append(e)
        if any(abs(b - e) <= 10 for b in wi_bounds):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    blocks = []
    for gi, col_edges in enumerate(groups):
        cols, wi_cids = [], set()
        for e in col_edges:
            cid = (pno, gi, len(cols))
            cols.append(cid)
            if any(abs(b - e) <= 10 for b in wi_bounds):
                wi_cids.add(cid)
        # rotated candidate header names, per column (reading order: the
        # right-hand vertical line first, then words top-to-bottom)
        rot = [w for w in words if not w["upright"]
               and not w["text"].startswith("Write-in")
               and w["text"] != "Totals" and w["top"] < data_top]
        names = {}
        for e in col_edges:
            mine = [w for w in rot if abs(w["x0"] - e) <= 20]
            if not mine:
                names[(pno, gi, len(names))] = ""
                continue
            vlines = []
            for w in sorted(mine, key=lambda w: (-w["x0"], w["top"])):
                if vlines and abs(w["x0"] - vlines[-1][0]) <= 3:
                    vlines[-1][1].append(w["text"])
                else:
                    vlines.append([w["x0"], [w["text"]]])
            names[(pno, gi, len(names))] = " ".join(
                " ".join(ws) for _, ws in vlines)
        # rough title for problem messages only
        span_lo, span_hi = col_edges[0] - 45, col_edges[-1] + 10
        hdr = [w for w in words if w["upright"] and 85 <= w["top"] < data_top - 2
               and span_lo <= w["x0"] <= span_hi]
        title_words = [clean_title_word(w["text"]) for w in hdr
                       if w["text"] not in ("VOTE", "FOR", "DEM", "REP")
                       and not re.fullmatch(r"\d+", w["text"])]
        title = " ".join(t for t in title_words if t).strip()
        sig = tuple(round(e, 1) for e in col_edges)
        out_rows = []
        for row in rows:
            vals = {}
            for cid, e in zip(cols, col_edges):
                cands = [w for w in row["nums"]
                         if abs(w["x1"] - e) <= 6
                         and row["top"] - 4 <= w["top"] <= row["top"] + 7]
                if len(cands) > 1:
                    problems.append("p%d: multiple tokens for col %.0f in %r"
                                    % (pno, e, row["label"]))
                vals[cid] = as_int(cands[0]["text"]) if cands else None
            if all(v is None for v in vals.values()):
                continue  # a row belonging to a neighbouring contest
            out_rows.append((row["label"], vals))
        blk = {"title": title, "sig": sig, "cols": cols,
               "wi_cids": wi_cids, "names": names, "rows": out_rows,
               "page": pno, "totals": None}
        for label, vals in out_rows:
            if label == "Totals":
                blk["totals"] = vals
        blocks.append(blk)
    return blocks


def merge_blocks(blocks, problems):
    """Merge page blocks into contests.

    A contest occupies one table slot: its leftmost column prints at the
    same x on every page it spans, so blocks are matched to open contests
    by leftmost column edge (page-contiguous). Overlapping row labels mean
    a column slice (its columns are new; per-label values concatenated);
    disjoint labels mean a continuation page (rows appended, columns
    remapped). A Totals row closes the contest. Column slices of oversized
    contests arrive after their predecessor closed and are re-joined by
    repair_slices below.
    """
    contests = []
    open_by_left = {}
    for blk in blocks:
        left = round(blk["sig"][0], 1)
        best = open_by_left.get(left)
        # no page-gap staleness test: some contests (e.g. Woodlynne's Male
        # Members of County Committee) print values only on the first and
        # last pages of their group, with ghost pages in between
        if best is None:
            best = {"title": blk["title"], "sig": blk["sig"], "cols": [],
                    "wi": [], "names": {}, "rows": [], "totals": [],
                    "pages": [], "label_set": set()}
            contests.append(best)
            open_by_left[left] = best
        is_new = not best["pages"]
        best["pages"].append(blk["page"])
        if is_new:
            best["cols"] = list(blk["cols"])
            best["wi"] = [cid in blk["wi_cids"] for cid in blk["cols"]]
            best["names"] = dict(blk["names"])
        labels = [r[0] for r in blk["rows"]]
        if set(labels) & best["label_set"]:
            # column slice: its columns are new; concatenate per-label values
            best["cols"].extend(blk["cols"])
            best["wi"].extend(cid in blk["wi_cids"] for cid in blk["cols"])
            for i, name in blk["names"].items():
                best["names"][(blk["page"],) + i[1:]] = name
            by_label = {r[0]: r[1] for r in best["rows"]}
            for label, vals in blk["rows"]:
                if label not in by_label:
                    problems.append("slice row %r missing for %s (%s)"
                                    % (label, best["title"], best["pages"]))
                    continue
                by_label[label].update(vals)
            if blk["totals"] is not None:
                best["totals"].extend(blk["totals"][cid] for cid in blk["cols"])
                open_by_left.pop(left, None)
        else:
            # continuation page: same columns (remap block cids), new rows.
            # A continuation block may carry MORE columns than the contest so
            # far (a write-in column whose values first print on a later page),
            # so extend rather than truncate.
            if len(blk["cols"]) > len(best["cols"]):
                old_n = len(best["cols"])
                best["cols"].extend(blk["cols"][old_n:])
                best["wi"].extend(cid in blk["wi_cids"]
                                  for cid in blk["cols"][old_n:])
                # adopt this block's rotated names for the new columns
                for i in range(old_n, len(blk["cols"])):
                    cid = best["cols"][i]
                    if not best["names"].get(cid):
                        for nkey, name in blk["names"].items():
                            if nkey[2] == i:
                                best["names"][cid] = name
                                break
            elif len(blk["cols"]) != len(best["cols"]):
                problems.append("continuation column mismatch for %s (%s): %d vs %d"
                                % (best["title"], best["pages"],
                                   len(blk["cols"]), len(best["cols"])))
            best["label_set"] |= set(labels)
            for label, vals in blk["rows"]:
                newvals = {best["cols"][i]: vals[cid]
                           for i, cid in enumerate(blk["cols"]) if cid in vals}
                best["rows"].append((label, newvals))
            for nkey, name in blk["names"].items():
                idx = nkey[2]
                cid = best["cols"][idx] if idx < len(best["cols"]) else None
                if cid is not None and not best["names"].get(cid):
                    best["names"][cid] = name
            if blk["totals"] is not None:
                best["totals"] = [blk["totals"][cid] for cid in blk["cols"]]
                open_by_left.pop(left, None)
    return contests


def repair_slices(contests, summary, problems):
    """Re-join adjacent same-anchor column-slice contests whose combined
    Totals vector matches exactly one unmatched summary contest."""
    unmatched = set(id(sc) for sc in summary)
    def vec_match(party_cols, total_vec):
        out = []
        for sc in summary:
            if id(sc) not in unmatched:
                continue
            n = len(sc["candidates"]) + 1
            want = sorted([v for _, v in sc["candidates"]]
                          + ([sc["writeins"] or 0]
                             if sc["writeins"] is not None else []))
            if n == party_cols and want == total_vec:
                out.append(sc)
        return out
    changed = True
    while changed:
        changed = False
        for i in range(len(contests)):
            a = contests[i]
            if not a["totals"]:
                continue
            for j in range(i + 1, len(contests)):
                b = contests[j]
                if (a["sig"][0] != b["sig"][0] or not b["totals"]
                        or a["label_set"] != b["label_set"]
                        or b["pages"][0] != a["pages"][-1] + 1):
                    continue
                merged_cols = a["cols"] + b["cols"]
                merged_totals = a["totals"] + b["totals"]
                matches = vec_match(len(merged_cols),
                                    sorted(t if t is not None else -1
                                           for t in merged_totals))
                if len(matches) != 1:
                    continue
                a["cols"] = merged_cols
                a["totals"] = merged_totals
                a["wi"] = a["wi"] + b["wi"]
                for cid, name in b["names"].items():
                    if not a["names"].get(cid):
                        a["names"][cid] = name
                a["pages"] = a["pages"] + b["pages"]
                by_label = {r[0]: r[1] for r in a["rows"]}
                for label, vals in b["rows"]:
                    by_label[label].update(vals)
                contests.pop(j)
                unmatched.discard(id(matches[0]))
                a["summary"] = matches[0]
                changed = True
                break
            if changed:
                break
    return unmatched


# ------------------------------------------------------------- main

def to_office(title, problems):
    t = re.sub(r"^(DEM|REP)\s+", "", title).strip()
    m = re.search(r"House of Representatives - CD (\d+)$", t)
    if m:
        return "U.S. House", m.group(1)
    if t == "United States Senator":
        return "U.S. Senate", ""
    if t == "Members of the Board of County Commissioners":
        return "Members of the Board of County Commissioners", ""
    if t in ("Sheriff", "County Clerk", "County Surrogate"):
        return t, ""
    # summary prints some titles without a " - " separator, e.g.
    # "Members of Council Brooklawn Borough"
    m = re.search(r"\b(Brooklawn|Gloucester City|Tavistock|Woodlynne) "
                  r"(Borough|Township|City)$", t)
    if m:
        suffix = {"Borough": "Boro", "Township": "Twp", "City": "City"}[m.group(2)]
        return "%s %s" % (t[:m.start(2) - 1].strip(), suffix), ""
    if " - " in t:
        left, right = t.rsplit(" - ", 1)
        wm = re.search(r"\s+W(\d+)$", right)
        ward = wm.group(1) if wm else None
        place = right[:wm.start()] if wm else right
        suffix = None
        for name in sorted(TOWNS, key=len, reverse=True):
            if place == name:
                suffix = TOWNS[name]
                break
            if place.startswith(name + " "):
                suffix = TOWNS[name]
                place = name
                break
        if suffix is None:
            problems.append("unmapped municipality in %r" % t)
            return t, ""
        name = "%s %s" % (left, place)
        if not name.endswith(" " + suffix):
            name += " " + suffix
        if ward:
            name += " (Ward %s)" % ward
        return name, ""
    problems.append("unmapped office title: %r" % t)
    return t, ""


def main():
    problems = []
    pdf = pdfplumber.open(str(PDF))
    summary = parse_summary(pdf, problems)
    stats = parse_statistics(pdf, problems)

    blocks = []
    for pno in CONTEST_PAGES:
        blocks.extend(page_blocks(pdf.pages[pno - 1], pno, problems))
    contests = merge_blocks(blocks, problems)
    unmatched = repair_slices(contests, summary, problems)

    # ---- match every contest to its Summary Report block ----
    by_vec = {}
    for sc in summary:
        vec = tuple(sorted([v for _, v in sc["candidates"]]
                           + ([sc["writeins"] or 0]
                              if sc["writeins"] is not None else [])))
        by_vec.setdefault((len(sc["candidates"]) + 1, vec), []).append(sc)

    for cont in contests:
        tag = "%s (p%s)" % (cont["title"] or "<untitled>", cont["pages"])
        if not cont["totals"]:
            problems.append("no Totals row: %s" % tag)
            continue
        if len(cont["totals"]) != len(cont["cols"]):
            problems.append("Totals %d values vs %d columns: %s"
                            % (len(cont["totals"]), len(cont["cols"]), tag))
            continue
        key = (len(cont["cols"]), tuple(sorted(t if t is not None else -1 for t in cont["totals"])))
        matches = by_vec.get(key, [])
        if len(matches) > 1:
            # disambiguate with the rotated candidate header names
            def score(sc):
                want = {name_key(n) for n, _ in sc["candidates"]}
                got = 0
                for ci, edge in enumerate(cont["cols"]):
                    if cont["wi"][ci]:
                        continue
                    rk = name_key(cont["names"].get(edge, ""))
                    if not rk:
                        continue
                    if any(rk == wk or rk.startswith(wk) or wk.startswith(rk)
                           for wk in want):
                        got += 1
                return got
            best_score = max(score(sc) for sc in matches)
            matches = [sc for sc in matches if score(sc) == best_score]
        if len(matches) > 1:
            # disambiguate with the block's horizontal title (carries the
            # town, e.g. "Mayor - Lawnside"); every remaining tie below is
            # between all-"NO PETITION FILED" contests whose rotated names
            # cannot tell them apart
            def title_score(sc):
                want = {w.lower() for w in re.findall(r"[A-Za-z]+", sc["title"])}
                want -= {"dem", "rep"}
                have = {w.lower() for w in re.findall(r"[A-Za-z]+", cont["title"])}
                have |= {w.lower() for label, _ in cont["rows"]
                         for w in re.findall(r"[A-Za-z]+", label)}
                have -= {"dem", "rep", "provisional"}
                if not have:
                    return 0.0
                return len(have & want) / len(have)
            best_score = max(title_score(sc) for sc in matches)
            matches = [sc for sc in matches if title_score(sc) == best_score]
        if len(matches) > 1:
            # All-"NO PETITION FILED" rosters tie across summary blocks with
            # identical candidate lists; the NO PETITION columns are dropped
            # from the output and the write-in total is identical, so any
            # match yields the same rows.
            def roster(sc):
                return sorted(name_key(n) for n, _ in sc["candidates"])
            if (all(t == 0 for t in cont["totals"])
                    and len({tuple(roster(sc)) for sc in matches}) == 1
                    and all(n == name_key("NO PETITION FILED")
                            for n in roster(matches[0]))):
                matches = matches[:1]
        if len(matches) != 1:
            problems.append("%s: %d summary matches by totals vector"
                            % (tag, len(matches)))
            continue
        sc = matches[0]
        if id(sc) in unmatched:
            unmatched.discard(id(sc))
        cont["summary"] = sc
        # per-column row sums must equal the Totals cell
        for ci, edge in enumerate(cont["cols"]):
            s, missing = 0, 0
            for label, vals in cont["rows"]:
                if label == "Totals":
                    continue
                v = vals.get(edge)
                if v is None:
                    missing += 1
                else:
                    s += v
            if missing:
                problems.append("%s: %d missing cells in column %d" % (tag, missing, ci))
            if s != cont["totals"][ci]:
                problems.append("%s: column %d sums to %d vs Totals %s"
                                % (tag, ci, s, cont["totals"][ci]))

    # ---- build per-contest column assignments ----
    for cont in contests:
        if "summary" not in cont:
            continue
        sc = cont["summary"]
        # multi-seat offices can list "NO PETITION FILED" once per seat, so
        # candidates are matched with a use-count rather than a used set
        pool = list(sc["candidates"])
        assignment = {}
        for ci, edge in enumerate(cont["cols"]):
            if cont["wi"][ci]:
                assignment[edge] = "Write-ins"
                continue
            rk = name_key(cont["names"].get(edge, ""))
            pick = None
            if rk:
                for i, (n, _) in enumerate(pool):
                    wk = name_key(n)
                    if wk and (rk == wk or rk.startswith(wk) or wk.startswith(rk)):
                        pick = i
                        break
            if pick is None:
                v = cont["totals"][ci]
                for i, (n, sv) in enumerate(pool):
                    if name_key(n) and sv == v:
                        pick = i
                        break
            if pick is None:
                problems.append("column with total %s matches no candidate in %r (p%s)"
                                % (cont["totals"][ci], sc["title"], cont["pages"]))
                continue
            assignment[edge] = pool[pick][0]
            pool.pop(pick)
        if sorted(assignment.values()) != sorted(
                [n for n, _ in sc["candidates"]] + ["Write-ins"]):
            problems.append("column assignment mismatch for %r (p%s)"
                            % (sc["title"], cont["pages"]))
            continue
        cont["assignment"] = assignment
        if sorted(assignment.values()) != sorted(
                [n for n, _ in sc["candidates"]] + ["Write-ins"]):
            problems.append("column assignment mismatch for %r (p%s)"
                            % (sc["title"], cont["pages"]))
            continue
        cont["assignment"] = assignment

    # ---- crosscheck vs official county file ----
    official = {}
    with open(COUNTY_CSV, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["county"] != "Camden" or row["office"] not in ("U.S. Senate", "U.S. House"):
                continue
            key = (row["office"], row["district"], name_key(row["candidate"]))
            official[key] = official.get(key, 0) + int(row["votes"])
    sums = defaultdict(int)
    for cont in contests:
        if "assignment" not in cont:
            continue
        office, district = to_office(cont["summary"]["title"], problems)
        if office not in ("U.S. Senate", "U.S. House"):
            continue
        for label, vals in cont["rows"]:
            if label == "Totals":
                continue
            for edge, name in cont["assignment"].items():
                v = vals.get(edge)
                if v:
                    sums[(office, district, name_key(name))] += v
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
        if "assignment" not in cont:
            continue
        office, district = to_office(cont["summary"]["title"], problems)
        for label, vals in cont["rows"]:
            if label == "Totals":
                continue
            for edge, cand in cont["assignment"].items():
                if cand.lower() == "no petition filed":
                    continue
                v = vals.get(edge)
                out.append({"precinct": label, "office": office,
                            "district": district, "party": cont["summary"]["party"],
                            "candidate": cand if cand != "Write-ins" else "Write-ins",
                            "votes": v if v else 0})

    contest_precincts = {r["precinct"] for r in out}
    precincts = sorted((l for l in stats if l != "Totals"), key=natkey)
    for label in precincts:
        st = stats[label]
        reg, bc = st["reg_total"], st["bc_total"]
        dem_rep = st["bc_dem"] + st["bc_rep"] + st["bc_np"]
        if dem_rep > bc:
            problems.append("Ballots Cast %d < DEM+REP+NP %d in %r"
                            % (bc, dem_rep, label))
        out.append({"precinct": label, "office": "Registered Voters",
                    "district": "", "party": "", "candidate": "", "votes": reg})
        out.append({"precinct": label, "office": "Ballots Cast",
                    "district": "", "party": "", "candidate": "", "votes": bc})
    for label in sorted(contest_precincts - set(stats)):
        problems.append("contest row label %r has no statistics row" % label)
    for label in sorted(set(stats) - contest_precincts - {"Totals"}):
        problems.append("statistics label %r has no contest rows" % label)

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
            wtr.writerow(["Camden", r["precinct"], r["office"], r["district"],
                          r["party"], r["candidate"], r["votes"]])

    print("wrote %d rows to %s" % (len(out), OUTPUT))
    print("summary contests: %d, table contests: %d, precincts: %d (stats %d)"
          % (len(summary), len(contests),
             len({r["precinct"] for r in out}), len(stats)))
    print("problems: %d" % len(problems))
    for p in problems:
        print("  ", p)


if __name__ == "__main__":
    sys.exit(main())