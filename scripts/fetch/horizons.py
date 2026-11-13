"""Fetch Earth-Mars one-way light time from JPL Horizons.

ASTRA's Crew & comms page shows how far a signal to Earth has to travel. The old value was a
fixed 760 s; this replaces it with the real light time for the mission date.

Source: NASA/JPL Horizons On-Line Ephemeris System
        https://ssd.jpl.nasa.gov/horizons/  (API docs: https://ssd.jpl.nasa.gov/api/horizons.api)

Run from the repo root (astra/):
    uv run --no-project python -I scripts/fetch/horizons.py
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import get_url, write_json  # noqa: E402

# The MERIDIAN-1 demo mission: a real Earth-Mars launch window.
# 2026-11-12 sits inside the 2026-11-03..2026-11-14 Mars launch window (see the
# "Mission launch windows" table at https://www.nasa.gov/mission/mars-sample-return/ ;
# the same window is published by the Mars launch-window tables of the International
# Mars Exploration Working Group). The mission is fictional, but its launch date is a
# real one so the light time that ASTRA computes is the real one.
LAUNCH_DATE = date(2026, 11, 12)
# 540 days reaches past the real Mars solar conjunction of spring 2028, so the comms-blackout
# scenario runs on real geometry.
DAYS = 540

# Horizons observer quantities:
#   20 = Observer range (AU)          21 = One-way light time (min)      23 = Sun-Observer-Target elongation (deg)
QUANTITIES = "20,21,23"
TARGET = "499"  # Mars
CENTER = "500@399"  # Earth geocentre

ROW = re.compile(
    r"^\s*(\d{4})-(\w{3})-(\d{2})\s+(\d{2}):(\d{2})\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
)
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def request_url(start: date, stop: date) -> str:
    params = {
        "format": "text",
        "COMMAND": f"'{TARGET}'",
        "CENTER": f"'{CENTER}'",
        "EPHEM_TYPE": "'OBSERVER'",
        "START_TIME": f"'{start.isoformat()}'",
        "STOP_TIME": f"'{stop.isoformat()}'",
        "STEP_SIZE": "'1d'",
        "QUANTITIES": f"'{QUANTITIES}'",
        "CSV_FORMAT": "'NO'",
        "EXTRA_PREC": "'YES'",
    }
    from urllib.parse import urlencode
    return f"https://ssd.jpl.nasa.gov/api/horizons.api?{urlencode(params)}"


def parse(text: str) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("$$SOE"):
            in_table = True
            continue
        if line.startswith("$$EOE"):
            break
        if not in_table:
            continue
        m = ROW.match(line)
        if not m:
            continue
        year, mon, day, _hh, _mm, range_au, _deldot, light_min, sot = m.groups()
        rows.append({
            "date": f"{year}-{MONTHS[mon]:02d}-{int(day):02d}",
            "range_au": round(float(range_au), 6),
            "light_time_s": round(float(light_min) * 60.0, 2),
            "sot_deg": round(float(sot), 4),
        })
    return rows


def main() -> None:
    start, stop = LAUNCH_DATE, LAUNCH_DATE + timedelta(days=DAYS)
    url = request_url(start, stop)
    print(f"GET {url}")
    text = get_url(url)
    rows = parse(text)
    if len(rows) < DAYS:
        raise SystemExit(f"ERROR: parsed only {len(rows)} rows from the Horizons table, expected about {DAYS}")
    path = write_json("horizons/mars_lt.json", rows)
    print(f"request URL for the manifest note:\n{url}")
    print(f"fixture: {path}")


if __name__ == "__main__":
    main()
