"""Parse Passaic County's 2026 primary District Summary (Dominion Custom
Table Report) into 2026/counties/20260602__nj__primary__passaic__precinct.csv.

Source: "Passaic NJ 2026 Primary District Summary.pdf" (71 pages).

- Pages 1-9: STATISTICS tables. Six integer columns (registered voters
  total/dem/rep, ballots cast total/dem/rep) are right-aligned at fixed x
  edges, followed by three turnout percentage columns.
- Pages 10-71: contest pages. Each page's header holds one or more contests;
  candidate names are printed vertically (rotated 90 degrees), one rotated
  column per candidate. A name too tall for one column wraps into a second
  rotated column 9.4pt to the LEFT; names read right-to-left across the
  columns of a slot. Data values are right-aligned to the right edge of each
  candidate's RIGHTMOST rotated column (+6.1); wrapped columns carry no
  values.
- A contest's rows span consecutive pages of one party section; the last page
  ends with a 'Totals' row whose values equal the county-wide total per
  candidate. For un-suppressed candidates these Totals match the official
  county results exactly; where a party's small districts were suppressed,
  Dominion EXCLUDES those votes from the Totals row too, so the printed
  Totals understate the official county totals.
- Suppression (NJSA 19:52-9): if a district's DEM or REP ballots cast is in
  1..13, that party's contest cells are all blanked and the row label carries
  a 'Suppressed' marker (printed on the district's rows in both party
  sections). The suppressed votes do not appear anywhere in this PDF (not
  even in the Totals row). Blank cells on suppressed rows parse as 0
  (Middlesex 'protected' precedent); the crosscheck against the official
  county file reports the resulting per-candidate undercount.
- A few contest titles are truncated for print space ('Mayor' with no town;
  a House title with no district line); towns are inferred from the districts
  that print values in the contest, House districts from the order of House
  contests in each party section.
- House district membership is per district, not per town: Woodland Park
  straddles districts (some of its districts are CD5, others CD11), so each
  district's House contest is inferred from where its values print.

Contest membership rules:
- U.S. Senate, Surrogate, Members of the Board of County Commissioners:
  every district.
- U.S. House: districts whose values print in that contest (a district's CD
  must agree between the DEMREP sections).
- Municipal contests: districts of the member town (ward offices additionally
  restricted to matching ward districts, e.g. Wayne's unexpired 5th Ward
  council seat).
- Districts whose party cast 1-13 ballots are members with zero votes.
"""

import csv
import os
import re
from collections import defaultdict

import pdfplumber

BASE = "/Users/dwillis/code/openelections-sources-nj/2026/primary"
PDF = os.path.join(BASE, "Passaic NJ 2026 Primary District Summary.pdf")
OUTPUT = "2026/counties/20260602__nj__primary__passaic__precinct.csv"
COUNTY_CSV = "2026/20260602__nj__primary__county.csv"

STAT_RIGHT_TOL = 4.0     # value right edge -> stats column
SLOT_RIGHT_TOL = 4.5     # value right edge -> contest slot
STAT_RIGHTS = [200.0, 242.0, 284.0, 326.0, 368.0, 410.0]
STAT_KEYS = ["reg_total", "reg_dem", "reg_rep",
             "cast_total", "cast_dem", "cast_rep"]
SUPPRESS_MAX = 13        # party ballots in 1..13 suppress that party's cells
HOUSE_ORDER = [5, 9, 11] # House contests appear in this order in each section

TOWN_SUFFIX = {
    "Bloomingdale": "Boro", "Clifton": "City", "Haledon": "Boro",
    "Hawthorne": "Boro", "Ringwood": "Boro", "North Haledon": "Boro",
    "Little Falls": "Twp", "Pompton Lakes": "Boro",
    "Prospect Park": "Boro", "Totowa": "Boro", "Wanaque": "Boro",
    "Wayne": "Twp", "West Milford": "Twp", "Woodland Park": "Boro",
    "Paterson": "City", "Passaic": "City",
}

OFFICE_RANK = {"U.S. Senate": 0, "U.S. House": 1}


def is_int(text):
    return bool(re.fullmatch(r"\d[\d,]*", text))


def as_int(text):
    return int(text.replace(",", ""))


