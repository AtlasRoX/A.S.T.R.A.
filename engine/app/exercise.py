"""Exercise countermeasures: the exercise catalog, the hardware each location has, and a weekly plan per crew member.

The week follows the shape of NASA's SPRINT study on the ISS (English et al., npj Microgravity 2020): resistance
training 3 days a week, aerobic training 3 days a week alternating interval and continuous sessions, with intervals
above 90 % of max heart rate. It matched the older 6-days-a-week programme with 34-44 % less resistance volume.

The plan is then adjusted per person, from two inputs:
  - medical history in the crew profile (e.g. a repaired knee, raised blood pressure), and
  - today's readings (e.g. a fever, short sleep, low food intake),
and every adjustment says why, so the crew can see what changed and what drove it.

Doses are illustrative for the demo, not a prescription.
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------------------------
# Hardware per location. Space-station hardware is real ISS hardware; transit uses a compact flywheel, as Orion
# does, because there is no room for ARED or a treadmill.
# --------------------------------------------------------------------------------------------
DEVICES: dict[str, dict[str, str]] = {
    "ared": {"name": "ARED", "full": "Advanced Resistive Exercise Device",
             "note": "Vacuum cylinders give up to about 270 kg (600 lb) of load, like a barbell on Earth."},
    "t2": {"name": "T2 treadmill", "full": "COLBERT / T2 treadmill",
           "note": "A harness and bungees pull you onto the belt so your feet take your weight."},
    "cevis": {"name": "CEVIS", "full": "Cycle Ergometer with Vibration Isolation and Stabilization",
              "note": "A seatless bike: you clip your shoes in and pedal, held in place by your feet."},
    "flywheel": {"name": "Flywheel", "full": "Compact flywheel exercise device",
                 "note": "A shoebox-sized flywheel, as on Orion: a cable resists both the pull and the return."},
    "cycle": {"name": "Cycle ergometer", "full": "Compact cycle ergometer",
              "note": "A small seatless bike that bolts to the floor of the habitat."},
    "weights": {"name": "Free weights", "full": "Barbell and plates",
                "note": "In partial gravity you need extra load: your body weighs only a fraction of Earth weight."},
    "treadmill": {"name": "Treadmill", "full": "Habitat treadmill",
                  "note": "Partial gravity lets you run without a harness, but impact is lower than on Earth."},
}

# Which device each exercise uses in each location; an exercise missing from a location is not available there.
_STATION = {"squat": "ared", "deadlift": "ared", "heel_raise": "ared", "press": "ared",
            "run": "t2", "cycle_intervals": "cevis", "cycle_steady": "cevis"}
_TRANSIT = {"squat": "flywheel", "deadlift": "flywheel", "heel_raise": "flywheel", "row": "flywheel",
            "cycle_intervals": "cycle", "cycle_steady": "cycle"}
_SURFACE = {"squat": "weights", "deadlift": "weights", "heel_raise": "weights", "press": "weights",
            "run": "treadmill", "cycle_intervals": "cycle", "cycle_steady": "cycle"}
LOCATION_DEVICES: dict[str, dict[str, str]] = {
    "station": _STATION, "transit": _TRANSIT, "rover": _TRANSIT, "lunar": _SURFACE, "mars": _SURFACE,
}

# --------------------------------------------------------------------------------------------
# Exercises. `anim` names the figure animation in the web app; `video` is filled from VIDEOS below.
# --------------------------------------------------------------------------------------------
EXERCISES: dict[str, dict[str, Any]] = {
    "squat": {
        "name": "Squat", "kind": "resistance", "anim": "squat",
        "targets": ["Hips", "Thighs", "Spine"],
        "why": "Loads the hips and spine, where astronauts lose the most bone: about 1-1.5 % a month without it.",
        "cues": ["Feet shoulder-width, bar across the upper back", "Sit back until thighs are level",
                 "Drive up through the heels; breathe out on the way up"],
    },
    "deadlift": {
        "name": "Deadlift", "kind": "resistance", "anim": "deadlift",
        "targets": ["Back", "Glutes", "Hamstrings"],
        "why": "Keeps the back and hip muscles strong; back pain is common after the spine lengthens in "
               "microgravity.",
        "cues": ["Hinge at the hips, back flat", "Bar close to the shins", "Stand tall, squeeze the glutes at the top"],
    },
    "heel_raise": {
        "name": "Heel raise", "kind": "resistance", "anim": "heel_raise",
        "targets": ["Calves", "Ankles"],
        "why": "Calf muscles shrink fastest in microgravity because feet no longer carry weight.",
        "cues": ["Bar on the shoulders, knees soft", "Rise onto the balls of the feet", "Lower slowly, 2 seconds down"],
    },
    "press": {
        "name": "Bench press", "kind": "resistance", "anim": "press",
        "targets": ["Chest", "Shoulders", "Arms"],
        "why": "Upper-body strength for EVA suit work, hatch operations and emergency egress.",
        "cues": ["Shoulder blades pulled back", "Lower the bar to mid-chest", "Press up and slightly back"],
    },
    "row": {
        "name": "Seated row", "kind": "resistance", "anim": "row",
        "targets": ["Back", "Arms", "Grip"],
        "why": "Upper-body pulling strength for suit work and hatch operations; the flywheel loads both directions.",
        "cues": ["Feet braced, back tall", "Pull the handle to the lower ribs",
                 "Let the flywheel pull you back slowly"],
    },
    "run": {
        "name": "Treadmill run", "kind": "aerobic", "anim": "run",
        "targets": ["Heart", "Lungs", "Legs", "Bones"],
        "why": "Running is the only aerobic exercise that also gives bones the impact they need.",
        "cues": ["Harness snug at hips and shoulders", "Short, quick steps", "Land mid-foot under the hips"],
    },
    "cycle_intervals": {
        "name": "Cycle intervals", "kind": "aerobic", "anim": "cycle",
        "targets": ["Heart", "Lungs"],
        "why": "Short hard intervals keep aerobic fitness (VO2max) high in a fraction of the time.",
        "cues": ["Clip in, hands light on the bars", "Hard: above 90 % of max heart rate",
                 "Easy pedalling between efforts"],
    },
    "cycle_steady": {
        "name": "Steady ride", "kind": "aerobic", "anim": "cycle",
        "targets": ["Heart", "Lungs"],
        "why": "Steady endurance work builds the base for EVAs and long work days.",
        "cues": ["Hold a pace you could talk at", "About 70-75 % of max heart rate", "Keep cadence smooth, 70-90 rpm"],
    },
}

# Real footage for every exercise on every device, trimmed to the seconds where that exercise is on screen.
# YouTube ids were checked against oEmbed (exists, embeddable, official agency channel); NASA files come from the
# public-domain NASA Image and Video Library. Start/end seconds were read off frames sampled from each video.
# Where no footage of the exact device exists, the closest real clip is used and `note` says so.
_NASA_TERMS = {"license": "NASA media: not copyrighted in the US; no endorsement implied",
               "license_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/"}


def _clip(youtube: str, start: int, end: int, shows: str, who: str, where: str, title: str, channel: str,
          published: str, **terms: str) -> dict[str, Any]:
    """A clip of an agency's YouTube video."""
    return {"youtube": youtube, "mp4": None, "start": start, "end": end, "shows": shows, "who": who,
            "where": where, "title": title, "channel": channel, "published": published,
            "url": f"https://www.youtube.com/watch?v={youtube}&t={start}s", **terms}


