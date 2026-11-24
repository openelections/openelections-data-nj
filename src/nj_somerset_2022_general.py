"""Parse Somerset County's 2022 general election precinct results.

Sources (ES&S-style "Statement of Vote" with rotated candidate headers):
  - "Somerset NJ 7th Congressional District.pdf" (one contest)
  - "Somerset NJ 12th Congressional Distric.pdf" (one contest)

Each page is a table: a horizontal contest banner (e.g. "NON PARTISAN
HOUSE OF REPRESENTATIVES 7TH DISTRICT"), then rotated header cells read
bottom-to-top: Registration | Ballots Cast | Turnout (%) | [candidate
columns...] | Write-In (candidate header text is printed rotated 90
degrees; pdfplumber's char boxes give upright=False glyphs that read
correctly in ascending-y order). Data rows are:

    <precinct> - <vote type>  REG  CAST  TURNOUT  CAND...

Rows cover Election Day, Mail-In Ballot, Early Voting (municipality-wide),
Provisional and Federal (overseas) vote types; the vote-type suffix is
kept in the precinct name ("Bedminster Dist 1 - Election Day"),
aggregated per (precinct, office). Trailing empty candidate columns are
ignored. Parties are not printed ("NON PARTISAN" header) and were filled
from the known 2022 ballot.

Output: 2022/20221108__nj__general__somerset__precinct.csv with
Registered Voters, Ballots Cast, candidates and Write-ins pseudo-rows.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
SOURCES = Path("/Users/dwillis/code/openelections-sources-nj/2022")
FILES = {
    "7th Congressional District": ("Somerset NJ 7th Congressional "
                                   "District.pdf", 7),
    "12th Congressional District": ("Somerset NJ 12th Congressional "
                                    "Distric.pdf", 12),
}
OUTPUT = BASE / "2022/20221108__nj__general__somerset__precinct.csv"
PARTY = {
    "Thomas H. Kean, Jr.": "REP",
    "Tom Malinowski": "DEM",
    "Darius Mayfield": "REP",
    "Bonnie Watson Coleman": "DEM",
    "C. Lynn Genrich": "",
}
SUFFIX_FIX = {
    "Election Day": "Election Day",
    "Mail-In Ballot": "Mail-In Ballot",
    "Early Voting": "Early Voting",
    "Early Voting Prov": "Early Voting Provisional",
    "Prov": "Provisional",
    "Overseas": "Federal Overseas",
}
NUM_TOKEN_RE = re.compile(r"-?\d[\d,\.]*$")


def rotated_headers(page):
    """Cluster rotated glyph columns; return [(x0, label)] ascending x."""
    chars = [c for c in page.chars if not c.get("upright", True)]
    clusters = []
    for c in chars:
        if clusters and abs(c["x0"] - clusters[-1][0][ "x0"]) < 6:
            clusters[-1].append(c)
        else:
            clusters.append([c])
    out = []
    for cl in clusters:
        txt = "".join(ch["text"] for ch in sorted(cl, key=lambda c: c["y0"]))
        out.append((min(c["x0"] for c in cl), txt.strip()))
    out.sort(key=lambda t: t[0])
    return out


def parse_pdf(path, district):
    pdfplumber_errs = []
    header = None
    rows = defaultdict(lambda: defaultdict(int))  # precinct -> cand -> votes
    reg = {}
    cast = {}
    errors = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            cols = [t for x, t in rotated_headers(page)]
            # drop the banner cluster and the first three stat columns
            cand_cols = [t for t in cols
                         if t not in ("Registration", "Ballots Cast",
                                      "Turnout (%)")
                         and "HOUSE OF REPRESENTATIVES" not in t.upper()
                         and not re.match(r"^[\d\s.]+$", t)]
            if not cand_cols:
                continue
            banner = None
            m = re.search(r"NON PARTISAN\s+(.+)", page.extract_text() or "")
            banner = m.group(1).strip() if m else None
            # horizontal data rows
            for line in (page.extract_text() or "").split("\n"):
                line = line.strip()
                if not line or "NON PARTISAN" in line:
                    continue
                if "*" in line:
                    # "Insufficient Turnout" rows: values up to the first
                    # starred cell are printed; cells after are suppressed
                    toks = []
                    for t in line.split():
                        if "*" in t:
                            mt = re.match(r"^\d+", t)
                            if mt:
                                toks.append(mt.group(0))
                            break
                        toks.append(t)
                else:
                    toks = line.split()
                nums = []
                i = len(toks)
                while i > 0 and NUM_TOKEN_RE.match(toks[i - 1]):
                    nums.append(toks[i - 1])
                    i -= 1
                if not (3 <= len(nums) <= 3 + len(cand_cols)):
                    continue
                if len(nums) != 3 + len(cand_cols) and "*" not in line:
                    continue
                nums = list(reversed(nums))
                name = " ".join(toks[:i]).rstrip().rstrip(" -–")
                if not name:
                    continue
                try:
                    vals = [float(n.replace(",", "")) for n in nums]
                    ints = [int(float(n.replace(",", ""))) for n in nums]
                except ValueError:
                    continue
                reg_v, cast_v, turnout = vals[0], vals[1], vals[2]
                cand_vals = ints[3:]
                cast_v = int(cast_v) if cast_v == int(cast_v) else cast_v
                if reg_v and turnout:
                    if abs(cast_v / reg_v * 100 - turnout) > 0.06 and (
                            cast_v <= reg_v):
                        errors.append(f"p{pno} {name}: turnout mismatch "
                                      f"{turnout} vs {cast_v/reg_v*100:.2f}")
                # map name to precinct label; drop summary/junk rows
                if ("Totals" in name or name in ("precinct",)
                        or re.search(r"Congressio", name)):
                    continue
                if " - " in name:
                    base, vtype = (x.strip() for x in name.rsplit(" - ", 1))
                else:
                    base, vtype = name, ""
                if re.match(r"^(Federal|State|Grand)", base):
                    continue
                base = re.sub(r"\s*D\s*(\d+)$", r" Dist \1", base)
                # classify the vote type
                vt = None
                if re.search(r" Dist \d+$", base) or base.endswith("Dist"):
                    if vtype.startswith("El"):
                        vt = "Election Day"
                    elif (vtype.startswith(("Mail", "In Ballot", "ail")) or
                          "ail" in vtype):
                        vt = "Mail-In Ballot"
                    elif vtype.startswith("Ea"):
                        vt = "Early Voting"
                    elif vtype.startswith("Provi"):
                        vt = "Provisional"
                    elif vtype.startswith("Fe"):
                        vt = "Federal Overseas"
                else:
                    for tail, label_vt in (
                            ("Early Voting Prov", "Early Voting "
                             "Provisional"),
                            ("Early Voting P", "Early Voting Provisional"),
                            ("Early Voting", "Early Voting"),
                            ("Overseas", "Federal Overseas"),
                            ("Prov", "Provisional")):
                        if base.endswith(tail):
                            base = base[:len(base) - len(tail)].rstrip()
                            vt = label_vt
                            break
                if vt is None:
                    continue
                label = f"{base} - {vt}"
                for col, v in zip(cand_cols, cand_vals):
                    rows[label][col] += v
                cur = reg.get(label, 0)
                if reg_v and (not cur or cur < reg_v):
                    reg[label] = int(reg_v)
                cast[label] = cast.get(label, 0) + cast_v
                header = banner
    return rows, reg, cast, cand_cols, header, errors


def main():
    out_rows = []
    all_errors = []
    for label, (fname, dist) in FILES.items():
        rows, reg, cast, cand_cols, banner, errs = parse_pdf(
            SOURCES / fname, dist)
        all_errors += errs
        office = "U.S. House"
        cand_norm = [c.rstrip() for c in cand_cols]
        for precinct in sorted(rows, key=lambda p: (p.split(" - ")[0], p)):
            cands = rows[precinct]
            for c in cand_norm:
                v = cands.get(c, 0)
                cand = "Write-ins" if c == "Write-In" else c
                party = ""
                if cand != "Write-ins":
                    party = PARTY.get(c, "")
                out_rows.append([
                    "Somerset", precinct, office, str(dist), party, cand, v])
            for kind, col in (("Registered Voters", "reg"),
                              ("Ballots Cast", "cast")):
                pass
            if precinct in reg:
                out_rows.append(["Somerset", precinct, "Registered Voters",
                                 str(dist), "", "", reg[precinct]])
            if precinct in cast:
                out_rows.append(["Somerset", precinct, "Ballots Cast",
                                 str(dist), "", "", cast[precinct]])
    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "party",
                    "candidate", "votes"])
        w.writerows(out_rows)
    print(f"wrote {len(out_rows)} rows; errors={len(all_errors)}")
    for e in all_errors[:10]:
        print(" ", e)


if __name__ == "__main__":
    main()