def town_of(label):
    for town in sorted(TOWN_SUFFIX, key=len, reverse=True):
        if label == town or label.startswith(town + " "):
            return town
    return None


def natkey(label):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", label)]


def is_suppressed_party(stats, label, party):
    """True if this party's ballots cast in the district is in 1..13."""
    s = stats.get(label)
    if not s:
        return False
    n = s["cast_dem"] if party == "DEM" else s["cast_rep"]
    return 0 < n <= SUPPRESS_MAX


# ------------------------------------------------------------------ statistics

def parse_stats(pdf):
    """Pages 1-9: per-district registration/turnout table."""
    stats = {}
    warnings = []
    for pno in range(1, 10):
        page = pdf.pages[pno - 1]
        words = page.extract_words()
        label_tops = sorted({round(w["top"], 1) for w in words
                             if w["x1"] <= 120 and w["top"] > 120})
        for top in label_tops:
            lws = sorted([w for w in words
                          if abs(w["top"] - top) < 0.6 and w["x1"] <= 120],
                         key=lambda x: x["x0"])
            text = " ".join(w["text"] for w in lws)
            nums = {}
            for w in words:
                if is_int(w["text"]) and 150 < w["x1"] < 560 \
                        and abs(w["top"] - top) < 2.0:
                    best = min(STAT_RIGHTS, key=lambda r: abs(w["x1"] - r))
                    if abs(w["x1"] - best) <= STAT_RIGHT_TOL:
                        nums[best] = as_int(w["text"])
                    else:
                        warnings.append(f"p{pno}: stray number {w['text']!r}"
                                        f"@x1={w['x1']:.0f} row {text!r}")
            if not nums:
                continue
            if len(nums) != len(STAT_RIGHTS):
                warnings.append(f"p{pno}: stats row with {len(nums)}/6 "
                                f"columns: {text!r} {nums}")
                continue
            row = {k: nums[r] for k, r in zip(STAT_KEYS, STAT_RIGHTS)}
            if text == "Totals":
                stats["__totals__"] = row
            elif text in stats:
                # p9 carries a truncated 4-column repeat of Bloomingdale
                # D1-D4 (already captured in full on page 1); skip repeats.
                warnings.append(f"p{pno}: stats row {text!r} repeats; ignoring")
            else:
                stats[text] = row
    return stats, warnings


def validate_stats(stats, warnings):
    for label, s in sorted(stats.items()):
        if label == "__totals__":
            continue
        if s["cast_dem"] + s["cast_rep"] > s["cast_total"]:
            warnings.append(f"stats {label}: cast_dem({s['cast_dem']}) + "
                            f"cast_rep({s['cast_rep']}) > "
                            f"cast_total({s['cast_total']})")
    t = stats.get("__totals__")
    if t:
        agg = {k: sum(s[k] for lab, s in stats.items() if lab != "__totals__")
               for k in STAT_KEYS}
        for k in STAT_KEYS:
            if agg[k] != t[k]:
                warnings.append(f"stats Totals row {k}: districts sum "
                                f"{agg[k]}, printed {t[k]}")


# ---------------------------------------------------------------- contest pages

def rotated_columns(page, fragment=False):
    """Rotated (vertical) header text, one entry per column x0.

    Returns a list of (x0, text) sorted by x0; a wrapped name spans several
    columns 9.4pt apart. Fragment mode covers p9, where the contest section
    begins half-way down the last statistics page and its rotated candidate
    names sit below y=300 (above them are the rotated STATISTICS column
    headers, which must be ignored)."""
    cols = defaultdict(list)
    for c in page.chars:
        if not c.get("upright", True) and c["x0"] > 150 and (
                300 < c["top"] < 545 if fragment else c["top"] < 230):
            cols[round(c["x0"], 1)].append((c["top"], c["text"]))
    return [(x, re.sub(r"\s+", " ", "".join(t for _, t in sorted(cols[x]))).strip())
            for x in sorted(cols)]