def _nasa(nasa_id: str, start: int, end: int, shows: str, who: str, where: str, title: str,
          published: str) -> dict[str, Any]:
    """A clip of a public-domain video in the NASA Image and Video Library, played from NASA's own file."""
    return {"youtube": None, "start": start, "end": end, "shows": shows, "who": who, "where": where,
            "mp4": f"https://images-assets.nasa.gov/video/{nasa_id}/{nasa_id}~medium.mp4",
            "title": title, "channel": "NASA Image and Video Library", "published": published,
            "url": f"https://images.nasa.gov/details/{nasa_id}", **_NASA_TERMS}


_WHEELOCK_T = ("Weightlifting on the International Space Station With Astronaut Doug Wheelock", "NASA Video",
               "2013-05-11")
_ARED_SQUAT = _clip("gzynkaHuHwY", 84, 172, "Squats on ARED", "Doug Wheelock", "International Space Station",
                    *_WHEELOCK_T, **_NASA_TERMS)
_ARED_BENCH = _clip("gzynkaHuHwY", 236, 276, "Bench press on ARED", "Doug Wheelock", "International Space Station",
                    *_WHEELOCK_T, **_NASA_TERMS)
_ARED_DEADLIFT = _clip("YxImeOomkUk", 224, 258, "Deadlifts on ARED", "Scott Kelly", "International Space Station",
                       "Working Out Aboard the Space Station", "NASA Johnson", "2010-12-17", **_NASA_TERMS)
