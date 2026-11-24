"""Parse Clarity Elections detail.xml files into precinct CSVs.

Inputs:  ~/code/openelections-sources-nj/2026/primary/<County> ... detail.xml
Outputs: 2026/counties/20260602__nj__primary__<county>__precinct.csv

Each XML is a Clarity "Election result snapshot" (Region <County>):
  <VoterTurnout totalVoters ballotsCast><Precincts><Precinct name .../>
  <Contest text="Office (party)" voteFor ...><VoteType name votes=total>
    <Precinct name votes/>...</VoteType>
    <Choice text party totalVotes><VoteType name votes=total>...</Choice>

The two counties use different report profiles:
  - Essex: contest text "Office (DEM)", per-contest Undervotes/Overvotes,
    candidate vote types Early Voting / Election Day / Mail-In / Provisional /
    Emergency Votes / Federal Votes. Its 508 per-precinct "County Committee
    (precinct) (party)" contests are excluded (repo precedent: county
    committee seats are not published in precinct CSVs).
  - Ocean: contest texts are ALL CAPS with a leading party token and are
    truncated at 55 characters ("TOWNSHIP OF BARNEGA"), so municipal names are
    completed from the full town names implied by the contest's covered
    precincts. Vote types Election Day / Early Voting / Mail-in / Provisional /
    Emergency / Overseas; candidates carry a party prefix ("REP Dana
    McDONALD") and a "REP NO PETITION FILED" placeholder choice is excluded.
    Its 836 per-precinct "MEMBER OF THE COUNTY COMMITTEE" contests are
    likewise excluded.

The `votes` column is the sum of all vote types (it matches the state's
official county totals); the remaining columns are the per-type breakdown.
Output headers and conventions mirror the 2024 Essex/Ocean precinct files.
"""

import csv
import os
import re
import xml.etree.ElementTree as ET

SOURCE_DIR = "/Users/dwillis/code/openelections-sources-nj/2026/primary"
OUTPUT_DIR = "2026/counties"
OUTPUT_PREFIX = "20260602__nj__primary"
COUNTY_CSV = "2026/20260602__nj__primary__county.csv"
CROSSCHECK_OFFICES = {"U.S. Senate", "U.S. House"}

BASE_HEADER = ["county", "precinct", "office", "district", "party",
               "candidate", "votes"]

PARTY_TOKEN = re.compile(r"^(REP|DEM)\s+")


# ---------------------------------------------------------------- helpers

def strip_trailing_party(text):
    """Essex: 'Office (DEM)' -> ('Office', 'DEM')."""
    m = re.match(r"^(.*) \(([A-Z]+)\)$", text)
    if not m:
        raise ValueError(f"Contest without party suffix: {text!r}")
    return m.group(1).strip(), m.group(2)


def normalize_precinct(name):
    """Precinct labels abbreviate 'Point Pleasant Beach' as 'Pt Pleasant Beach'
    (the 2024 precedent file spells the town out); expand for consistency."""
    return re.sub(r"^Pt ", "Point ", name) if name else name


def strip_leading_party(text):
    """Ocean: 'REP Office' -> ('Office', 'REP')."""
    m = PARTY_TOKEN.match(text)
    if m:
        return text[m.end():].strip(), m.group(1)
    return text, ""


def house_district(office):
    """('U.S. House', '8') from '... 11th Congressional District'; else None."""
    m = re.search(r"(\d+)\s*(ST|ND|RD|TH)\s+CON", office, re.IGNORECASE)
    if m:
        return "U.S. House", str(int(m.group(1)))
    return None, None


# ------------------------------------------------------- Essex contest text

def parse_essex_contest(text, precincts_covered):
    """(office, district, party) or None to skip."""
    office, party = strip_trailing_party(text)
    if office.startswith("County Committee"):
        return None
    if office == "United States Senator":
        return "U.S. Senate", "", party
    house = re.match(r"^Representative in Congress - (\d+)(st|nd|rd|th) "
                     r"Congressional District$", office, re.IGNORECASE)
    if house:
        return "U.S. House", str(int(house.group(1))), party
    return office, "", party


def parse_essex_candidate(text, contest_party):
    return text


# ------------------------------------------------------- Ocean contest text

