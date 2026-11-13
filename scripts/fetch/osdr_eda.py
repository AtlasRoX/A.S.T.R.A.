"""Fetch real ISS cabin air and radiation telemetry from the NASA OSDR Environmental Data App.

The EDA (https://visualization.osdr.nasa.gov/eda) publishes the ISS cabin environment and the
crew's radiation dose for every ISS research mission. Its API reference is at
https://visualization.osdr.nasa.gov/eda/api_reference

We take Rodent Research 7 (RR-7): the longest continuous cabin telemetry series in the EDA
(2018-06-29 to 2018-09-18), with matching daily radiation dose for the same dates.

Source: NASA Open Science Data Repository, Environmental Data Application (EDA)

Run from the repo root (astra/):
    uv run --no-project python -I scripts/fetch/osdr_eda.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import get_json, write_json  # noqa: E402

API = "https://visualization.osdr.nasa.gov/eda/api"
MISSION = "RR-7"

# The ISS cabin runs at about 14.5 psia, i.e. ~760 mmHg. The EDA reports CO2 in ppm and
# does not publish the cabin pressure, so we convert with the standard atmospheric pressure
# and record the assumption in the manifest note.
CABIN_PRESSURE_MMHG = 760.0

# The EDA records the cabin every 5 minutes. We keep one averaged reading per hour so the
# fixture stays inside the 500 KB budget while the daily shape survives.
STEP_MINUTES = 60


def series(mission: str, measurement: str) -> list[dict]:
    url = f"{API}/missions/{mission}/{measurement}/"
    print(f"GET {url}")
    payload = get_json(url)
    return payload.get("data", []) if isinstance(payload, dict) else payload


def sane_co2(ppm: float, median_ppm: float) -> bool:
    """Reject sensor spikes.

    The EDA CO2 series contains a handful of readings in the thousands of ppm
    (9000 ppm is a 9x jump over the rest of the series and physically implausible
    for a scrubbed cabin), so we drop anything more than 2x the median of the
    series and keep the rest untouched.
    """
    return ppm <= median_ppm * 2.0


def to_rows(raw: list[dict], key: str) -> list[dict]:
    """Telemetry rows -> one record per reading, CO2 converted to mmHg."""
    out = []
    for r in raw:
        ppm = r.get(key)
        if ppm is None:
            continue
        out.append({
            "t": r["time"],
            "co2_ppm": float(ppm),
            "co2_mmhg": round(float(ppm) / 1_000_000.0 * CABIN_PRESSURE_MMHG, 4),
        })
    return out


def median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def downsample(rows: list[dict], step_minutes: int) -> list[dict]:
    """Keep one reading per step window, averaging the values inside it.

    The EDA samples the cabin every 5 minutes; the raw series is 2.7 MB, well over the
    500 KB fixture budget. One reading per hour keeps the shape of the day (which is all
    ASTRA charts) and the averages stay faithful to the original series.
    """
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        stamp = datetime.fromisoformat(r["t"].replace("Z", "+00:00"))
        key = stamp.replace(minute=0, second=0, microsecond=0)
        if key.minute % step_minutes:
            key = (key + timedelta(minutes=step_minutes)).replace(minute=0, second=0, microsecond=0)
        buckets.setdefault(key.isoformat().replace("+00:00", "Z"), []).append(r)

    out = []
    for key in sorted(buckets):
        group = buckets[key]
        first = group[0]
        out.append({
            "t": key,
            "co2_mmhg": round(sum(g["co2_mmhg"] for g in group) / len(group), 4),
            "co2_ppm": round(sum(g["co2_ppm"] for g in group) / len(group), 2),
            "temp_c": round(sum(g["temp_c"] for g in group) / len(group), 3),
            "rh_pct": round(sum(g["rh_pct"] for g in group) / len(group), 3),
        })
    return out


def main() -> None:
    co2 = series(MISSION, "co2")
    temp = series(MISSION, "temperature")
    hum = series(MISSION, "humidity")
    if not co2:
        raise SystemExit(f"ERROR: no CO2 telemetry returned for mission {MISSION}")

    # Only non-null samples go into the lookup maps: the EDA sends a row per timestamp with
    # nulls where the sensor did not report, and a null row would otherwise overwrite a good
    # reading for the same timestamp.
    temp_by_t = {r["time"]: r["temperature_iss"] for r in temp if r.get("temperature_iss") is not None}
    hum_by_t = {r["time"]: r["humidity_iss"] for r in hum if r.get("humidity_iss") is not None}

    rows = to_rows(co2, "co2_iss")
    # Drop the sensor spikes before we join, otherwise one 9000 ppm reading drags the
    # series average around.
    med = median([r["co2_ppm"] for r in rows])
    kept = [r for r in rows if sane_co2(r["co2_ppm"], med)]
    dropped = len(rows) - len(kept)
    print(f"co2 readings: {len(rows)}, dropped {dropped} spikes (median {med:.0f} ppm)")

    # Keep only readings that have a matching temperature/humidity sample, so every point on
    # the cabin chart is a complete observation of the cabin environment.
    cabin = []
    for r in kept:
        t = temp_by_t.get(r["t"])
        h = hum_by_t.get(r["t"])
        if t is None or h is None:
            continue
        cabin.append({
            "t": r["t"],
            "co2_mmhg": r["co2_mmhg"],
            "co2_ppm": r["co2_ppm"],
            "temp_c": float(t),
            "rh_pct": float(h),
        })
    cabin = downsample(cabin, STEP_MINUTES)
    if not cabin:
        raise SystemExit("ERROR: no ISS reading had a matching temperature and humidity sample")
    write_json("osdr_eda/iss_cabin.json", cabin)

    # Daily radiation dose for the same mission, in mSv/day.
    rad = series(MISSION, "radiation_data")
    dose = []
    for r in rad:
        if r.get("total") is None:
            continue
        dose.append({"date": r["time"][:10], "dose_msv": round(float(r["total"]), 5)})
    if dose:
        write_json("osdr_eda/iss_dose.json", dose)

    print(f"cabin readings: {len(cabin)} from {cabin[0]['t']} to {cabin[-1]['t']}")
    if dose:
        print(f"dose days: {len(dose)} from {dose[0]['date']} to {dose[-1]['date']}")


if __name__ == "__main__":
    main()