_T2_RUN = _clip("_ikouWcXhd0", 156, 200, "Running on the T2 treadmill in a harness", "Karen Nyberg",
                "International Space Station", "Running in Space!", "NASA Johnson", "2013-09-20", **_NASA_TERMS)
_CEVIS = _clip("eRyE0ElfLhQ", 40, 140, "Cycling on CEVIS", "Koichi Wakata", "International Space Station",
               "Koichi Wakata Weekly Activity Report, Vol. 13", "JAXA", "2014-01-15",
               license="JAXA/NASA. Embedded from JAXA's channel; not re-hosted", license_url="https://global.jaxa.jp/policy.html")
_CSA = {"license": "CSA/NASA. Embedded from the Canadian Space Agency's channel; not re-hosted",
        "license_url": "https://asc-csa.gc.ca/eng/terms.asp#copyright"}
# NASA public-domain B-roll from the Johnson Space Center: Orion flywheel testing, and ARED physical training.
_ORION_REEL = ("jsc2025m000683", "Orion Flywheel Exercise Device Reel", "2025-05-29")
_FLY_SQUAT = _nasa(_ORION_REEL[0], 136, 162, "Harness squat on the Orion flywheel", "NASA test team",
                   "Johnson Space Center, Houston", _ORION_REEL[1], _ORION_REEL[2])
_FLY_DEADLIFT = _nasa(_ORION_REEL[0], 70, 98, "Deadlift on the Orion flywheel", "NASA test team",
                      "Johnson Space Center, Houston", _ORION_REEL[1], _ORION_REEL[2])
_FLY_ROW = _nasa(_ORION_REEL[0], 8, 30, "Seated row on the Orion flywheel", "NASA test team",
                 "Johnson Space Center, Houston", _ORION_REEL[1], _ORION_REEL[2])
_ARED_HEEL = _nasa("jsc2018m000791-ARED_PT_Hopkins_1", 98, 108, "Heel raises on ARED (close-up of the feet)",
                   "Mike Hopkins", "ARED ground trainer, Johnson Space Center", "ARED physical training, Mike Hopkins",
                   "2019-05-06")
VIDEOS: dict[str, dict[str, dict[str, Any]]] = {
    "ared": {"squat": _ARED_SQUAT, "deadlift": _ARED_DEADLIFT, "press": _ARED_BENCH, "heel_raise": _ARED_HEEL},
    "t2": {"run": _T2_RUN},
    "cevis": {"cycle_intervals": _CEVIS, "cycle_steady": _CEVIS},
    "flywheel": {"squat": _FLY_SQUAT, "deadlift": _FLY_DEADLIFT, "row": _FLY_ROW,
                 "heel_raise": {**_ARED_HEEL, "note": "Filmed on ARED: flywheel heel raises have not been filmed."}},
    # No footage from these devices yet: show the closest real equivalent, and say so.
    "cycle": {e: {**_CEVIS, "note": "Filmed on CEVIS, the station's bike, the closest real footage."}
              for e in ("cycle_intervals", "cycle_steady")},
    "weights": {e: {**v, "note": "Filmed on ARED; nobody has lifted on the Moon or Mars yet."}
                for e, v in (("squat", _ARED_SQUAT), ("deadlift", _ARED_DEADLIFT), ("press", _ARED_BENCH),
                             ("heel_raise", _ARED_HEEL))},
    "treadmill": {"run": {**_T2_RUN, "note": "Filmed on the ISS; on the Moon or Mars no harness is needed."}},
}


# --------------------------------------------------------------------------------------------
# The week. Mission day % 7 picks the day of the plan; day 0 is Monday.
# --------------------------------------------------------------------------------------------
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_WEEK = [
    ("resistance", "lower"),  # Mon: squat, deadlift, heel raise
    ("intervals", None),      # Tue
    ("resistance", "full"),   # Wed: squat, heel raise, upper
    ("continuous", None),     # Thu
    ("resistance", "lower"),  # Fri
    ("intervals", None),      # Sat
    ("rest", None),           # Sun: rest or light
]
SESSION_TITLE = {"resistance": "Resistance", "intervals": "Intervals", "continuous": "Endurance", "rest": "Rest day",
                 "light": "Light session"}