def parse_ocean_contest(text, precincts_covered):
    """(office, district, party) or None; completes truncated town names."""
    office, party = strip_leading_party(text)
    if "COUNTY COMMITTEE" in office:
        return None
    if office == "MEMBER OF THE UNITED STATES SENATE":
        return "U.S. Senate", "", party
    house = re.match(r"^MEMBER OF THE HOUSE OF REPRESENTATIVES "
                     r"(\d+)(ND|ST|RD|TH)\s*CONGRESS", office)
    if house:
        return "U.S. House", str(int(house.group(1))), party

    # Term-duration suffixes ('... 1 YR') push the town fragment past the
    # 55-char cut; the 2024 precedent file keeps the suffix on the office,
    # so split it off and re-attach it after completing the town name.
    term = ""
    m_term = re.search(r"\s+\d+ YRS?$", office)
    if m_term:
        term = office[m_term.start() + 1:]
        office = office[:m_term.start()].rstrip()

    towns = {re.sub(r" District \d+$", "", normalize_precinct(p))
             for p in precincts_covered}
    tail = re.search(r"((TOWN|TOWNSHIP|BOROUGH) OF)\s+([A-Z0-9 ]+)$", office)
    if not tail:
        return office + (f" {term}" if term else ""), "", party
    kind, fragment = tail.group(1), tail.group(3).strip()
    # 'TOWNSHIP OF BRICK DIS' style fragments cut off 'DISTRICT'; those are
    # county committee contests, so completing them is just a safety net.
    district_suffix = ""
    words = fragment.split()
    last = words[-1] if words else ""
    if last and last != "DISTRICT" and "DISTRICT".startswith(last):
        fragment = " ".join(words[:-1]).strip()
        if len(precincts_covered) == 1:
            district_suffix = " DISTRICT " + re.search(
                r" District (\d+)$", precincts_covered[0]
            ).group(1)
        else:
            print(f"WARN Ocean: cannot complete district for {text!r}")
    matches = [t for t in towns if t.upper().startswith(fragment)]
    if not matches:
        print(f"WARN Ocean: no town matches fragment {fragment!r} in {text!r}")
        return office, "", party
    if len(matches) > 1:
        print(f"WARN Ocean: ambiguous town in {text!r}: {matches}")
        return office + (f" {term}" if term else ""), "", party
    return (office[:tail.start()].rstrip() + f" {kind} {matches[0].upper()}"
            + district_suffix + (f" {term}" if term else "")), "", party


def parse_ocean_candidate(text, contest_party):
    partyless, _ = strip_leading_party(text)
    if partyless.upper() == "NO PETITION FILED":
        return "No Petition"
    return partyless


PROFILES = [
    {
        "region": "Essex",
        "source": "Essex NJ 2026 primary detail.xml",
        "header": BASE_HEADER + ["early_voting", "emergency_votes", "mail",
                                 "federal_votes", "provisional",
                                 "election_day"],
        "vote_types": {"Early Voting": "early_voting",
                       "Emergency Votes": "emergency_votes",
                       "Mail-In": "mail", "Federal Votes": "federal_votes",
                       "Provisional": "provisional",
                       "Election Day": "election_day"},
        "parse_contest": parse_essex_contest,
        "parse_candidate": parse_essex_candidate,
    },
    {
        "region": "Ocean",
        "source": "Ocean NJ 2026 primary detail.xml",
        "header": BASE_HEADER + ["early_voting", "overseas", "mail-in",
                                 "provisional", "emergency", "election_day"],
        "vote_types": {"Early Voting": "early_voting", "Overseas": "overseas",
                       "Mail-in": "mail-in", "Provisional": "provisional",
                       "Emergency": "emergency",
                       "Election Day": "election_day"},
        "parse_contest": parse_ocean_contest,
        "parse_candidate": parse_ocean_candidate,
    },
]


# ------------------------------------------------------------------ parsing

def turnout_rows(root):
    """[(precinct, registered, ballots cast)] in document order."""
    return [
        (normalize_precinct(p.get("name")), int(p.get("totalVoters")),
         int(p.get("ballotsCast")))
        for p in root.find("VoterTurnout/Precincts").findall("Precinct")
    ]


