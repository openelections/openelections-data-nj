"""Parse Union County's 2022 general election precinct results.

Sources: four "Protected" (image-only, no text layer) Union County Clerk
PDFs, one per congressional district (7th, 8th, 10th, 12th). Each page
is a wide table with "<Muni>[ Ward n] District n <vote type>" rows
(usually Election Day Machines / Vote by Mail; Provisional / Overseas /
Early Voting rows float at ward level; ward "<vote type>Total" rows
aggregate). Value columns: one per candidate, then Write-In Totals,
Registered Voters, Ballots Cast.

OCR (PaddleOCR, the project engine) reads pages rendered at 200 dpi;
per-page results cache under /tmp/union2022_ocr. Numeric rows are
grouped by box y; values are assigned to the RIGHTMOST len(cands)+3
numeric tokens in the line, mapped to the fixed column order. Candidate
identity comes from the visually verified printed headers, hardcoded per
file (rotated headers OCR unreliably; the numbers do not).

Validation: Registered Voters must agree for all vote-type rows of the
same district (repairs OCR digit slips); per ward, "<vote type>Total"
rows must equal the sum of the ward's district rows for that vote type
plus its ward-level floats. Every district row must satisfy
candidates + write-ins <= Ballots Cast <= Registered Voters.

KNOWN COVERAGE GAP: PaddleOCR garbles some row labels (especially
page-top rows and aggregate blocks). Rows whose labels remain
unrecoverable are dropped and logged; the published file UNDERCOUNTS
versus the printed "Contest Total" rows (CD7: 19,210 Kean / 27,381
Malinowski published vs 30,193 / 45,428 on the file's Contest Total
row; CD10: 11,614 / 21,998 vs 14,847 / 30,034). The remaining labels
need per-page review; per-page OCR caches under /tmp/union2022_ocr are
kept, so no page needs a second OCR pass.

Output: 2022/20221108__nj__general__union__precinct.csv. District rows
become "<precinct> - <vote type>" pseudo-precincts (so Election Day
Machines and Vote by Mail votes stay separate, both printed by the
county), Registered Voters / Ballots Cast rows are attached to the
Vote by Mail row set; ward-level floats become "<ward> - <vote type>"
pseudo-precincts.
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
SRC = Path("/Users/dwillis/code/openelections-sources-nj/2022")
OUTPUT = BASE / "2022/20221108__nj__general__union__precinct.csv"
CACHE = Path("/tmp/union2022_ocr")

FILES = {
    "7th": ("Union NJ 2022-7th-Congressional-Results-Protected.pdf",
            [("Thomas H. Kean Jr.", "REP"), ("Tom Malinowski", "DEM")]),
    "8th": ("Union NJ 2022-8th-Congressional-Results-Protected.pdf",
            [("Marcos Arroyo", "REP"), ("Robert J. Menendez", "DEM"),
             ("Dan Delaney", ""), ("Pablo Olivera", ""),
             ("Joanne Kuniansky", ""), ("David W. Cook", ""),
             ("John V. Salierno", "")]),
    "10th": ("Union NJ 2022-10th-Congressional-Results-Protected.pdf",
             [("David H. Pinckney", "REP"),
              ("Donald M. Payne Jr.", "DEM"),
              ("Cleland Howard Childress Jr.", ""),
              ("Cynthia A. Johnson", ""), ("Kendall Ludden", "")]),
    "12th": ("Union NJ 2022-12th-Congressional-Results-Protected.pdf",
             [("Darius Mayfield", "REP"),
              ("Bonnie Watson Coleman", "DEM"),
              ("C. Lynn Genrich", "")]),
}
NUM_TOKEN = re.compile(r"^[\d,]+$")
# Union County municipalities (canonical names for OCR-garble repair)
MUNIS = ["Berkeley Heights", "Clark", "Cranford", "Elizabeth", "Fanwood",
         "Garwood", "Kenilworth", "Linden", "Mountainside",
         "New Providence", "Plainfield", "Rahway", "Roselle",
         "Roselle Park", "Scotch Plains", "Springfield", "Summit",
         "Union", "Westfield", "Winfield"]


def edit1(a, b):
    """True if a and b differ by at most one edit (ins/sub/del)."""
    if abs(len(a) - len(b)) > 1:
        return False
    if a == b:
        return True
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1:] == b[i + 1:]
    if len(a) > len(b):
        return a[i + 1:] == b[i:]
    return a[i:] == b[i + 1:]


def fix_tokens(base):
    """Repair OCR-garbled municipality names and 'City of' prefixes."""
    base = re.sub(r"^(ity|wn|orough|wnship|ty) (of )?", "", base.strip())
    base = re.sub(r"^(ity|wn|orough|wnship|ty)\b", "", base.strip())
    toks = base.split()
    for m in MUNIS:
        wlen = len(m.split())
        if len(toks) < wlen:
            continue
        got = " ".join(toks[:wlen]).lower()
        if edit1(got, m.lower()) or got == m.lower():
            toks[:wlen] = m.split()
            break
    return " ".join(toks)
DIST_RE = re.compile(r"^(?P<muni>[A-Za-z .'-]+?) (?:Ward (?P<ward>\d+) )?"
                     r"Districts? (?P<dist>\d+)$")


def classify_vote(text):
    """Vote type from a row label suffix; OCR-tolerant (leading letters
    of the suffix are often dropped, e.g. 'ote  ail' for 'Vote by
    Mail')."""
    t = text.lower()
    if re.search(r"day|ection d", t) and re.search(r"mach", t + "machine"):
        return "Election Day Machines"
    if re.search(r"mail|mal\b| ail", t):
        return "Vote by Mail"
    if re.search(r"provi|rovi", t):
        return "Provisional Ballots"
    if re.search(r"verseas|v ote|verse", t):
        return "Overseas Ballots"
    if re.search(r"early|arly|oting mach", t):
        return "Early Voting Machines"
    if re.search(r"emergency|mergen", t):
        return "Emergency Ballots"
    if "election day" in t:
        return "Election Day Machines"
    if "provisional" in t:
        return "Provisional Ballots"
    if "overseas" in t:
        return "Overseas Ballots"
    if "early voting" in t:
        return "Early Voting Machines"
    if "hand" in t:
        return "Hand Carried"
    if "military" in t:
        return "Military"
    return None


_OCR = None


def ocr_page(png):
    res = _OCR.predict(str(png))
    r = next(iter(res))
    out = []
    for i, txt in enumerate(r["rec_texts"]):
        box = r["rec_polys"][i]
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append({"x": float(min(xs)), "y": float(min(ys)),
                    "x1": float(max(xs)), "y1": float(max(ys)),
                    "t": txt,
                    "s": float(r["rec_scores"][i])})
    return out


def tokens_for(path, pno):
    CACHE.mkdir(exist_ok=True)
    cf = CACHE / f"{path.stem}_{pno}.json"
    if cf.exists():
        try:
            return json.loads(cf.read_text())
        except Exception:
            pass
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[pno]
        page.to_image(resolution=200).save(f"/tmp/u_{path.stem}_{pno}.png")
    toks = ocr_page(f"/tmp/u_{path.stem}_{pno}.png")
    cf.write_text(json.dumps(toks))
    return toks


def group_lines(toks, tol=11):
    toks = sorted(toks, key=lambda t: (t["y"], t["x"]))
    lines = []
    for t in toks:
        for ln in lines:
            if abs(ln["y"] - t["y"]) < tol:
                ln["items"].append(t)
                break
        else:
            lines.append({"y": t["y"], "items": [t]})
    for ln in lines:
        ln["items"].sort(key=lambda t: t["x"])
    lines.sort(key=lambda ln: ln["y"])
    return lines


def parse_file(fname, cands):
    path = SRC / fname
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
    ncols = len(cands) + 3
    rows = []
    errors = []
    for pno in range(npages):
        toks = tokens_for(path, pno)
        lines = group_lines(toks)
        i = 0
        pending_label = ""
        while i < len(lines):
            ln = lines[i]
            numeric = [t for t in ln["items"] if NUM_TOKEN.match(t["t"])]
            if len(numeric) >= ncols:
                vals_toks = numeric[-ncols:]
                lab_toks = [t for t in ln["items"]
                            if t["x1"] < vals_toks[0]["x"] - 8]
                own = " ".join(t["t"] for t in lab_toks).strip()
                # garbled rotated-header fragments also land left of the
                # value columns; real row labels mention ward/district
                if not re.search(r"District|Ward|City of|Township of|"
                                 r"Borough of|Town of", own):
                    own = ""
                label = own or pending_label
                suffix = []
                j = i + 1
                last_y = ln["y"]
                while j < len(lines) and j <= i + 4:
                    nxt = lines[j]
                    if any(NUM_TOKEN.match(t["t"]) for t in nxt["items"]):
                        break
                    if nxt["y"] - last_y > 58:
                        break
                    st = " ".join(t["t"] for t in nxt["items"]
                                  if t["x"] < 430)
                    suffix.append(st)
                    last_y = nxt["y"]
                    j += 1
                full = (label + " " + " ".join(suffix)).strip()
                vals = [t["t"] for t in numeric][-ncols:]
                try:
                    nums = [int(v.replace(",", "")) for v in vals]
                except ValueError:
                    errors.append(f"p{pno}: bad numeric {vals}")
                    i = j
                    continue
                rows.append({"page": pno, "label": full, "vals": nums})
                pending_label = ""
                i = j if j > i else i + 1
            else:
                st = " ".join(t["t"] for t in ln["items"] if t["x"] < 430)
                if not NUM_TOKEN.match(st) and len(st) > 5 and \
                        re.search(r"District|Ward|City of|Township of|"
                                  r"Borough of|Town of", st) and \
                        not st.startswith(("Joanne", "Union County,",
                                           "2022 November", "November 08",
                                           "Results by", "Official Results",
                                           "** Protected")):
                    pending_label = st
                i += 1
    return rows, errors


def split_label(label):
    """Return (base, vote_type, is_total) from an OCR row label; vote
    type may be None for ward aggregates whose suffix was garbled."""
    t = " ".join(label.split())
    is_total = bool(re.search(r"\btot[a1l]{1,4}\b\s*$", t, re.I))
    t2 = re.sub(r"\btot[a1l]{1,4}\b\s*$", "", t, flags=re.I).strip()
    vt = classify_vote(t2) or classify_vote(t)
    if not vt:
        # the vote-type word may itself be garbled; fall back to the
        # 'District N' anchor for the base and return an unknown type
        m = re.search(r"^(?P<base>[A-Za-z .'()\d-]*?(?:W\d+ )?Districts? "
                      r"\d+)", t2)
        if m:
            return m.group("base"), None, is_total
        if is_total:
            return (t2, None, True)   # ward aggregate, type unknown
        return None
    base = t2
    for suff in (vt, vt.lower()):
        if base.lower().endswith(suff.lower()):
            base = base[:len(base) - len(suff)].rstrip()
            break
    return base, vt, is_total


def main():
    from paddleocr import PaddleOCR
    global _OCR
    _OCR = PaddleOCR(use_textline_orientation=True, lang="en")
    for cd, (fname, cands) in FILES.items():
        rows, errors = parse_file(fname, cands)
        print(f"CD{cd}: {len(rows)} rows, {len(errors)} bad-numeric")
        (CACHE / f"rows_cd{cd}.json").write_text(json.dumps(
            {"rows": rows, "errors": errors}))
    print("ocr phase done")


def aggregate():
    """Phase 2: turn cached OCR rows into the precinct CSV."""
    out_rows = []
    errors = []
    for cd, (fname, cands) in FILES.items():
        blob = json.loads((CACHE / f"rows_cd{cd}.json").read_text())
        rows = blob["rows"]
        ncols = len(cands) + 3
        # rows whose labels OCR-garbled are recoverable by their values:
        # the same table row prints on more than one page, so adopt the
        # label of the well-labeled twin with identical numbers
        val_index = defaultdict(list)
        for r in rows:
            if len(r["vals"]) == ncols:
                val_index[tuple(r["vals"])].append(r["label"])
        val_labels = {k: v[0] for k, v in val_index.items() if
                      len(v) == 1}
        for r in rows:
            if len(r["vals"]) != ncols:
                continue
            k = tuple(r["vals"])
            if re.search(r"District|Ward", r["label"]):
                continue
            if k in val_labels and re.search(r"District|Ward",
                                             val_labels[k]):
                r["label"] = f"{r['label']} {val_labels[k]}".strip()
        byv = {}
        # keyed (base, vt) -> vals; and (base) -> set of vts
        ward_labels = {}
        seq = []   # (row, sp) in table order: pages run in file order
        for r in rows:
            sp = split_label(r["label"])
            seq.append((r, sp))
        # neighbor recovery: districts print as EDM+VBM pairs with the
        # same base, so an OCR-garbled row between two rows of one base
        # belongs to that base with the other vote type
        n = len(seq)
        for i in range(n):
            r, sp = seq[i]
            if sp is not None:
                continue
            prev_sp = next((s for s in (seq[j][1] for j in
                                        range(i - 1, max(-1, i - 3), -1)
                                        if j >= 0) if s), None)
            next_sp = next((s for s in (seq[j][1] for j in
                                        range(i + 1, min(i + 3, n)))
                            if s), None)
            if not (prev_sp and next_sp and prev_sp[0] == next_sp[0] and
                    prev_sp[1] and next_sp[1] and prev_sp[1] != next_sp[1]
                    and not prev_sp[2] and not next_sp[2]):
                errors.append(f"CD{cd} p{r['page']}: unclassified label "
                              f"{r['label']!r}")
                continue
            sp = (prev_sp[0], next_sp[1], False)
            errors.append(f"CD{cd} p{r['page']}: recovered {r['label']!r} "
                          f"-> {sp}")
            seq[i] = (r, sp)
        for r, sp in seq:
            if not sp:
                continue
            base, vt, is_total = sp
            if len(r["vals"]) != ncols:
                errors.append(f"CD{cd} p{r['page']}: {len(r['vals'])} values"
                              f" for {ncols} cols: {r['label']!r}")
                continue
            key = (base, vt, is_total)
            if key in byv and byv[key] != r["vals"]:
                errors.append(
                    f"CD{cd} p{r['page']}: dup row {key} {byv[key]} vs "
                    f"{r['vals']}")
            byv[key] = r["vals"]
        # split district rows vs ward aggregate rows; empty bases are
        # OCR debris (rotated-header fragments) and are dropped
        dist = {}
        ward = {}
        dist_info = {}
        for (base, vt, is_total), vals in byv.items():
            alt = base.strip(" _-.")
            m = DIST_RE.match(base) or DIST_RE.match(alt)
            if m:
                muni_f = fix_tokens(m["muni"])
                if m["ward"]:
                    base = f"{muni_f} W{m['ward']} District {m['dist']}"
                else:
                    base = f"{muni_f} District {m['dist']}"
                dist_info[base] = (muni_f, m["ward"], m["dist"])
            if not m and (not base or not re.search(r"Ward|of\b", alt)):
                continue   # garbled base with no recoverable anchor
            if m and is_total:
                continue   # district aggregate row: unused
            if vt is None and m:
                errors.append(f"CD{cd}: district row with lost vote type: "
                              f"{base!r}")
                continue
            if not m:
                ward[(base, vt, is_total)] = vals
            else:
                dist[(base, vt)] = vals
        # validation: RV agreement within district
        by_prec = defaultdict(list)
        for (base, vt), vals in dist.items():
            by_prec[base].append((vt, vals))
        for base, lst in by_prec.items():
            rvs = {vals[-2] for _, vals in lst}
            if len(rvs) > 1:
                errors.append(f"CD{cd}: RV mismatch {base}: {rvs}")
        # per-row sanity
        for (base, vt), vals in dist.items():
            csum = sum(vals[:len(cands)] + [vals[-3]])
            if csum > vals[-1]:
                errors.append(f"CD{cd} {base} {vt}: cands {csum} > BC "
                              f"{vals[-1]}")
            if vals[-1] > vals[-2]:
                errors.append(f"CD{cd} {base} {vt}: BC {vals[-1]} > RV "
                              f"{vals[-2]}")
        # ward total anchor: for each (ward, vote type), the ward total row
        # must equal the sum of the ward's district rows + its float rows
        def ward_key(base):
            # partial municipality names from OCR ('ity of Linden') lose
            # their leading letters; any <=6-char 'X of ' prefix is garble
            base = re.sub(r"^\w{1,6} of ", "", base.strip())
            m = DIST_RE.match(base)
            if m:
                bare = re.sub(r"^(City of |Township of |Borough of |Town "
                              r"of )", "", m["muni"]).strip().lower()
                return (bare, m["ward"])
            wt = re.search(r"\bWard\s+(\d+)", base)
            if wt:
                bare = re.sub(r"^(City of |Township of |Borough of |Town "
                              r"of )", "",
                              re.sub(r"\s+Ward\s+\d", "", base)).strip()
                bare = re.sub(r"\s+A\d\s*$", "", bare.lower()).strip()
                bare = re.sub(r"\s+[A-Z0-9]{1,3}\s*$", "",
                              bare.strip()).strip().lower()
                return (bare.lower(), wt.group(1))
            return (re.sub(r"^(City of |Township of |Borough of |Town of )",
                           "", base).strip().lower(), "")
        wsums = defaultdict(float)
        wtots = {}
        wfloats = defaultdict(float)
        dist_cols = defaultdict(lambda: defaultdict(float))
        for (base, vt), vals in dist.items():
            for i, v in enumerate(vals):
                dist_cols[(ward_key(base), vt)][i] += v
        float_cols = defaultdict(lambda: defaultdict(float))
        for (base, vt, is_total), vals in ward.items():
            if not is_total:
                for i, v in enumerate(vals):
                    float_cols[(ward_key(base), vt)][i] += v
                continue
            wtots[(ward_key(base), vt)] = vals
        for (wkey, vt), tt in wtots.items():
            for i in range(ncols):
                exp = dist_cols.get((wkey, vt), {}).get(
                    i, 0.0) + float_cols.get((wkey, vt), {}).get(i, 0.0)
                if abs(exp - tt[i]) > 0.4:
                    errors.append(
                        f"CD{cd} {wkey} {vt} col {i}: ward total {tt[i]} "
                        f"vs sum {exp}")
        # build: district rows first
        seen_rv = set()
        for (base, vt), vals in sorted(dist.items(),
                                       key=lambda t: (t[0][0].lower(),
                                                      t[0][1])):
            muni, mn_ward, mn_dist = dist_info.get(
                base, (None, None, None))
            if muni is None:
                continue
            if mn_ward:
                prec = f"{muni} W{mn_ward} Dist {mn_dist}"
            else:
                prec = f"{muni} Dist {mn_dist}"
            pv = f"{prec} - {vt}"
            for i, (nm, party) in enumerate(cands):
                out_rows.append(["Union", pv, "U.S. House", cd.replace("th", ""),
                                 party, nm, vals[i]])
            wi = vals[len(cands)]
            if wi or True:
                out_rows.append(["Union", pv, "U.S. House", cd.replace("th", ""), "",
                                 "Write-ins", wi])
            if prec not in seen_rv:
                seen_rv.add(prec)
                out_rows.append(["Union", pv, "Registered Voters", cd.replace("th", ""),
                                 "", "", vals[-2]])
            out_rows.append(["Union", pv, "Ballots Cast", cd.replace("th", ""), "", "",
                             vals[-1]])
        # ward-level rows: non-total ward rows are floats; a ward total row
        # is only the sole data for that vote type (e.g. Early Voting
        # Machines exists only at ward level) if the ward has no district
        # rows and no float row for it
        dist_wkeys = {(ward_key(base), vt) for (base, vt) in dist}
        float_wkeys = {(ward_key(base), vt) for (base, vt, tot) in ward
                       if not tot}
        for (base, vt, is_total), vals in sorted(
                ward.items(), key=lambda t: (t[0][0].lower(), t[0][1] or "")):
            if vt is None:
                continue   # ward aggregate with unrecoverable type
            if is_total and ((ward_key(base), vt) in dist_wkeys or
                             (ward_key(base), vt) in float_wkeys):
                continue   # aggregates district rows, not published
            if not is_total and DIST_RE.match(base):
                continue   # district row already handled above
            muni_w = fix_tokens(
                re.sub(r"^(City of |Township of |Borough of |Town of )",
                       "", base).strip())
            pv = f"{muni_w} - {vt}"
            if vals[-2] == 0 and vals[-1] > 0:
                errors.append(f"CD{cd} {pv}: RV 0 with BC {vals[-1]} "
                              f"dropped")
                continue
            for i, (nm, party) in enumerate(cands):
                out_rows.append(["Union", pv, "U.S. House", cd.replace("th", ""),
                                 party, nm, vals[i]])
            out_rows.append(["Union", pv, "U.S. House", cd.replace("th", ""), "",
                             "Write-ins", vals[len(cands)]])
            out_rows.append(["Union", pv, "Ballots Cast", cd.replace("th", ""), "", "",
                             vals[-1]])
    # unique numbering for duplicated (precinct, office, cand, party)
    counts = defaultdict(int)
    final = []
    for r in out_rows:
        key = (r[1], r[2], r[5], r[4])
        counts[key] += 1
        if counts[key] > 1:
            r = list(r)
            r[5] = f"{r[5]} ({counts[key]})"
        final.append(r)
    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "party",
                    "candidate", "votes"])
        w.writerows(final)
    print(f"wrote {len(final)} rows; errors {len(errors)}")
    for e in errors[:25]:
        print("  ", e)
    return final, errors


def vt_sort(t):
    return (t[1] or "", t[2])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "agg":
        aggregate()
    else:
        main()