def slot_clusters(rotcols):
    """Group rotated columns into candidate slots (gap > 20pt = new slot)."""
    if not rotcols:
        return []
    clusters, cur = [], [rotcols[0]]
    for rc in rotcols[1:]:
        if rc[0] - cur[-1][0] > 20:
            clusters.append(cur)
            cur = [rc]
        else:
            cur.append(rc)
    clusters.append(cur)
    out = []
    for cl in clusters:
        # word order: rightmost column first (names read right-to-left)
        name = " ".join(text for _, text in sorted(cl, key=lambda c: -c[0]))
        if name in ("Write-in Totals", "Write-ins"):
            name = "Write-ins"
        base = max(x for x, _ in cl)
        out.append({"base": base, "name": name, "right": base + 6.1})
    return out


def parse_contests(pdf):
    """Accumulate per-contest rows and Totals across pages 10-71.

    A contest key is (party, title); it stays open across pages until the page
    whose rows carry its Totals row."""
    contests = []
    open_map = {}   # (party, title) -> contest awaiting Totals
    problems = []

    for pno in range(9, 72):
        fragment = pno == 9   # p9: contest section begins mid-page
        page = pdf.pages[pno - 1]
        words = page.extract_words()
        if fragment:
            # only the contest section half of the page
            words = [w for w in words if w["top"] > 380]
        anchors = sorted([w for w in words
                          if w["text"] in ("DEM", "REP")
                          and 50 < w["top"] < 460], key=lambda w: w["x0"])
        vote_tops = [w["top"] for w in words
                     if w["text"] == "VOTE" and w["x0"] > 150]
        vote_top = min(vote_tops) if vote_tops else 118
        rotcols = rotated_columns(page, fragment=fragment)
        footer_top = next((w["top"] for w in words
                           if w["text"] == "Page" and w["x0"] > 650), None)

        # per-anchor contest windows and their candidate slots
        # A contest's first candidate column sits at/just right of its DEM/REP
        # anchor; its remaining slots continue left-to-right at ~42pt pitch.
        # The last slot before the next contest's start column belongs to this
        # contest, so slots are walked right from each anchor's start column
        # instead of using fixed x windows (windows clip the write-in column
        # whenever the next contest starts close behind).
        all_slots = slot_clusters(rotcols)
        start_of = {}
        for idx, a in enumerate(anchors):
            win = [s for s in all_slots
                   if a["x0"] - 6 <= s["base"] <= a["x0"] + 34]
            if win:
                start_of[(idx, a["x0"])] = min(win, key=lambda s: s["base"])
            else:
                problems.append(f"p{pno}: no candidate column within 34pt of "
                                f"{a['text']} anchor at x={a['x0']:.0f}")
        headers = []
        for idx, a in enumerate(anchors):
            x_hi = (anchors[idx + 1]["x0"] - 16
                    if idx + 1 < len(anchors) else 660)
            title = " ".join(w["text"] for w in sorted(
                [w for w in words if a["x0"] - 8 <= w["x0"] < x_hi
                 and w["top"] < vote_top - 1 and w is not a],
                key=lambda w: (w["top"], w["x0"])))
            title = re.split(r"reported to", title)[-1].strip()
            title = re.sub(r"^ELECTION\s+", "", title, flags=re.I)
            start = start_of.get((idx, a["x0"]))
            slots = []
            if start is not None:
                slots.append(start)
                for s in all_slots[all_slots.index(start) + 1:]:
                    if any(s is t for t in start_of.values()):
                        break
                    if s["base"] - slots[-1]["base"] > 52:
                        problems.append(f"p{pno}: gap {s['base'] - slots[-1]['base']:.0f}pt "
                                        f"after slot {slots[-1]['name']!r} of "
                                        f"{(a['text'], title)!r}")
                        break
                    slots.append(s)
            key = (a["text"], title,
                   round(start["base"], 1) if start else None)
            cont = open_map.get(key)
            if cont is not None:
                old = [s["name"] for s in cont["slots"]]
                new = [s["name"] for s in slots]
                if old != new:
                    problems.append(f"p{pno}: {key} slots changed: "
                                    f"{old} -> {new}")
            else:
                cont = {"party": a["text"], "title": title, "slots": slots,
                        "rows": {}, "totals": None, "pages": [pno]}
                open_map[key] = cont
                contests.append(cont)
            if pno not in cont["pages"]:
                cont["pages"].append(pno)
            headers.append({"contest": cont, "slots": slots, "key": key})

        # data rows and the Totals row (below the VOTE header; on the p9
        # fragment that header sits mid-page, so this also skips the
        # statistics rows above it)
        label_tops = sorted({round(w["top"], 1) for w in words
                             if w["x0"] < 160 and w["x1"] < 162
                             and w["top"] > vote_top + 5})
        all_slots = [s for h in headers for s in h["slots"]]
        for top in label_tops:
            lws = sorted([w for w in words
                          if abs(w["top"] - top) < 0.6 and w["x0"] < 160
                          and w["x1"] < 162], key=lambda x: x["x0"])
            text = " ".join(w["text"] for w in lws)
            if footer_top and top > footer_top - 5:
                continue
            if text.startswith("District Summary Report"):
                continue
            # values at each slot's right edge
            vals = {}
            for s in all_slots:
                vw = sorted([w for w in words
                             if is_int(w["text"]) and w["x0"] > 150
                             and abs(w["top"] - top) < 2.0
                             and abs(w["x1"] - s["right"]) <= SLOT_RIGHT_TOL],
                            key=lambda w: abs(w["x1"] - s["right"]))
                if vw:
                    vals[s["right"]] = as_int(vw[0]["text"])
            # any int that matched no slot is a parsing bug
            for w in words:
                if is_int(w["text"]) and 150 < w["x1"] < 660 \
                        and abs(w["top"] - top) < 2.0 and not any(
                            abs(w["x1"] - s["right"]) <= SLOT_RIGHT_TOL
                            for s in all_slots):
                    problems.append(f"p{pno}: unmatched number {w['text']!r}"
                                    f"@x1={w['x1']:.0f} row {text!r}")

            if text == "Totals":
                for h in headers:
                    cont = h["contest"]
                    if cont["totals"] is not None:
                        problems.append(f"p{pno}: second Totals row for "
                                        f"{(cont['party'], cont['title'])}")
                    cont["totals"] = {s["right"]: vals.get(s["right"])
                                      for s in h["slots"]}
                    open_map.pop(h["key"], None)
                continue

            suppressed = "Suppressed" in [w["text"] for w in lws]
            text = " ".join(w["text"] for w in lws
                            if w["text"] != "Suppressed")
            for h in headers:
                cont = h["contest"]
                row = cont["rows"].setdefault(
                    text, {"suppressed": suppressed, "values": {}})
                if row["suppressed"] != suppressed:
                    problems.append(f"p{pno}: row {text!r} Suppressed flag "
                                    f"differs from earlier page")
                for s in h["slots"]:
                    if s["right"] in vals:
                        if s["right"] in row["values"]:
                            problems.append(f"p{pno}: {text}: duplicate value "
                                            f"at x={s['right']:.0f}")
                        row["values"][s["right"]] = vals[s["right"]]
    # Merge the p9 fragment contests (the DEM run begins mid-page on p9
    # with no printed titles and only Bloomingdale D1-D4) into their full
    # contests, matched by party + candidate slot names.
    for cont in [c for c in contests if c["title"] == ""]:
        target = None
        for c2 in contests:
            if c2 is cont or c2["title"] == "" \
                    or c2["party"] != cont["party"]:
                continue
            if [s["name"] for s in c2["slots"]] == \
                    [s["name"] for s in cont["slots"]]:
                target = c2
                break
        if target is None:
            problems.append(f"fragment contest "
                            f"({cont['party']}, slots "
                            f"{[s['name'] for s in cont['slots']]}) "
                            f"merged nowhere")
            continue
        cont["merged_into"] = target
        for label, row in cont["rows"].items():
            tr = target["rows"].setdefault(
                label, {"suppressed": row["suppressed"], "values": {}})
            if tr["values"] and row["values"]:
                problems.append(f"fragment merge: duplicate values for "
                                f"{label!r} in {cont['party']}")
            tr["values"].update(row["values"])
    contests = [c for c in contests if "merged_into" not in c]
    # any contest still open at document end?
    for cont in open_map.values():
        if cont["title"] == "":
            continue    # p9 fragments are merged above
        problems.append(f"contest never closed (no Totals row): "
                        f"{(cont['party'], cont['title'])}")
    return contests, problems