SESSION_TIME = "10:00"


def _it(eid: str, minutes: int, intensity: str, sets: int | None = None, reps: int | None = None,
        role: str = "main") -> dict[str, Any]:
    return {"id": eid, "sets": sets, "reps": reps, "intensity": intensity, "minutes": minutes, "role": role}


# Each training day fills the 2-hour exercise block the rest of ASTRA counts against (warm-up, main work, second
# part); the remainder of the block is setup and cool-down, as on the ISS.
BLOCK_MIN = 120
WARM_UP = ("cycle_steady", 10, "Easy spin to warm up")


def _session(kind: str, focus: str | None) -> list[dict[str, Any]]:
    warm = _it(*WARM_UP, role="warm-up")
    if kind == "resistance":
        lifts = [_it("squat", 25, "85 % of 1-rep max", 4, 6),
                 _it("deadlift", 20, "80 % of 1-rep max", 3, 6) if focus != "full"
                 else _it("press", 20, "75 % of 1-rep max", 3, 8),
                 _it("heel_raise", 15, "70 % of 1-rep max", 3, 12)]
        return [warm, *lifts, _it("run", 30, "Steady, 70-75 % of max heart rate", role="second")]
    if kind == "intervals":
        return [warm, _it("cycle_intervals", 30, "6 x 2 min hard (above 90 % max HR), 2 min easy", 6),
                _it("heel_raise", 15, "70 % of 1-rep max", 3, 12, role="second"),
                _it("run", 40, "Easy, 65-70 % of max heart rate", role="second")]
    if kind == "continuous":
        return [warm, _it("cycle_steady", 45, "70-75 % of max heart rate"),
                _it("run", 40, "Steady pace you could talk at"),
                _it("heel_raise", 15, "70 % of 1-rep max", 3, 12, role="second")]
    if kind == "light":
        return [_it("cycle_steady", 30, "Easy spin, stop if you feel worse")]
    # Rest day: ISS crews train six days a week; the seventh is optional and easy.
    return [_it("cycle_steady", 30, "Optional easy spin")]


def _place(items: list[dict[str, Any]], devices: dict[str, str]) -> list[dict[str, Any]]:
    """Swap exercises for what this location has (press -> row on the flywheel; run -> longer ride without a
    treadmill), and attach the device."""
    out = []
    for it in items:
        eid = it["id"]
        if eid == "press" and "press" not in devices:
            eid = "row"
        if eid == "run" and "run" not in devices:
            # No treadmill: fold the running minutes into the ride before it, or ride instead.
            if out and out[-1]["id"].startswith("cycle"):
                out[-1] = {**out[-1], "minutes": out[-1]["minutes"] + it["minutes"]}
                continue
            eid = "cycle_steady"
        if eid not in devices:
            continue
        out.append({**it, "id": eid, "device": devices[eid]})
    return out


def _status(states: dict[str, dict[str, Any]], metric: str) -> str:
    st = states.get(metric) or {}
    return st.get("status", "ok") if st.get("has_data") else "ok"


