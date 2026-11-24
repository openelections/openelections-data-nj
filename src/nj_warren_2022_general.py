"""Parse Warren County's 2022 general election precinct results.

Source: "Warren NJ Precinct level report Gen.pdf" (267 pages), a
"Summary Results Report - Federal and State District Report" with one
section per election district. Each section has a district header line
("<Municipality> District N"), a STATISTICS block (Registered Voters -
Total, Ballots Cast - Total with six vote-type columns), then five
contests (U.S. House CD7, County Sheriff, County Clerk, County
Commissioner, County Surrogate), each printing:

    <party> <name> TOTAL ED EVP VBM PROV EMERG
    Write-In Totals ...
    Total Votes Cast ...
    Overvotes ... / Undervotes ...
    Contest Totals ...

Sections can span page breaks, so state carries across pages and the
district header line is the only section delimiter. Validation per
contest: candidates + write-ins = Total Votes Cast, Total Votes Cast +
overvotes + undervotes = Contest Totals, breakdown columns sum to TOTAL.

Output: 2022/20221108__nj__general__warren__precinct.csv with Registered
Voters, Ballots Cast, candidates, and Write-ins pseudo-rows (votes =
TOTAL; breakdown columns are validated but not published).
"""

import csv
import re
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
PDF = (Path("/Users/dwillis/code/openelections-sources-nj/2022/") /
       "Warren NJ Precinct level report Gen.pdf")
OUTPUT = BASE / "2022/20221108__nj__general__warren__precinct.csv"

PRECINCT_RE = re.compile(r"^.+ District (\d+(-\d+)?)$")
HOUSE_RE = re.compile(r"Member of the House of Representatives - "
                      r"(\d+)th Congressional")
OFFICE_MAP = {
    "County Sheriff": "County Sheriff",
    "County Clerk": "County Clerk",
    "County Commissioner": "County Commissioner",
    "County Surrogate": "County Surrogate",
}
NUM_TOKEN_RE = re.compile(r"^-?\d[\d,]*$")


def compress(name):
    """'Borough of Alpha District 1' -> 'Alpha Boro Dist 1'."""
    name = re.sub(r"^(Borough of |Town of |City of )", "", name).strip()
    name = name.replace(" District ", " Dist ")
    name = name.replace(" Township", " Twp").replace(" Borough", " Boro")
    return name


def peel_ints(tokens, n):
    """Peel n trailing integer tokens; return (rest, values) or (None, None)."""
    vals = []
    i = len(tokens)
    while len(vals) < n and i > 0 and NUM_TOKEN_RE.match(tokens[i - 1]):
        vals.append(int(tokens[i - 1].replace(",", "")))
        i -= 1
    if len(vals) < n:
        return None, None
    return tokens[:i], list(reversed(vals))


