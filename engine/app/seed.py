"""Deterministic demo data: 30 days of history for four fictional crew members.

Each crew member has a storyline so the demo shows every part of ASTRA:
  * Ana (Commander): sleep debt pulling mood and reaction time down, low fluids, a missed workout.
  * Kenji (CMO): blood pressure creeping up for a week, and a slight blur on his last vision check.
  * Sara (Engineer): all nominal, long streak (the reference crew member).
  * Lucas (Specialist): early infection pattern (temperature + breathing), weight loss, missed checks.
"""

from __future__ import annotations

import random
from typing import Any

from .catalog import (
    BASE_TASKS,
    CREW,
    HISTORY_DAYS,
    METRIC_BY_ID,
    SEED_DAY,
    SEED_SECONDS_OF_DAY,
    WEEKLY_DAY_MOD,
    WEEKLY_TASKS,
)
from .store import Store, hhmm_to_s, met_of

GENERIC: dict[str, tuple[float, float]] = {
    "hr": (64.0, 2.5), "sys": (116.0, 3.5), "dia": (76.0, 2.5), "spo2": (97.6, 0.6), "resp": (14.5, 0.9),
    "temp": (36.85, 0.12), "glucose": (87.0, 4.0), "hydration": (2.3, 0.15), "sleep": (7.6, 0.3),
    "mood": (4.3, 0.45), "reaction": (262.0, 9.0), "exercise": (136.0, 6.0), "nutrition": (96.0, 5.0),
}
PERSONAL: dict[str, dict[str, float]] = {
    "kenji": {"hr": 66.0, "sys": 117.0},
    "sara": {"hr": 57.0, "reaction": 248.0, "sleep": 7.8, "exercise": 142.0},
    "lucas": {"hr": 69.0, "glucose": 90.0, "sleep": 7.4},
}
STORIES: dict[str, dict[str, Any]] = {
    "ana": {
        "drift": {"sleep": (134, 6.2), "mood": (134, 3.0), "reaction": (134, 338.0), "hydration": (137, 1.8)},
        "fixed": {(141, "exercise"): 95.0},
        "symptoms": {140: ["headache"], 141: ["headache", "fatigue"]},
        "skip": {(138, "wellbeing")},
    },
    "kenji": {
        "drift": {"sys": (134, 134.0), "dia": (134, 86.0), "hr": (134, 79.0)},
        "vision": {135: 1},
        "symptoms": {139: ["congestion"], 141: ["congestion"]},
        "skip": {(137, "fluids")},
    },
    "sara": {"drift": {}},
    "lucas": {
        "drift": {"temp": (139, 37.9), "resp": (139, 21.0), "hr": (138, 88.0), "nutrition": (136, 70.0)},
        "mass_loss": 2.5,
        # Lucas logs a headache on day 141 as well. The real ISS cabin CO2 in the EDA fixture
        # sits in the Watch band (the 7-day average is above 2.5 mmHg), so the demo needs two
        # crew reporting a headache in the same 24 hours for the cabin-air insight to fire.
        "symptoms": {140: ["sore_throat"], 141: ["headache", "fatigue"]},
        "miss_rate": 0.15,
        "late_morning": True,
        "skip": {(SEED_DAY, "glucose")},
    },
}


def _tasks_for_day(day: int) -> list[dict[str, Any]]:
    tasks = list(BASE_TASKS)
    if day % 7 == WEEKLY_DAY_MOD:
        tasks += WEEKLY_TASKS
    return sorted(tasks, key=lambda t: t["time"])


def _last_day_for(metric_key: str) -> int:
    """Last seeded day for a metric: today if its task already happened before the seed time."""
    m = {"sys": "bp", "dia": "bp"}.get(metric_key, metric_key)
    for t in BASE_TASKS:
        if m in t["metrics"] and hhmm_to_s(t["time"]) < SEED_SECONDS_OF_DAY:
            return SEED_DAY
    return SEED_DAY - 1


def _value(key: str, crew_id: str, day: int, rng: random.Random) -> float:
    mean, sd = GENERIC[key]
    mean = PERSONAL.get(crew_id, {}).get(key, mean)
    drift = STORIES[crew_id].get("drift", {}).get(key)
    if drift:
        start, target = drift
        end = _last_day_for(key)
        t = max(0.0, min(1.0, (day - start) / max(1, end - start)))
        if day >= end:
            return target
        return mean + (target - mean) * t + rng.gauss(0, sd * 0.45)
    return mean + rng.gauss(0, sd)


