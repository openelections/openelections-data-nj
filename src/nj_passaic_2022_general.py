"""Parse Passaic County's 2022 general election precinct results.

Source: "Passaic NJ 2022 Election Results Summ.pdf" (609 pages), an
Electionware "Summary Results Report" with one section (1-3 pages) per
election district. Every page repeats the report header ("2022 11
PASSAIC General ELECTION <Municipality> By District / District Report");
the district is announced only on a section's first page, ALWAYS as the
4th line: "<Municipality> [W<n> ]D<n>[ <n>] Suppressed". Each district's
table also reprints once per suppression group ("... Federal
Suppressed" / "... Overseas/Emer. Prov. Suppressed"); those group pages
carry only that vote group's numbers and are skipped — only BASE pages
publish, and the aggregate TOTAL is the FIRST number of every data row.

Per contest: a header line, "Vote For N", column headers, candidate
rows "<PARTY> <name> TOTAL [breakdown...]", "Write-In Totals",
"Total Votes Cast" (= candidates + write-ins), "Contest Totals".
Fully suppressed rows print no number and are skipped. Validation:
sum(candidates) + write-ins == Total Votes Cast, and Contest Totals >=
TVC.

Output: 2022/20221108__nj__general__passaic__precinct.csv with
Registered Voters, Ballots Cast, candidates, and Write-ins rows; the
section municipality token is stripped from contest labels.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

BASE = Path("/Users/dwillis/code/openelections-data-nj")
PDF = (Path("/Users/dwillis/code/openelections-sources-nj/2022/") /
       "Passaic NJ 2022 Election Results Summ.pdf")
OUTPUT = BASE / "2022/20221108__nj__general__passaic__precinct.csv"

REPORT_RE = re.compile(r"^2022 11 PASSAIC General ELECTION (.+?) "
                       r"(By District|District Report)$")
DISTRICT_RE = re.compile(
    r"^(?P<muni>[A-Za-z .'-]+?) (?P<dist>(?:W\d+ )?D\d+|\d+(?: \d+)?)"
    r"\s+Suppressed$")
GROUP_RE = re.compile(r"Federal|Overseas")
HOUSE_RE = re.compile(r"Member House of Representatives, (\d+)(?:st|nd|rd|"
                      r"th) Cong")
PARTY_RE = re.compile(r"^([A-Z]{2,4}) (.+)$")
PARTY_SET = {"REP", "DEM", "LIB", "GRN", "IND", "BOE", "NME", "NMC",
             "NMD", "NMI", "CON", "PRO", "SSP", "NLP", "WF"}
RESERVED = ("Statistics", "TOTAL", "Vote For", "Registered Voters",
            "Voter Turnout", "Day", "Voting", "Mail-In", "Provisional",
            "Fed/Overs", "eas/", "Prov.", "Ballots Cast", "Election")


NUM_TOKEN_RE = re.compile(r"^-?\d[\d,]*$")


def digits(s):
    return [int(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*", s)]


def dist_label(dist_str):
    """'W1 D18' -> 'W1 Dist 18'; '1' -> 'Dist 1'."""
    s = re.sub(r"\bD(\d+)", r"Dist \1", dist_str.strip())
    if not s.startswith(("W", "Dist")):
        s = "Dist " + s
    return re.sub(r"\s+", " ", s).strip()


def main():
    stats = defaultdict(dict)     # (muni, dist) -> rv/bc
    cands = defaultdict(dict)     # (muni, dist) -> {(ok, cand): (party,v)}
    contest_meta = defaultdict(dict)  # (muni, dist, ok) -> tvc/ct/wi
    errors = []
    probs = []
    pages = 0
    group_pages = 0
    cur_muni = cur_dist = None
    office = None
    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            if pno < 12:
                continue   # county summary pages (1-11)
            lines = [l.strip() for l in (page.extract_text() or "").split("\n")
                     if l.strip()]
            if not lines:
                continue
            m2 = REPORT_RE.match(lines[1]) if len(lines) > 1 else None
            if not m2:
                errors.append(f"p{pno}: no report header")
                continue
            cur_muni = m2.group(1)
            # district line (if any) always sits at lines[3]; group pages
            # repeat the district with a vote-group name ("... Federal")
            d = DISTRICT_RE.match(lines[3]) if len(lines) > 3 else None
            d3 = DISTRICT_RE.match(lines[3]) if len(lines) > 3 else None
            if d3 is None and len(lines) > 3 and \
                    re.search(r"[A-Za-z .'-]+ +"
                              r"(Federal|Overseas/Emer\. Prov\.?)"
                              r"( Suppressed)?$", lines[3]):
                group_pages += 1
                continue   # suppression-group page: skip entirely
            section_start = bool(d) and "Congress" not in lines[3] and \
                d["muni"].strip() == cur_muni
            if section_start:
                cur_dist = dist_label(d["dist"])
                office = None
            pages += 1
            # group pages can precede any DISTRICT_RE match: detect by the
            # trailing group name
            if len(lines) > 3 and re.match(
                    r"^[A-Za-z .'-]+ (?:W\d+ )?(?:D?\d+(?: \d+)?)? ?"
                    r"(?:Federal|Overseas/Emer\. Prov\.?)( Suppressed)?$",
                    lines[3]):
                group_pages += 1
                continue   # suppression-group page: skip entirely
            for line in lines[3:]:
                if section_start and line == lines[3]:
                    continue   # the district line, already consumed
                if line.startswith("Registered Voters - Total"):
                    stats[(cur_muni, cur_dist)].setdefault(
                        "rv", digits(line)[0])
                    office = None
                    continue
                if line.startswith("Ballots Cast - Total"):
                    stats[(cur_muni, cur_dist)].setdefault(
                        "bc", digits(line)[0])
                    office = None
                    continue
                hm = HOUSE_RE.match(line)
                if hm:
                    office = ("U.S. House", hm.group(1))
                    continue
                if any(line.startswith(p) for p in RESERVED):
                    continue
                if re.search(r"\d\d/\d\d/20\d\d|\d+:\d\d ?[AP]M", line) or \
                        re.search(r"Report generated with", line):
                    continue
                # contest headers may embed year-term suffixes ("2YT"); a
                # line whose only digits are such suffixes is a header
                probe = re.sub(r"\d+YT", "", line)
                nums = digits(probe)
                if cur_dist is None:
                    continue
                okey = str(office) if office is not None else None
                key3 = (cur_muni, cur_dist, okey)
                if okey and line.startswith("Write-In Totals"):
                    if nums:
                        contest_meta[key3]["wi"] = max(
                            contest_meta[key3].get("wi", 0), nums[0])
                    continue
                if okey and line.startswith("Total Votes Cast"):
                    if nums:
                        contest_meta[key3]["tvc"] = max(
                            contest_meta[key3].get("tvc", 0), nums[0])
                    continue
                if okey and line.startswith("Contest Totals"):
                    if nums:
                        contest_meta[key3]["ct"] = max(
                            contest_meta[key3].get("ct", 0), nums[0])
                    continue
                if nums:
                    if okey is None:
                        errors.append(f"p{pno} {cur_dist}: data row "
                                      f"outside contest: {line!r}")
                        continue
                    toks = line.split()
                    vals = []
                    j = len(toks)
                    while j > 0 and NUM_TOKEN_RE.match(toks[j - 1]):
                        vals.append(toks[j - 1])
                        j -= 1
                    vals = [int(v.replace(",", "")) for v in
                            reversed(vals)]
                    ptoks = toks[:j]
                    pm = PARTY_RE.match(" ".join(ptoks))
                    party, cand = "", " ".join(ptoks)
                    if pm and pm.group(1) in PARTY_SET:
                        party, cand = pm.group(1), pm.group(2).strip()
                    votes = vals[0] if vals else None
                    if votes is None:
                        continue
                    ck = (okey, cand)
                    prev = cands[(cur_muni, cur_dist)].get(ck)
                    if prev:
                        cands[(cur_muni, cur_dist)][ck] = (
                            party or prev[0], max(prev[1], votes))
                    else:
                        cands[(cur_muni, cur_dist)][ck] = (party, votes)
                    continue
                # no digits: a suppressed candidate row (has PARTY token)
                # or the next contest header
                if PARTICIPANT_RE := None:
                    pass
                pm = PARTY_RE.match(line)
                if pm and pm.group(1) in PARTY_SET:
                    errors.append(f"p{pno} {cur_dist} {okey}: suppressed "
                                  f"row {line!r}")
                    continue
                office = " ".join(line.split())
    # ---- validation
    for key3, meta in sorted(contest_meta.items(),
                             key=lambda t: (t[0][0], str(t[0][1]),
                                            str(t[0][2]))):
        muni, dist, okey = key3
        cdict = cands[(muni, dist)]
        rows_ = {ck: v for ck, v in cdict.items() if str(ck[0]) == okey}
        tot = sum(v for _, (p, v) in rows_.items())
        wi = meta.get("wi", 0)
        tvc = meta.get("tvc")
        ct = meta.get("ct")
        if tvc is None:
            errors.append(f"{muni} {dist} {okey}: no TVC")
            continue
        if tot + wi != tvc:
            probs.append(f"{muni} {dist} {okey}: cands {int(tot)}+wi "
                         f"{int(wi)} vs TVC {tvc}")
        elif ct is not None and ct < tvc:
            probs.append(f"{muni} {dist} {okey}: ct {ct} < tvc {tvc}")
    # ---- output
    out_rows = []
    for (muni, dist), st in sorted(stats.items(),
                                   key=lambda t: (t[0][0].lower(),
                                                  str(t[0][1]))):
        label = f"{muni} {dist}"
        if st.get("rv"):
            out_rows.append(["Passaic", label, "Registered Voters", "",
                             "", "", st["rv"]])
        if st.get("bc"):
            out_rows.append(["Passaic", label, "Ballots Cast", "", "", "",
                             st["bc"]])
    for (muni, dist), cdict in sorted(cands.items(),
                                      key=lambda t: (t[0][0].lower(),
                                                     str(t[0][1]))):
        label = f"{muni} {dist}"
        muni_stripped = re.sub(
            r"^(Township of |Town of |Borough of |City of )", "", muni)
        for (okey, cand), (party, votes) in sorted(
                cdict.items(), key=lambda t: (str(t[0][0]), t[0][1])):
            if okey is None:
                errors.append("no office")
                continue
            if okey.startswith("('U.S. House'"):
                off, odst = "U.S. House", okey.split("'")[3]
            else:
                odst, off = "", okey
                # strip the municipality mention from printed headers
                toks = off.split()
                while len(toks) > 1 and toks[-1].rstrip(",") in (
                        muni, muni_stripped,
                        muni_stripped.replace(" ", "")):
                    toks.pop()
                off = " ".join(toks) or off
            out_rows.append(["Passaic", label, off, odst,
                             party if cand != "Write-ins" else "", cand,
                             votes])
    with open("OUTPUT_PLACEHOLDER" if False else
              str(OUTPUT), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "party",
                    "candidate", "votes"])
        w.writerows(out_rows)
    print(f"pages {pages}; group pages {group_pages}; districts "
          f"{len(stats)}; rows {len(out_rows)}; problems {len(probs)}; "
          f"errors {len(errors)}")
    for p in probs[:15]:
        print("  P:", p)
    for e in list(dict.fromkeys(errors))[:10]:
        print("  E:", e)
    return out_rows, probs, errors, contest_meta, cands


if __name__ == "__main__":
    main()
    print("done")