# ----------------------------------------------------------------- finalize

def canon_office(cont, problems):
    """Map a printed title to (office, district, town, ward)."""
    t = re.sub(r"\s+", " ", cont["title"]).strip()
    t = re.sub(r"^ELECTION\s+", "", t, flags=re.I)
    low = t.lower()
    if "u.s. senate" in low:
        return "U.S. Senate", "", None, None
    if "house of representatives" in low or re.search(r"\d+th cong", low):
        m = re.search(r"(\d+)\s*th cong", low)
        return "U.S. House", m.group(1) if m else None, None, None
    if low == "surrogate":
        return "Surrogate", "", None, None
    if "board of county commissioners" in low:
        return "Members of the Board of County Commissioners", "", None, None
    if low.startswith("mayor"):
        town = t[len("Mayor"):].strip() or None
        return None, "", town, None        # office name built after inference
    m = re.search(r"(\d+)(?:st|nd|rd|th) ward council", low)
    if m:
        town = re.search(r"[Cc]ouncil [Mm]ember (.+?) [Uu]nexpired", t)
        town = town.group(1).strip() if town else None
        return None, "", town, int(m.group(1))
    m = re.search(r"(Borough|Township|City|Town) Council (.+)$", t)
    if m:
        kind, town = m.group(1), m.group(2).strip()
        return None, "", town, None
    problems.append(f"unrecognized contest title: {cont['title']!r}")
    return "?" + t, "", None, None


