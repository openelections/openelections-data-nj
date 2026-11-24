"""Parse Hunterdon County's 2022 general election results.

Source: "Hunterdon NJ G2022OfficialMunicipality.pdf" (108 pages), a
Dominion "Summary Results Report - OFFICIAL RESULTS BY MUNICIPALITY"
with one section per municipality (only municipality totals exist; the
report is the official certified summary, so output uses municipal
granularity). Every page repeats the report header, and the
municipality is ALWAYS the 4th line: "<Municipality>. Contest headers
("Vote For N" preceded by the office line) repeat per contest; candidate
rows are:

    [<party>] <name> TOTAL ED EV Mail Prov Overseas Emerg
    Write-In Totals ... / Write-In: <name> ... / Not Assigned ...

The FIRST number of each row is the TOTAL and is published as `votes`;
the breakdown columns are validated against it. All 26 municipalities'
U.S. House contest lists THOMAS H. KEAN JR. / TOM MALINOWSKI, i.e. CD7
(verified across every section), so House rows get district 7.

Output: 2022/20221108__nj__general__hunterdon__municipal.csv with
Registered Voters, Ballots Cast, candidates, Write-ins and Not
Assigned rows.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
PDF = (Path("/Users/dwillis/code/openelections-sources-nj/2022/") /
       "Hunterdon NJ G2022OfficialMunicipality.pdf")
OUTPUT = BASE / "2022/20221108__nj__general__hunterdon__municipal.csv"

MUNI_RE = re.compile(r"^([A-Za-z .'-]+ (Township|Borough|Town|City))$")
NUM_TOKEN = re.compile(r"^-?\d[\d,]*$")
RESERVED = ("Statistics", "Vote For", "Registered Voters -",
            "Ballots Cast -", "Voter Turnout", "TOTAL Election", "Day",
            "Voting", "Mail In", "Provisional", "Overseas", "Emergenc",
            "Election")
PARTY_RE = re.compile(r"^([A-Z]{2,4}) (.+)$")
PARTY_SET = {"REP", "DEM", "LIB", "GRN", "IND", "CON", "PRO", "SSP",
             "NLP", "NMI", "WF", "LBR"}


def digits(s):
    return [int(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*", s)]


def main():
    stat_rows = {}
    cand_rows = []
    writeins = {}
    not_assigned = {}
    errors = []
    muni = None
    office = None
    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            lines = [l.strip() for l in (page.extract_text() or "").split("\n")
                     if l.strip()]
            if not lines:
                continue
            # report header occupies lines 0-2; the muni line is lines[3]
            mm = MUNI_RE.match(lines[3]) if len(lines) > 3 else None
            if lines[0].startswith("Summary Results Report") and mm:
                muni = mm.group(1)
                office = None
            for line in lines[4:] if mm else lines:
                if line.startswith("Summary Results Report") or \
                        line.startswith("Hunterdon County") or \
                        line.startswith("November 8, 2022") or \
                        line.startswith("Precinct Summary"):
                    continue
                if line.startswith("Registered Voters - Total"):
                    stat_rows.setdefault(muni, {})["rv"] = digits(line)[0]
                    office = None
                    continue
                if line.startswith("Ballots Cast - Total"):
                    vals = digits(line)
                    stat_rows.setdefault(muni, {})["bc"] = vals[0]
                    if len(vals) > 1 and sum(vals[1:]) != vals[0]:
                        errors.append(f"p{pno} {muni}: ballots cast "
                                      f"breakdown {vals}")
                    office = None
                    continue
                if any(line.startswith(p) for p in RESERVED):
                    continue
                if line.startswith("Write-In:"):
                    continue   # enumerated write-ins (totals cover them)
                if line.startswith("Write-In Totals"):
                    vals = digits(line)
                    if vals:
                        prev = writeins.get((muni, office))
                        writeins[(muni, office)] = max(prev or 0, vals[0])
                        if len(vals) > 1 and sum(vals[1:]) != vals[0]:
                            if sum(vals[1:]) or vals[0]:
                                errors.append(f"p{pno} {muni} {office}: wi "
                                              f"breakdown {vals}")
                    continue
                if line.startswith("Not Assigned"):
                    vals = digits(line)
                    if vals:
                        prev = not_assigned.get((muni, office))
                        not_assigned[(muni, office)] = max(prev or 0, vals[0])
                    continue
                toks = line.split()
                nums = []
                j = len(toks)
                while j > 0 and NUM_TOKEN.match(toks[j - 1]):
                    nums.append(toks[j - 1])
                    j -= 1
                name = " ".join(toks[:j]).strip()
                if not nums:
                    office = name
                    continue
                if not name:
                    continue
                total = int(nums[-1].replace(",", ""))
                breakdown = [int(x.replace(",", "")) for x in
                             list(reversed(nums))[1:]]
                if breakdown and sum(breakdown) != total:
                    errors.append(f"p{pno} {muni} {office} {name}: "
                                  f"breakdown {sum(breakdown)} != {total}")
                pm = PARTY_RE.match(name)
                party, cand = "", name
                if pm and pm.group(1) in PARTY_SET:
                    party, cand = pm.group(1), pm.group(2).strip()
                dist = "7" if office == "United States House of " \
                    "Representatives" else ""
                off = "U.S. House" if office == ("United States House "
                                                 "of Representatives") \
                    else office
                cand_rows.append((muni, off, dist, party, cand, total))
    out_rows = []
    for m in sorted(stat_rows):
        st = stat_rows[m]
        if st.get("rv"):
            out_rows.append(["Hunterdon", m, "Registered Voters", "", "",
                             "", st["rv"]])
        if st.get("bc"):
            out_rows.append(["Hunterdon", m, "Ballots Cast", "", "", "",
                             st["bc"]])
    for mu, off, dist, party, cand, v in cand_rows:
        c = "Write-ins" if cand == "Write-ins" else cand
        out_rows.append(["Hunterdon", mu, off, dist,
                         party if c != "Write-ins" else "", c, v])
    for (mu, off), v in sorted(writeins.items()):
        if v:
            off = "U.S. House" if off == ("United States House "
                                          "of Representatives") else off
            out_rows.append(["Hunterdon", mu, off, "", "", "Write-ins", v])
    for (mu, off), v in sorted(not_assigned.items()):
        if v:
            off = "U.S. House" if off == ("United States House "
                                          "of Representatives") else off
            out_rows.append(["Hunterdon", mu, off, "", "", "Not Assigned",
                             v])
    # vote-for-N contests can print two identical "NO NOMINATION MADE"
    # slots; number the repeats so (precinct, office, candidate) is unique
    counts = defaultdict(int)
    final = []
    for r in out_rows:
        key = (r[1], r[2], r[5], r[4])
        counts[key] += 1
        if counts[key] > 1:
            r = list(r)
            r[5] = f"{r[5]} ({counts[key]})"
        final.append(r)
    out_rows = final
    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "party",
                    "candidate", "votes"])
        w.writerows(out_rows)
    print(f"munis {len(stat_rows)}; cand rows {len(cand_rows)}; rows "
          f"{len(out_rows)}; errors {len(errors)}")
    for e in list(dict.fromkeys(errors))[:12]:
        print("  ", e)


if __name__ == "__main__":
    main()