def collect_warnings_and_rows(profile, root, turnout, warnings):
    """Build contest result rows and validate them.

    Returns a list of (precinct, office, district, party, candidate,
    values-dict) ordered by contest, covering every contest precinct.
    """
    rows = []
    contests_used = 0
    for contest in root.findall(".//Contest"):
        precinct_names = list(dict.fromkeys(
            normalize_precinct(p.get("name")) for p in contest.iter("Precinct")
        ))
        parsed = profile["parse_contest"](contest.get("text"), precinct_names)
        if parsed is None:
            continue  # county committee seat
        office, district, party = parsed
        contests_used += 1
        for choice in contest.findall("Choice"):
            candidate = profile["parse_candidate"](choice.get("text"), party)
            if candidate == "No Petition":
                continue
            # Per-precinct breakdown keyed by precinct; validate each
            # precinct's vote-type value appears at most once and that
            # precincts are real (from the turnout table).
            cells = {}
            for vt in choice.findall("VoteType"):
                column = profile["vote_types"].get(vt.get("name"))
                if column is None:
                    raise ValueError(
                        f"Unknown vote type {vt.get('name')!r} in "
                        f"{office!r}"
                    )
                for precinct in vt.findall("Precinct"):
                    name = normalize_precinct(precinct.get("name"))
                    if name not in turnout:
                        warnings.append(
                            f"{profile['region']} {office}: precinct "
                            f"{name!r} not in VoterTurnout; skipped"
                        )
                        continue
                    values = cells.setdefault(
                        name, dict.fromkeys(profile["vote_types"].values(), 0)
                    )
                    if values[column]:
                        raise ValueError(
                            f"{profile['region']} {office} {name} "
                            f"{candidate}: duplicate {vt.get('name')!r}"
                        )
                    values[column] = int(precinct.get("votes"))
            for precinct, values in cells.items():
                rows.append((precinct, office, district, party, candidate,
                             values))
            # choice total must equal its per-precinct total
            declared = int(choice.get("totalVotes"))
            if declared != cell_sum(cells, profile):
                warnings.append(
                    f"{profile['region']} {office} {candidate}: totalVotes "
                    f"{declared} != precinct sum {cell_sum(cells, profile)}"
                )
    return rows, contests_used


def cell_sum(cells, profile):
    return sum(
        sum(v.values()) for v in cells.values()
    ) if cells else 0


PARTY_NAMES = {"REP": "REPUBLICAN", "DEM": "DEMOCRATIC"}


def crosscheck_official(region, rows, warnings):
    """Compare U.S. Senate/House candidate sums to the official county CSV."""
    if not os.path.exists(COUNTY_CSV):
        print(f"CROSSCHECK: {COUNTY_CSV} not found; skipped")
        return

    def norm_party(p):
        return PARTY_NAMES.get(p, p).upper()

    official = {}
    with open(COUNTY_CSV) as f:
        for row in csv.DictReader(f):
            if row["county"] == region and row["office"] in CROSSCHECK_OFFICES:
                key = (row["office"], str(int(row["district"]))
                       if row["district"] else "", norm_party(row["party"]),
                       row["candidate"].upper())
                official[key] = int(row["votes"])
    tallies = {}
    for precinct, office, district, party, candidate, values in rows:
        if office in CROSSCHECK_OFFICES and candidate.upper() != "WRITE-IN":
            key = (office, str(district), norm_party(party or ""),
                   candidate.upper())
            tallies[key] = tallies.get(key, 0) + sum(values.values())
    for key in sorted(set(official) | set(tallies)):
        ours, theirs = tallies.get(key), official.get(key)
        if ours != theirs:
            warnings.append(
                f"{region} {key[0]} d{key[1]} {key[3]}: precinct total "
                f"{ours} vs official {theirs}"
            )


def write_csv(profile, turnout, contest_rows, output):
    os.makedirs(os.path.dirname(output), exist_ok=True)
    breakdown = profile["header"][7:]
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(profile["header"])
        n = 0
        for precinct, registered, ballots in turnout:
            # pad to header width so every row has the same column count
            pad = [""] * (len(profile["header"]) - 7)
            writer.writerow([profile["region"], precinct,
                             "Registered Voters", "", "", "", registered] + pad)
            writer.writerow([profile["region"], precinct, "Ballots Cast",
                             "", "", "", ballots] + pad)
            n += 2
        for precinct, office, district, party, candidate, values in contest_rows:
            total = sum(values.values())
            writer.writerow(
                [profile["region"], precinct, office, district, party,
                 candidate, total] + [values[col] for col in breakdown]
            )
            n += 1
    print(f"Wrote {n} rows to {output}")


def main():
    for profile in PROFILES:
        region = profile["region"]
        root = ET.parse(os.path.join(SOURCE_DIR, profile["source"])).getroot()
        turnout = turnout_rows(root)
        warnings = []
        rows, n_contests = collect_warnings_and_rows(
            profile, root, {p for p, _, _ in turnout}, warnings
        )
        print(f"== {region}: {n_contests} contests, {len(turnout)} precincts, "
              f"{len(rows)} contest rows")
        crosscheck_official(region, rows, warnings)
        for w in warnings:
            print("WARN:", w)
        if not warnings:
            print("   no warnings")
        output = os.path.join(
            OUTPUT_DIR,
            f"{OUTPUT_PREFIX}__{region.lower()}__precinct.csv",
        )
        write_csv(profile, turnout, rows, output)


if __name__ == "__main__":
    main()