def infer_house_districts(contests, problems):
    """Fill in House contests with no printed district, in HOUSE_ORDER."""
    for party in ("DEM", "REP"):
        hs = [c for c in contests
              if c["office"] == "U.S. House" and c["party"] == party]
        have = {c["district"] for c in hs if c["district"]}
        missing = [c for c in hs if not c["district"]]
        rem = [d for d in HOUSE_ORDER if str(d) not in have]
        if set(have) <= {str(d) for d in HOUSE_ORDER} \
                and len(have) == len(hs) - len(missing) \
                and len(missing) == len(rem):
            for c, d in zip(missing, rem):
                c["district"] = str(d)
                problems.append(f"inferred {party} U.S. House district "
                                f"{d} from section order (truncated title)")
        elif missing:
            problems.append(f"could not infer {party} House districts: "
                            f"have {have}, {len(hs)} contests")


def finish_municipal_office(cont):
    """Build the canonical office name once the town is known."""
    town = cont["town"]
    suf = TOWN_SUFFIX.get(town, "")
    ward = cont["ward"]
    if ward:
        ordn = {1: "st", 2: "nd", 3: "rd"}.get(ward, "th")
        cont["office"] = (f"{ward}{ordn} Ward Councilmember "
                          f"{town} {suf} (Unexpired Term)")
        return
    low = cont["title"].lower()
    if low.startswith("mayor"):
        cont["office"] = f"Mayor {town} {suf}"
    else:
        m = re.search(r"(Borough|Township|City|Town) Council", cont["title"],
                      re.I)
        kind = m.group(1).title() if m else "Council"
        cont["office"] = f"{kind} Council {town} {suf}"