def build_plan(crew: dict[str, Any], profile: dict[str, Any], env_id: str, day: int,
               states: dict[str, dict[str, Any]], minutes_by_day: dict[int, float]) -> dict[str, Any]:
    """The week around `day` and today's session, adjusted for this person's history and today's readings."""
    devices = LOCATION_DEVICES.get(env_id, _STATION)
    history = " ".join(h["condition"].lower() for h in profile.get("history", []))
    adjustments: list[dict[str, Any]] = []

    def adjust(title: str, reason: str, source: str, severity: str = "watch", metric: str | None = None) -> None:
        adjustments.append({"title": title, "reason": reason, "source": source, "severity": severity,
                            "metric": metric})

    kind, focus = _WEEK[day % 7]
    items = _session(kind, focus)

    # --- Today's readings first: they can change the whole session. ---
    if _status(states, "temp") != "ok":
        adjust("Light session instead of hard work", "Body temperature is raised. Hard exercise with a possible "
               "infection can make it worse; keep it easy until it is back to normal.", "Today's reading", "act",
               "temp")
        kind, items = "light", _session("light", None)
    elif _status(states, "sleep") != "ok" and kind == "intervals":
        adjust("Intervals swapped for a steady ride", "Short sleep last night. Hard intervals on little sleep raise "
               "injury risk and add stress; a steady ride keeps the habit.", "Today's reading", "watch", "sleep")
        kind, items = "continuous", _session("continuous", None)
    if _status(states, "nutrition") == "act" and kind == "resistance":
        adjust("Lower volume: one set fewer per exercise", "Food intake is well below plan. Training hard without "
               "enough energy speeds up muscle loss instead of preventing it.", "Today's reading", "act", "nutrition")
        items = [{**it, "sets": max(1, it["sets"] - 1)} if it.get("sets") and it["id"] != "cycle_intervals" else it
                 for it in items]

    items = _place(items, devices)

    # --- Medical history: how today's exercises are done. Only notes that apply to today's session. ---
    ids = {it["id"] for it in items}
    lifting = bool(ids & {"squat", "deadlift", "press", "row", "heel_raise"})
    if ("acl" in history or "knee" in history) and ids & {"squat", "deadlift", "run"}:
        adjust("Squat to parallel, no deeper" if "squat" in ids else "Short strides, land softly",
               "Repaired right knee (2016). Keep load progression small, about 5 % a week, and stop on any knee "
               "pain.", "Medical history", "ok")
    if "blood pressure" in history and (lifting or "cycle_intervals" in ids):
        adjust("Breathe out on every effort", "Raised blood pressure history. Holding your breath while lifting "
               "or sprinting spikes pressure; exhale through the hard part.", "Medical history",
               "watch" if _status(states, "bp") != "ok" else "ok", "bp")
    if "kidney stone" in history:
        adjust("Drink 500 mL extra during the session", "Past kidney stone. Sweat loss plus bone calcium released in "
               "microgravity raise the risk of another one.", "Medical history",
               "watch" if _status(states, "hydration") != "ok" else "ok", "hydration")
    if "reflux" in history:
        adjust("No exercise within 2 hours of a meal", "Acid reflux. Bending and straining on a full stomach brings "
               "it on, and it gets worse in microgravity.", "Medical history", "ok")
    if "asthma" in history and "cycle_intervals" in ids:
        adjust("Warm up fully before the intervals", "Childhood asthma. A gradual warm-up lowers the chance of "
               "airway tightening; stop if oxygen drops.", "Medical history",
               "watch" if _status(states, "spo2") != "ok" else "ok", "spo2")

    planned = sum(it["minutes"] for it in items)
    exercises = {it["id"]: {**EXERCISES[it["id"]], "id": it["id"],
                            "video": VIDEOS.get(it["device"], {}).get(it["id"])} for it in items}

    # --- The week, Monday to Sunday, around today. ---
    start = day - day % 7
    week = []
    for d in range(start, start + 7):
        k, f = _WEEK[d % 7]
        plan_min = sum(it["minutes"] for it in _place(_session(k, f), devices))
        week.append({"day": d, "weekday": WEEKDAYS[d % 7], "kind": k, "title": SESSION_TITLE[k],
                     "planned_min": plan_min, "done_min": minutes_by_day.get(d), "today": d == day,
                     "past": d < day})
    if week[day - start]["kind"] != kind:
        week[day - start] = {**week[day - start], "kind": kind, "title": SESSION_TITLE[kind], "planned_min": planned,
                             "adjusted": True}

    order = {"act": 0, "watch": 1, "ok": 2}
    return {
        "crew_id": crew["id"], "env": env_id, "day": day, "time": SESSION_TIME,
        "today": {"kind": kind, "title": SESSION_TITLE[kind], "minutes": planned, "items": items,
                  "block_min": BLOCK_MIN if kind not in ("rest", "light") else planned},
        "exercises": exercises,
        "devices": {k: DEVICES[k] for k in sorted({it["device"] for it in items})},
        "adjustments": sorted(adjustments, key=lambda a: order[a["severity"]]),
        "week": week,
        "source": "Weekly shape from NASA's SPRINT study on the ISS (English et al., npj Microgravity 2020). "
                  "Doses are illustrative, not a prescription.",
    }
