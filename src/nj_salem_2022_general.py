"""Parse Salem County's 2022 general election precinct results.

Source: "Salem NJ Statement-Of-Votes-Cast-min-1.pdf" (823 pages), an ES&S
"Statement of Votes Cast" report. Contests appear sequentially; a
contest's name prints once on the first page of its block as "<CONTEST
NAME> (Vote for N)"; later pages carry no name, so the contest tracks
the last header seen by page order.

Each page is a table (up to two side by side) over THE SAME list of
precincts, per vote type: a broad label cell, optional stat cells (Times
Cast / Registered Voters / Undervotes / Overvotes) and one value cell
per candidate. Candidate headers print rotated; the glyphs read
correctly in ascending-y order ("Times Cast", "JEFF VAN DREW" + "(REP)"
side cluster), but some exports use the mirrored orientation, so the
orientation is voted per page against the known stat labels. Vertical
rules define the cells; values are assigned by geometry, never by
order. "****" cells are suppressed and skipped.

Row types (first token): a "<Precinct> (Ward n )District n" header row,
then Early Voting / Election Day / Mail-In / Provisional / Emergency /
Federal / Total. The 'Total' rows carry the per-precinct candidate
totals that get published; per contest/precinct the candidate Total
cells must satisfy sum(candidates) = Times Cast * vote_for - undervotes
- overvotes; a dozen rows fall a few votes short because the county
suppressed individual cells with "****". Zero precincts (contest does
not involve that precinct) are omitted.

Output: 2022/20221108__nj__general__salem__precinct.csv with Registered
Voters, Ballots Cast, candidates, Write-ins rows.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
PDF = (Path("/Users/dwillis/code/openelections-sources-nj/2022/") /
       "Salem NJ Statement-Of-Votes-Cast-min-1.pdf")
OUTPUT = BASE / "2022/20221108__nj__general__salem__precinct.csv"

CONTEST_RE = re.compile(r"^([A-Z][A-Z0-9 ./\'&,-]+) ?\(Vote for (\d+)\)$")
DISTRICT_RE = re.compile(
    r"^(?P<muni>[A-Za-z .\'-]+?) (Ward (?P<ward>\d+) )?"
    r"District (?P<dist>\d+)$")
VOTE_ROW = {"Early Voting": "EV", "Election Day": "ED", "Mail-In": "MI",
            "Provisional": "P", "Emergency": "EM", "Federal": "FED",
            "Total": "T"}
STAT_ROLES = {"Times Cast": "cast", "Registered Voters": "reg",
              "Undervotes": "under", "Overvotes": "over"}
NUM_RE = re.compile(r"^-?\d[\d,]*$")

# office labels: printed wording kept, with county/muni qualifiers
OFFICE_NAMES = {
    "UNITED STATES HOUSE OF REPRESENTATIVES": ("U.S. House", "2"),
    "SALEM COUNTY COMMISSIONERS": ("County Commissioner", ""),
    "ALLOWAY TOWNSHIP COMMITTEE": ("Township Committee Alloway Twp", ""),
    "CARNEYS POINT TOWNSHIP COMMITTEE":
        ("Township Committee Carneys Point Twp", ""),
    "ELMER BOROUGH COUNCIL": ("Borough Council Elmer", ""),
    "ELSINBORO TOWNSHIP COMMITTEE": ("Township Committee Elsinboro Twp",
                                     ""),
    "LOWER ALLOWAYS CREEK TOWNSHIP COMMITTEE":
        ("Township Committee Lower Alloways Creek Twp", ""),
    "MANNINGTON TOWNSHIP COMMITTEE": ("Township Committee Mannington Twp",
                                      ""),
    "OLDMANS TOWNSHIP COMMITTEE": ("Township Committee Oldmans Twp", ""),
    "PENNS GROVE BOROUGH COUNCIL": ("Borough Council Penns Grove", ""),
    "PENNSVILLE TOWNSHIP COMMITTEE":
        ("Township Committee Pennsville Twp", ""),
    "PILESGROVE TOWNSHIP COMMITTEE": ("Township Committee Pilesgrove Twp",
                                      ""),
    "PITTSGROVE TOWNSHIP COMMITTEE":
        ("Township Committee Pittsgrove Twp", ""),
    "QUINTON TOWNSHIP COMMITTEE": ("Township Committee Quinton Twp", ""),
    "SALEM CITY COUNCIL - EAST WARD":
        ("City Council Salem City (East Ward)", ""),
    "SALEM CITY COUNCIL - WEST WARD":
        ("City Council Salem City (West Ward)", ""),
    "SALEM CITY COUNCIL - WEST WARD 3 YR UNEXPIRED TERM":
        ("City Council Salem City (West Ward, 3-Yr Unexpired)", ""),
    "UPPER PITTSGROVE TOWNSHIP COMMITTEE":
        ("Township Committee Upper Pittsgrove Twp", ""),
    "WOODSTOWN BOROUGH COUNCIL": ("Borough Council Woodstown", ""),
    "ALLOWAY SCHOOL BOARD": ("School Board Alloway", ""),
    "CARNEYS POINT REGIONAL SCHOOL BOARD":
        ("School Board Carneys Point Regional", ""),
    "PITTSGROVE-ELMER SCHOOL BOARD": ("School Board Pittsgrove-Elmer", ""),
    "PITTSGROVE-ELMER SCHOOL BOARD 2 YEAR UNEXPIRED TERM":
        ("School Board Pittsgrove-Elmer 2-Yr Unexpired", ""),
    "PITTSGROVE-ELMER SCHOOL BOARD 1 YEAR UNEXPIRED TERM":
        ("School Board Pittsgrove-Elmer 1-Yr Unexpired", ""),
    "ELSINBORO SCHOOL BOARD": ("School Board Elsinboro", ""),
    "LOWER ALLOWAYS CREEK SCHOOL BOARD":
        ("School Board Lower Alloways Creek", ""),
    "MANNINGTON SCHOOL BOARD": ("School Board Mannington", ""),
    "OLDMANS SCHOOL BOARD": ("School Board Oldmans", ""),
    "PENNS GROVE REGIONAL SCHOOL BOARD":
        ("School Board Penns Grove Regional", ""),
    "PENNSVILLE SCHOOL BOARD": ("School Board Pennsville", ""),
    "PILESGROVE REGIONAL SCHOOL BOARD":
        ("School Board Pilesgrove Regional", ""),
    "QUINTON SCHOOL BOARD": ("School Board Quinton", ""),
    "SALEM CITY SCHOOL BOARD": ("School Board Salem City", ""),
    "UPPER PITTSGROVE SCHOOL BOARD":
        ("School Board Upper Pittsgrove", ""),
    "WOODSTOWN REGIONAL SCHOOL BOARD":
        ("School Board Woodstown Regional", ""),
    "SALEM CITY SCHOOL BOND PROPOSAL":
        ("Public Question Salem City School Bond", ""),
}


def cell_of(rules, x):
    for i in range(len(rules) - 1):
        if rules[i] - 0.6 <= x < rules[i + 1]:
            return i
    return None


def main():
    # contests: (start_page, header, vote_for)
    contests = []
    data = defaultdict(dict)    # (contest, muni, dist) -> {(kind,name): v}
    errors = []
    n_pages = 0
    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            if pno < 12:
                continue
            for l in (page.extract_text() or "").split("\n"):
                m = CONTEST_RE.match(l.strip())
                if m and (m.group(1).strip(), int(m.group(2))) not in [
                        (c[1], c[2]) for c in contests]:
                    contests.append((pno, m.group(1).strip(),
                                     int(m.group(2))))
    starts = [c[0] for c in contests]

    def contest_for(pageno):
        cur = None
        for start, contest, vf in contests:
            if start <= pageno:
                cur = (contest, vf)
        return cur

    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            if pno < 12:
                continue
            ct = contest_for(pno)
            if ct is None:
                errors.append(f"p{pno}: no contest yet")
                continue
            upright = page.filter(lambda o: o.get("upright", True))
            words = upright.extract_words()
            xs = sorted({round(l["x0"], 1) for l in page.lines
                         if abs(l["x0"] - l["x1"]) < 0.6 and
                         (l["bottom"] - l["top"]) >= 8})
            rules = []
            for x in xs:
                if rules and x - rules[-1] < 2:
                    continue
                rules.append(x)
            if len(rules) < 4:
                continue
            # cells: skip the wide label spans (> 70pt)
            cells = {}
            for i in range(len(rules) - 1):
                if rules[i + 1] - rules[i] > 70:
                    continue
                cells[i] = (rules[i], rules[i + 1])
            # rotated labels per cell index
            rot_cells = defaultdict(list)
            for c in page.chars:
                if c.get("upright", True):
                    continue
                idx = cell_of(rules, c["x0"] + 0.5)
                if idx is not None:
                    rot_cells[idx].append(c)
            n_stat_hits = 0
            labels = {}
            for idx, chs in rot_cells.items():
                lines_ = defaultdict(list)
                for c in chs:
                    lines_[round(c["x0"], 1)].append(c)
                pieces = []
                for x in sorted(lines_):
                    pieces.append("".join(
                        ch["text"] for ch in
                        sorted(lines_[x], key=lambda c: c["y0"])).strip())
                asc = " ".join(" ".join(pieces).split())
                rev = " ".join(p[::-1] for p in pieces)
                if rev in STAT_ROLES or rev.startswith(("Times Cast",
                                                        "Registered",
                                                        "Undervotes",
                                                        "Overvotes")):
                    # reversed orientation
                    n_stat_hits += -1
                    labels[idx] = rev
                else:
                    if asc in STAT_ROLES or asc.startswith(("Times Cast",
                                                            "Registered",
                                                            "Undervotes",
                                                            "Overvotes")):
                        n_stat_hits += 1
                    labels[idx] = asc
            stat_cells = {}
            cand_cells = {}
            for idx, label in labels.items():
                lbl = label.strip()
                role = None
                for key, r in STAT_ROLES.items():
                    if lbl.startswith(key):
                        role = r
                        break
                if lbl in ("Total Votes", "Votes Total", "slaV latoT",
                           "tsaC setoT") or lbl.startswith("Total Vote"):
                    stat_cells[idx] = "total"   # row-total column, unused
                elif role:
                    stat_cells[idx] = role
                elif "(" in lbl and ")" in lbl:
                    pm = re.match(r"^(.+?)\s*\((\w+)\)\s*$", lbl)
                    if pm:
                        cand_cells[idx] = (pm.group(1).strip(),
                                           pm.group(2))
                    else:
                        cand_cells[idx] = (lbl.strip(), "")
                else:
                    cand_cells[idx] = (lbl.strip(), "")
            if not cand_cells and not stat_cells:
                continue
            n_pages += 1
            # value cells sorted by x; the wide gap before a table's first
            # value cell bounds that table's label span
            vcells = sorted(
                [(cidx, c0, c1) for cidx, (c0, c1) in cells.items()
                 if cidx in cand_cells or cidx in stat_cells],
                key=lambda t: t[1])
            label_spans = []   # (x_start, x_end) per table
            prev_x1 = 0.0
            for cidx, c0, c1 in vcells:
                label_spans.append((prev_x1, c0 + 0.6))
                prev_x1 = c1
            def label_for(g):
                # the same row label appears once per table; use the
                # first label span that contains words
                for xs0, xe0 in label_spans:
                    out = [w for w in g if w["x0"] >= xs0 - 0.6 and
                           w["x1"] <= xe0 + 12]
                    if out:
                        return " ".join(w["text"] for w in out).strip()
                return ""
            # rows
            ws = sorted(words, key=lambda w: (w["top"], w["x0"]))
            groups = []
            curr = [ws[0]] if ws else []
            for w in ws[1:]:
                if w["top"] - curr[-1]["top"] <= 3.5:
                    curr.append(w)
                else:
                    groups.append(curr)
                    curr = [w]
            if curr:
                groups.append(curr)
            prec_key = None
            for g in groups:
                g = sorted(g, key=lambda w: w["x0"])
                label = label_for(g)
                if not label:
                    continue
                vm = DISTRICT_RE.match(label)
                if vm:
                    prec_key = (vm["muni"].strip(),
                                ("W" + vm["ward"] + " Dist " + vm["dist"])
                                if vm["ward"] else "Dist " + vm["dist"])
                    continue
                vcode = None
                for vt, code in VOTE_ROW.items():
                    if label.startswith(vt):
                        vcode = code
                        break
                if vcode is None or prec_key is None:
                    continue
                rec = data[(ct[0], prec_key[0], prec_key[1])]
                for w in g:
                    idx = cell_of(rules, w["x1"])
                    if not NUM_RE.match(w["text"]):
                        continue
                    if idx not in cand_cells and idx not in stat_cells:
                        continue
                    try:
                        v = int(w["text"].replace(",", ""))
                    except ValueError:
                        continue
                    if idx in cand_cells:
                        nm, party = cand_cells[idx]
                        nm = re.sub(r"\s+Qualified Write In$", "",
                                    " " + nm).strip()
                        if vcode == "T":
                            rec[f"c:{nm}"] = (v, party)
                        rec.setdefault("vtype:" + nm, {})[vcode] = v
                    else:
                        role = stat_cells[idx]
                        key = f"s:{role}"
                        if vcode == "T" or key not in rec:
                            rec[key] = v
    # validation: per (contest, precinct): sum(candidate Total values) =
    # Times Cast * vote_for - undervotes - overvotes
    for (contest, muni, dist), rec in data.items():
        vote_for = next((c[2] for c in contests if c[1] == contest), 1)
        cast = rec.get("s:cast")
        if not cast:
            continue
        cands = {k[2:]: v for k, v in rec.items() if k.startswith("c:")}
        csum = sum(v[0] or 0 for v in cands.values())
        slack = rec.get("s:under", 0) + rec.get("s:over", 0)
        missing_uo = ("s:under" not in rec or "s:over" not in rec) and \
            vote_for == 1
        expect = cast * vote_for - slack
        if csum != expect and not (csum < expect and missing_uo):
            errors.append(f"{contest} {muni} {dist}: candidate sum {csum} "
                          f"vs cast*vf - u/o {expect}")
    return data, contests, errors


def emit(data, contests, errors):
    out_rows = []
    stats_seen = set()
    n_zero = 0
    for (contest, muni, dist), rec in sorted(data.items(), key=lambda t:
                                             (contests.index(
        [c for c in contests if c[1] == t[0][0]][0]) if any(
        c[1] == t[0][0] for c in contests) else 0, t[0][1], t[0][2])):
        office, dist_no = OFFICE_NAMES.get(contest,
                                           (contest.title(), ""))
        cands = {k[2:]: v for k, v in rec.items() if k.startswith("c:")}
        any_votes = any(v for v, _ in cands.values())
        if not any_votes and not rec.get("s:cast"):
            n_zero += 1
            continue   # precinct not involved in this contest
        if (muni, dist) not in stats_seen:
            stats_seen.add((muni, dist))
            if rec.get("s:reg"):
                out_rows.append(["Salem", f"{muni} {dist}",
                                 "Registered Voters", "", "", "",
                                 rec["s:reg"]])
            if rec.get("s:cast"):
                out_rows.append(["Salem", f"{muni} {dist}", "Ballots Cast",
                                 "", "", "", rec["s:cast"]])
        for nm, (v, party) in sorted(cands.items()):
            out_rows.append(["Salem", f"{muni} {dist}", office, dist_no,
                             party, nm, v])
    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "party",
                    "candidate", "votes"])
        w.writerows(out_rows)
    print(f"rows {len(out_rows)}; zero skipped {n_zero}; errors "
          f"{len(errors)}")
    for e in errors[:12]:
        print("  ", e)
    return out_rows


if __name__ == "__main__":
    data, contests, errors = main()
    emit(data, contests, errors)