def district_memberships(contests, labels, stats, problems):
    """Decide, for every contest, which district labels it covers."""
    towns = set()
    for label in labels:
        t = town_of(label)
        if t is None:
            problems.append(f"unknown district label: {label!r}")
        towns.add(t)

    # per-label House district from where the label's values print
    label_cd = {}
    for cont in contests:
        if cont["office"] != "U.S. House" or not cont["district"]:
            continue
        for label, row in cont["rows"].items():
            if row["values"]:
                prev = label_cd.get(label)
                if prev and prev != cont["district"]:
                    problems.append(f"{label}: values in both House "
                                    f"{prev} and House {cont['district']}")
                label_cd[label] = cont["district"]
    unmapped = [lab for lab in labels if lab not in label_cd]
    if unmapped:
        problems.append(f"districts with no House votes in either section "
                        f"(CD unknown): {unmapped}")

    for cont in contests:
        office = cont["office"]
        rights = [s["right"] for s in cont["slots"]]
        if office in ("U.S. Senate", "Surrogate",
                      "Members of the Board of County Commissioners"):
            cont["members"] = list(labels)
        elif office == "U.S. House":
            cont["members"] = [lab for lab in labels
                               if label_cd.get(lab) == cont["district"]]
        else:
            # municipal: all districts of the member town, ward-filtered
            town = cont["town"]
            printed = {lab for lab, row in cont["rows"].items()
                       if row["values"]}
            if town is not None and town not in towns:
                # titles truncated for print space may cut a town name
                # ('Prospect' for Prospect Park); complete the prefix
                cands = [t2 for t2 in towns
                         if t2 and t2.lower().startswith(town.lower())]
                if len(cands) == 1:
                    problems.append(f"completed truncated town {town!r} -> "
                                    f"{cands[0]!r} for "
                                    f"{(cont['party'], cont['title'])!r}")
                    town = cont["town"] = cands[0]
            if town not in towns or town is None:
                itowns = {t for t in (town_of(lab) for lab in printed) if t}
                if len(itowns) == 1:
                    town = cont["town"] = itowns.pop()
                    problems.append(f"inferred town for truncated title "
                                    f"{(cont['party'], cont['title'])!r}: "
                                    f"{town}")
                else:
                    problems.append(f"cannot infer town for "
                                    f"{(cont['party'], cont['title'])!r}: "
                                    f"towns {sorted(itowns or ['?'])}")
                    if town is None:
                        cont["office"] = "??" + cont["title"]
                    else:
                        cont["office"] = "??" + f"{cont['title']} {town}"
                    cont["members"] = []
                    continue
            mem = [lab for lab in labels if town_of(lab) == town]
            if cont["ward"]:
                mem = [lab for lab in mem
                       if re.search(rf"\bW{cont['ward']}\b", lab)]
            for lab in printed:
                if lab not in mem:
                    problems.append(f"{(cont['party'], office, town)}: "
                                    f"value row {lab!r} outside membership")
            cont["members"] = mem
        if office is None:
            finish_municipal_office(cont)
    # duplicate contest check after all inference
    seen = {}
    for cont in contests:
        key = (cont["party"], cont["office"], cont["district"])
        if key in seen:
            problems.append(f"duplicate contest after inference: {key}")
        seen[key] = True


def build_rows(contests, labels, stats, problems):
    """Produce output rows and per-candidate suppressed-vote deltas."""
    out = []
    notes = []          # expected zero-fill events (suppressed cells)
    deltas = {}         # (office, district, party, candidate) -> undercount
    for cont in contests:
        cands = [s for s in cont["slots"]
                 if s["name"].strip().upper() != "NO PETITION FILED"]
        totals = cont["totals"]
        for cand in cands:
            if totals is None:
                problems.append(f"contest never closed: "
                                f"{(cont['office'], cont['district'], cont['party'])}")
                break
            if totals.get(cand["right"]) is None:
                problems.append(f"no Totals value for "
                                f"{(cont['office'], cont['district'], cont['party'], cand['name'])}")
        memset = set(cont.get("members", []))
        summed = {cand["right"]: 0 for cand in cands}
        warned_partial = set()
        for label in cont.get("members", []):
            row = cont["rows"].get(label)
            has_vals = bool(row and row["values"])
            suppressed = is_suppressed_party(stats, label, cont["party"])
            if not has_vals:
                why = ("no row anywhere" if row is None else
                       "no values" if not suppressed else
                       "suppressed (1-%d ballots cast)" % SUPPRESS_MAX)
                (notes if row is not None and suppressed else problems
                 ).append(f"{(cont['office'], cont['district'], cont['party'])}: "
                          f"member {label}: {why}")
            for cand in cands:
                votes = (row["values"].get(cand["right"], 0)
                         if row else 0)
                summed[cand["right"]] += votes
                if (row is not None and not row["suppressed"] and has_vals
                        and cand["right"] not in row["values"]):
                    warned_partial.add((label, cand["right"]))
                    problems.append(f"{(cont['office'], cont['district'], cont['party'], cand['name'])}: "
                                    f"{label} missing one of several values")
                out.append({"precinct": label, "office": cont["office"],
                            "district": cont["district"],
                            "party": cont["party"],
                            "candidate": cand["name"], "votes": votes})
        for cand in cands:
            if totals is None:
                continue
            tv = totals.get(cand["right"])
            if tv is not None:
                delta = tv - summed[cand["right"]]
                if delta > 0:
                    key = (cont["office"], cont["district"],
                           cont["party"], cand["name"])
                    deltas[key] = delta
                elif delta < 0:
                    problems.append(f"precinct sum EXCEEDS Totals by "
                                    f"{-delta}: "
                                    f"{(cont['office'], cont['district'], cont['party'], cand['name'])}")
    return out, deltas, notes



