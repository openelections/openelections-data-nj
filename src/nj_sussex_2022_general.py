"""Parse Sussex County's 2022 general election precinct results.

Source: "Sussex NJ Official-District-Summary-Suppressed-Nov-8-2022.pdf"
(217 pages), a Dominion "District Summary Results Report - Reporting Group
Details Suppressed" with one section per election district. Each section
starts with a "<Municipality>, District N Suppressed" line (printed once;
continuation pages carry no district line, so the district tracks state) and
holds Registered Voters / Voter Turnout statistics and then contests. Every
contest is an all-caps header line immediately followed by a "Vote For N"
line, then candidate rows:

    [<party token>] <candidate name> TOTAL [breakdown...]

Breakdown columns are suppressed to "*"; the FIRST number on each row is
the contest TOTAL and is published as `votes`. A few rows (all-zero
rows such as "Write-In Totals" / "No Petition Filed") print all six
columns; the extra numbers are validated against the TOTAL but not
published. Local contest headers repeat the municipality at the end
(e.g. "TOWNSHIP COMMITTEE Andover Twp Andover Township"); the repeated
municipal suffix is peeled using variants of the section's municipality.

Output: 2022/20221108__nj__general__sussex__precinct.csv with Registered
Voters, candidates, and Write-ins pseudo-rows (party kept as printed
abbreviations; no Ballots Cast row exists in this report).
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
PDF = (Path("/Users/dwillis/code/openelections-sources-nj/2022/") /
       "Sussex NJ Official-District-Summary-Suppressed-Nov-8-2022.pdf")
OUTPUT = BASE / "2022/20221108__nj__general__sussex__precinct.csv"

DISTRICT_RE = re.compile(
    r"^(?P<muni>[^,]+?),? District (?P<dist>\d+)(?: Suppressed)?$")
HOUSE_RE = re.compile(r"^U\.S\. HOUSE OF REPRESENTATIVES - (\d+)th ")
PARTY_RE = re.compile(r"^([A-Z]{2,3}) (.+)$")
PARTY_SET = {"REP", "DEM", "LIB", "GRN", "IND", "LBR", "CON", "PRO",
             "SSP", "NMI", "WF", "NLP"}
NUM_TOKEN_RE = re.compile(r"-?\d[\d,]*$")
SKIP_PREFIXES = ("Statistics", "Vote For", "Registered Voters",
                 "Voter Turnout", "TOTAL", "Day Voting", "Voting", "Mail-In",
                 "Provisional", "Emergenc", "Federal Overseas", "Federal",
                 "Overseas", "Precinct Summary", "Election Day")
TYPE_EXPAND = {"Twp": "Township", "Boro": "Borough", "Town": "Town",
               "City": "City"}


MUNI_FORMS = set()


def add_muni_forms(raw):
    """Register spellings of a municipality for peeling header tails."""
    raw = raw.strip()
    if not raw:
        return
    bare = re.sub(r"^(Town of |Borough of |City of |Township of )", "",
                  raw)
    MUNI_FORMS.update({raw, bare})
    if bare != raw:
        return
    m = re.match(r"^(.+?) (Twp|Boro|Town|City)$", raw)
    if m:
        MUNI_FORMS.add(f"{m.group(1)} {TYPE_EXPAND[m.group(2)]}")
        MUNI_FORMS.add(m.group(1))
    else:
        MUNI_FORMS.update({"Town of " + raw, "Township of " + raw,
                           "Borough of " + raw, "City of " + raw,
                           raw + " Boro", raw + " Borough",
                           raw + " Township", raw + " Town",
                           raw + " City"})


def peel_muni(header):
    """Strip trailing municipality mentions from a contest header."""
    forms = sorted((f for f in MUNI_FORMS if len(f) > 4), key=len,
                   reverse=True)
    label = header
    changed = True
    while changed and label:
        changed = False
        for form in forms:
            if label.lower().endswith(form.lower()):
                label = label[:len(label) - len(form)].rstrip()
                changed = True
                break
    label = re.sub(r"[-\s]+$", "", label).strip()
    if not label:
        label = header  # safety: never emit an empty office
    return label


FIXED = {"BD": "Board", "BOE": "Board of Education", "RGNL": "Regional",
         "WALLKILLL": "Wallkill",
         "OF": "of", "H.S.": "H.S.",
         "SUSSEX-WANTAGE": "Sussex-Wantage", "SANDYSTON-WALPACK":
         "Sandyston-Walpack", "1-YR": "1-Yr", "2-YR": "2-Yr", "3-YR":
         "3-Yr", "3-YR.": "3-Yr", "1-YR.": "1-Yr", "2-YR.": "2-Yr"}


def title_label(label):
    words = []
    for w in label.split():
        key = w.upper().rstrip(".")
        if key in FIXED:
            words.append(FIXED[key])
        elif key == "H.S":
            words.append("H.S.")
        elif w.isupper() and len(w) > 2:
            words.append(w.capitalize())
        else:
            words.append(w.capitalize() if w.islower() else w)
    return " ".join(words)


def office_from(header, muni=None):
    m = HOUSE_RE.match(header)
    if m:
        return "U.S. House", m.group(1)
    if header == "SHERIFF":
        return "Sheriff", ""
    if header == "COUNTY COMMISSIONER":
        return "County Commissioner", ""
    return title_label(peel_muni(header)), ""


def main():
    rows = []
    errors = []
    district = None
    muni_raw = None
    office = None
    dist_n = ""
    # first pass: collect municipality spellings
    pages_lines = []
    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            lines = [l.strip() for l in (page.extract_text() or "").split("\n")
                     if l.strip()]
            pages_lines.append((pno, lines))
            for line in lines:
                d = DISTRICT_RE.match(line)
                if d:
                    add_muni_forms(d["muni"])
    with pdfplumber.open(PDF) as pdf:
        for pno, lines in pages_lines:
            if any(re.match(r"^Federal OS \w+ Cong Dist Suppressed", l)
                   for l in lines):
                continue  # federal/overseas suppression-group page
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                d = DISTRICT_RE.match(line)
                if d and "Congressional" not in line:
                    muni_raw = d["muni"].strip()
                    muni = re.sub(r"^(Town of |Borough of |City of "
                                  r"|Township of )", "", muni_raw)
                    muni = (muni.replace(" Township", " Twp")
                            .replace(" Borough", " Boro"))
                    district = f"{muni} Dist {d['dist']}"
                    continue
                if line.startswith("Registered Voters - Total"):
                    n = int(line.split("Total")[1].replace(",", "").strip())
                    rows.append(["Sussex", district, "Registered Voters",
                                 "", "", "", n])
                    continue
                if any(line.startswith(p) for p in SKIP_PREFIXES):
                    continue
                if line == "Voter Turnout" or line.startswith("Voter "):
                    continue
                is_header = not NUM_TOKEN_RE.match(line.split()[-1])
                if is_header:
                    office, dist_n = office_from(line)
                    continue
                if office is None or district is None:
                    continue
                toks = line.split()
                nums = []
                j = len(toks)
                while j > 0 and NUM_TOKEN_RE.match(toks[j - 1]):
                    nums.append(toks[j - 1])
                    j -= 1
                nums = [int(x.replace(",", "")) for x in reversed(nums)]
                if not nums:
                    errors.append(f"p{pno} no-number line under {office}: "
                                  f"{line!r}")
                    continue
                rest = " ".join(toks[:j])
                votes = nums[0]
                if len(nums) > 1:
                    if sum(nums[1:]) != nums[0]:
                        errors.append(f"p{pno} {district} {office} "
                                      f"{line!r}: breakdown sum {sum(nums[1:])}"
                                      f" != total {nums[0]}")
                if rest in ("Write-In Totals", "No Nomination Made",
                            "No Petition Filed"):
                    rows.append(["Sussex", district, office, "", "",
                                 "Write-ins" and rest == "Write-In Totals"
                                 and "Write-ins" or rest, votes])
                    continue
                pm = PARTY_RE.match(rest)
                party, cand = "", rest
                if pm and pm.group(1) in PARTY_SET:
                    party, cand = pm.group(1), pm.group(2)
                rows.append(["Sussex", district, office, dist_n, party,
                             cand, votes])
    # some vote-for-N contests print two identical "No Nomination Made"
    # slots; number the repeats so (precinct, office, candidate) is unique
    counts = defaultdict(int)
    final = []
    for r in rows:
        key = (r[1], r[2], r[5], r[4])
        counts[key] += 1
        if counts[key] > 1:
            r = list(r)
            r[5] = f"{r[5]} ({counts[key]})"
        final.append(r)
    rows = final
    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "party",
                    "candidate", "votes"])
        w.writerows(rows)
    nd = len(set(r[1] for r in rows))
    print(f"wrote {len(rows)} rows; {nd} districts; {len(errors)} errors")
    for e in errors[:10]:
        print(" ", e)
    return rows, errors


if __name__ == "__main__":
    main()
