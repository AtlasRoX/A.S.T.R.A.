"""Fetch real solar particle events from NASA DONKI.

DONKI (Discrete Occurrence Notification and Knowledge Information) is NASA CCMC's space-weather
event service. It publishes Solar Particle Events (SEP), solar flares (FLR) and geomagnetic storms
(GST).

Base URLs, in the order we try them:
  1. https://ccmc.gsfc.nasa.gov/DONKI-API/get/   (CCMC's current DONKI API, no key needed; confirmed
     working on 2026-11-09)
  2. https://api.nasa.gov/DONKI/                 (the api.nasa.gov gateway; the shared DEMO_KEY is often
     rate-limited, so set NASA_API_KEY to your own free key from https://api.nasa.gov/)

Both serve the same data. The old kauai.ccmc.gsfc.nasa.gov/DONKI/WS/ hosts did not answer from our
network, so they are no longer tried.

Besides the raw event lists, the script writes donki/replay.json: the event ASTRA replays, taken
from the real SEP list, plus the replay model's dose numbers, which are ILLUSTRATIVE (DONKI records
when and where a particle event was seen, not what dose a crew would get).

Source: NASA DONKI, https://donki.gsfc.nasa.gov/  and  https://kauai.ccmc.gsfc.nasa.gov/DONKI/

Run from the repo root (astra/):
    uv run --no-project python -I scripts/fetch/donki.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import get_json, write_json  # noqa: E402

START_DATE = "2021-10-01"
END_DATE = "2021-11-30"
API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")

# We replay the 28 October 2021 solar particle event (the first ground-level enhancement of
# solar cycle 25). This sepID is GOES-P's >100 MeV detection of it, as listed by DONKI.
REPLAY_EVENT_ID = "2021-10-28T16:35:00-SEP-001"

# Replay model. ILLUSTRATIVE numbers chosen by the ASTRA team, not DONKI measurements:
# extra dose an unsheltered crew would take over the event, how long the event lasts, how long the
# crew takes to reach the shelter, and the fraction of the dose rate left inside the shelter.
REPLAY_MODEL = {
    "event_dose_msv": 10.0,
    "duration_h": 24.0,
    "shelter_delay_s": 600.0,
    "shelter_factor": 0.25,
}

GATEWAYS = [
    ("ccmc-donki-api", "https://ccmc.gsfc.nasa.gov/DONKI-API/get", {}),
    ("api.nasa.gov", "https://api.nasa.gov/DONKI", {"api_key": API_KEY}),
]


def fetch(kind: str) -> tuple[list[dict], str]:
    """Fetch one DONKI product, trying each gateway in turn. Returns (rows, gateway name)."""
    errors = []
    for name, base, extra in GATEWAYS:
        params = {"startDate": START_DATE, "endDate": END_DATE, **extra}
        url = f"{base}/{kind}"
        try:
            print(f"GET {url}?{params}")
            payload = get_json(url, params)
        except Exception as exc:  # noqa: BLE001 - we want to try the next gateway
            errors.append(f"{name}: {exc}")
            continue
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            errors.append(f"{name}: unexpected response type {type(payload).__name__}")
            continue
        return payload, name
    raise SystemExit("ERROR: no DONKI gateway answered.\n  " + "\n  ".join(errors))


def slim(rows: list[dict]) -> list[dict]:
    """Keep only the fields ASTRA shows: which event, when, what measured it, and the link."""
    out = []
    for r in rows:
        out.append({
            "sepID": r.get("sepID"),
            "eventTime": r.get("eventTime"),
            "instruments": r.get("instruments"),
            "linkedEvents": r.get("linkedEvents"),
            "link": r.get("link"),
        })
    return out


def slim_flares(rows: list[dict]) -> list[dict]:
    """Keep the flare fields ASTRA shows: when, how strong (GOES class), where on the Sun, and the link."""
    return [{
        "flrID": r.get("flrID"),
        "beginTime": r.get("beginTime"),
        "peakTime": r.get("peakTime"),
        "endTime": r.get("endTime"),
        "classType": r.get("classType"),
        "sourceLocation": r.get("sourceLocation"),
        "activeRegionNum": r.get("activeRegionNum"),
        "link": r.get("link"),
    } for r in rows]


def replay(sep: list[dict]) -> dict:
    """The replay fixture the engine reads: one real event plus the illustrative dose model."""
    row = next((r for r in sep if r.get("sepID") == REPLAY_EVENT_ID), None)
    if row is None:
        raise SystemExit(f"ERROR: replay event {REPLAY_EVENT_ID} is not in the DONKI SEP list")
    instruments = [i.get("displayName") for i in row.get("instruments") or [] if i.get("displayName")]
    return {
        "shelter_delay_s": REPLAY_MODEL["shelter_delay_s"],
        "shelter_factor": REPLAY_MODEL["shelter_factor"],
        "events": [{
            "event_id": row["sepID"],
            "label": "Solar particle event of 28 Oct 2021 (replay of DONKI " + row["sepID"] + ")",
            "event_time": row.get("eventTime"),
            "instruments": instruments,
            "link": row.get("link"),
            "duration_h": REPLAY_MODEL["duration_h"],
            "event_dose_msv": REPLAY_MODEL["event_dose_msv"],
            "illustrative_note": "The event's time, instruments and link are real NASA DONKI data. The dose, "
            "duration and shelter numbers are an illustrative ASTRA replay model, not a DONKI measurement.",
            "is_default": True,
        }],
    }


def main() -> None:
    sep, sep_gateway = fetch("SEP")
    if not sep:
        raise SystemExit("ERROR: DONKI returned no solar particle events for the window")
    write_json("donki/sep.json", slim(sep))
    print(f"SEP events: {len(sep)} (gateway: {sep_gateway})")
    write_json("donki/replay.json", replay(sep))

    try:
        flr, flr_gateway = fetch("FLR")
        write_json("donki/flr.json", slim_flares(flr))
        print(f"flares: {len(flr)} (gateway: {flr_gateway})")
    except SystemExit as exc:
        print(f"WARNING: flares not fetched ({exc}); SEP is the one ASTRA needs.")


if __name__ == "__main__":
    main()
