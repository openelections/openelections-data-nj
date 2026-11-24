"""Parse Warren County's 2026 primary precinct-level report into a CSV.

Input:  ~/code/openelections-sources-nj/2026/primary/Warren NJ 2026 Primary Precinct Level Report.pdf
Output: 2026/counties/20260602__nj__primary__warren__precinct.csv

The PDF is a Dominion "Custom Table Report" with two sections:
  - STATISTICS pages: one row per precinct (registered voters total/rep/dem,
    ballots cast total/rep/dem/blank), ending in a 'Totals' row.
  - Contest sections: one row per precinct per contest, each row being
    [candidate columns..., Write-in, Totals Cast, Overvotes, Undervotes,
    Contest Total].

The embedded text has scrambled per-character positioning, so words come from
pdfplumber and are grouped into lines with coordinates. A few pages place two
contests side by side on shared lines ("REP [House 7th] REP County
Commissioner", or two towns' committee contests). Those pages are split into
left/right strips at the column boundary that makes both halves' totals
consistent. Continuation pages repeat a contest's header and are merged.
Candidate names are reconstructed from stacked header words; corrections live
in NAME_FIXES. Output conventions follow
2024/20241105__nj__general__warren__precinct.csv (REP/DEM party abbreviations,
Registered Voters / Ballots Cast / Blank Ballots Cast pseudo-offices,
Write-ins / Over Votes / Under Votes pseudocandidates).
"""

import re

import pdfplumber

SOURCE = (
    "/Users/dwillis/code/openelections-sources-nj/2026/primary/"
    "Warren NJ 2026 Primary Precinct Level Report.pdf"
)
OUTPUT = "2026/counties/20260602__nj__primary__warren__precinct.csv"

# The PDF shortens municipality names; the rest of the repo (e.g. the 2024
# Warren precinct file) spells them out.
TOWNS = {
    "Allamuchy": "Allamuchy Township",
    "Alpha": "Borough of Alpha",
    "Belvidere": "Town of Belvidere",
    "Blairstown": "Township of Blairstown",
    "Franklin": "Franklin Township",
    "Frelinghuysen": "Frelinghuysen Township",
    "Greenwich": "Township of Greenwich",
    "Hackettstown": "Town of Hackettstown",
    "Hardwick": "Township of Hardwick",
    "Harmony": "Township of Harmony",
    "Hope": "Hope Township",
    "Independence": "Independence Township",
    "Knowlton": "Township of Knowlton",
    "Liberty": "Liberty Township",
    "Lopatcong": "Township of Lopatcong",
    "Mansfield": "Township of Mansfield",
    "Oxford": "Township of Oxford",
    "Phillipsburg": "Town of Phillipsburg",
    "Pohatcong": "Township of Pohatcong",
    "Washington Borough": "Borough of Washington",
    "Township of Washington": "Washington Township",
    "White Township": "Township of White",
}

# Candidate headers stack name parts with scrambled glyph positions, so the
# top-down join occasionally reads "Last First M.I." or appends a trailing
# middle initial. Verified against the PDF's word coordinates.
NAME_FIXES = {
    "Anna Skoog Marie": "Anna Marie Skoog",
    "Bonnie Kelsey L.": "Bonnie L. Kelsey",
    "Bronico, James Jr. V.": "James V. Bronico, Jr.",
    "Chamberlin Suzanne": "Suzanne Chamberlin",
    "Deborah Bonanno A.": "Deborah A. Bonanno",
    "Edward France S.": "Edward S. France",
    "Gesumaria Kathleen": "Kathleen Gesumaria",
    "Harrington Kasey": "Kasey Harrington",
    "Hofmann Sharon": "Sharon Hofmann",
    "Lohman G. Eric": "Eric G. Lohman",
    "Michael Kovacs J.": "Michael J. Kovacs",
    "Parichuk Dale E.": "Dale E. Parichuk",
    "Robert Lebovics S.": "Robert S. Lebovics",
    "Spangenberg Wayne": "Wayne Spangenberg",
    "Thomas Kean, Jr. H.": "Thomas H. Kean Jr.",
    "William Sosis N.": "William N. Sosis",
    "William Wright D.": "William D. Wright",
}