def _round(metric: str, v: float) -> float:
    m = METRIC_BY_ID[metric]
    if metric == "mood":
        return float(max(1, min(5, round(v))))
    if metric == "spo2":
        return float(min(100, round(v)))
    if metric in ("exercise", "nutrition"):
        return float(max(0, round(v / 5) * 5))
    return round(v, m["decimals"])


def seed(store: Store, rng_seed: int = 7) -> None:
    store.wipe()
    now = met_of(SEED_DAY, SEED_SECONDS_OF_DAY)
    store.set_clock(now)
    first_day = SEED_DAY - HISTORY_DAYS + 1
    rows: list[tuple[Any, ...]] = []

    for crew in CREW:
        cid = crew["id"]
        rng = random.Random(f"{rng_seed}-{cid}")
        story = STORIES[cid]
        skips: set[tuple[int, str]] = set(story.get("skip", set()))
        for day in range(first_day, SEED_DAY + 1):
            for task in _tasks_for_day(day):
                t_s = hhmm_to_s(task["time"])
                if day == SEED_DAY and t_s >= SEED_SECONDS_OF_DAY:
                    continue
                if (day, task["id"]) in skips:
                    continue
                miss = story.get("miss_rate", 0.0)
                if miss and day >= SEED_DAY - 10 and day < SEED_DAY and rng.random() < miss:
                    continue
                offset = rng.randint(0, 9) * 60
                if day == SEED_DAY and task["id"] == "morning" and story.get("late_morning"):
                    offset = 55 * 60
                met = met_of(day, t_s + offset)
                for metric in task["metrics"]:
                    value2: float | None = None
                    meta: dict[str, Any] | None = None
                    if metric == "bp":
                        value = _round("bp", _value("sys", cid, day, rng))
                        value2 = _round("bp", _value("dia", cid, day, rng))
                    elif metric == "mass":
                        loss = story.get("mass_loss", 0.0) * (day - first_day) / (SEED_DAY - first_day)
                        value = round(crew["mass_ref"] - loss + rng.gauss(0, 0.2), 1)
                    elif metric == "vision":
                        value = float(story.get("vision", {}).get(day, 0))
                    elif metric == "symptoms":
                        items = list(story.get("symptoms", {}).get(day, []))
                        value, meta = float(len(items)), {"items": items}
                    else:
                        fixed = story.get("fixed", {}).get((day, metric))
                        value = _round(metric, fixed if fixed is not None else _value(metric, cid, day, rng))
                    rows.append((cid, metric, value, value2, _json(meta), met, day, task["id"], "seed"))
                    met += 40  # each measurement in a bundle a little later

    store.add_readings_bulk(rows)

    # Historical comms so the ground link is not empty.
    store.add_packet(
        "kenji", "message", 0, "Requesting review of my BP trend",
        "Systolic has been creeping up all week (now ~133/85). Requesting a review at the next conference.",
        "Flight surgeon: We reviewed your 7-day trend. Continue twice-daily blood pressure, go easy on sodium, "
        "and keep the aerobic sessions. We'll discuss it at Thursday's private medical conference.",
        met_of(SEED_DAY - 1, hhmm_to_s("08:05")), 760.0, "transit",
    )
    store.add_packet(
        "lucas", "alert", 1, "Temperature 37.9 °C with breathing 21/min",
        "ASTRA tier-1 alert: temperature and breathing rate rising together for 2 days. Symptoms: sore throat, "
        "fatigue.",
        "Flight surgeon: Pattern fits a mild viral infection. Rest, fluids, sleep in your own station, re-check "
        "temperature every 4 h. Call us if above 38.5 °C or SpO2 below 94%.",
        met_of(SEED_DAY - 1, hhmm_to_s("18:30")), 760.0, "transit",
    )
    store.add_badge("sara", "drill_ready", met_of(SEED_DAY - 22, hhmm_to_s("15:00")))
    store.add_badge("kenji", "drill_ready", met_of(SEED_DAY - 22, hhmm_to_s("15:00")))
    store.meta_set("seeded", "1")


def _json(meta: dict[str, Any] | None) -> str | None:
    import json

    return json.dumps(meta) if meta else None