# ----------------------------------------------------------------- crosscheck

def crosscheck(out, county_csv, problems):
    official = {}
    with open(county_csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["county"] != "Passaic":
                continue
            if r["office"] not in ("U.S. Senate", "U.S. House"):
                continue
            key = (r["office"], r["district"].strip(),
                   r["candidate"].strip().lower())
            official[key] = int(r["votes"])
    sums = defaultdict(int)
    for r in out:
        if r["office"] in ("U.S. Senate", "U.S. House"):
            key = (r["office"], r["district"], r["candidate"].strip().lower())
            sums[key] += r["votes"]
    lines = []
    ok = True
    for key in sorted(official):
        mine = sums.get(key, 0)
        d = mine - official[key]
        if d:
            ok = False
        lines.append((key, mine, official[key], d))
        if key not in sums:
            problems.append(f"official candidate {key} has no precinct rows")
    for key in sorted(sums):
        if key not in official:
            if key[2] == "write-ins":
                continue    # official county file carries no write-in rows
            problems.append(f"precinct candidate {key} not in official file")
    # also compare against the PDF Totals (deltas = suppressed votes)
    return lines, ok


# ----------------------------------------------------------------- write

def write_csv(out, stats):
    pseudo = {}
    for label, s in stats.items():
        if label == "__totals__":
            continue
        pseudo[label] = [("Registered Voters", s["reg_total"]),
                         ("Ballots Cast", s["cast_total"])]
    rows = []
    for label in sorted(pseudo, key=natkey):
        for cand, n in pseudo[label]:
            rows.append(["Passaic", label, cand, "", "", "", n])
    for r in sorted(out, key=lambda r: (
            OFFICE_RANK.get(r["office"], 2), r["office"],
            natkey(r["precinct"]),
            int(r["district"]) if r["district"] else 0,
            0 if r["party"] == "REP" else 1)):
        rows.append(["Passaic", r["precinct"], r["office"], r["district"],
                     r["party"], r["candidate"], r["votes"]])
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        w.writerows(rows)
    return len(rows)


def main():
    pdf = pdfplumber.open(PDF)
    problems = []
    stats, warnings = parse_stats(pdf)
    validate_stats(stats, warnings)
    contests, pwarnings = parse_contests(pdf)
    print(f"statistics districts: {len(stats) - 1}")
    for w in warnings + pwarnings:
        print("WARN:", w)
    for cont in contests:
        office, district, town, ward = canon_office(cont, problems)
        cont["office"], cont["district"] = office, district or ""
        cont["town"], cont["ward"] = town, ward
    infer_house_districts(contests, problems)
    labels = [l for l in stats if l != "__totals__"]
    district_memberships(contests, labels, stats, problems)
    out, deltas, notes = build_rows(contests, labels, stats, problems)
    lines, ok = crosscheck(out, COUNTY_CSV, problems)
    print(f"suppressed-cell zero-fills (expected): {len(notes)}")
    for p in problems:
        print("PROBLEM:", p)
    print("\nFederal crosscheck (precinct sum vs official):")
    for key, mine, off, d in lines:
        if d:
            print(f"  {key[0]} d{key[1]} {key[2]}: {mine} vs {off} "
                  f"(delta {d})")
    print("  all federal sums match" if ok else
          "  see deltas above")
    n = write_csv(out, stats)
    print(f"\nwrote {n} rows to {OUTPUT}")
    print("\nsuppressed-vote deltas (PDF Totals - precinct sums):")
    for key in sorted(deltas):
        print(f"  {key[0]} d{key[1]} {key[2]:3} {key[3]}: "
              f"{deltas[key]}")
    pdf.close()


if __name__ == "__main__":
    main()