PARTIES = ("REP", "DEM")
LABEL_COL_X1 = 175  # row-label words end left of here; value columns start after
FOOTER_COL_X = 700  # page-footer numbers sit right of the last value column
COUNTYWIDE_ROWS = 86
TOWN_ORDER = sorted(TOWNS, key=len, reverse=True)  # longest prefix wins


def is_number(text):
    return bool(re.fullmatch(r"\d{1,3}(,\d{3})*", text))


def to_lines(words, tol=2.0):
    """Group word dicts into visual lines by top coordinate."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def precinct_name(pdf_label):
    """Map a PDF precinct label ('Allamuchy District 1') to the repo form."""
    town, sep, district = pdf_label.rpartition(" District ")
    if not sep:
        raise ValueError(f"Can't split precinct label {pdf_label!r}")
    if town not in TOWNS:
        raise ValueError(f"Unknown town in precinct label {pdf_label!r}")
    return f"{TOWNS[town]} District {district}"


def parse_statistics(pdf):
    """Return ({pdf precinct label: stats dict}, warnings) from the stats table.

    The table ends with a 'Totals' row that shares a page with the first
    contest section; parsing stops there.
    """
    stats = {}
    warnings = []
    done = False
    for page in pdf.pages[:3]:
        if done:
            break
        for line in to_lines(page.extract_words()):
            if "District" not in " ".join(w["text"] for w in line):
                continue
            label_words = [w for w in line if w["x1"] < LABEL_COL_X1]
            numbers = [
                w for w in line if is_number(w["text"]) and w["x0"] >= LABEL_COL_X1
            ]
            if not label_words or len(numbers) != 7:
                continue
            label = " ".join(w["text"] for w in label_words)
            if label.startswith("Totals"):
                done = True
                break
            reg_total, reg_rep, reg_dem, cast_total, cast_rep, cast_dem, blank = (
                int(w["text"].replace(",", "")) for w in numbers
            )
            if cast_rep + cast_dem + blank != cast_total:
                warnings.append(
                    f"{label}: REP {cast_rep} + DEM {cast_dem} + blank {blank} "
                    f"= {cast_rep + cast_dem + blank} ballots, but total is {cast_total}"
                )
            stats[label] = {
                "registered": reg_total,
                "cast_total": cast_total,
                "cast_rep": cast_rep,
                "cast_dem": cast_dem,
                "blank": blank,
            }
    if len(stats) != COUNTYWIDE_ROWS:
        raise ValueError(f"Expected {COUNTYWIDE_ROWS} precincts, got {len(stats)}")
    return stats, warnings


def cluster_x(centers, gap=25):
    """Cluster sorted x0 values into numeric columns; returns centers."""
    columns = []
    for x in centers:
        if columns and x - columns[-1][-1] <= gap:
            columns[-1].append(x)
        else:
            columns.append([x])
    return [sum(c) / len(c) for c in columns]


def contest_title(title):
    """Map a contest title to (office, district) with canonical names."""
    text = re.sub(r"Dis\s*trict", "District", title).strip()
    m = re.search(r"(\d+)th Congressional District", text)
    if m:
        return "U.S. House", int(m.group(1))
    if "United States Senator" in text:
        return "U.S. Senate", None
    text = re.sub(r"^(REP|DEM)\s+", "", text)
    return text, None


def town_of_label(label):
    for town in TOWN_ORDER:
        if label.startswith(town):
            return town
    return None


def find_split(lines):
    """Column-cluster split for a side-by-side page, or None if single contest.

    Both tables share visual lines, so a row can carry one or both contests'
    numbers. A valid split index makes every half with numbers on a line have
    sum(candidates) == totals-cast and totals-cast + over + under == total.
    """
    data_rows = [
        ln for ln in lines
        if [w for w in ln if w["x1"] < LABEL_COL_X1 and w["text"] not in PARTIES]
        and any(is_number(w["text"]) and w["x0"] >= LABEL_COL_X1 for w in ln)
    ]
    numbers = [
        w for ln in data_rows for w in ln
        if is_number(w["text"]) and LABEL_COL_X1 <= w["x0"] < FOOTER_COL_X
    ]
    clusters = cluster_x(sorted(w["x0"] for w in numbers))

    def half_ok(cluster_set):
        for ln in data_rows:
            nums = [
                w for w in ln
                if is_number(w["text"]) and LABEL_COL_X1 <= w["x0"] < FOOTER_COL_X
            ]
            values = []
            for c in cluster_set:
                matches = [w for w in nums if abs(w["x0"] - c) <= 21]
                if len(matches) != 1:
                    values = None
                    break
                values.append(int(matches[0]["text"].replace(",", "")))
            if values is None:
                if any(
                    abs(w["x0"] - c) <= 21
                    for c in cluster_set for w in nums
                ):
                    return False  # partially populated half
                continue  # this contest's numbers are on the other half
            if sum(values[:-4]) != values[-4] or \
                    values[-4] + values[-3] + values[-2] != values[-1]:
                return False
        return True

    valid = [
        s for s in range(5, len(clusters) - 4)
        if len(clusters[:s]) >= 5 and len(clusters[s:]) >= 5
        and half_ok(clusters[:s]) and half_ok(clusters[s:])
    ]
    return clusters, valid


def parse_contest_unit(lines, stats, warnings, page_no):
    """Parse one contest block (a page or half-page of lines) -> dict or None."""
    header_line = next(
        (ln for ln in lines if ln[0]["text"] in PARTIES and len(ln) > 1), None
    )
    if header_line is None:
        return None
    party = next(w["text"] for w in header_line if w["text"] in PARTIES)

    title = party
    title_done = False
    header_lines = []
    data_rows = []
    for ln in lines:
        joined = " ".join(w["text"] for w in ln)
        if ln is header_line:
            title = joined
            continue
        if "VOTE FOR" in joined:
            title_done = True
            continue
        if "Precincts Reporting" in joined:
            continue
        label_words = [w for w in ln if w["x1"] < LABEL_COL_X1 and w["x0"] < 300]
        numbers = [
            w for w in ln
            if is_number(w["text"]) and LABEL_COL_X1 <= w["x0"] < FOOTER_COL_X
        ]
        if label_words and numbers:
            if label_words[0]["text"] in ("Totals", "Warren"):
                continue  # contest totals row / page footer
            data_rows.append((label_words, numbers))
        elif not title_done:
            title += f" {joined}"
        elif not data_rows:
            header_lines.append(ln)
    office, district = contest_title(title)

    if not data_rows:
        raise ValueError(f"No data rows for {party} {office} (p{page_no})")

    # Grid from the first data row; every row must fill every column.
    grid = cluster_x([w["x0"] for w in data_rows[0][1]], gap=21)

    def cell_values(number_words):
        values = []
        for c in grid:
            matches = [w for w in number_words if abs(w["x0"] - c) <= 21]
            if len(matches) != 1:
                raise ValueError(
                    f"{party} {office} (p{page_no}): expected one value in "
                    f"column {c}, got {[w['text'] for w in matches]}"
                )
            values.append(int(matches[0]["text"].replace(",", "")))
        return values

    rows = []
    for label_words, number_words in data_rows:
        label = " ".join(w["text"] for w in label_words)
        if label not in stats:
            raise ValueError(f"Unknown precinct {label!r} in {party} {office}")
        rows.append((label, cell_values(number_words)))

    # Candidate names: header words over the columns left of the 4 summary
    # columns (Totals Cast, Overvotes, Undervotes, Contest Total).
    header_words = [w for ln in header_lines for w in ln]
    names = []
    for center in grid[:-4]:
        words = [w for w in header_words if abs(w["x0"] - center) <= 21]
        raw = " ".join(w["text"] for w in sorted(words, key=lambda w: w["top"]))
        names.append(NAME_FIXES.get(raw, raw))
    names = ["No Petition" if n.startswith("No Petition") else n for n in names]

    return {
        "party": party, "office": office, "district": district,
        "names": names, "rows": rows, "first_page": page_no,
    }


def drop_stats_lines(lines):
    """Drop the statistics table that shares page 3 with the first contest."""
    for i, ln in enumerate(lines):
        label_words = [w for w in ln if w["x1"] < LABEL_COL_X1]
        has_numbers = any(
            is_number(w["text"]) and w["x0"] >= LABEL_COL_X1 for w in ln
        )
        if label_words and label_words[0]["text"] == "Totals" and has_numbers:
            return lines[i + 1:]
    raise ValueError("Page 3: statistics Totals row not found")


def merge_unit(unit, contests, warnings):
    """Merge a parsed contest block into the running contest list."""
    for existing in contests:
        if (existing["party"], existing["office"], existing["district"]) == (
            unit["party"], unit["office"], unit["district"]
        ):
            if existing["names"] != unit["names"]:
                warnings.append(
                    f"{unit['party']} {unit['office']}: header names differ "
                    f"between pages ({existing['names'][:2]}... vs "
                    f"{unit['names'][:2]}...); keeping the first set"
                )
            seen = {label: values for label, values in existing["rows"]}
            for label, values in unit["rows"]:
                if label in seen:
                    if seen[label] != values:
                        raise ValueError(
                            f"{unit['party']} {unit['office']}: conflicting "
                            f"values for {label}"
                        )
                else:
                    seen[label] = values
                    existing["rows"].append((label, values))
            return
    contests.append(unit)


def validate_contests(contests, stats, warnings):
    """Cross-check each contest against the statistics table."""
    for contest in contests:
        party = contest["party"]
        office = contest["office"]
        if "write" not in contest["names"][-1].lower():
            warnings.append(
                f"{party} {office}: last column is "
                f"{contest['names'][-1]!r}, expected the Write-in column"
            )
        labels = [label for label, _ in contest["rows"]]
        if contest["district"] is None and office in ("U.S. Senate", "U.S. House"):
            # Countywide contests: exactly one row per precinct.
            if len(labels) != COUNTYWIDE_ROWS or set(labels) != set(stats):
                missing = set(stats) - set(labels)
                extra = set(labels) - set(stats)
                warnings.append(
                    f"{party} {office}: {len(labels)} rows (expected "
                    f"{COUNTYWIDE_ROWS}); missing {sorted(missing)[:3]}, "
                    f"extra {sorted(extra)[:3]}"
                )
        else:
            # Municipal contest: every row belongs to the contest's town.
            towns = {town_of_label(label) for label in labels}
            if len(towns) != 1 or None in towns:
                warnings.append(
                    f"{party} {office}: rows span towns {sorted(str(t) for t in towns)}"
                )
            else:
                town = towns.pop()
                expected = sum(1 for s in stats if s.startswith(town))
                if len(labels) != expected:
                    warnings.append(
                        f"{party} {office}: {len(labels)} rows for {town}, "
                        f"expected {expected}"
                    )
        for label, values in contest["rows"]:
            candidates, cast, over, under, total = (
                values[:-4], values[-4], values[-3], values[-2], values[-1]
            )
            if sum(candidates) != cast:
                warnings.append(
                    f"{party} {office} {label}: candidates sum to "
                    f"{sum(candidates)}, totals-cast is {cast}"
                )
            if cast + over + under != total:
                warnings.append(
                    f"{party} {office} {label}: cast {cast} + over {over} + "
                    f"under {under} != contest total {total}"
                )
            for name, votes in zip(contest["names"][:-1], candidates[:-1]):
                if votes != 0 and name == "No Petition":
                    warnings.append(
                        f"{party} {office} {label}: {name} has {votes} votes"
                    )
            if over != 0:
                warnings.append(
                    f"{party} {office} {label}: {over} overvotes"
                )
            ballots = stats[label]["cast_rep" if party == "REP" else "cast_dem"]
            if total != ballots:
                warnings.append(
                    f"{party} {office} {label}: contest total {total} vs "
                    f"{party.lower()} ballots cast {ballots} in statistics"
                )


def write_csv(contests, stats):
    import csv
    import os

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["county", "precinct", "office", "district", "party",
             "candidate", "votes"]
        )
        n_rows = 0
        for label, s in stats.items():
            precinct = precinct_name(label)
            # Pseudo-office rows, then contest rows per the 2024 file's order.
            writer.writerow(
                ["Warren", precinct, "Registered Voters", "", "", "",
                 s["registered"]]
            )
            writer.writerow(
                ["Warren", precinct, "Ballots Cast", "", "", "", s["cast_total"]]
            )
            writer.writerow(
                ["Warren", precinct, "Blank Ballots Cast", "", "", "",
                 s["blank"]]
            )
            n_rows += 3
            for contest in contests:
                all_rows = dict(contest["rows"])
                if label not in all_rows:
                    # Municipal contests only cover their own municipality.
                    continue
                values = all_rows[label]
                # values = [candidates..., Totals Cast, Overvotes,
                # Undervotes, Contest Total]
                candidates, under = values[:-4], values[-2]
                district = (
                    str(contest["district"])
                    if contest["district"] is not None else ""
                )
                for name, votes in zip(contest["names"][:-1], candidates[:-1]):
                    if name == "No Petition":
                        continue
                    writer.writerow(
                        ["Warren", precinct, contest["office"], district,
                         contest["party"], name, votes]
                    )
                    n_rows += 1
                writer.writerow(
                    ["Warren", precinct, contest["office"], district,
                     contest["party"], "Write-ins", candidates[-1]]
                )
                writer.writerow(
                    ["Warren", precinct, contest["office"], district,
                     contest["party"], "Under Votes", under]
                )
                n_rows += 2
    print(f"Wrote {n_rows} rows to {OUTPUT}")


def parse_contests(pdf, stats):
    contests = []
    warnings = []
    for page_no, page in enumerate(pdf.pages[2:], start=3):
        lines = to_lines(page.extract_words())
        # Skip the front-of-report statistics table (ends on the page that
        # starts the first contest).
        if page_no == 3:
            lines = drop_stats_lines(lines)

        header_lines = [
            ln for ln in lines if ln[0]["text"] in PARTIES and len(ln) > 1
        ]
        if not header_lines:
            raise ValueError(f"p{page_no}: no contest header found")
        party_tokens = [
            w for w in header_lines[0] if w["text"] in PARTIES
        ]

        if len(party_tokens) == 1:
            unit = parse_contest_unit(lines, stats, warnings, page_no)
            units = [unit]
        else:
            # Side-by-side contests: split at the validated column boundary.
            clusters, valid = find_split(lines)
            if len(valid) != 1:
                raise ValueError(
                    f"p{page_no}: ambiguous column split, candidates {valid} "
                    f"of {len(clusters)} clusters"
                )
            s = valid[0]
            split_x = (clusters[s - 1] + clusters[s]) / 2
            left = [
                w for w in page.extract_words() if w["x1"] <= split_x
            ]
            right = [
                w for w in page.extract_words()
                if w["x0"] >= split_x or w["x1"] < LABEL_COL_X1
            ]
            left_unit = parse_contest_unit(to_lines(left), stats, warnings, page_no)
            right_unit = parse_contest_unit(to_lines(right), stats, warnings, page_no)
            units = [left_unit, right_unit]
        for unit in units:
            merge_unit(unit, contests, warnings)
    validate_contests(contests, stats, warnings)
    return contests, warnings


def main():
    pdf = pdfplumber.open(SOURCE)
    stats, warnings = parse_statistics(pdf)
    contests, more_warnings = parse_contests(pdf, stats)
    for w in warnings:
        print("WARN:", w)
    names = {tuple(c["names"]) for c in contests}
    print(f"{len(contests)} contests parsed:")
    for names_tuple in sorted(names):
        print(" ", names_tuple)
    write_csv(contests, stats)


if __name__ == "__main__":
    main()