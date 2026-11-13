"""Mission simulator: real NASA data played back as scenarios, with ASTRA's rules applied.

Each scenario is a timeline the page plays like a video. The *inputs* are the NASA fixtures
the app already ships (DONKI, OSDR EDA, OSDR Inspiration4, JPL Horizons). The *reactions*
come from ASTRA's own rules (`rules.cabin_status`, `rules.cabin_insight`, `rules.classify_lab`)
and the same solar replay model the dashboard uses. Anything that is not NASA data (the replay
dose model, the crew's headache reports) is listed in the scenario's `illustrative` notes, and
the page shows those notes next to the player.

The timelines are computed, not stored: the same fixtures always give the same timeline, so a
demo video can be re-recorded frame for frame. Nothing here writes to the database, so playing
a scenario never disturbs the live demo state.

Shapes (all JSON):
  scenario = {id, title, kicker, summary, env_id, status, frame_ms, frames, charts, events,
              x_ticks, sources, datasets, real, illustrative}
  frame    = {t, label, sublabel, status, gauges, guidance, hold_ms}
  chart    = {id, label, unit, series, thresholds, y_min, y_max}
  series   = {id, label, tone, dashed, points: [[t, value | null], ...]}   (null breaks the line)
  event    = {t, frame, status, kind, title, detail, source}
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from . import rules
from .catalog import (
    CABIN,
    CONJUNCTION_SOT_DEG,
    CONJUNCTION_WARNING_DAYS,
    CREW,
    ENV_BY_ID,
    LAB_BY_ID,
    LABS,
    MISSION,
    TRANSIT_DAYS,
)
from .nasa import Registry

REPLY_THINK_S = 90.0  # same as the comms model in services.py

# Event holds: how long (ms) the player lingers on a frame where something happens, so a
# caption can be read on video.
HOLD_MAJOR = 2600
HOLD_MINOR = 1200


# ------------------------------------------------------------------------------------ helpers
def _iso(s: str) -> datetime:
    """Parse the ISO forms the fixtures use (with Z, with or without seconds)."""
    s = s.replace("Z", "+00:00")
    if len(s) == len("2021-10-28T16:35+00:00"):
        s = s[:16] + ":00" + s[16:]
    return datetime.fromisoformat(s)


def _hhmm(d: datetime) -> str:
    return d.strftime("%H:%M")


def _fmt_min(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def _gauge(gid: str, label: str, value: Any, unit: str = "", status: str | None = None,
           note: str | None = None) -> dict[str, Any]:
    return {"id": gid, "label": label, "value": value, "unit": unit, "status": status, "note": note}


def _attach_frames(events: list[dict[str, Any]], frames: list[dict[str, Any]]) -> None:
    """Give each event the index of the first frame at or after it, and hold that frame."""
    for ev in events:
        idx = next((i for i, f in enumerate(frames) if f["t"] >= ev["t"] - 1e-9), len(frames) - 1)
        ev["frame"] = idx
        hold = HOLD_MAJOR if ev["status"] in ("act", "watch") or ev.get("major") else HOLD_MINOR
        frames[idx]["hold_ms"] = max(frames[idx].get("hold_ms", 0), hold)
    events.sort(key=lambda e: (e["t"], e["frame"]))


def _json(nasa: Registry | None, source_id: str, file: str) -> Any:
    if nasa is None or not nasa.has(source_id, file):
        return None
    try:
        return nasa.json(source_id, file)
    except Exception:  # noqa: BLE001 - a broken fixture makes the scenario unavailable, not the engine
        return None


def _unavailable(sid: str, title: str, kicker: str, reason: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kicker": kicker, "status": "unavailable", "summary": reason,
            "frames": [], "charts": [], "events": [], "x_ticks": [], "sources": [], "datasets": [],
            "real": [], "illustrative": [], "frame_ms": 0, "env_id": None}


def _light_time_rows(nasa: Registry | None) -> list[dict[str, Any]]:
    return _json(nasa, "horizons-mars-lt", "horizons/mars_lt.json") or []


def _mission_delay_s(rows: list[dict[str, Any]], mission_day: int) -> float | None:
    """The one-way delay ASTRA uses on a mission day (same model as Engine.env)."""
    d = (date.fromisoformat(MISSION["launch_utc"][:10]) + timedelta(days=mission_day - 1)).isoformat()
    row = next((r for r in rows if r["date"] == d), None)
    if row is None:
        return None
    lt = float(row["light_time_s"])
    return lt * min(1.0, mission_day / TRANSIT_DAYS) if mission_day < TRANSIT_DAYS else lt


# =============================================================================================
# 1. Solar storm on the way to Mars  (DONKI + MSL/RAD + Horizons)
# =============================================================================================
# The transit day we drop the real 2021 storm onto: late in the transit, so the signal to Earth
# takes over 8 minutes and Earth's answer arrives after the crew is already in the shelter.
SOLAR_MISSION_DAY = 170


def _solar_frames_times(start: datetime, end: datetime, dense: list[tuple[datetime, datetime, int]]) -> list[datetime]:
    """Frame times: hourly by default, denser inside the given (from, to, minutes) windows."""
    out: list[datetime] = []
    t = start
    while t <= end:
        step = 60
        for a, b, minutes in dense:
            if a <= t < b:
                step = minutes
                break
        out.append(t)
        t += timedelta(minutes=step)
    return out


def solar_storm(nasa: Registry | None) -> dict[str, Any]:
    sid, title, kicker = "solar-storm", "Solar storm on the way to Mars", "NASA DONKI · MSL/RAD · JPL Horizons"
    sep = _json(nasa, "donki-sep", "donki/sep.json")
    model = _json(nasa, "donki-sep", "donki/replay.json")
    flr = _json(nasa, "donki-sep", "donki/flr.json") or []
    if not sep or not model or not model.get("events"):
        return _unavailable(sid, title, kicker, "The DONKI fixture is not downloaded yet "
                            "(run scripts/fetch/donki.py).")
    replay = next((e for e in model["events"] if e.get("is_default")), model["events"][0])
    alert_at = _iso(replay["event_time"])
    duration_s = float(replay["duration_h"]) * 3600.0
    event_dose = float(replay["event_dose_msv"])
    shelter_delay = float(model["shelter_delay_s"])
    factor = float(model["shelter_factor"])
    base_rate = float(ENV_BY_ID["transit"]["radiation_msv_day"])  # MSL/RAD cruise, mSv/day
    rows = _light_time_rows(nasa)
    delay = _mission_delay_s(rows, SOLAR_MISSION_DAY) or float(ENV_BY_ID["transit"]["delay_s"])

    # Real flares and particle detections in a window around the storm.
    flares = [f for f in flr if f.get("classType") and f["classType"][0] in "MX"]
    start = alert_at.replace(minute=0) - timedelta(hours=10)
    end = alert_at + timedelta(seconds=duration_s) + timedelta(hours=3)
    flares = [f for f in flares if start <= _iso(f["peakTime"] or f["beginTime"]) <= end]
    detections = [s for s in sep if start <= _iso(s["eventTime"]) <= end]
    x_flare = next((f for f in flares if f["classType"].startswith("X")), None)

    end_at = alert_at + timedelta(seconds=duration_s)
    sheltered_at = alert_at + timedelta(seconds=shelter_delay)
    dense = [(alert_at - timedelta(hours=2), alert_at + timedelta(hours=1), 5),
             (alert_at + timedelta(hours=1), alert_at + timedelta(hours=3), 15),
             (end_at - timedelta(minutes=30), end_at + timedelta(minutes=30), 10)]
    if x_flare:
        xt = _iso(x_flare["peakTime"] or x_flare["beginTime"])
        dense.insert(0, (xt - timedelta(minutes=30), xt + timedelta(minutes=30), 10))
    times = _solar_frames_times(start, end, dense)

    def hours(d: datetime) -> float:
        return round((d - start).total_seconds() / 3600.0, 4)

    def extra_dose(d: datetime, sheltered: bool) -> float:
        """Cumulative event dose (illustrative replay model, same maths as Engine.radiation)."""
        elapsed = min(max(0.0, (d - alert_at).total_seconds()), duration_s)
        rate = event_dose / duration_s
        if not sheltered:
            return rate * elapsed
        exposed = min(elapsed, shelter_delay)
        return rate * (exposed + max(0.0, elapsed - shelter_delay) * factor)

    frames: list[dict[str, Any]] = []
    for d in times:
        in_event = alert_at <= d < end_at
        watch = x_flare is not None and _iso(x_flare["peakTime"] or x_flare["beginTime"]) <= d < alert_at
        status = "act" if in_event else "watch" if watch else "ok"
        in_shelter = in_event and d >= sheltered_at
        with_astra = extra_dose(d, True)
        without = extra_dose(d, False)
        background = base_rate * (d - start).total_seconds() / 86400.0
        mission_day = SOLAR_MISSION_DAY + (d - start).days
        if in_event:
            guidance = {"title": "Get to the storm shelter" if not in_shelter else "Stay in the storm shelter",
                        "actions": (["Go to the water-walled aft storage module now", "Wear the shielding vest",
                                     "Postpone EVAs and non-critical maintenance"] if not in_shelter else
                                    ["Stay in the shelter until ASTRA clears the event",
                                     "Wear the shielding vest", "Keep logging how you feel"])}
        elif watch:
            guidance = {"title": "Big flare: particles may follow",
                        "actions": ["Stow EVA plans for today", "Check the route to the shelter module",
                                    "Keep the shielding vest within reach"]}
        else:
            guidance = None
        frames.append({
            "t": hours(d),
            "label": f"{d:%d %b %Y} · {_hhmm(d)} UTC",
            "sublabel": f"Replayed on mission day {mission_day} · {ENV_BY_ID['transit']['name']}",
            "status": status,
            "gauges": [
                _gauge("crew", "Crew location", "Storm shelter" if in_shelter else
                       ("Moving to shelter" if in_event else "Habitat"), "", status),
                _gauge("event", "Extra dose with ASTRA", round(with_astra, 2), "mSv",
                       "act" if in_event else None, "illustrative replay model"),
                _gauge("noshelter", "Extra dose with no shelter", round(without, 2), "mSv", None,
                       "illustrative replay model"),
                _gauge("background", "Background dose so far", round(background, 2), "mSv", None,
                       f"MSL/RAD cruise rate {base_rate} mSv/day"),
                _gauge("delay", "Signal to Earth", _fmt_min(delay), "", None,
                       "one way, JPL Horizons distance scaled to the transit"),
            ],
            "guidance": guidance,
        })

    events: list[dict[str, Any]] = []
    for f in flares:
        ft = _iso(f["peakTime"] or f["beginTime"])
        big = f["classType"].startswith("X")
        events.append({"t": hours(ft), "status": "watch" if big else "ok", "kind": "data",
                       "title": f"{f['classType']} solar flare"
                                + (f" from {f['sourceLocation']}" if f.get("sourceLocation") else ""),
                       "detail": ("An X-class flare: the strongest kind. ASTRA moves to Watch, because energetic "
                                  "particles can reach the spacecraft within an hour." if big else
                                  "Recorded by NASA DONKI. An M-class flare on its own does not change the "
                                  "crew's day."),
                       "source": "donki", "link": f.get("link"), "major": big})
    for s in detections:
        st = _iso(s["eventTime"])
        is_alert = s["sepID"] == replay["event_id"]
        names = ", ".join(i.get("displayName", "") for i in s.get("instruments") or []) or "spacecraft sensor"
        if is_alert:
            continue
        events.append({"t": hours(st), "status": "ok", "kind": "data",
                       "title": "Particles detected" if st < alert_at else "Particle event continues",
                       "detail": f"NASA DONKI solar particle event {s['sepID']}, measured by {names}.",
                       "source": "donki", "link": s.get("link")})
    instruments = ", ".join(replay.get("instruments") or []) or "GOES"
    events += [
        {"t": hours(alert_at), "status": "act", "kind": "astra", "title": "ASTRA: Act. Go to the shelter",
         "detail": f"{instruments} sees high-energy protons (DONKI {replay['event_id']}). ASTRA sends the "
                   "crew to the water-walled shelter and starts counting the event dose.",
         "source": "donki", "link": replay.get("link"), "major": True},
        {"t": hours(alert_at), "status": "ok", "kind": "comms", "title": "Alert sent to Mission Control",
         "detail": f"The signal needs {_fmt_min(delay)} to reach Earth. The crew acts on ASTRA's guidance "
                   "without waiting.", "source": "horizons"},
        {"t": hours(sheltered_at), "status": "watch", "kind": "astra", "title": "Crew in the shelter",
         "detail": f"From now on the shelter cuts the dose rate to {factor:.0%} (illustrative).",
         "major": True},
        {"t": hours(alert_at + timedelta(seconds=delay)), "status": "ok", "kind": "comms",
         "title": "Mission Control receives the alert",
         "detail": f"{_fmt_min(delay)} after it was sent. The crew has been in the shelter for "
                   f"{_fmt_min(delay - shelter_delay)}." if delay > shelter_delay else
                   f"{_fmt_min(delay)} after it was sent.", "source": "horizons"},
        {"t": hours(alert_at + timedelta(seconds=2 * delay + REPLY_THINK_S)), "status": "ok", "kind": "comms",
         "title": "Earth's reply arrives", "detail": "Mission Control confirms the shelter plan, about "
         f"{_fmt_min(2 * delay + REPLY_THINK_S)} after ASTRA had already acted.", "source": "horizons"},
        {"t": hours(end_at), "status": "ok", "kind": "astra", "title": "ASTRA: event over, leave the shelter",
         "detail": f"Dose taken: {extra_dose(end_at, True):.1f} mSv with the shelter, against "
                   f"{extra_dose(end_at, False):.1f} mSv with no shelter (illustrative).", "major": True},
    ]
    _attach_frames(events, frames)

    def series_points(fn) -> list[list[float]]:  # noqa: ANN001
        return [[f["t"], round(fn(d), 3)] for f, d in zip(frames, times, strict=True)]

    ticks = []
    t = start
    while t <= end:
        ticks.append({"t": hours(t), "label": f"{t:%d %b} {_hhmm(t)}"})
        t += timedelta(hours=6)

    saved = extra_dose(end_at, False) - extra_dose(end_at, True)
    return {
        "id": sid, "title": title, "kicker": kicker, "status": "ready", "env_id": "transit",
        "summary": (f"The real solar storm of 28 October 2021, replayed on day {SOLAR_MISSION_DAY} of a Mars "
                    f"transit. NASA DONKI recorded the {x_flare['classType'] if x_flare else 'big'} flare and the "
                    f"particle storm that followed. ASTRA sends the crew to the shelter at once. Earth hears about it "
                    f"{_fmt_min(delay)} later, and its answer arrives after {_fmt_min(2 * delay + REPLY_THINK_S)}, "
                    f"when the crew is already safe. The shelter saves about {saved:.1f} mSv in this illustrative "
                    "model."),
        "frame_ms": 420, "frames": frames, "events": events, "x_ticks": ticks,
        "x_label": "UTC, 28 to 29 October 2021",
        "charts": [{
            "id": "dose", "label": "Extra radiation dose from the storm", "unit": "mSv",
            "y_min": 0, "y_max": round(event_dose * 1.08, 1),
            "series": [
                {"id": "noshelter", "label": "No shelter", "tone": "act", "dashed": True,
                 "points": series_points(lambda d: extra_dose(d, False))},
                {"id": "astra", "label": "With ASTRA (shelter)", "tone": "accent", "dashed": False,
                 "points": series_points(lambda d: extra_dose(d, True))},
            ],
            "thresholds": [],
            "markers": [{"t": e["t"], "label": e["title"], "status": e["status"]}
                        for e in events if e["kind"] == "data" and e.get("major")],
        }],
        "sources": ["donki", "msl_rad_cruise", "horizons", "std3001v1"],
        "datasets": ["donki-sep", "msl-rad", "horizons-mars-lt"],
        "real": [
            f"Flare times and classes, and particle detections: NASA DONKI ({len(flares)} M/X flares and "
            f"{len(detections)} particle events in this window).",
            f"The alert event {replay['event_id']} and its instrument ({instruments}).",
            f"Background dose rate {base_rate} mSv/day: Curiosity's MSL/RAD cruise measurement.",
            f"Signal delay on mission day {SOLAR_MISSION_DAY}: JPL Horizons Earth-Mars distance.",
        ],
        "illustrative": [
            f"The storm's extra dose ({event_dose:g} mSv over {replay['duration_h']:g} h), the time to "
            f"reach the shelter ({shelter_delay / 60:.0f} min) and the shelter factor ({factor:.0%}) are "
            "ASTRA's replay model, not measurements.",
            "The 2021 storm is replayed as if it hit a 2027 Mars transit.",
        ],
    }


# =============================================================================================
# 2. Stale cabin air on the ISS  (OSDR EDA + STD-3001 + OCHMO-TB-004)
# =============================================================================================
CABIN_FROM = "2018-08-15T00:00:00Z"
CABIN_TO = "2018-08-29T00:00:00Z"
CABIN_STEP_H = 2
HEADACHE_AFTER_ACT_H = 6  # simulated: two crew report headaches after this many hours at Act
FILL_PPM = 200.0  # the first days of the EDA series are a constant 200 ppm sensor fill


def cabin_air(nasa: Registry | None) -> dict[str, Any]:
    sid, title, kicker = "cabin-air", "Stale air on the space station", "NASA OSDR EDA · STD-3001 · OCHMO"
    rows = _json(nasa, "osdr-eda-iss", "osdr_eda/iss_cabin.json")
    if not rows:
        return _unavailable(sid, title, kicker, "The OSDR EDA fixture is not downloaded yet.")
    rows = [r for r in rows if float(r.get("co2_ppm") or 0) > FILL_PPM]
    times = [_iso(r["t"]) for r in rows]
    t0, t1 = _iso(CABIN_FROM), _iso(CABIN_TO)
    idx = [i for i, t in enumerate(times) if t0 <= t <= t1]
    if not idx:
        return _unavailable(sid, title, kicker, "The OSDR EDA fixture does not cover the scenario window.")

    def hours(d: datetime) -> float:
        return round((d - t0).total_seconds() / 3600.0, 4)

    def avg_7d(i: int) -> float:
        lo = times[i] - timedelta(days=7)
        vals = [float(rows[j]["co2_mmhg"]) for j in range(i, -1, -1) if times[j] > lo]
        return sum(vals) / len(vals)

    two = [c["name"].split()[0] for c in CREW[:3:2]]  # Ana and Sara: the two the dashboard seed uses
    frames: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    co2_pts: list[list[float | None]] = []
    avg_pts: list[list[float | None]] = []
    prev_status = None
    act_since: datetime | None = None
    headache_at: datetime | None = None
    insight_on = False
    peak = max(idx, key=lambda i: float(rows[i]["co2_mmhg"]))

    for k, i in enumerate(idx):
        r, d = rows[i], times[i]
        if k and (d - times[idx[k - 1]]) > timedelta(hours=CABIN_STEP_H + 1):
            gap_t = hours(times[idx[k - 1]]) + 0.01
            co2_pts.append([gap_t, None])
            avg_pts.append([gap_t, None])
        if k and (d - times[idx[k - 1]]) >= timedelta(hours=12):
            gap_t = hours(times[idx[k - 1]]) + 0.01
            events.append({"t": gap_t, "status": "ok", "kind": "data", "title": "Gap in the telemetry",
                           "detail": f"No EDA readings for {(d - times[idx[k - 1]]).total_seconds() / 3600:.0f} h. "
                                     "The chart leaves the gap empty instead of drawing a line through it.",
                           "source": "osdr_eda"})
        co2, a7 = float(r["co2_mmhg"]), avg_7d(i)
        status = rules.cabin_status(co2, a7)
        co2_pts.append([hours(d), round(co2, 3)])
        avg_pts.append([hours(d), round(a7, 3)])

        if status == "act":
            act_since = act_since or d
        else:
            act_since = None
        if headache_at is None and act_since and d - act_since >= timedelta(hours=HEADACHE_AFTER_ACT_H):
            headache_at = d
            events.append({"t": hours(d), "status": "watch", "kind": "crew",
                           "title": f"{two[0]} and {two[1]} log a headache",
                           "detail": "Simulated crew reports, logged in ASTRA's symptom check.", "major": True})
        headache_crew = list(two) if headache_at and d - headache_at <= timedelta(hours=24) else []
        cab = {"status": status, "co2_1h_mmhg": co2}
        insight = rules.cabin_insight(cab, headache_crew)
        if insight and not insight_on:
            events.append({"t": hours(d), "status": insight["severity"], "kind": "astra",
                           "title": f"ASTRA: {insight['title']}", "detail": insight["body"],
                           "source": "ochmo_tb004", "major": True})
        insight_on = insight is not None

        if prev_status is None:
            events.append({"t": hours(d), "status": status, "kind": "astra",
                           "title": f"Cabin air: {rules_label(status)}",
                           "detail": f"CO2 {co2:.2f} mmHg this hour, {a7:.2f} mmHg over 7 days. "
                                     + CABIN["guide"][status], "source": "osdr_eda"})
        if status != prev_status and prev_status is not None:
            events.append({"t": hours(d), "status": status, "kind": "astra",
                           "title": f"Cabin air: {rules_label(status)}",
                           "detail": CABIN["guide"][status],
                           "source": "std3001v2" if status == "act" else "ochmo_tb004"})
        prev_status = status
        if i == peak:
            events.append({"t": hours(d), "status": "act", "kind": "data",
                           "title": f"Highest reading: {co2:.2f} mmHg",
                           "detail": f"{float(r['co2_ppm']):.0f} ppm on {d:%d %b %Y} at {_hhmm(d)} UTC, real ISS "
                                     f"telemetry. That is {co2 / CABIN['act_1h_mmhg']:.1f} times NASA's "
                                     "one-hour limit.",
                           "source": "osdr_eda", "major": True})

        if k % CABIN_STEP_H and i != peak:
            continue
        frames.append({
            "t": hours(d),
            "label": f"{d:%d %b %Y} · {_hhmm(d)} UTC",
            "sublabel": "International Space Station · Rodent Research 7 telemetry",
            "status": status,
            "gauges": [
                _gauge("co2", "CO2, this hour", round(co2, 2), "mmHg", "act" if co2 >= CABIN["act_1h_mmhg"] else None,
                       f"limit {CABIN['act_1h_mmhg']} mmHg (STD-3001)"),
                _gauge("co2_7d", "CO2, 7-day average", round(a7, 2), "mmHg",
                       "watch" if a7 >= CABIN["watch_7d_mmhg"] else None,
                       f"watch at {CABIN['watch_7d_mmhg']} mmHg (OCHMO)"),
                _gauge("ppm", "CO2 as measured", round(float(r["co2_ppm"])), "ppm", None, "outdoor air is about 420"),
                _gauge("temp", "Cabin temperature", round(float(r["temp_c"]), 1), "°C"),
                _gauge("rh", "Humidity", round(float(r["rh_pct"])), "%"),
                _gauge("headache", "Crew with a headache", len(headache_crew), "",
                       "watch" if headache_crew else None, "simulated reports"),
            ],
            "guidance": ({"title": insight["title"], "actions": insight.get("actions") or CABIN["actions"][status]}
                         if insight else
                         {"title": rules_label(status), "actions": CABIN["actions"][status]}
                         if status != "ok" else None),
        })

    _attach_frames(events, frames)
    ticks = []
    d = t0
    while d <= t1:
        ticks.append({"t": hours(d), "label": f"{d:%d %b}"})
        d += timedelta(days=2)
    return {
        "id": sid, "title": title, "kicker": kicker, "status": "ready", "env_id": "station",
        "summary": ("Two weeks of real ISS cabin telemetry from August 2018. On 20 August the CO2 jumps from "
                    "about 3,000 to 6,500 ppm and stays high for a week. ASTRA applies NASA's limits hour by hour, "
                    "and when two crew log headaches it tells them the cause is the air, not them."),
        "frame_ms": 230, "frames": frames, "events": events, "x_ticks": ticks, "x_label": "UTC, August 2018",
        "charts": [{
            "id": "co2", "label": "Cabin CO2", "unit": "mmHg", "y_min": 1.5, "y_max": 5.5,
            "series": [
                {"id": "co2", "label": "CO2, hourly (real)", "tone": "accent", "dashed": False, "points": co2_pts},
                {"id": "avg", "label": "7-day average", "tone": "muted", "dashed": True, "points": avg_pts},
            ],
            "thresholds": [
                {"value": CABIN["act_1h_mmhg"], "label": "Act: 1-hour limit (STD-3001)", "status": "act"},
                {"value": CABIN["watch_7d_mmhg"], "label": "Watch: 7-day level (OCHMO)", "status": "watch"},
            ],
            "markers": [],
        }],
        "sources": ["osdr_eda", "std3001v2", "ochmo_tb004"],
        "datasets": ["osdr-eda-iss", "std3001v2", "ochmo-tb004"],
        "real": [
            "Hourly CO2, temperature and humidity: NASA OSDR Environmental Data App, Rodent Research 7 "
            "(ISS, 15 to 29 August 2018). Gaps are real gaps in the telemetry.",
            f"Limits: {CABIN['act_1h_mmhg']} mmHg one-hour (NASA-STD-3001 Vol 2) and "
            f"{CABIN['watch_7d_mmhg']} mmHg 7-day (OCHMO-TB-004).",
        ],
        "illustrative": [
            f"The headache reports from {two[0]} and {two[1]} are simulated crew input.",
            "ppm is converted to mmHg at 760 mmHg cabin pressure (the EDA does not publish pressure).",
            "The sensor sits in the RR-7 hardware location, so it may read higher than the cabin average.",
        ],
    }


def rules_label(status: str) -> str:
    return {"ok": "Nominal", "watch": "Watch", "act": "Act"}[status]


# =============================================================================================
# 3. Blood work around a real spaceflight  (OSDR Inspiration4)
# =============================================================================================
I4_TIMEPOINTS = [("L-92", "92 days before launch"), ("L-44", "44 days before launch"),
                 ("L-3", "3 days before launch"), ("R+1", "1 day after landing"),
                 ("R+45", "45 days after landing"), ("R+82", "82 days after landing"),
                 ("R+194", "194 days after landing")]
I4_FEATURED = ["potassium", "glucose", "lymphocytes", "hemoglobin"]


def _side(r: dict[str, Any]) -> str:
    return "high" if r.get("ref_high") is not None and r["value"] > r["ref_high"] else "low"


def inspiration4_labs(nasa: Registry | None) -> dict[str, Any]:
    sid, title, kicker = "inspiration4", "Blood work around a real spaceflight", "NASA OSDR · Inspiration4"
    rows = _json(nasa, "osdr-i4-labs", "osdr_i4/labs.json")
    if not rows:
        return _unavailable(sid, title, kicker, "The OSDR Inspiration4 fixture is not downloaded yet.")
    subjects = sorted({r["subject"] for r in rows})
    present = [lab for lab in LABS if any(r["analyte"] == lab["id"] for r in rows)]
    by_tp: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_tp.setdefault(r["timepoint"], []).append(r)
    timepoints = [(tp, label) for tp, label in I4_TIMEPOINTS if tp in by_tp]

    frames: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for tp, label in timepoints:
        tp_rows = by_tp[tp]
        day = tp_rows[0]["day"]
        flagged = []
        for r in tp_rows:
            st = rules.classify_lab(r["value"], r.get("ref_low"), r.get("ref_high"))
            if st != "ok":
                flagged.append((r, st))
        worst = "act" if any(s == "act" for _, s in flagged) else "watch" if flagged else "ok"
        gauges = []
        for lab in present:
            vals = [r for r in tp_rows if r["analyte"] == lab["id"]]
            if not vals:
                continue
            sts = [rules.classify_lab(r["value"], r.get("ref_low"), r.get("ref_high")) for r in vals]
            n_bad = sum(1 for s in sts if s != "ok")
            gauges.append(_gauge(lab["id"], lab["label"], f"{n_bad} of {len(vals)}" if n_bad else "all in range",
                                 "", "act" if "act" in sts else "watch" if "watch" in sts else "ok"))
        frames.append({
            "t": day, "label": label, "sublabel": f"Sample {tp} · {len(tp_rows)} real lab values",
            "status": worst, "gauges": gauges,
            "guidance": ({"title": f"{len(flagged)} value(s) outside the reference range",
                          "actions": [f"{r['subject']}: {LAB_BY_ID[r['analyte']]['label']} {r['value']:g} "
                                      f"{r['unit']} ({_side(r)})"
                                      for r, _ in sorted(flagged, key=lambda x: x[1] != "act")][:5]}
                         if flagged else None),
        })
        if tp == "R+1":
            events.append({"t": day, "status": "ok", "kind": "data", "title": "Back on Earth after 3 days in orbit",
                           "detail": "Inspiration4 splashed down on 18 September 2021. This is the first "
                                     "blood draw after "
                                     "landing.", "source": "osdr_i4", "major": True})
        for r, st in flagged:
            if st != "act":
                continue
            lab = LAB_BY_ID[r["analyte"]]
            hi = r.get("ref_high") is not None and r["value"] > r["ref_high"]
            rng = f"{r.get('ref_low')}–{r.get('ref_high')} {r['unit']}"
            events.append({"t": day, "status": "act", "kind": "astra",
                           "title": f"ASTRA flags {lab['label'].lower()} for crew {r['subject'][-1]}",
                           "detail": f"{r['value']:g} {r['unit']} is {'above' if hi else 'below'} the range ({rng}) "
                                     f"by more than 10%. {lab['why']}", "source": "osdr_i4"})
        if not flagged:
            events.append({"t": day, "status": "ok", "kind": "astra", "title": "All values in range",
                           "detail": "Every lab value for all four crew sits inside its reference range.",
                           "source": "osdr_i4"})
    _attach_frames(events, frames)

    charts = []
    for aid in I4_FEATURED + [lab["id"] for lab in present if lab["id"] not in I4_FEATURED]:
        lab = LAB_BY_ID.get(aid)
        entries = [r for r in rows if r["analyte"] == aid]
        if not lab or not entries:
            continue
        lows = [e["ref_low"] for e in entries if e.get("ref_low") is not None]
        highs = [e["ref_high"] for e in entries if e.get("ref_high") is not None]
        low = min(lows) if lows else None  # widest range: men and women have different ranges
        high = max(highs) if highs else None
        vals = [e["value"] for e in entries] + [v for v in (low, high) if v is not None]
        pad = (max(vals) - min(vals)) * 0.12 or 1.0
        thresholds = []
        if low is not None:
            thresholds.append({"value": low, "label": f"Low end {low:g}", "status": "watch"})
        if high is not None:
            thresholds.append({"value": high, "label": f"High end {high:g}", "status": "watch"})
        charts.append({
            "id": aid, "label": lab["label"], "unit": lab["unit"],
            "y_min": round(min(vals) - pad, 2), "y_max": round(max(vals) + pad, 2),
            "series": [{"id": s, "label": f"Crew {s[-1]}", "tone": tone, "dashed": False,
                        "points": [[e["day"], e["value"]] for e in sorted(entries, key=lambda x: x["day"])
                                   if e["subject"] == s]}
                       for s, tone in zip(subjects, ["accent", "muted", "ok", "watch"], strict=False)],
            "thresholds": thresholds, "markers": [],
        })
    return {
        "id": sid, "title": title, "kicker": kicker, "status": "ready", "env_id": "station",
        "summary": ("Four real civilians flew Inspiration4 in September 2021. Their blood was drawn seven times, "
                    "from three months before launch to six months after landing. ASTRA reads each draw against "
                    "the dataset's own reference ranges and flags what a crew medical officer should look at."),
        "frame_ms": 3200, "frames": frames, "events": events,
        "x_ticks": [{"t": f["t"], "label": tp} for f, (tp, _) in zip(frames, timepoints, strict=True)],
        "x_label": "Days from launch (Inspiration4, 2021)", "x_scale": "ordinal",
        "charts": charts,
        "sources": ["osdr_i4", "i4_omics"],
        "datasets": ["osdr-i4-labs"],
        "real": [f"{len(rows)} lab values for {len(subjects)} crew at {len(timepoints)} draws, with the reference "
                 "ranges the NASA OSDR dataset ships with."],
        "illustrative": ["The Watch / Act labels are ASTRA's rule (outside the range, and more than 10% "
                         "outside), not a clinical judgement."],
    }


# =============================================================================================
# 4. Mars behind the Sun  (JPL Horizons)
# =============================================================================================
CONJ_STEP_DAYS = 3


def conjunction(nasa: Registry | None) -> dict[str, Any]:
    sid, title, kicker = "conjunction", "Mars goes behind the Sun", "NASA/JPL Horizons"
    rows = _light_time_rows(nasa)
    if not rows:
        return _unavailable(sid, title, kicker, "The JPL Horizons fixture is not downloaded yet.")
    launch = date.fromisoformat(MISSION["launch_utc"][:10])

    def mday(r: dict[str, Any]) -> int:
        return (date.fromisoformat(r["date"]) - launch).days + 1

    blackout = [r for r in rows if float(r["sot_deg"]) <= CONJUNCTION_SOT_DEG]
    first_b = blackout[0] if blackout else None
    last_b = blackout[-1] if blackout else None
    closest = min(rows, key=lambda r: float(r["sot_deg"]))
    warn_from = mday(first_b) - CONJUNCTION_WARNING_DAYS if first_b else None

    frames: list[dict[str, Any]] = []
    delay_pts, sot_pts = [], []
    key_days = {mday(r) for r in (first_b, last_b, closest) if r} | {TRANSIT_DAYS, 1, mday(rows[-1])}
    if warn_from:
        key_days.add(warn_from)
    for r in rows:
        day = mday(r)
        delay = _mission_delay_s(rows, day) or float(r["light_time_s"])
        delay_pts.append([day, round(delay / 60, 2)])
        sot_pts.append([day, round(float(r["sot_deg"]), 2)])
        if (day - 1) % CONJ_STEP_DAYS and day not in key_days:
            continue
        sot = float(r["sot_deg"])
        status = ("act" if sot <= CONJUNCTION_SOT_DEG else
                  "watch" if warn_from and warn_from <= day < mday(first_b) else "ok")
        where = "Mars transit" if day < TRANSIT_DAYS else "Mars surface base"
        frames.append({
            "t": day, "label": f"Mission day {day} · {date.fromisoformat(r['date']):%d %b %Y}",
            "sublabel": where, "status": status,
            "gauges": [
                _gauge("delay", "Signal to Earth, one way", _fmt_min(delay), "", None,
                       "scaled to the transit" if day < TRANSIT_DAYS else "real light time"),
                _gauge("rt", "Question and answer", _fmt_min(2 * delay + REPLY_THINK_S), "", None,
                       "round trip plus 90 s to reply"),
                _gauge("sot", "Sun-Mars angle seen from Earth", round(sot, 2), "°",
                       status if status != "ok" else None, f"blackout below {CONJUNCTION_SOT_DEG:g}°"),
                _gauge("range", "Earth-Mars distance", round(float(r["range_au"]), 3), "AU"),
                _gauge("link", "Radio link", "Blocked by the Sun" if status == "act" else
                       "Plan ahead" if status == "watch" else "Normal", "", status if status != "ok" else None),
            ],
            "guidance": ({"title": "Solar conjunction: ASTRA runs on its own",
                          "actions": ["Treat every medical problem with the onboard protocols",
                                      "The Crew Medical Officer has the final call",
                                      "Queue routine reports until the link returns"]} if status == "act" else
                         {"title": f"Conjunction in {mday(first_b) - day} days",
                          "actions": ["Send routine medical data to Earth now",
                                      "Ask Mission Control the open questions before the blackout",
                                      "Refresh the onboard medical kit inventory"]} if status == "watch" else None),
        })

    def at(day: int) -> float:
        return next(p[1] for p in delay_pts if p[0] >= day)

    events: list[dict[str, Any]] = [
        {"t": 1, "status": "ok", "kind": "data", "title": "Launch",
         "detail": f"{launch:%d %b %Y}, inside a real 2026 Earth-Mars launch window. Earth is "
                   f"{_fmt_min(_mission_delay_s(rows, 1) or 0)} away by radio.", "source": "horizons"},
    ]
    for mins in (5, 10):
        hit = next((p for p in delay_pts if p[1] >= mins), None)
        if hit:
            events.append({"t": hit[0], "status": "ok", "kind": "data", "title": f"Signal delay passes {mins} minutes",
                           "detail": "ASTRA stops waiting for Earth: a question and answer now takes over "
                                     f"{2 * mins} minutes.", "source": "horizons"})
    events.append({"t": TRANSIT_DAYS, "status": "ok", "kind": "data", "title": "Arrival at Mars",
                   "detail": f"One-way delay {at(TRANSIT_DAYS):.1f} min.", "source": "horizons", "major": True})
    if first_b and last_b and warn_from:
        events += [
            {"t": warn_from, "status": "watch", "kind": "astra", "title": "ASTRA: conjunction in 30 days",
             "detail": "Horizons shows the Sun moving between Earth and Mars. ASTRA starts the pre-blackout "
                       "checklist.", "source": "horizons"},
            {"t": mday(first_b), "status": "act", "kind": "astra", "title": "Radio blackout begins",
             "detail": f"{date.fromisoformat(first_b['date']):%d %b %Y}: Mars is within {CONJUNCTION_SOT_DEG:g}° of "
                       "the Sun. The crew relies on ASTRA and the Crew Medical Officer.", "source": "horizons",
             "major": True},
            {"t": mday(closest), "status": "act", "kind": "data",
             "title": f"Sun almost directly between: {float(closest['sot_deg']):.2f}°",
             "detail": f"{date.fromisoformat(closest['date']):%d %b %Y}, {float(closest['range_au']):.2f} AU away, "
                       f"{float(closest['light_time_s']) / 60:.1f} min one way.", "source": "horizons"},
            {"t": mday(last_b) + 1, "status": "ok", "kind": "astra", "title": "Link back: blackout over",
             "detail": f"{len(blackout)} days without reliable contact. ASTRA sends the queued medical "
                       "reports.", "source": "horizons", "major": True},
        ]
    _attach_frames(events, frames)
    span = mday(rows[-1])
    ticks = [{"t": d, "label": f"Day {d}"} for d in range(1, span + 1, 90)]
    return {
        "id": sid, "title": title, "kicker": kicker, "status": "ready", "env_id": "mars",
        "summary": (f"The real Earth-Mars geometry for a crew launched on {launch:%d %b %Y}. The radio delay grows "
                    f"from {delay_pts[0][1] * 60:.0f} s to {max(p[1] for p in delay_pts):.0f} min, and "
                    + (f"from {date.fromisoformat(first_b['date']):%d %b} to "
                       f"{date.fromisoformat(last_b['date']):%d %b %Y} "
                       f"the Sun blocks the link for {len(blackout)} days. ASTRA plans for it a month ahead."
                       if first_b and last_b else "no conjunction falls inside the downloaded window.")),
        "frame_ms": 170, "frames": frames, "events": events, "x_ticks": ticks, "x_label": "Mission day",
        "charts": [
            {"id": "delay", "label": "Signal delay to Earth, one way", "unit": "min", "y_min": 0,
             "y_max": round(max(p[1] for p in delay_pts) * 1.1, 1),
             "series": [{"id": "delay", "label": "One-way delay", "tone": "accent", "dashed": False,
                         "points": delay_pts}],
             "thresholds": [], "markers": []},
            {"id": "sot", "label": "Sun-Mars angle seen from Earth", "unit": "°", "y_min": 0,
             "y_max": round(max(p[1] for p in sot_pts) * 1.05, 0),
             "series": [{"id": "sot", "label": "Sun-Mars angle", "tone": "watch", "dashed": False,
                         "points": sot_pts}],
             "thresholds": [{"value": CONJUNCTION_SOT_DEG, "label": f"Blackout below {CONJUNCTION_SOT_DEG:g}°",
                             "status": "act"}], "markers": []},
        ],
        "sources": ["horizons"],
        "datasets": ["horizons-mars-lt"],
        "real": [f"{len(rows)} days of Earth-Mars distance, light time and Sun-Mars angle from NASA/JPL Horizons "
                 f"({rows[0]['date']} to {rows[-1]['date']})."],
        "illustrative": [
            f"The {CONJUNCTION_SOT_DEG:g}° blackout threshold is ASTRA's planning rule; real link loss depends "
            "on the radio system.",
            f"During the {TRANSIT_DAYS}-day transit the delay is the Earth-Mars light time scaled by progress.",
        ],
    }


# =============================================================================================
# Slots for the official data released on 13 November
# =============================================================================================
def slot_scenarios(nasa: Registry | None) -> list[dict[str, Any]]:
    out = []
    for src in (nasa.sources() if nasa else []):
        # A filled slot holding documents (role "evidence") has no timeline to play, so only the
        # slots still waiting for data are listed as scenarios.
        if not src.get("slot") or src.get("status") == "ready":
            continue
        out.append({
            "id": src["id"], "title": f"Slot {src['slot']}: official data",
            "kicker": src.get("title") or "Official challenge data",
            "status": "pending" if src.get("status") != "ready" else "ready-unwired",
            "summary": src.get("note") or "Reserved for the official data released on 13 November.",
            "frames": [], "charts": [], "events": [], "x_ticks": [], "sources": [], "datasets": [src["id"]],
            "real": [], "illustrative": [], "frame_ms": 0, "env_id": None,
        })
    return out


# =============================================================================================
BUILDERS = {
    "solar-storm": solar_storm,
    "cabin-air": cabin_air,
    "conjunction": conjunction,
    "inspiration4": inspiration4_labs,
}
STORY_ORDER = ["cabin-air", "solar-storm", "conjunction", "inspiration4"]


class Simulator:
    """Builds the scenarios once per registry and keeps them (the fixtures are read-only)."""

    def __init__(self, nasa: Registry | None) -> None:
        self.nasa = nasa
        self._cache: dict[str, dict[str, Any]] = {}

    def scenario(self, sid: str) -> dict[str, Any] | None:
        if sid not in BUILDERS:
            return next((s for s in slot_scenarios(self.nasa) if s["id"] == sid), None)
        if sid not in self._cache:
            self._cache[sid] = BUILDERS[sid](self.nasa)
        return self._cache[sid]

    def summaries(self) -> list[dict[str, Any]]:
        out = []
        for sid in STORY_ORDER:
            sc = self.scenario(sid)
            assert sc is not None
            out.append({k: sc.get(k) for k in ("id", "title", "kicker", "summary", "status", "env_id",
                                                "sources", "datasets")}
                       | {"frames": len(sc["frames"]), "events": len(sc["events"])})
        for sc in slot_scenarios(self.nasa):
            out.append({k: sc.get(k) for k in ("id", "title", "kicker", "summary", "status", "env_id",
                                                "sources", "datasets")} | {"frames": 0, "events": 0})
        return out
