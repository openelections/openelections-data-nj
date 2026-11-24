"""Parse Cumberland County's 2022 general election precinct results.

Source: "Cumberland NJ STATEMENT-OF-VOTE-BOOK.pdf" (113 pages), an ES&S
"Cumberland County District Canvass" report. Each contest's table is
printed once per suppression group: the same rows appear on several
consecutive pages, each page carrying a DIFFERENT set of candidate
columns (first page: machine candidates plus their immediate write-ins;
later pages: further write-in candidates). Page geometry is per page,
so candidate values are matched by CELL, and pages are merged per
(contest, row-label) keyed by CANDIDATE NAME (with max() across pages;
conflicting non-zero values are reported).

Candidate headers print rotated; each rotated line's glyphs are
upright=False and read correctly as reversed strings taken in
descending-x order ("WERD" + "NAV FFEJ - PER" -> "REP - JEFF VAN
DREW"). Banner lines ("1 Council-at-Large - Bridgeton") identify the
contest; "***" rows are suppressed cells and skipped.

District "Total" rows hold Election Day + VBM + Emergency votes; Early
Voting and Provisional votes float at the municipality level ("<muni>
EV Total" / "<muni> Prov Total" rows) and are published as
pseudo-precincts "<muni> - Early Voting" / "<muni> - Provisional".
Validation per contest and candidate: those sums must equal the county
"Contest Total" cell (except where a row was suppressed).
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
PDF = (Path("/Users/dwillis/code/openelections-sources-nj/2022/") /
       "Cumberland NJ STATEMENT-OF-VOTE-BOOK.pdf")
OUTPUT = BASE / "2022/20221108__nj__general__cumberland__precinct.csv"

HOUSE_RE = re.compile(r"Member of House of Representative[s]? - "
                      r"(\d+)(?:st|nd|rd|th)? Congressional")
BANNER_KEYWORD = re.compile(
    r"^(Member|Members|Mayor|Proposal|Council|City|Township|Borough|"
    r"Committee|Board)\b")
NUM_RE = re.compile(r"^-?\d[\d,\.]*%?$")
VTYPE_RE = re.compile(
    r"^(?P<base>.+?)\s+(?P<vtype>EV Total|Prov Total)$")
COUNTY_TOTAL_RE = re.compile(r"^Total - ")


def num(t):
    t = t.rstrip("%")
    v = float(t.replace(",", ""))
    iv = int(v)
    return iv if iv == v else v


def cell_of(rules, x):
    for i in range(len(rules) - 1):
        if rules[i] - 0.6 <= x < rules[i + 1]:
            return i
    return None


def rotated_cell_labels(page, rules):
    """Map cell index -> rotated header label (reversed-piece method)."""
    cells = defaultdict(list)
    for c in page.chars:
        if c.get("upright", True):
            continue
        idx = cell_of(rules, c["x0"] + 0.5)
        if idx is not None:
            cells[idx].append(c)
    out = {}
    for idx, chs in cells.items():
        lines = defaultdict(list)
        for c in chs:
            lines[round(c["x0"], 1)].append(c)
        pieces = ["".join(ch["text"] for ch in
                          sorted(lines[x], key=lambda c: c["y0"]))[::-1]
                  for x in sorted(lines, reverse=True)]
        out[idx] = " ".join(pieces).strip()
    return out


def parse_candidate(label):
    m = re.match(r"^([A-Z]{2,4})\s*-\s*(.+)$", label)
    if m:
        return " ".join(m.group(1).split()), " ".join(m.group(2).split())
    return "", " ".join(label.split())


def normalize_office(banner):
    text = re.sub(r"^\d+\s+", "", banner.strip())
    m = HOUSE_RE.search(text)
    if m:
        return ("U.S. House", m.group(1))
    text = re.sub(r"\s+", " ", text).strip()
    return ("U.S. Senate" if False else text, "")


def main():
    # acc[(contest,label)] = {'reg':v,'cast':v,'cand':{name:v}, 'kinds'}
    acc = defaultdict(dict)
    cand_party = {}   # contest -> {cand: party}
    cand_pages = defaultdict(set)   # (contest, cand) -> pages
    contest_total = defaultdict(lambda: defaultdict(float))
    errors = []
    contest = None
    contests = []
    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
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
            # banner markers
            timeline = []
            for i, w in enumerate(words):
                if w["x0"] > 200 or not w["text"].isdigit():
                    continue
                nxt = words[i + 1]["text"] if i + 1 < len(words) else ""
                if BANNER_KEYWORD.match(nxt):
                    timeline.append((w["top"], i))
            if timeline:
                contest = None
            # rows: cluster by top gaps
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
            # banner text: from digits word to end of its group
            banner_text = {}
            for y, wi in timeline:
                tgt = words[wi]
                grp = max((g for g in groups if any(w is tgt for w in g)),
                          key=len, default=None)
                if grp is None:
                    continue
                banner_text[y] = " ".join(
                    w["text"] for w in sorted(grp, key=lambda w: w["x0"])
                    if w["x0"] >= tgt["x0"])
            if len(timeline) > 1:
                errors.append(f"p{pno}: {len(timeline)} banner starts on "
                              f"one page")
            if len(timeline) == 1:
                contest = normalize_office(
                    banner_text[timeline[0][0]])
                if contest not in contests:
                    contests.append(contest)
            if contest is None:
                errors.append(f"p{pno}: no banner")
                continue
            rot = rotated_cell_labels(page, rules)
            reg_cell = cast_cell = turn_cell = None
            cand_cells = {}
            for idx, lbl in rot.items():
                if not lbl:
                    continue
                low = lbl.lower()
                if "registered" in low and "voter" in low:
                    reg_cell = idx
                elif "cast" in low:
                    cast_cell = idx
                elif "turnout" in low:
                    turn_cell = idx
                else:
                    cand_cells[idx] = lbl
            label_edge = rules[reg_cell] if reg_cell is not None else 180
            page_cands = {}
            for idx, lbl in cand_cells.items():
                party, cand = parse_candidate(lbl)
                page_cands[idx] = cand
                cand_party.setdefault(contest, {}).setdefault(
                    cand, party if party else "")
                if cand_party[contest][cand] and party and \
                        cand_party[contest][cand] != party:
                    errors.append(f"p{pno}: party conflict {cand} "
                                  f"{cand_party[contest][cand]} vs {party}")
                cand_pages[(contest, cand)].add(pno)
            for g in groups:
                g = sorted(g, key=lambda w: w["x0"])
                label = " ".join(w["text"] for w in g
                                 if w["x1"] <= label_edge + 1).strip()
                if not label or len(label) < 2:
                    continue
                if (label.startswith("Printed:") or
                        label.startswith("***") or
                        re.search(r"Page \d+ of", label)):
                    continue
                is_ct = label.startswith("Contest Total")
                if COUNTY_TOTAL_RE.match(label) or is_ct:
                    kind = "county_total"
                elif VTYPE_RE.match(label):
                    kind = "vtype"
                elif label.endswith("Total") and re.match(
                        r"^(City of |Borough of |Township of )", label):
                    kind = "muni_total"
                elif label.endswith("Total"):
                    kind = "precinct"
                else:
                    continue
                key = (contest, label)
                rec = acc[key]
                rec.setdefault("kind", kind)
                vals = {}
                stars = False
                for w in g:
                    if w["x1"] <= label_edge + 1:
                        continue
                    if "*" in w["text"]:
                        stars = True
                        break
                    if not NUM_RE.match(w["text"]):
                        continue
                    idx = cell_of(rules, w["x1"])
                    if idx == reg_cell:
                        vals["reg"] = num(w["text"])
                    elif idx == cast_cell:
                        vals["cast"] = num(w["text"])
                    elif idx == turn_cell or idx is None:
                        pass
                    elif idx in page_cands:
                        vals[page_cands[idx]] = num(w["text"])
                    else:
                        errors.append(f"p{pno} {label}: unlabeled cell "
                                      f"{idx}")
                if stars:
                    errors.append(f"p{pno} {label}: suppressed row")
                    # a suppressed row can hold up to `cast` ballots for
                    # any candidate; record its cast for the validator
                    if "cast" in vals:
                        supp = acc[key].setdefault("suppressed", 0)
                        acc[key]["suppressed"] = max(supp,
                                                     vals["cast"])
                    continue
                rec.setdefault("pages", set()).add(pno)
                for k, v in vals.items():
                    if k in rec and rec[k] != v and rec[k] and v:
                        errors.append(f"p{pno} {label} {k}: value conflict "
                                      f"{rec[k]} vs {v}")
                    # max across suppression-group pages
                    if k not in rec or v > rec.get(k, -1):
                        rec[k] = v
                if is_ct:
                    for k, v in vals.items():
                        contest_total[contest][k] = max(
                            contest_total[contest][k], v)
    return acc, cand_party, contest_total, errors, contests


MUNI_PREFIX = re.compile(r"^(City of |Borough of |Township of )")


def classify_label(label):
    """Return (precinct_name, kind) for a row label, or None."""
    if label.endswith("EV Total"):
        base = MUNI_PREFIX.sub("", label[:-8].rstrip())
        return (f"{base} - Early Voting", "pseudo")
    if label.endswith("Prov Total"):
        base = MUNI_PREFIX.sub("", label[:-10].rstrip())
        return (f"{base} - Provisional", "pseudo")
    if not label.endswith("Total"):
        return None
    if COUNTY_TOTAL_RE.match(label) or label.startswith("Contest Total"):
        return None        # county-level rows are validation-only
    if MUNI_PREFIX.match(label):
        return None        # municipal summary rows are aggregates
    if re.search(r"\s(City|Township|Borough|Town)$", label[:-6].rstrip()):
        return None        # municipal summary rows are aggregates
    return (re.sub(r"\s*Total$", "", label), "precinct")


def emit(acc, cand_party, contest_total, errors, contests):
    out_rows = []
    problems = []
    checked = 0
    seen_reg = set()
    for (contest, _label) in sorted(acc, key=lambda k: (contests.index(
            k[0]), k[1])):
        rec = acc[(contest, _label)]
        cls = classify_label(_label)
        office, dist = contest
        if cls is None:
            continue
        pname, kind = cls
        reg = rec.get("reg")
        if reg and kind == "precinct":
            if pname not in seen_reg:
                seen_reg.add(pname)
                out_rows.append(["Cumberland", pname, "Registered Voters",
                                 dist, "", "", int(reg)])
        for cand in sorted(k for k in rec if k not in
                           ("reg", "cast", "kind", "pages", "suppressed")):
            v = int(rec[cand])
            out_rows.append(["Cumberland", pname, office, dist,
                             cand_party.get(contest, {}).get(cand, ""),
                             cand, v])
    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "party",
                    "candidate", "votes"])
        w.writerows(out_rows)
    print(f"wrote {len(out_rows)} rows")
    return problems


def validate(acc, cand_party, contest_total, errors, contests):
    problems = []
    # per contest & candidate: precinct + pseudo rows == contest total
    sums = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for (contest, label), rec in acc.items():
        cls = classify_label(label)
        if cls is None:
            continue
        _pname, kind = cls
        for k, v in rec.items():
            if k in ("reg", "cast", "kind", "pages"):
                continue
            sums[contest][k][kind] += v
    for contest in contests:
        # suppressed rows bound the votes a candidate can hold
        suppressed_bound = sum(
            rec.get("suppressed", 0) for (c, _l), rec in acc.items()
            if c == contest)
        for cand in cand_party.get(contest, {}):
            ct = contest_total[contest].get(cand, 0)
            got = (sums[contest][cand].get("precinct", 0) +
                   sums[contest][cand].get("pseudo", 0))
            if got > ct + 0.4 or (got < ct - 0.4 and
                                  ct - got > suppressed_bound + 0.4):
                problems.append(f"{contest} | {cand}: rows sum {int(got)} "
                                f"vs contest total {int(ct)} sup_bound "
                                f"{int(suppressed_bound)}")
            checked = 0
    print(f"validation problems: {len(problems)}")
    for p in problems[:25]:
        print("   ", p)
    return problems


if __name__ == "__main__":
    acc, cand_party, contest_total, errors, contests = main()
    print("errors:", len(errors))
    for e in errors[:16]:
        print("  ", e)
    print("contests:", len(contests))
    emit(acc, cand_party, contest_total, errors, contests)
    validate(acc, cand_party, contest_total, errors, contests)
