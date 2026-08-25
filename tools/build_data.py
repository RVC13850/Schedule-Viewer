#!/usr/bin/env python3
"""Convert the Google Sheet timetable into data/schedule.json.

Reads the workbook as .xlsx so that merged cells (which encode how long a class
runs) are preserved -- a CSV export would lose them.

Usage:
    python3 tools/build_data.py                 # download from Google Sheets
    python3 tools/build_data.py path/to.xlsx    # use a local export
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

SHEET_ID = "1waL56rvh-HMbbGhfuZDH4ydvoonSyrkjCFBKGjbnh1s"
XLSX_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOT_MINUTES = 30

# Display names that differ from the column headers in the spreadsheet.
RENAME = {"Govind": "Mansi"}

SCHOOLS = {
    "Abhiram": "UTD",
    "Rishna": "UTD",
    "Sreevasan": "UTD",
    "Sashaank": "UTD",
    "Swayam": "UTD",
    "Anveetha": "UTD",
    "Mansi": "UT Austin",
    "Suchit": "UT Austin",
    "Aaryaa": "Carnegie Mellon",
    "Rithwik": "American Airlines",
    "Nidhi": "JPMC",
    "Krigga": "UTD",
}

ICONS = {
    "UTD": "UTD.svg.webp",
    "UT Austin": "UT.svg.webp",
    "American Airlines": "aa.png",
    "JPMC": "jpmc.png",
    "Carnegie Mellon": "cmu.png",
}

# People whose blocks are shifts rather than classes.
WORK_PEOPLE = {"Rithwik", "Nidhi"}

# UTD classes run 75 minutes, so the spreadsheet's merged block only marks the start.
UTD_CLASS_MINUTES = 75

# UTD blocks that are not 75 minutes, keyed by (person, course).
FIXED_BLOCKS = {
    ("Swayam", "CS 6301"): ("13:00", "15:45"),
    ("Sashaank", "ARTS 3375"): ("16:00", "18:45"),
    ("Anveetha", "HONS 3116"): ("09:00", "09:50"),
    ("Rithwik", "AA 1000 INP"): ("09:00", "17:00"),
}

# Course codes the sheet records wrong.
TITLE_FIXES = {
    ("Sashaank", "CS 4375"): "CS 4384",
    ("Sashaank", "CS 4394"): "CS 4393",
    ("Nidhi", "JPM 1000"): "JPMC 1000",
}

# Rooms the sheet only records as a building.
ROOM_FIXES = {
    ("Anveetha", "HONS 3116"): "AD 2.238",
    ("Anveetha", "CS 4352"): "GR 4.428",
    ("Abhiram", "CS 6375"): "ECSS 2.412",
    ("Rishna", "CS 6363"): "JO 4.102",
    ("Sreevasan", "CS 6363"): "JO 4.102",
    ("Sashaank", "CS 4371"): "FN 2.102",
    ("Sashaank", "CS 4384"): "GR 3.420",
    ("Abhiram", "CS 6301"): "ECSS 2.305",
    ("Rishna", "CS 6301"): "ECSS 2.305",
    ("Sreevasan", "CS 6301"): "ECSS 2.305",
    ("Rishna", "CS 6360"): "ECSS 2.306",
    ("Sreevasan", "CS 6326"): "GR 4.428",
    ("Sashaank", "CS 4393"): "CR 1.202",
    ("Swayam", "CS 6364"): "ECSS 2.311",
    ("Swayam", "CS 6314"): "ECSS 2.410",
    ("Anveetha", "MATH 4301"): "FN 2.214",
    ("Anveetha", "CS 4365"): "ECSS 2.415",
    ("Nidhi", "JPMC 1000"): "Plano, TX",
    ("Rithwik", "AA 1000 WFH"): "Irving, TX",
    ("Rithwik", "AA 1000 INP"): "Fort Worth, TX",
    ("Sashaank", "ARTS 3375"): "ATC 1.802",
}

# Classes whose real times the spreadsheet's 30-minute grid cannot express, as
# (person, days, title, room, start, end[, kind]). These REPLACE that person's sheet column,
# so delete a person's rows here once the sheet alone is good enough.
EXTRA_EVENTS = [
    ("Mansi", ["Tuesday", "Thursday"], "KIN 106C", "BEL 348", "09:00", "10:30"),
    ("Mansi", ["Tuesday", "Thursday"], "NTR 306", "Home", "12:30", "14:00"),
    ("Mansi", ["Tuesday", "Thursday"], "CS 378", "GDC 5.302", "14:00", "15:30"),
    ("Mansi", ["Monday", "Wednesday", "Friday"], "CS 371L", "RLP 0.128", "13:00", "14:00"),
    ("Suchit", ["Tuesday", "Wednesday", "Thursday"], "Civil Procedure", "TNH 2.123", "10:30", "11:37"),
    ("Suchit", ["Monday", "Tuesday", "Wednesday"], "Property", "TNH 2.139", "13:05", "14:12"),
    ("Suchit", ["Monday", "Tuesday", "Wednesday"], "Contracts", "TNH 2.139", "14:30", "15:37"),
    ("Suchit", ["Thursday"], "Legal Analysis & Comm", "TNH 3.127", "14:30", "15:37"),
    ("Suchit", ["Friday"], "Legal Analysis & Comm", "TNH 3.127", "11:50", "12:57"),
    ("Krigga", ["Monday"], "Work", "", "08:00", "12:30", "work"),
    ("Krigga", ["Monday"], "Work", "", "13:00", "17:00", "work"),
    ("Krigga", ["Tuesday"], "CLDP 3394", "CB 1.219", "11:30", "12:45"),
    ("Krigga", ["Tuesday", "Thursday"], "PSY 2314", "GR 3.420", "14:30", "15:45"),
    ("Krigga", ["Tuesday", "Thursday"], "NSC 4351", "FO 2.702", "16:30", "17:45"),
    ("Krigga", ["Wednesday"], "Killing Rats", "", "13:00", "16:00", "work"),
    ("Krigga", ["Thursday"], "Killing Rats", "", "10:00", "14:00", "work"),
    ("Krigga", ["Friday"], "Killing Rats", "", "09:00", "15:00", "work"),
]

OVERRIDDEN_PEOPLE = {row[0] for row in EXTRA_EVENTS}

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# xlsx reading
# --------------------------------------------------------------------------- #

def col_to_index(ref: str) -> int:
    """'C' -> 2"""
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def split_ref(ref: str) -> tuple[int, int]:
    """'C7' -> (row_index_0based, col_index_0based)"""
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return int(m.group(2)) - 1, col_to_index(m.group(1))


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        xml = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    out = []
    for si in ET.fromstring(xml):
        out.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    return out


def sheet_targets(zf: zipfile.ZipFile) -> dict[str, str]:
    """Map visible sheet name -> zip path of its worksheet xml."""
    rels = {
        rel.get("Id"): rel.get("Target")
        for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    }
    out = {}
    for sheet in ET.fromstring(zf.read("xl/workbook.xml")).iter(f"{NS}sheet"):
        target = rels[sheet.get(f"{DOC_REL}id")]
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        out[sheet.get("name")] = target
    return out


def read_grid(zf: zipfile.ZipFile, path: str, strings: list[str]):
    """Return (cells, merges) where cells[(row, col)] = value (str or float)."""
    root = ET.fromstring(zf.read(path))
    cells: dict[tuple[int, int], object] = {}

    for c in root.iter(f"{NS}c"):
        ref = c.get("r")
        if not ref:
            continue
        ctype = c.get("t")
        if ctype == "inlineStr":
            node = c.find(f"{NS}is")
            value = "".join(t.text or "" for t in node.iter(f"{NS}t")) if node is not None else ""
        else:
            v = c.find(f"{NS}v")
            if v is None or v.text is None:
                continue
            if ctype == "s":
                value = strings[int(v.text)]
            elif ctype in (None, "n"):
                try:
                    value = float(v.text)
                except ValueError:
                    value = v.text
            else:
                value = v.text
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        cells[split_ref(ref)] = value

    merges = []
    for m in root.iter(f"{NS}mergeCell"):
        a, b = m.get("ref").split(":")
        merges.append((split_ref(a), split_ref(b)))
    return cells, merges


# --------------------------------------------------------------------------- #
# timetable parsing
# --------------------------------------------------------------------------- #

TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*([AaPp])\.?[Mm]\.?$")


def parse_time(value) -> int | None:
    """Return minutes past midnight, or None."""
    if isinstance(value, (int, float)):
        # Excel serial time: fraction of a day.
        frac = float(value) % 1
        return int(round(frac * 24 * 60))
    if not isinstance(value, str):
        return None
    m = TIME_RE.match(value.strip())
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    hour = hour % 12 + (12 if ampm == "p" else 0)
    return hour * 60 + minute


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def from_hhmm(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def apply_school_rules(event):
    """The spreadsheet grid is 30-minute, so real class lengths come from these rules."""
    title = TITLE_FIXES.get((event["person"], event["title"]))
    if title:
        event["title"] = title
    room = ROOM_FIXES.get((event["person"], event["title"]))
    if room:
        event["location"] = room
    fixed = FIXED_BLOCKS.get((event["person"], event["title"]))
    if fixed:
        event["startMinutes"], event["endMinutes"] = from_hhmm(fixed[0]), from_hhmm(fixed[1])
        event["endEstimated"] = False
    elif event["kind"] == "class" and SCHOOLS.get(event["person"]) == "UTD":
        event["endMinutes"] = event["startMinutes"] + UTD_CLASS_MINUTES
        event["endEstimated"] = False
    event["start"] = hhmm(event["startMinutes"])
    event["end"] = hhmm(event["endMinutes"])
    return event


def apply_merges(cells, merges):
    """Fill merged ranges with the anchor value and tag every cell with a block id."""
    block_of: dict[tuple[int, int], str] = {}
    for i, ((r1, c1), (r2, c2)) in enumerate(merges):
        anchor = cells.get((r1, c1))
        if anchor is None:
            continue
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cells[(r, c)] = anchor
                block_of[(r, c)] = f"m{i}"
    return block_of


def parse_day_sheet(cells, merges):
    """Return (people, events) for one day sheet."""
    block_of = apply_merges(cells, merges)

    rows_with_time: list[tuple[int, int]] = []  # (row, minutes)
    time_col = None
    for (r, c), value in sorted(cells.items()):
        if c > 3:
            continue
        minutes = parse_time(value)
        if minutes is not None:
            if time_col is None:
                time_col = c
            if c == time_col:
                rows_with_time.append((r, minutes))
    if not rows_with_time:
        return [], []
    rows_with_time.sort()

    first_data_row = rows_with_time[0][0]

    # Header row = nearest row above the first time row holding >= 3 labels.
    header_row = None
    for r in range(first_data_row - 1, -1, -1):
        labels = [c for (rr, c), v in cells.items()
                  if rr == r and c > time_col and isinstance(v, str)]
        if len(labels) >= 3:
            header_row = r
            break
    if header_row is None:
        return [], []

    people: list[tuple[int, str]] = sorted(
        (c, RENAME.get(str(v).strip(), str(v).strip()))
        for (r, c), v in cells.items()
        if r == header_row and c > time_col and isinstance(v, str) and v.strip()
    )

    events = []
    for col, name in people:
        if name in OVERRIDDEN_PEOPLE:
            continue
        current = None
        for row, minutes in rows_with_time:
            raw = cells.get((row, col))
            text = str(raw).strip() if isinstance(raw, str) else ""
            block = block_of.get((row, col), f"r{row}")
            if not text:
                current = None
                continue
            if current and current["_text"] == text and (
                current["_block"] == block or current["_block"].startswith("r")
            ) and current["_endMin"] == minutes:
                current["_endMin"] = minutes + SLOT_MINUTES
                current["_slots"] += 1
                continue
            current = {
                "_text": text,
                "_block": block,
                "_startMin": minutes,
                "_endMin": minutes + SLOT_MINUTES,
                "_slots": 1,
                "person": name,
            }
            events.append(current)

    cleaned = []
    for e in events:
        title, _, location = e["_text"].partition("\n")
        cleaned.append(apply_school_rules({
            "person": e["person"],
            "kind": "work" if e["person"] in WORK_PEOPLE else "class",
            "title": title.strip(),
            "location": location.strip().replace("\n", " "),
            "start": hhmm(e["_startMin"]),
            "end": hhmm(e["_endMin"]),
            "startMinutes": e["_startMin"],
            "endMinutes": e["_endMin"],
            # A lone 30-minute cell means nobody recorded how long it runs.
            "endEstimated": e["_slots"] == 1,
        }))
    cleaned.sort(key=lambda e: (e["startMinutes"], e["person"]))

    day_start = rows_with_time[0][1]
    day_end = rows_with_time[-1][1] + SLOT_MINUTES
    return [n for _, n in people], (cleaned, day_start, day_end)


def main() -> int:
    if len(sys.argv) > 1:
        source = Path(sys.argv[1]).read_bytes()
    else:
        print(f"Downloading {XLSX_URL}")
        with urllib.request.urlopen(XLSX_URL) as resp:  # noqa: S310 - fixed https URL
            source = resp.read()

    tmp = ROOT / "tools" / ".workbook.xlsx"
    tmp.write_bytes(source)

    with zipfile.ZipFile(tmp) as zf:
        strings = read_shared_strings(zf)
        targets = sheet_targets(zf)
        days = {}
        people_order: list[str] = []
        grid_start, grid_end = None, None

        for name, path in targets.items():
            if name.strip().title() not in DAY_ORDER:
                continue
            cells, merges = read_grid(zf, path, strings)
            people, payload = parse_day_sheet(cells, merges)
            if not payload:
                continue
            events, day_start, day_end = payload
            for p in people:
                if p not in people_order:
                    people_order.append(p)
            grid_start = day_start if grid_start is None else min(grid_start, day_start)
            grid_end = day_end if grid_end is None else max(grid_end, day_end)
            days[name.strip().title()] = events

    tmp.unlink(missing_ok=True)

    for person, on_days, title, room, start, end, *extra in EXTRA_EVENTS:
        kind = extra[0] if extra else ("work" if person in WORK_PEOPLE else "class")
        if person not in people_order:
            people_order.append(person)
        for d in on_days:
            if d not in days:
                continue
            days[d].append(apply_school_rules({
                "person": person,
                "kind": kind,
                "title": title,
                "location": room,
                "start": start,
                "end": end,
                "startMinutes": from_hhmm(start),
                "endMinutes": from_hhmm(end),
                "endEstimated": False,
            }))
            days[d].sort(key=lambda e: (e["startMinutes"], e["person"]))

    ordered_days = [d for d in DAY_ORDER if d in days]
    data = {
        "source": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timezone": "America/Chicago",
        "slotMinutes": SLOT_MINUTES,
        "gridStart": hhmm(grid_start or 8 * 60),
        "gridEnd": hhmm(grid_end or 21 * 60),
        "people": people_order,
        "schools": {p: SCHOOLS.get(p, "") for p in people_order},
        "icons": {
            p: f"assets/icons/{ICONS[SCHOOLS[p]]}"
            for p in people_order
            if SCHOOLS.get(p) in ICONS
        },
        "dayOrder": ordered_days,
        "days": {d: days[d] for d in ordered_days},
    }

    out = ROOT / "data" / "schedule.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n")

    total = sum(len(v) for v in days.values())
    print(f"Wrote {out.relative_to(ROOT)}: {len(people_order)} people, "
          f"{len(ordered_days)} days, {total} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
