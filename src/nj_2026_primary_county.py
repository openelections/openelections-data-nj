"""Parse the official 2026 primary results PDFs into a county-level CSV.

Inputs: ~/code/openelections-sources-nj/2026/primary/
          2026-official-primary-results-us-senate.pdf
          2026-official-primary-results-us-house.pdf
Output: 2026/20260602__nj__primary__county.csv

Both PDFs are Division of Elections "Official List" tallies: one candidate per
block with 21 county rows (Senate) or one row per district county (House),
in three columns (County, Slogan, Tally) at fixed x positions. Slogans vary
by county and are not exported. In the House PDF each section is introduced
by a "First Congressional District: ..." header line.
"""

import re

from natural_pdf import PDF

SOURCE_DIR = "/Users/dwillis/code/openelections-sources-nj/2026/primary"
SOURCES = [
    ("2026-official-primary-results-us-senate.pdf", "U.S. Senate"),
    ("2026-official-primary-results-us-house.pdf", "U.S. House"),
]
OUTPUT = "2026/20260602__nj__primary__county.csv"

COUNTY_X0 = (300, 370)  # county name column
TALLY_X0 = 540  # rightmost column; vote tallies and page totals

ORDINALS = {
    "First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5, "Sixth": 6,
    "Seventh": 7, "Eighth": 8, "Ninth": 9, "Tenth": 10, "Eleventh": 11,
    "Twelfth": 12,
}

SENATE_COUNTIES = 21  # one row per NJ county per candidate


def is_number(text):
    return bool(re.fullmatch(r"\d{1,3}(,\d{3})*", text))


def words_to_lines(words, tol=2):
    """Group word elements into visual lines by top coordinate."""
    lines = []
    for w in sorted(words, key=lambda w: (w.top, w.x0)):
        if lines and abs(w.top - lines[-1][0].top) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w.x0) for line in lines]


def parse_candidates(pdf, with_districts):
    """Yield candidate records: name, party, district, county rows, PDF total.

    The tally column holds each candidate's rows, a row-group "Total", and a
    per-district "Total" at the end of each House section. A candidate's total
    is the first Total after its county rows; a Total seen with no open
    candidate block closes the district.
    """
    candidates = []
    district = None
    district_candidate_totals = []
    district_pdf_total = None
    cur = None
    expect_name_continuation = False

    def flush():
        if cur is None:
            return
        if not cur["rows"]:
            raise ValueError(f"Candidate {cur['name']} has no county rows")
        if cur["total"] is None:
            raise ValueError(f"Candidate {cur['name']} has no Total row")
        if cur["total"] != sum(v for _, v in cur["rows"]):
            raise ValueError(
                f"County totals for {cur['name']} don't match the PDF total "
                f"({cur['total']})"
            )
        if with_districts and district is None:
            raise ValueError(f"Candidate {cur['name']} has no district")
        candidates.append(cur.copy())
        if with_districts:
            district_candidate_totals.append(cur["total"])

    for page in pdf.pages:
        for line in words_to_lines(page.find_all("word")):
            line_text = " ".join(w.text for w in line)
            tally_words = [
                w for w in line if w.x0 >= TALLY_X0 and is_number(w.text)
            ]
            county_words = [
                w for w in line if COUNTY_X0[0] <= w.x0 < COUNTY_X0[1]
            ]

            district_match = re.match(
                r"(\w+) Congressional District:", line_text
            )
            if district_match:
                next_district = ORDINALS[district_match.group(1)]
                if next_district != district:
                    # The header repeats on continuation pages of the same
                    # district; only a new district flushes and resets.
                    flush()
                    cur = None
                    district = next_district
                    district_candidate_totals = []
                    district_pdf_total = None
                continue
            if county_words and tally_words:
                # Data row: county name (may wrap, but the tally sits on its
                # first line); the slogan between the columns is ignored.
                if cur is None:
                    raise ValueError(f"Data row before any candidate: {line_text}")
                county = " ".join(w.text for w in county_words)
                cur["rows"].append(
                    (county, int(tally_words[0].text.replace(",", "")))
                )
                continue
            if any(w.text == "Total" for w in line) and len(tally_words) == 1:
                total = int(tally_words[0].text.replace(",", ""))
                if cur is not None:
                    # Candidate total: the block is complete, so validate now.
                    cur["total"] = total
                    flush()
                    cur = None
                elif district_candidate_totals:
                    # District total closing the section.
                    district_pdf_total = total
                    expected = sum(district_candidate_totals)
                    if total != expected:
                        raise ValueError(
                            f"Candidate totals for district {district} sum to "
                            f"{expected}, PDF says {total}"
                        )
                    district_candidate_totals = []
                continue
            # Candidate line: name column plus a party word. The party token
            # can merge with the address element, so match on the line text
            # (slogans are all-caps, so title-case matches are unambiguous).
            party = next(
                (p for p in ("Democratic", "Republican") if p in line_text),
                None,
            )
            name_words = [
                w.text for w in line if w.x0 < 125 and not w.text[0].isdigit()
            ]
            # The trailing summary page lists party names in the name column
            # ("Democratic 38"); those aren't candidate lines.
            if party and name_words and not any(
                w.x0 < 125 and w.text in ("Democratic", "Republican")
                for w in line
            ):
                # A candidate block can straddle a page break: the name line
                # repeats under the next page's header before the block ends.
                if (
                    cur is not None
                    and cur["total"] is None
                    and " ".join(name_words) == cur["name"]
                ):
                    continue
                flush()
                cur = {
                    "name": " ".join(name_words),
                    "party": party,
                    "district": district if with_districts else None,
                    "rows": [],
                    "total": None,
                }
                expect_name_continuation = True
                continue
            # A long candidate name wraps to a second line in the name
            # column (e.g. "VERLINA REYNOLDS-" / "JACKSON").
            if expect_name_continuation and cur is not None and not (
                party or county_words or tally_words
            ):
                continuation = " ".join(
                    w.text for w in line if w.x0 < 125 and not w.text[0].isdigit()
                )
                if continuation and "Slogan" not in continuation:
                    cur["name"] += (
                        continuation
                        if cur["name"].endswith("-")
                        else " " + continuation
                    )
                    continue
            expect_name_continuation = False

    flush()
    if district_candidate_totals:
        raise ValueError(
            f"District {district} candidates sum to "
            f"{sum(district_candidate_totals)} with no closing PDF total"
        )
    return candidates


def main():
    all_records = []
    for filename, office in SOURCES:
        pdf = PDF(f"{SOURCE_DIR}/{filename}")
        candidates = parse_candidates(pdf, office == "U.S. House")
        if office == "U.S. Senate" and len(candidates) != 5:
            raise ValueError(f"Expected 5 Senate candidates, got {len(candidates)}")
        if office == "U.S. House" and len(candidates) != 52:
            raise ValueError(f"Expected 52 House candidates, got {len(candidates)}")
        print(f"{office}: {len(candidates)} candidates, "
              f"{sum(len(c['rows']) for c in candidates)} county rows")
        for cand in candidates:
            for county, votes in cand["rows"]:
                all_records.append((county, office, cand, votes))

    with open(OUTPUT, "w") as f:
        f.write("county,office,district,party,candidate,votes\n")
        for county, office, cand, votes in all_records:
            # Strip the PDF's winner marker "(w)" and incumbent marker "*".
            name = cand["name"].replace(" (w)", "").replace(" *", "")
            district = cand["district"] or ""
            f.write(
                f"{county.title()},{office},{district},{cand['party']},"
                f"{name},{votes}\n"
            )

    print(f"Wrote {len(all_records)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()