def main():
    stat_rows = []            # (precinct, kind, votes)
    cand_rows = []            # (precinct, office, party, candidate, votes)
    errors = []
    precinct = None
    office = None
    ctx = None                # validation context of current contest
    n_precincts = 0

    def expect(cond, msg):
        if not cond:
            errors.append(msg)

    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            lines = [l.strip() for l in (page.extract_text() or "").split("\n")
                     if l.strip()]
            # skip header/footer noise
            lines = [l for l in lines if not l.startswith("Summary Results")
                     and not l.startswith("November 21, 2022")
                     and not l.startswith("2022 General Election")
                     and "Federal and State District Report -" not in l
                     and "Warren Co." != l]
            for line in lines:
                if line.startswith("Page "):
                    continue
                if PRECINCT_RE.match(line) and "Congressional" not in line:
                    precinct = compress(line)
                    office = None
                    ctx = None
                    n_precincts += 1
                    continue
                m = HOUSE_RE.search(line)
                if m:
                    office = ("U.S. House", m.group(1))
                    ctx = {"cands": [], "writeins": 0, "tvc": None,
                           "over": None, "under": None,
                           "label": line, "page": pno, "prec": precinct}
                    expect(office is not None, "")
                    continue
                if line in OFFICE_MAP:
                    office = (OFFICE_MAP[line], "")
                    ctx = {"cands": [], "writeins": 0, "tvc": None,
                           "over": None, "under": None,
                           "label": line, "page": pno, "prec": precinct}
                    continue
                if precinct is None:
                    continue
                if line.startswith("Registered Voters - Total"):
                    _, rest = line.split("Total", 1)
                    rest = rest.replace(",", "").strip()
                    expect(rest.isdigit(), f"p{pno} bad RV line: {line!r}")
                    stat_rows.append((precinct, "Registered Voters",
                                      int(rest)))
                    continue
                if line.startswith("Ballots Cast - Total"):
                    _, rest = line.split("Total", 1)
                    vals = re.findall(r"-?\d[\d,]*", rest)
                    expect(len(vals) == 6, f"p{pno} bad BC line: {line!r}")
                    nums = [int(v.replace(",", "")) for v in vals]
                    total, breakdown = nums[0], nums[1:]
                    if sum(breakdown) != total:
                        errors.append(f"p{pno} {precinct} Ballots Cast: "
                                      f"breakdown sum {sum(breakdown)} "
                                      f"!= total {total}")
                    stat_rows.append((precinct, "Ballots Cast", int(total)))
                    continue
                if line == "Vote For 1" or line == "STATISTICS":
                    continue
                if line.startswith("Contest Totals"):
                    if ctx:
                        vals = [int(v.replace(",", "")) for v in
                                re.findall(r"-?[\d,]+",
                                           line[len("Contest Totals"):])]
                        expect(len(vals) == 6, f"p{pno} bad CT:{line!r}")
                        ctx["contest_total"] = vals[0]
                        # validate and flush this contest
                        cand_sum = sum(v for _, _, v in ctx["cands"])
                        expect(cand_sum + ctx["writeins"] == ctx["tvc"][0],
                               f"p{pno} {precinct} {ctx['label']}: cands "
                               f"{cand_sum}+wi {ctx['writeins']} != TVC "
                               f"{ctx['tvc'][0]}")
                        expect(ctx["tvc"][0] + ctx["over"][0] +
                               ctx["under"][0] == ctx["contest_total"],
                               f"p{pno} {precinct} {ctx['label']}: TVC "
                               f"{ctx['tvc'][0]}+O{ctx['over'][0]}+U"
                               f"{ctx['under'][0]} != {ctx['contest_total']}")
                        for c_party, c_cand, c_total in ctx["cands"]:
                            cand_rows.append((precinct, office, c_party,
                                              c_cand, c_total))
                        cand_rows.append((precinct, office, "",
                                          "Write-ins", ctx["writeins"]))
                    ctx = None
                    continue
                if line.startswith("Total Votes Cast"):
                    if ctx:
                        vals = [int(v.replace(",", "")) for v in
                                re.findall(r"-?[\d,]+",
                                           line[len("Total Votes Cast"):])]
                        expect(len(vals) == 6, f"p{pno} bad TVC:{line!r}")
                        ctx["tvc"] = vals
                    continue
                if line.startswith("Overvotes"):
                    if ctx:
                        ctx["over"] = [int(v.replace(",", "")) for v in
                                       re.findall(r"\d[\d,]*",
                                                  line[len("Overvotes"):])]
                    continue
                if line.startswith("Undervotes"):
                    if ctx:
                        ctx["under"] = [int(v.replace(",", "")) for v in
                                        re.findall(r"-?\d[\d,]*",
                                                   line[len("Undervotes"):])]
                    continue
                if line.startswith("Write-In Totals"):
                    vals = [int(v.replace(",", "")) for v in
                            re.findall(r"-?\d[\d,]*",
                                       line[len("Write-In Totals"):])]
                    if ctx:
                        expect(len(vals) == 6, f"p{pno} bad WI:{line!r}")
                        ctx["writeins"] = vals[0]
                    continue
                # candidate row: <party> <name> N [N...]
                tokens = line.split()
                if not tokens or precinct is None or office is None:
                    continue
                rest, vals = peel_ints(tokens, 6)
                if vals is None:
                    continue
                total, breakdown = vals[0], vals[1:]
                rest = tokens[:len(tokens) - 6]
                m2 = re.match(r"^([A-Z]{2,4}) (.+)$", " ".join(rest))
                expect(m2 is not None, f"p{pno} unparseable cand: {line!r}")
                if not m2:
                    continue
                party, cand = m2.group(1), m2.group(2)
                if sum(breakdown) != total:
                    errors.append(f"p{pno} {precinct} {office[0]} {cand}: "
                                  f"breakdown {sum(breakdown)} != {total}")
                if ctx is not None:
                    ctx["cands"].append((party, cand, total))

    if errors:
        print(f"{len(errors)} parse errors (first 30):")
        for e in errors[:30]:
            print(" ", e)
    return errors, stat_rows, cand_rows


def main_out(stat_rows, cand_rows):
    out_rows = []
    for prec, kind, votes in stat_rows:
        out_rows.append(["Warren", prec, kind, "", "", "", votes])
    for prec, (off, dist), party, cand, votes in cand_rows:
        p = "" if cand == "Write-ins" else party
        out_rows.append(["Warren", prec, off, dist, p, cand, votes])
    out_rows = [r for r in out_rows if r[6] is not None]
    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "party",
                    "candidate", "votes"])
        for row in out_rows:
            w.writerows([row])
    print(f"wrote {len(out_rows)} rows")


if __name__ == "__main__":
    errs, stats, cands = main()
    print(f"stat_rows={len(stats)} cand_rows={len(cands)}")
    main_out(stats, cands)
