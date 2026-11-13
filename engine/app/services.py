"""ASTRA Core services: turn stored readings + rules into what the crew needs to see and do."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from . import exercise as exercise_plan
from . import gamification as honest
from . import rules
from .catalog import (
    ACTIVE_CONTEXTS,
    ADHOC_XP,
    BADGES,
    BASE_TASKS,
    BUDDY_DAILY_CAP,
    BUDDY_XP,
    CABIN,
    CABIN_DEMO_DATE,
    CABIN_FILL_PPM,
    CAREER_LIMIT_MSV,
    COMM_WINDOWS,
    CONJUNCTION_SOT_DEG,
    CONJUNCTION_WARNING_DAYS,
    CONTEXT_BY_ID,
    CREW,
    CREW_BY_ID,
    CREW_GOAL_RATIO,
    CREW_GOAL_REWARD,
    CREW_PROFILES,
    DEFAULT_CONTEXT,
    DEFAULT_ENV,
    DRILL_XP,
    ENV_BY_ID,
    ESCALATION,
    LABS,
    LEVELS,
    LOOP_XP,
    METRIC_BY_ID,
    METRICS,
    MISSION,
    MISSION_DOSE_AT_SEED_MSV,
    ORGANS,
    PROTOCOL_BY_ID,
    QUEST_XP,
    RECENT_EXERCISE_S,
    RECHECK_AFTER_MIN,
    SEED_DAY,
    SEED_SECONDS_OF_DAY,
    STATUS_LABEL,
    SYMPTOM_BY_ID,
    SYMPTOMS,
    TASK_CONTEXT,
    TRANSIT_DAYS,
    WEEKLY_DAY_MOD,
    WEEKLY_TASKS,
    XP_PER_LEVEL,
)
from .nasa import Registry
from .store import DAY_S, Store, day_of, hhmm_to_s, met_of, utc_of

SYMPTOM_IDS = {s["id"] for s in SYMPTOMS}
WEEKLY_METRICS = {m for t in WEEKLY_TASKS for m in t["metrics"]}
# A reading older than this (days) no longer describes how the crew member is now.
STALE_AFTER_DAYS = {"daily": 3, "weekly": 10}
# Graded on a rolling average, not one day: bone and kidney-stone risk build up over days, not in one session.
ROLLING_DAYS = {"exercise": 3, "hydration": 3}
GROUND_KINDS = ("alert", "message", "emergency")
REPLY_THINK_S = 90.0


class EngineError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def fmt_value(metric_id: str, value: float | None, value2: float | None = None) -> str:
    if value is None:
        return "-"
    m = METRIC_BY_ID[metric_id]
    if metric_id == "bp" and value2 is not None:
        return f"{value:.0f}/{value2:.0f}"
    return f"{value:.{m['decimals']}f}"


def fmt_delay(seconds: float) -> str:
    if seconds < 1:
        return "< 1 s"
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, sec = divmod(round(seconds), 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours} h {minutes:02d} min"
    return f"{minutes} min {sec:02d} s"


def fmt_tod(met_s: float) -> str:
    s = int(met_s % DAY_S)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"


class Engine:
    def __init__(self, store: Store, nasa: Registry | None = None) -> None:
        self.store = store
        self.nasa = nasa

    # ------------------------------------------------------------------ basics
    def now(self) -> float:
        return self.store.met_now()

    def clock(self) -> dict[str, Any]:
        now = self.now()
        return {"met_s": now, "day": day_of(now), "time": fmt_tod(now), "label": f"Day {day_of(now)} · {fmt_tod(now)}"}

    def crew(self, crew_id: str) -> dict[str, Any]:
        c = CREW_BY_ID.get(crew_id)
        if not c:
            raise EngineError(404, f"Unknown crew member '{crew_id}'")
        return c

    def profile(self, crew_id: str) -> dict[str, Any]:
        """A crew member's static profile: bio, body, missions, medical history (fictional)."""
        crew = self.crew(crew_id)
        return {"crew": crew, **CREW_PROFILES.get(crew_id, {})}

    # ------------------------------------------------------------------ NASA fixtures
    def _horizons(self) -> list[dict[str, Any]]:
        """The JPL Horizons light-time table, or an empty list when the fixture is absent."""
        if self.nasa is None or not self.nasa.has("horizons-mars-lt", "horizons/mars_lt.json"):
            return []
        try:
            return self.nasa.json("horizons-mars-lt", "horizons/mars_lt.json")
        except Exception:  # noqa: BLE001 - a broken fixture must not take the engine down
            return []

    def _light_time(self, now: float) -> dict[str, Any] | None:
        """The real Earth-Mars light time for the mission date, from the Horizons table.

        The table has one row per day from launch. We pick the row for the mission date and
        fall back to the closest row on either side, so the number is always a real
        Horizons measurement rather than an interpolation.
        """
        rows = self._horizons()
        if not rows:
            return None
        target = utc_of(now, MISSION["launch_utc"]).date().isoformat()
        exact = next((r for r in rows if r["date"] == target), None)
        if exact is not None:
            return exact
        earlier = [r for r in rows if r["date"] < target]
        later = [r for r in rows if r["date"] > target]
        if not earlier and not later:
            return None
        return earlier[-1] if not later else (later[0] if not earlier else earlier[-1])

    def env(self, env_id: str | None) -> dict[str, Any]:
        """The environment, with the signal delay computed for the current mission date."""
        base = ENV_BY_ID.get(env_id or DEFAULT_ENV) or ENV_BY_ID[DEFAULT_ENV]
        env = dict(base)
        now = self.now()
        lt = self._light_time(now)
        if env["id"] == "mars" and lt:
            env["delay_s"] = float(lt["light_time_s"])
            env["delay_note"] = f"JPL Horizons · {lt['light_time_s']:.0f} s one way today"
            env["light_time_source"] = "horizons"
        elif env["id"] == "transit":
            # Transit delay scales with the Earth-Mars distance over the outbound leg.
            progress = min(1.0, max(0.0, (now / DAY_S) / TRANSIT_DAYS))
            if lt:
                env["delay_s"] = float(lt["light_time_s"]) * progress
                env["delay_note"] = (f"approximate, scaled from Earth-Mars distance "
                                     f"({progress * 100:.0f}% of the {TRANSIT_DAYS}-day transit)")
                env["light_time_source"] = "horizons-scaled"
            else:
                env["delay_note"] = "varies 4-24 min with planet positions"
                env["light_time_source"] = None
        else:
            env["light_time_source"] = None
        if env["id"] == "transit" and env.get("light_time_source"):
            env["tip"] = (f"Deep space, no evacuation. ASTRA runs fully on board, and a reply from Earth takes "
                          f"about {fmt_delay(2 * env['delay_s'] + REPLY_THINK_S)} round-trip today.")
        # Where each dose rate comes from. Rover and lunar rates are planning estimates with no source yet.
        if env["id"] == "station":
            rate, src = self._station_dose_rate(float(env["radiation_msv_day"]))
            env["radiation_msv_day"] = round(rate, 2)
            env["radiation_source"] = src
        elif env["id"] in ("transit", "mars"):
            env["radiation_source"] = "msl-rad"
        else:
            env["radiation_source"] = None
        env["utc"] = utc_of(now, MISSION["launch_utc"]).isoformat().replace("+00:00", "Z")
        env["mission_day"] = day_of(now)
        return env

    def metric(self, metric_id: str) -> dict[str, Any]:
        m = METRIC_BY_ID.get(metric_id)
        if not m:
            raise EngineError(404, f"Unknown metric '{metric_id}'")
        return m

    # ------------------------------------------------------------------ data helpers
    def _readings(self, crew_id: str, now: float, days: int = 40) -> list[dict[str, Any]]:
        return self.store.readings(crew_id, day_of(now) - days, until_met=now)

    @staticmethod
    def _daily(readings: list[dict[str, Any]], metric_id: str) -> list[dict[str, Any]]:
        """The last reading of each day. Post-exertion readings are left out: status, baseline,
        trend and persistence are about the resting value."""
        last: dict[int, dict[str, Any]] = {}
        for r in readings:
            if r["metric"] == metric_id and not rules.is_active(metric_id, r.get("meta")):
                last[r["day"]] = r
        return [last[d] for d in sorted(last)]

    @staticmethod
    def _latest_active(readings: list[dict[str, Any]], metric_id: str, today: int) -> dict[str, Any] | None:
        """Today's newest post-exertion reading, when it is newer than the last resting one."""
        newest = next((r for r in reversed(readings) if r["metric"] == metric_id and r["day"] == today), None)
        if not newest or not rules.is_active(metric_id, newest.get("meta")):
            return None
        ctx = CONTEXT_BY_ID[newest["meta"]["context"]]
        return {"display": fmt_value(metric_id, newest["value"], newest.get("value2")),
                "context": ctx["id"], "context_label": ctx["label"], "time": fmt_tod(newest["met_s"]),
                "status": rules.classify(metric_id, newest["value"], newest.get("value2"), None, newest["meta"]),
                "source": newest.get("source", "manual")}

    @staticmethod
    def _ref(crew: dict[str, Any], metric_id: str) -> float | None:
        return crew["mass_ref"] if metric_id == "mass" else None

    def _status_of(self, crew: dict[str, Any], r: dict[str, Any]) -> str:
        return rules.classify(r["metric"], r["value"], r.get("value2"), self._ref(crew, r["metric"]), r.get("meta"))

    @staticmethod
    def _baselines(metric_id: str, daily: list[dict[str, Any]], today: int) -> tuple[dict | None, dict | None]:
        m = METRIC_BY_ID[metric_id]
        window = [d for d in daily if today - 28 <= d["day"] <= today - 8]
        if len(window) < 5:
            window = [d for d in daily if d["day"] < today]
        b = rules.baseline([d["value"] for d in window], m["min_sd"])
        b2 = None
        if metric_id == "bp":
            b2 = rules.baseline([d["value2"] for d in window if d.get("value2") is not None], m["min_sd"])
        return b, b2

    def _metric_state(self, crew: dict[str, Any], metric_id: str, daily: list[dict[str, Any]],
                      today: int) -> dict[str, Any]:
        m = METRIC_BY_ID[metric_id]
        if not daily:
            return {"metric": metric_id, "has_data": False, "status": "ok", "value": None, "value2": None,
                    "display": "-", "spark": [], "age_days": None, "trend": {"direction": "stable",
                    "quality": "neutral"}, "baseline": None, "delta": None, "personal": False}
        last = daily[-1]
        ref = self._ref(crew, metric_id)
        status = self._status_of(crew, last)
        basis = None
        if metric_id in ROLLING_DAYS:
            n = ROLLING_DAYS[metric_id]
            window = [d for d in daily if d["day"] > last["day"] - n]
            avg = sum(d["value"] for d in window) / len(window)
            status = self._status_of(crew, {**last, "value": avg})
            basis = {"days": n, "average": round(avg, 2)}
        b, b2 = self._baselines(metric_id, daily, today)
        z = rules.zscore(last["value"], b)
        personal = False
        if (status == "ok" and z is not None and b and b["n"] >= 5 and abs(z) >= rules.PERSONAL_Z
                and rules.is_worse_direction(metric_id, z)):
            status, personal = "watch", True
        newest_first = [self._status_of(crew, d) for d in reversed(daily)]
        newest_first[0] = status
        persist = rules.persistence(newest_first)
        recent = [(d["day"], d["value"]) for d in daily if d["day"] > today - 7]
        slope = rules.slope_per_day(recent)
        state: dict[str, Any] = {
            "metric": metric_id, "has_data": True, "status": status, "personal": personal, "basis": basis,
            "value": last["value"], "value2": last.get("value2"), "display": fmt_value(metric_id, last["value"],
                                                                                       last.get("value2")),
            "meta": last.get("meta"), "day": last["day"], "time": fmt_tod(last["met_s"]),
            "age_days": today - last["day"],
            "source": last.get("source", "manual"),
            "baseline": round(b["mean"], 2) if b else None,
            "baseline2": round(b2["mean"], 2) if b2 else None,
            "delta": round(last["value"] - b["mean"], 2) if b else None,
            "z": round(z, 2) if z is not None else None,
            "slope": round(slope, 3), "trend": rules.trend_label(metric_id, slope, m["min_sd"]),
            "persistence": persist,
            "spark": [d["value"] for d in daily if d["day"] > today - 14],
            "band": rules.absolute_band(metric_id, ref),
        }
        if metric_id == "mass":
            state["change_pct"] = round(rules.relative_change(last["value"], ref), 1)
        return state

    # ------------------------------------------------------------------ routine
    def tasks_for_day(self, day: int, env_id: str | None) -> list[dict[str, Any]]:
        tasks = list(BASE_TASKS)
        if day % 7 == WEEKLY_DAY_MOD:
            tasks += WEEKLY_TASKS
        if env_id:
            tasks += self.env(env_id)["extra_tasks"]
        return sorted(tasks, key=lambda t: t["time"])

    @staticmethod
    def _task_done(task: dict[str, Any], day_readings: list[dict[str, Any]]) -> bool:
        logged = {r["metric"] for r in day_readings if r.get("task_id") == task["id"]}
        return all(mm in logged for mm in task["metrics"])

    def _completion(self, readings: list[dict[str, Any]], day: int, env_id: str | None) -> tuple[int, int]:
        day_r = [r for r in readings if r["day"] == day]
        tasks = self.tasks_for_day(day, env_id)
        done = sum(1 for t in tasks if self._task_done(t, day_r))
        return done, len(tasks)

    def routine(self, crew_id: str, env_id: str | None, readings: list[dict[str, Any]] | None = None,
                now: float | None = None) -> dict[str, Any]:
        self.crew(crew_id)
        now = self.now() if now is None else now
        today, tod = day_of(now), now % DAY_S
        readings = self._readings(crew_id, now) if readings is None else readings
        today_r = [r for r in readings if r["day"] == today]
        out = []
        for t in self.tasks_for_day(today, env_id):
            t_s = hhmm_to_s(t["time"])
            mine = [r for r in today_r if r.get("task_id") == t["id"]]
            done = self._task_done(t, today_r)
            logged = sorted({r["metric"] for r in mine})
            if done:
                state = "done"
            elif tod > t_s + 2 * 3600:
                state = "overdue"
            elif tod >= t_s - 30 * 60:
                state = "due"
            else:
                state = "upcoming"
            done_at = max((r["met_s"] for r in mine), default=None)
            out.append({**t, "state": state, "logged": logged, "weekly": t in WEEKLY_TASKS,
                        "done_at": fmt_tod(done_at) if done and done_at is not None else None,
                        "on_time": bool(done and done_at is not None and done_at % DAY_S <= t_s + 3600)})
        done_n = sum(1 for t in out if t["state"] == "done")
        nxt = next((t for t in out if t["state"] in ("overdue", "due")), None) or next(
            (t for t in out if t["state"] == "upcoming"), None)
        return {"day": today, "tasks": out, "done": done_n, "total": len(out),
                "overdue": sum(1 for t in out if t["state"] == "overdue"), "next": nxt}

    def _attach_task(self, metric_id: str, env_id: str | None, readings: list[dict[str, Any]],
                     now: float) -> str | None:
        today, tod = day_of(now), now % DAY_S
        today_r = [r for r in readings if r["day"] == today]
        for t in self.tasks_for_day(today, env_id):
            if metric_id not in t["metrics"]:
                continue
            already = any(r["metric"] == metric_id and r.get("task_id") == t["id"] for r in today_r)
            if not already and tod >= hhmm_to_s(t["time"]) - 3600:
                return t["id"]
        return None

    # ------------------------------------------------------------------ gamification
    def _badges(self, crew_id: str, readings: list[dict[str, Any]], today: int,
                crew_days_reached: set[int]) -> set[str]:
        """Earned badges. Every rule counts actions (logging, re-measuring, drills, helping), never values."""
        crew = self.crew(crew_id)
        comp = honest.completion_by_day(self, readings, today - 60, today, None)
        core = honest.core_done_by_day(self, readings, today - 60, today, None)
        streak = honest.streak_state(comp, today, core)
        progress = honest.badge_progress(self, crew, readings, comp, streak, today, crew_days_reached)
        return {bid for bid, p in progress.items() if p["earned"]}

    def _crew_goal(self, env_id: str | None, now: float) -> dict[str, Any]:
        today = day_of(now)
        per_crew = []
        by_day: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for c in CREW:
            rs = self._readings(c["id"], now, days=8)
            for d in range(today - 6, today + 1):
                by_day[d].append(self._completion(rs, d, env_id if d == today else None))
            done, total = by_day[today][-1]
            per_crew.append({"crew_id": c["id"], "initials": c["initials"], "hue": c["hue"], "done": done,
                             "total": total})
        reached = {d for d, vals in by_day.items()
                   if d < today and sum(v[0] for v in vals) >= CREW_GOAL_RATIO * sum(v[1] for v in vals)}
        done = sum(p["done"] for p in per_crew)
        total = sum(p["total"] for p in per_crew)
        return {"done": done, "total": total, "target": int(-(-CREW_GOAL_RATIO * total // 1)),
                "reward": CREW_GOAL_REWARD, "per_crew": per_crew, "reached_days": sorted(reached)}

    def game(self, crew_id: str, env_id: str | None, readings: list[dict[str, Any]] | None = None,
             now: float | None = None) -> dict[str, Any]:
        crew = self.crew(crew_id)
        now = self.now() if now is None else now
        today = day_of(now)
        readings = self._readings(crew_id, now) if readings is None else readings
        xp = int(crew["base_xp"] + self.store.xp_sum(crew_id))
        level = xp // XP_PER_LEVEL + 1
        comp = honest.completion_by_day(self, readings, today - 60, today, env_id)
        core = honest.core_done_by_day(self, readings, today - 60, today, env_id)
        st = honest.streak_state(comp, today, core)
        streak = st["current"]
        # The streak a check finished today extends (today itself only counts once its checks are done).
        streak_before_today = streak - (1 if st["status"].get(today) in ("done", "eased") else 0)
        xp_today = sum(e["amount"] for e in self.store.xp_events(crew_id, 400) if day_of(e["met_s"]) == today)
        goal = self._crew_goal(env_id, now)
        earned = self._badges(crew_id, readings, today, set(goal["reached_days"]))
        op = honest.crew_week(self, env_id, now)["operation"]
        return {
            "xp": xp, "level": level, "title": LEVELS[min(level - 1, len(LEVELS) - 1)],
            "level_xp": xp % XP_PER_LEVEL, "xp_per_level": XP_PER_LEVEL, "streak": streak,
            "streak_before_today": streak_before_today, "xp_today": xp_today,
            "badges": [{**b, "earned": b["id"] in earned} for b in BADGES],
            "earned_count": len(earned), "crew_goal": goal,
            "challenge": {"title": op["name"], "detail": op["detail"], "value": op["value"], "target": op["target"]},
        }

    def approve_perk(self, crew_id: str, week: int, days: int) -> dict[str, Any]:
        return honest.approve_perk(self, crew_id, week, days)

    def game_hub(self, crew_id: str, env_id: str | None) -> dict[str, Any]:
        """The Missions page: level, shielded streak, momentum guard, chapter, quests, badges, crew week, XP log."""
        self.crew(crew_id)
        return honest.hub(self, crew_id, env_id)

    # ------------------------------------------------------------------ radiation & comms
    def _solar_event(self) -> dict[str, Any] | None:
        """The active solar particle event, if the crew is replaying one."""
        raw = self.store.meta_get("solar_event")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def start_solar_replay(self, event_id: str | None = None) -> dict[str, Any]:
        """Start a replay of a real solar particle event from the DONKI fixture.

        The event itself (when it happened, which instruments saw it) is real. The dose the
        crew would receive is an *illustrative* figure from our own replay model, not a DONKI
        measurement, and the payload says so.
        """
        replay = self._replay_model()
        if not replay:
            raise EngineError(503, "The solar-event replay fixture is not available yet")
        events = replay.get("events", [])
        chosen = next((e for e in events if e.get("event_id") == event_id), None) if event_id else None
        if event_id and chosen is None:
            raise EngineError(404, f"Unknown solar particle event '{event_id}'")
        if chosen is None:
            chosen = next((e for e in events if e.get("is_default")), None) or (events[0] if events else None)
        if chosen is None:
            raise EngineError(503, "The solar-event replay fixture has no events")

        now = self.now()
        state = {
            "event_id": chosen["event_id"],
            "label": chosen["label"],
            "event_time": chosen.get("event_time"),
            "instruments": chosen.get("instruments"),
            "link": chosen.get("link"),
            "started_met": now,
            "duration_s": float(chosen.get("duration_h", 24.0)) * 3600.0,
            "event_dose_msv": float(chosen.get("event_dose_msv", 0.0)),
            "illustrative": True,
            "illustrative_note": chosen.get("illustrative_note"),
            "shelter_delay_s": float(replay.get("shelter_delay_s", 600.0)),
            "shelter_factor": float(replay.get("shelter_factor", 0.25)),
            "source": "donki-sep",
        }
        self.store.meta_set("solar_event", json.dumps(state))
        return state

    def stop_solar_replay(self) -> dict[str, Any]:
        self.store.meta_set("solar_event", "")
        return {"ok": True}

    def _replay_model(self) -> dict[str, Any] | None:
        if self.nasa is None or not self.nasa.has("donki-sep", "donki/replay.json"):
            return None
        try:
            return self.nasa.json("donki-sep", "donki/replay.json")
        except Exception:  # noqa: BLE001 - a broken fixture must not take the engine down
            return None

    def _donki_events(self) -> list[dict[str, Any]]:
        """The real solar particle events from the DONKI fixture."""
        if self.nasa is None or not self.nasa.has("donki-sep", "donki/sep.json"):
            return []
        try:
            return self.nasa.json("donki-sep", "donki/sep.json")
        except Exception:  # noqa: BLE001 - a broken fixture must not take the engine down
            return []

    # ------------------------------------------------------------------ Inspiration4 reference
    def inspiration4(self) -> dict[str, Any]:
        """The real Inspiration4 blood panels, with ASTRA's rules applied.

        The four crew members flew a 3-day mission in 2021. The values, the reference ranges
        and the sampling days are the ones the NASA OSDR dataset ships with; only the status
        labels are ours.
        """
        if self.nasa is None or not self.nasa.has("osdr-i4-labs", "osdr_i4/labs.json"):
            return {"available": False, "analytes": [], "subjects": [], "series": []}
        try:
            rows = self.nasa.json("osdr-i4-labs", "osdr_i4/labs.json")
        except Exception:  # noqa: BLE001 - a broken fixture must not take the engine down
            return {"available": False, "analytes": [], "subjects": [], "series": []}

        subjects = sorted({r["subject"] for r in rows})
        by_analyte: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            by_analyte.setdefault(r["analyte"], []).append(r)

        analytes = []
        series = []
        for lab in LABS:
            entries = by_analyte.get(lab["id"], [])
            if not entries:
                continue
            lows = [e["ref_low"] for e in entries if e.get("ref_low") is not None]
            highs = [e["ref_high"] for e in entries if e.get("ref_high") is not None]
            # The band drawn on the chart is the widest range any crew member is held to; the
            # per-point ranges carry the exact one used for each status.
            low = min(lows) if lows else None
            high = max(highs) if highs else None
            ranges = {(e.get("ref_low"), e.get("ref_high")) for e in entries}
            points = []
            for e in sorted(entries, key=lambda x: (x["day"], x["subject"])):
                status = rules.classify_lab(e["value"], e.get("ref_low"), e.get("ref_high"))
                points.append({
                    "subject": e["subject"],
                    "day": e["day"],
                    "timepoint": e["timepoint"],
                    "value": e["value"],
                    "status": status,
                    # Reference ranges differ by sex, so each point carries its own.
                    "ref_low": e.get("ref_low"),
                    "ref_high": e.get("ref_high"),
                })
            series.append({
                "id": lab["id"],
                "label": lab["label"],
                "unit": lab["unit"],
                "why": lab["why"],
                "ref_low": low,
                "ref_high": high,
                "ranges_differ": len(ranges) > 1,
                "points": points,
            })
            analytes.append({**lab, "ref_low": low, "ref_high": high})

        days = sorted({p["day"] for s in series for p in s["points"]})
        # Inspiration4 flew for about three days: launch is day 0 and splashdown day 3. The last
        # draw before launch is at day -3 and the first after landing at day 1 (after splashdown).
        return {
            "available": True,
            "analytes": analytes,
            "subjects": subjects,
            "series": series,
            "days": days,
            "flight_window": {"from": 0, "to": 3},
            "source": "osdr-i4-labs",
            "sources": ["osdr_i4", "i4_omics"],
        }

    def _solar_view(self, now: float) -> dict[str, Any]:
        event = self._solar_event()
        if not event:
            return {"status": "ok", "label": "No solar particle event in progress", "source": "donki-sep",
                    "actions": [], "event_id": None}
        started = float(event.get("started_met", now))
        elapsed = now - started
        duration = float(event.get("duration_s", 0.0))
        if elapsed >= duration:
            return {"status": "ok", "label": f"Solar particle event over: {event.get('label', 'replay')}",
                    "source": "donki-sep", "actions": [], "event_id": event.get("event_id"), "ended": True,
                    "link": event.get("link"), "illustrative": True}
        shelter_delay = float(event.get("shelter_delay_s", 600.0))
        in_shelter = elapsed >= shelter_delay
        remaining = max(0.0, duration - elapsed)
        shelter_remaining = max(0.0, shelter_delay - elapsed)
        return {
            "status": "act",
            "label": event.get("label", "Solar particle event in progress"),
            "event_id": event.get("event_id"),
            "event_time": event.get("event_time"),
            "instruments": event.get("instruments"),
            "link": event.get("link"),
            "source": "donki-sep",
            "illustrative": True,
            "illustrative_note": event.get("illustrative_note"),
            "in_shelter": in_shelter,
            "shelter_until_s": round(shelter_remaining, 1),
            "shelter_label": (f"Get to the shelter module now ({fmt_delay(shelter_remaining)})"
                              if not in_shelter else "In the shelter module"),
            "event_remaining_label": fmt_delay(remaining),
            "actions": [
                "Get to the water-walled aft storage module.",
                "Wear the shielding vest.",
                "Postpone EVAs and non-critical maintenance.",
            ] if not in_shelter else [
                "Stay in the shelter module until ASTRA says the event is over.",
                "Wear the shielding vest.",
            ],
        }

    def _station_dose_rate(self, fallback: float) -> tuple[float, str | None]:
        """The station dose rate from the real EDA daily dose, when the fixture is present."""
        dose = self._eda_dose()
        if not dose:
            return fallback, None
        vals = [float(d["dose_msv"]) for d in dose if d.get("dose_msv") is not None]
        if not vals:
            return fallback, None
        return sum(vals) / len(vals), "osdr-eda-iss"

    def radiation(self, crew_id: str, env_id: str | None, now: float | None = None) -> dict[str, Any]:
        crew, env = self.crew(crew_id), self.env(env_id)
        now = self.now() if now is None else now
        rate = env["radiation_msv_day"]
        rate_source = None
        sim_rate = self.store.meta_get("sim_rad_rate")
        if sim_rate:
            rate = float(sim_rate)
            rate_source = "simulator"
        elif env["id"] == "station":
            # The station dose rate is the real daily dose measured on the ISS, averaged over
            # the EDA series, rather than a number we made up.
            rate, rate_source = self._station_dose_rate(rate)
        elif env["id"] in ("transit", "mars"):
            # The transit and surface rates are the MSL/RAD measurements Curiosity flew.
            rate_source = "msl-rad"
        seed_met = met_of(SEED_DAY, SEED_SECONDS_OF_DAY)
        mission = MISSION_DOSE_AT_SEED_MSV + max(0.0, (now - seed_met) / DAY_S) * rate
        solar = self._solar_view(now)
        event = self._solar_event()
        if event:
            # The event dose is only added for the time the crew was NOT sheltered: the shelter
            # cuts the dose rate by the factor in the replay model.
            # The extra dose stops when the event ends.
            elapsed = min(max(0.0, now - float(event.get("started_met", now))),
                          float(event.get("duration_s", 86400.0)))
            shelter_delay = float(event.get("shelter_delay_s", 600.0))
            factor = float(event.get("shelter_factor", 0.25))
            exposed = max(0.0, min(elapsed, shelter_delay))
            sheltered = max(0.0, elapsed - shelter_delay)
            dose_rate = float(event.get("event_dose_msv", 0.0)) / max(1.0, float(event.get("duration_s", 86400.0)))
            mission += dose_rate * (exposed + sheltered * factor)
        career = crew["prior_dose_msv"] + mission
        pct = career / CAREER_LIMIT_MSV * 100
        status = "act" if pct > 85 else "watch" if pct > 60 else "ok"
        if solar.get("status") == "act":
            status = "act"  # a solar particle event in progress is an Act, whatever the career dose
        rate_docs = {"station": ["osdr_eda"], "transit": ["msl_rad_cruise"],
                     "mars": ["msl_rad_surface"]}.get(env["id"], [])
        if rate_source == "simulator":
            rate_docs = []  # a simulated rate is not a NASA measurement, so it cites nothing
        return {"mission_msv": round(mission, 1), "career_msv": round(career, 1), "limit_msv": CAREER_LIMIT_MSV,
                "percent": round(pct, 1), "status": status, "rate_msv_day": rate,
                "rate_source": rate_source, "rate_docs": rate_docs,
                "margin_days": int((CAREER_LIMIT_MSV - career) / rate) if rate else None,
                "solar": solar,
                "shelter": "Water-walled aft storage module"}

    def _packet_view(self, p: dict[str, Any], now: float) -> dict[str, Any]:
        delay = float(p["delay_s"])
        elapsed = max(0.0, now - p["created_met"])
        reply_at = 2 * delay + REPLY_THINK_S
        crew = CREW_BY_ID.get(p["crew_id"], {})
        view = {k: p[k] for k in ("id", "crew_id", "kind", "priority", "title", "body", "delay_s", "env_id")}
        view.update({"crew_name": crew.get("name", p["crew_id"]), "initials": crew.get("initials", "?"),
                     "hue": crew.get("hue", 200), "created": f"Day {day_of(p['created_met'])} · "
                     f"{fmt_tod(p['created_met'])}", "elapsed_s": round(elapsed, 1)})
        if p["kind"] == "cmo":
            view.update({"status": "delivered", "progress": 1.0, "eta_s": 0, "reply": None, "reply_eta_s": None})
        elif elapsed < delay:
            view.update({"status": "in_transit", "progress": round(elapsed / delay, 4),
                         "eta_s": round(delay - elapsed, 1),
                         "reply": None, "reply_eta_s": round(reply_at - elapsed, 1)})
        elif elapsed < reply_at:
            view.update({"status": "delivered", "progress": 1.0, "eta_s": 0, "reply": None,
                         "reply_eta_s": round(reply_at - elapsed, 1)})
        else:
            view.update({"status": "replied", "progress": 1.0, "eta_s": 0, "reply": p["reply"], "reply_eta_s": 0})
        return view

    def _next_window(self, now: float) -> dict[str, Any]:
        tod = now % DAY_S
        for w in COMM_WINDOWS:
            s = hhmm_to_s(w)
            if s > tod:
                return {"time": w, "in_s": round(s - tod)}
        return {"time": COMM_WINDOWS[0], "in_s": round(DAY_S - tod + hhmm_to_s(COMM_WINDOWS[0]))}

    # ------------------------------------------------------------------ cabin air
    def _cabin_series(self) -> list[dict[str, Any]]:
        """The ISS cabin CO2 series from the EDA fixture."""
        if self.nasa is None or not self.nasa.has("osdr-eda-iss", "osdr_eda/iss_cabin.json"):
            return []
        try:
            return self.nasa.json("osdr-eda-iss", "osdr_eda/iss_cabin.json")
        except Exception:  # noqa: BLE001 - a broken fixture must not take the engine down
            return []

    def _eda_dose(self) -> list[dict[str, Any]]:
        """The ISS daily radiation dose from the EDA fixture."""
        if self.nasa is None or not self.nasa.has("osdr-eda-iss", "osdr_eda/iss_dose.json"):
            return []
        try:
            return self.nasa.json("osdr-eda-iss", "osdr_eda/iss_dose.json")
        except Exception:  # noqa: BLE001 - a broken fixture must not take the engine down
            return []

    def _cabin_days(self) -> list[tuple[str, list[dict[str, Any]]]]:
        """The EDA readings grouped by calendar day, without the sensor-fill rows.

        The first days of the series are a constant 200 ppm that the sensor reports before it
        has real data (well below outdoor air), so they are not air quality and are dropped.
        """
        days: dict[str, list[dict[str, Any]]] = {}
        for r in self._cabin_series():
            if float(r.get("co2_ppm") or 0) > CABIN_FILL_PPM:
                days.setdefault(str(r["t"])[:10], []).append(r)
        return sorted(days.items())

    def cabin(self, env_id: str | None) -> dict[str, Any]:
        """The cabin air picture for the current mission date.

        The EDA series is real ISS telemetry from Rodent Research 7 (2018-07-01 to 2018-09-18).
        The mission clock is mapped onto it one mission day per series day (and the hour of
        the day onto the hour), looping when it runs out. The seeded demo moment lands on
        CABIN_DEMO_DATE, so the demo opens on a real stretch of elevated CO2. The 7-day
        average is a true 7 days: the six days before today plus today so far.
        """
        sim_co2 = self.store.meta_get("cabin_sim_co2")
        if (env_id or DEFAULT_ENV) != "station" and not sim_co2:
            return {"available": False}
        days = self._cabin_days()
        if not days and not sim_co2:
            return {"available": False}
        now = self.now()
        n = len(days) if days else 1
        demo_idx = next((i for i, (d, _) in enumerate(days) if d == CABIN_DEMO_DATE), 0) if days else 0
        idx = (int(now // DAY_S) - (SEED_DAY - 1) + demo_idx) % n
        hour = int((now % DAY_S) // 3600)
        today = days[idx][1] if days else []
        current = min(today, key=lambda r: abs(int(str(r["t"])[11:13]) - hour)) if today else {
            "co2_mmhg": 2.2, "temp_c": 22.0, "rh_pct": 45.0
        }
        window = [r for k in range(6, 0, -1) for r in days[(idx - k) % n][1]] if days else []
        window += [r for r in today if int(str(r["t"])[11:13]) <= hour] or [current]
        co2_1h = float(sim_co2) if sim_co2 else float(current["co2_mmhg"])
        co2_7d = sum(float(r["co2_mmhg"]) for r in window) / len(window) if window else co2_1h
        status = rules.cabin_status(co2_1h, co2_7d)
        # One point per day for the sparkline: each of the last 7 days' mean.
        spark = []
        for k in range(6, -1, -1):
            vals = [float(r["co2_mmhg"]) for r in days[(idx - k) % n][1]]
            spark.append(sum(vals) / len(vals))
        series = self._cabin_series()
        return {
            "available": True,
            "status": status,
            "status_label": STATUS_LABEL[status],
            "co2_1h_mmhg": round(co2_1h, 3),
            "co2_7d_mmhg": round(co2_7d, 3),
            "unit": "mmHg",
            "act_1h_mmhg": CABIN["act_1h_mmhg"],
            "watch_7d_mmhg": CABIN["watch_7d_mmhg"],
            "temp_c": float(current["temp_c"]),
            "rh_pct": float(current["rh_pct"]),
            "spark": [round(v, 3) for v in spark],
            "spark_label": "Daily average, last 7 days",
            "series_start": series[0]["t"],
            "series_end": series[-1]["t"],
            "mission_day": day_of(now),
            "source": "simulator" if sim_co2 else "osdr-eda-iss",
            "sources": list(CABIN["sources"]),
            "guide": CABIN["guide"][status],
        }

    def _headache_crew_ids(self, now: float) -> list[str]:
        """Ids of crew members whose latest symptom check in the last 24 hours lists a headache."""
        out = []
        for c in CREW:
            readings = self._readings(c["id"], now, days=2)
            for r in reversed(readings):
                if r["metric"] != "symptoms" or now - r["met_s"] > 86400:
                    continue
                items = (r.get("meta") or {}).get("items", [])
                if "headache" in items:
                    out.append(c["id"])
                break
        return out

    def _headache_crew(self, now: float) -> list[str]:
        """Crew members (names) who logged a headache in the last 24 hours."""
        ids = set(self._headache_crew_ids(now))
        return [c["name"] for c in CREW if c["id"] in ids]

    def ship_sense(self, env_id: str | None, now: float | None = None) -> dict[str, Any]:
        """Ship Sense: the crew-wide check for a shared cause. When two or more crew members report the same
        symptom, ASTRA looks at the habitat (the cabin CO2, from real ISS telemetry at the station) before anyone
        is treated as a separate patient: "it's the air, not you"."""
        now = self.now() if now is None else now
        cabin = self.cabin(env_id)
        if not cabin.get("available"):
            return {"available": False, "cabin": None, "symptom_crew": [], "insight": None}
        aching = self._headache_crew_ids(now)
        insight = rules.cabin_insight(cabin, [c["name"] for c in CREW if c["id"] in aching])
        keep = ("status", "status_label", "co2_1h_mmhg", "co2_7d_mmhg", "act_1h_mmhg", "watch_7d_mmhg",
                "source", "spark")
        return {"available": True, "cabin": {k: cabin.get(k) for k in keep}, "symptom_crew": aching,
                "insight": insight}

    def _conjunction_rows(self) -> list[dict[str, Any]]:
        return sorted(self._horizons(), key=lambda r: r["date"])

    def conjunction_warning_met(self) -> float | None:
        """The mission time at which the conjunction warning begins (a day inside the warning window).

        Used by the demo control that skips the clock there; None when the Horizons table has no
        conjunction in it.
        """
        rows = self._conjunction_rows()
        first = next((r for r in rows if float(r["sot_deg"]) <= CONJUNCTION_SOT_DEG), None)
        if first is None:
            return None
        launch = date.fromisoformat(MISSION["launch_utc"][:10])
        start = date.fromisoformat(first["date"]) - timedelta(days=CONJUNCTION_WARNING_DAYS - 1)
        return float(max(0, (start - launch).days) * DAY_S)

    def _conjunction(self, env_id: str) -> dict[str, Any] | None:
        """The solar-conjunction picture: a warning ahead of the blackout, then the blackout itself.

        `sot_deg` is the Sun-Observer-Target elongation from the Horizons table: the angle
        between the Sun and Mars as seen from Earth. Near 0 degrees the Sun is directly
        between the two planets and the radio link is badly degraded.

        * Within CONJUNCTION_WARNING_DAYS before the angle drops below the threshold, the phase is
          "warning" (Watch): send routine reports and ask Earth the open questions now.
        * While the angle is below the threshold, the phase is "blackout" (Act): ASTRA and the Crew
          Medical Officer handle everything on board.
        """
        if env_id not in ("transit", "mars"):
            return None
        rows = self._conjunction_rows()
        lt = self._light_time(self.now())
        if not rows or not lt:
            return None
        today = date.fromisoformat(lt["date"])
        in_blackout = float(lt["sot_deg"]) <= CONJUNCTION_SOT_DEG
        base = {"sot_deg": round(float(lt["sot_deg"]), 3), "threshold_deg": CONJUNCTION_SOT_DEG,
                "date": lt["date"], "warning_days": CONJUNCTION_WARNING_DAYS, "source": "horizons"}
        if in_blackout:
            end = next((r for r in rows if r["date"] > lt["date"] and float(r["sot_deg"]) > CONJUNCTION_SOT_DEG), None)
            ends = date.fromisoformat(end["date"]) if end else date.fromisoformat(rows[-1]["date"])
            days_left = max(0, (ends - today).days)
            return {**base, "phase": "blackout", "status": "act", "days_left": days_left,
                    "ends": ends.isoformat(),
                    "label": "Solar conjunction: radio blackout",
                    "detail": f"The Sun is between Earth and Mars. The radio link is degraded until about "
                              f"{ends:%d %b %Y} ({days_left} days). ASTRA and the Crew Medical Officer handle every "
                              "medical problem on board, and routine reports queue until the link returns."}
        first = next((r for r in rows if r["date"] > lt["date"] and float(r["sot_deg"]) <= CONJUNCTION_SOT_DEG), None)
        if first is None:
            return None
        starts = date.fromisoformat(first["date"])
        days_until = (starts - today).days
        if days_until > CONJUNCTION_WARNING_DAYS:
            return None
        length = 0
        for r in rows:
            if r["date"] >= first["date"]:
                if float(r["sot_deg"]) > CONJUNCTION_SOT_DEG:
                    break
                length += 1
        return {**base, "phase": "warning", "status": "watch", "days_until": days_until,
                "starts": starts.isoformat(), "blackout_days": length,
                "label": f"Solar conjunction in {days_until} days",
                "detail": f"From {starts:%d %b %Y} the Sun sits between Earth and Mars and the radio link is "
                          f"degraded for about {length} days. Send routine medical data and ask Mission Control your "
                          "open questions now. ASTRA keeps guiding the crew through the blackout."}

    def comms(self, env_id: str | None, crew_id: str | None = None, limit: int = 30) -> dict[str, Any]:
        env, now = self.env(env_id), self.now()
        packets = [self._packet_view(p, now) for p in self.store.packets(crew_id, limit)]
        return {
            "env_id": env["id"], "env_name": env["name"], "delay_s": env["delay_s"],
            "delay_label": fmt_delay(env["delay_s"]), "round_trip_label": fmt_delay(2 * env["delay_s"]),
            "live": env["delay_s"] < 5, "delay_note": env["delay_note"], "next_window": self._next_window(now),
            "light_time_source": env.get("light_time_source"),
            "utc": env["utc"],
            "conjunction": self._conjunction(env["id"]),
            "ground": [p for p in packets if p["kind"] in GROUND_KINDS],
            "cmo": [p for p in packets if p["kind"] == "cmo"],
        }

    def _send(self, crew_id: str, kind: str, priority: int, title: str, body: str, reply: str,
              env_id: str | None) -> dict[str, Any]:
        env, now = self.env(env_id), self.now()
        delay = 0.0 if kind == "cmo" else env["delay_s"]
        pid = self.store.add_packet(crew_id, kind, priority, title, body, reply, now, delay, env["id"])
        p = next(x for x in self.store.packets(crew_id, 5) if x["id"] == pid)
        return self._packet_view(p, now)

    def escalate_simulated(self, crew_id: str, metric_ids: list[str]) -> list[dict[str, Any]]:
        """Run the rules over readings the live simulator just wrote, and raise packets like a real save.

        The simulator writes straight to the store, so without this a simulated Act reading would never
        reach the Crew Medical Officer or the ground. It does NOT award XP, complete routine tasks or
        unlock badges (the readings are not the crew member's). A packet is sent only when a metric first
        reaches a tier, or reaches a higher one, and again after it has dropped back to tier 0, so a
        scenario that stays at Act does not send one packet per tick. The packet reads like a real alert;
        its body says the reading came from live telemetry (the readings themselves carry source "sim").
        """
        crew = self.crew(crew_id)
        try:
            state = json.loads(self.store.meta_get("sim_escalated") or "{}")
        except json.JSONDecodeError:
            state = {}
        now = self.now()
        readings = self._readings(crew_id, now)
        sent: list[dict[str, Any]] = []
        for mid in metric_ids:
            if mid not in METRIC_BY_ID:
                continue
            newest = next((r for r in reversed(readings) if r["metric"] == mid), None)
            if newest is None:
                continue
            ev = self.evaluate(crew_id, mid, newest["value"], newest.get("value2"), newest.get("meta"), None)
            key = f"{crew_id}:{mid}"
            tier = int(ev["tier"])
            if tier == 0:
                state.pop(key, None)
                continue
            if state.get(key, 0) >= tier:
                continue
            state[key] = tier
            title = f"{ev['label']} {ev['display']} {ev['unit']} · {ev['status_label']}".replace("  ", " ")
            reasons = "; ".join(ev["tier_reasons"] or [ev["status_label"]])
            body = f"Tier-{tier} alert for {crew['name']}: {reasons}. From live telemetry."
            if tier == 2:
                reply = ("Flight surgeon: Received the telemetry alert. Re-measure by hand to confirm, and continue "
                         "the onboard protocol. The CMO stays your first contact.")
                sent.append(self._send(crew_id, "alert", 2, title, body, reply, DEFAULT_ENV))
            else:
                sent.append(self._send(crew_id, "cmo", 1, title, body, "", DEFAULT_ENV))
        self.store.meta_set("sim_escalated", json.dumps(state))
        return sent

    def send_message(self, crew_id: str, text: str, env_id: str | None) -> dict[str, Any]:
        self.crew(crew_id)
        text = text.strip()
        if not text:
            raise EngineError(422, "Message is empty")
        title = text if len(text) <= 64 else text[:61] + "..."
        reply = ("Flight surgeon: Message received. We'll review it against your recent ASTRA data and reply in "
                 "detail at the next comm window. If anything gets worse, follow the onboard guidance and call "
                 "your Crew Medical Officer.")
        return self._send(crew_id, "message", 0, title, text, reply, env_id)

    # ------------------------------------------------------------------ attention queue
    def _derive_crew_attention_items(self, crew_id: str, env_id: str, now: float, today: int,
                                     readings: list[dict[str, Any]], states: dict[str, Any],
                                     ins: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        # 1. Metric Watch/Act readings
        for m_id, s in states.items():
            if not s.get("has_data") or s.get("status") not in ("watch", "act"):
                continue
            m = METRIC_BY_ID[m_id]
            severity = s["status"]
            reading_day = s.get("day", today)
            key = f"metric:{crew_id}:{m_id}:{reading_day}"
            val_display = s.get("display") or "-"
            unit = m.get("unit", "")
            unit_suffix = f" {unit}" if unit and not val_display.endswith(unit) else ""
            title = f"{m['label']} {val_display}{unit_suffix}".strip()

            if s.get("personal"):
                reason = "Inside normal range, but unusual for you compared with your personal baseline."
            else:
                guide_str = m.get("guide", {}).get(severity, "")
                reason = guide_str.split(". ")[0] + "." if ". " in guide_str else guide_str

            stale = bool(s.get("stale"))
            action = {"label": "Re-measure" if stale else "Measure again", "href": f"/measure/{m_id}"}
            source = s.get("source", "manual")
            daily = self._daily(readings, m_id)
            age = max(0.0, now - daily[-1]["met_s"]) if daily else 0.0

            flags = rules.red_flags(m_id, s.get("value"), s.get("value2"), s.get("meta"))
            tier, _ = rules.escalation_tier(severity, flags, s.get("persistence", {}))
            escalation_tier = tier if tier in (1, 2) else None

            items.append({
                "key": key,
                "crew_id": crew_id,
                "severity": severity,
                "title": title,
                "reason": reason,
                "action": action,
                "source": source,
                "age": round(age, 1),
                "stale": stale,
                "escalation_tier": escalation_tier,
            })

        # 2. Cross-metric insights
        for i in ins:
            i_sev = i.get("severity")
            i_id = i.get("id", "")
            if i_sev not in ("watch", "act") or i_id in ("all_clear", "cabin_air") or i_id.startswith("metric_"):
                continue
            key = f"insight:{crew_id}:{i_id}"
            body_text = i.get("body", "")
            reason = body_text.split(". ")[0] + "." if ". " in body_text else body_text
            target_metric = i["metrics"][0] if i.get("metrics") else ""
            action = {"label": "View trend", "href": f"/trends?m={target_metric}" if target_metric else "/trends"}

            underlying = [r for r in readings if r["metric"] in i.get("metrics", [])]
            age = max(0.0, now - max(r["met_s"] for r in underlying)) if underlying else 0.0
            is_sim = bool(underlying and all(r.get("source") == "sim" for r in underlying))

            items.append({
                "key": key,
                "crew_id": crew_id,
                "severity": i_sev,
                "title": i.get("title", ""),
                "reason": reason,
                "action": action,
                "source": "sim" if is_sim else "manual",
                "age": round(age, 1),
                "stale": False,
                "escalation_tier": 1 if i_sev == "act" else None,
            })

        return items

    def _derive_packet_attention_items(self, crew_id: str | None, now: float) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        packets = self.store.packets(crew_id, limit=30) if crew_id else self.store.packets(None, limit=40)
        for p in packets:
            pv = self._packet_view(p, now)
            if p["kind"] == "cmo":
                key = f"packet:{p['id']}"
                sev = "act" if p.get("priority", 0) > 0 else "watch"
                body = p.get("body", "")
                reason = body.split(". ")[0] + "." if ". " in body else body
                items.append({
                    "key": key,
                    "crew_id": p["crew_id"],
                    "severity": sev,
                    "title": f"CMO alert: {p['title']}",
                    "reason": reason,
                    "action": {"label": "Review on Crew", "href": "/crew"},
                    "source": "manual",
                    "age": round(max(0.0, now - p["created_met"]), 1),
                    "stale": False,
                    "escalation_tier": 1,
                })
            elif p["kind"] in GROUND_KINDS and pv.get("status") == "replied":
                key = f"packet:{p['id']}"
                rep = p.get("reply", "")
                reason = rep.split(". ")[0] + "." if ". " in rep else rep
                delay = float(p["delay_s"])
                items.append({
                    "key": key,
                    "crew_id": p["crew_id"],
                    "severity": "watch",
                    "title": f"Ground reply: {p['title']}",
                    "reason": reason,
                    "action": {"label": "Read reply", "href": "/crew"},
                    "source": "manual",
                    "age": round(max(0.0, now - (p["created_met"] + 2 * delay + REPLY_THINK_S)), 1),
                    "stale": False,
                    "escalation_tier": 2,
                })
        return items

    def _derive_env_attention_items(self, env_id: str, now: float, crew_id: str = "all") -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        env = self.env(env_id)

        # Solar particle event
        rad = self.radiation("ana", env["id"], now)
        solar = rad.get("solar", {})
        if solar.get("status") in ("watch", "act") and not solar.get("ended"):
            ev = self._solar_event()
            age = max(0.0, now - float(ev.get("started_met", now))) if ev else 0.0
            in_shelter = solar.get("in_shelter", False)
            reason = ("Get to the shelter module now and wear shielding vest."
                      if not in_shelter else "In shelter module; remain sheltered until ASTRA confirms event is over.")
            items.append({
                "key": "env:solar",
                "crew_id": crew_id,
                "severity": solar["status"],
                "title": solar.get("label", "Solar particle event in progress"),
                "reason": reason,
                "action": {"label": "Shelter protocol", "href": "/#radiation"},
                "source": solar.get("source", "sensor"),
                "age": round(age, 1),
                "stale": False,
                "escalation_tier": 2,
            })

        # Solar conjunction
        conj = self._conjunction(env["id"])
        if conj and conj.get("status") in ("watch", "act"):
            det = conj.get("detail", "")
            reason = det.split(". ")[0] + "." if ". " in det else det
            items.append({
                "key": "env:conjunction",
                "crew_id": crew_id,
                "severity": conj["status"],
                "title": conj.get("label", "Solar conjunction"),
                "reason": reason,
                "action": {"label": "Comms status", "href": "/crew"},
                "source": "horizons",
                "age": 0.0,
                "stale": False,
                "escalation_tier": 1 if conj["status"] == "act" else None,
            })

        # Cabin CO2
        cab = self.cabin(env["id"])
        if cab.get("available") and cab.get("status") in ("watch", "act"):
            items.append({
                "key": "env:cabin",
                "crew_id": crew_id,
                "severity": cab["status"],
                "title": f"Cabin CO₂: {cab['status'].capitalize()} ({cab.get('co2_1h_mmhg')} mmHg)",
                "reason": cab.get("guide", "Elevated CO2 in habitat."),
                "action": {"label": "Check scrubbers", "href": "/#cabin"},
                "source": cab.get("source", "sensor"),
                "age": 0.0,
                "stale": False,
                "escalation_tier": 1 if cab["status"] == "act" else None,
            })

        return items

    def attention(self, crew_id: str | None = None, env_id: str | None = None) -> dict[str, Any]:
        env = self.env(env_id)
        now = self.now()
        today = day_of(now)

        derived_items: list[dict[str, Any]] = []
        if crew_id:
            c = self.crew(crew_id)
            readings = self._readings(crew_id, now)
            states = {m["id"]: self._metric_state(c, m["id"], self._daily(readings, m["id"]), today) for m in METRICS}
            for k, s in states.items():
                limit = STALE_AFTER_DAYS["weekly" if k in WEEKLY_METRICS else "daily"]
                s["stale"] = not s["has_data"] or (s["age_days"] or 0) > limit
            snap = {k: {"status": s["status"], "value": s["value"], "baseline": s["baseline"], "slope": s["slope"],
                        "recent": [(d["day"], d["value"]) for d in self._daily(readings, k) if d["day"] > today - 7],
                        "items": (s.get("meta") or {}).get("items", []), "change_pct": s.get("change_pct", 0),
                        "personal": s["personal"]}
                    for k, s in states.items() if s["has_data"]}
            ins = rules.insights(snap)
            derived_items.extend(
                self._derive_crew_attention_items(crew_id, env["id"], now, today, readings, states, ins)
            )
            derived_items.extend(self._derive_packet_attention_items(crew_id, now))
            derived_items.extend(self._derive_env_attention_items(env["id"], now, crew_id=crew_id))
        else:
            for c in CREW:
                cid = c["id"]
                readings = self._readings(cid, now)
                states = {
                    m["id"]: self._metric_state(c, m["id"], self._daily(readings, m["id"]), today)
                    for m in METRICS
                }
                for k, s in states.items():
                    limit = STALE_AFTER_DAYS["weekly" if k in WEEKLY_METRICS else "daily"]
                    s["stale"] = not s["has_data"] or (s["age_days"] or 0) > limit
                snap = {
                    k: {
                        "status": s["status"], "value": s["value"], "baseline": s["baseline"], "slope": s["slope"],
                        "recent": [(d["day"], d["value"]) for d in self._daily(readings, k) if d["day"] > today - 7],
                        "items": (s.get("meta") or {}).get("items", []), "change_pct": s.get("change_pct", 0),
                        "personal": s["personal"],
                    }
                    for k, s in states.items() if s["has_data"]
                }
                ins = rules.insights(snap)
                derived_items.extend(
                    self._derive_crew_attention_items(cid, env["id"], now, today, readings, states, ins)
                )
            derived_items.extend(self._derive_packet_attention_items(None, now))
            derived_items.extend(self._derive_env_attention_items(env["id"], now, crew_id="all"))

        active_keys = {item["key"] for item in derived_items}

        # Auto-resolve previously recorded items that are no longer active
        unresolved = self.store.attention_unresolved(crew_id)
        for row in unresolved:
            if row["key"] not in active_keys:
                self.store.set_attention_resolved(
                    row["key"], row["crew_id"], "auto", now, "Auto-resolved: condition returned to nominal"
                )

        active_items = []
        for item in derived_items:
            ack = self.store.attention_ack(item["key"])
            if ack:
                if ack["state"] == "resolved":
                    continue
                item["state"] = ack["state"]
                item["acknowledged_by"] = ack.get("by_crew_id")
                item["acknowledged_at"] = ack.get("at_met")
                item["resolved_by"] = None
                item["resolved_at"] = None
                item["note"] = ack.get("note")
            else:
                self.store.set_attention_open(item["key"], item["crew_id"])
                item["state"] = "open"
                item["acknowledged_by"] = None
                item["acknowledged_at"] = None
                item["resolved_by"] = None
                item["resolved_at"] = None
                item["note"] = None
            active_items.append(item)

        def _sort_key(it: dict[str, Any]) -> tuple:
            is_stale = 1 if it.get("stale") else 0
            sev_rank = 0 if it["severity"] == "act" else 1
            ack_rank = 1 if it["state"] == "acknowledged" else 0
            return (is_stale, sev_rank, ack_rank, -it.get("age", 0.0))

        active_items.sort(key=_sort_key)

        counts = {
            "act": sum(1 for i in active_items if i["severity"] == "act"),
            "watch": sum(1 for i in active_items if i["severity"] == "watch"),
            "stale": sum(1 for i in active_items if i.get("stale")),
            "open": sum(1 for i in active_items if i["state"] == "open"),
            "acknowledged": sum(1 for i in active_items if i["state"] == "acknowledged"),
        }

        history_rows = self.store.attention_history(crew_id, limit=15)
        history_items = []
        for h in history_rows:
            history_items.append({
                "key": h["key"],
                "crew_id": h["crew_id"],
                "severity": "act" if "act" in (h.get("note") or "").lower() else "watch",
                "title": h["key"],
                "reason": h.get("note") or "Resolved",
                "action": {"label": "View", "href": "/trends"},
                "source": "manual",
                "age": 0.0,
                "stale": False,
                "state": "resolved",
                "acknowledged_by": h.get("by_crew_id"),
                "acknowledged_at": h.get("at_met"),
                "resolved_by": h.get("resolved_by"),
                "resolved_at": h.get("resolved_at"),
                "note": h.get("note"),
            })

        return {
            "crew_id": crew_id,
            "counts": counts,
            "items": active_items,
            "history": history_items,
        }

    def ack_attention(self, key: str, crew_id: str) -> dict[str, Any]:
        self.crew(crew_id)
        now = self.now()
        target_crew_id = crew_id
        if key.startswith("metric:") or key.startswith("insight:"):
            parts = key.split(":")
            if len(parts) >= 2:
                target_crew_id = parts[1]
        elif key.startswith("env:"):
            target_crew_id = "all"
        elif key.startswith("packet:"):
            pid = int(key.split(":")[1])
            p = next((x for x in self.store.packets(limit=50) if x["id"] == pid), None)
            if p:
                target_crew_id = p["crew_id"]

        self.store.set_attention_ack(key, target_crew_id, crew_id, now)
        xp = 0
        # Buddy check: acknowledging a crewmate's alert earns XP once per alert (never your own, never habitat alerts).
        reason = None
        if target_crew_id in {c["id"] for c in CREW} and target_crew_id != crew_id:
            reason = f"Buddy check on {self.crew(target_crew_id)['name'].split()[0]}'s alert"
        # ... and at most BUDDY_DAILY_CAP a mission day, so acknowledging a whole queue at once cannot farm XP.
        today_start = (day_of(now) - 1) * DAY_S
        paid_today = sum(1 for e in self.store.xp_events(crew_id, limit=200)
                         if e["reason"].startswith("Buddy check") and e["met_s"] >= today_start)
        if reason and paid_today < BUDDY_DAILY_CAP and not self.store.xp_reason_exists(crew_id, f"{reason} [{key}]"):
            self.store.add_xp(crew_id, BUDDY_XP, f"{reason} [{key}]", now)
            xp = BUDDY_XP
        return {
            "ok": True,
            "xp_gained": xp,
            "key": key,
            "state": "acknowledged",
            "acknowledged_by": crew_id,
            "acknowledged_at": now,
        }

    def resolve_attention(self, key: str, crew_id: str, note: str) -> dict[str, Any]:
        c = self.crew(crew_id)
        if not c.get("is_cmo"):
            raise EngineError(403, "Only the Crew Medical Officer may resolve attention items")
        if not note or not note.strip():
            raise EngineError(422, "A note is required to resolve an attention item")

        now = self.now()
        target_crew_id = crew_id
        if key.startswith("metric:") or key.startswith("insight:"):
            parts = key.split(":")
            if len(parts) >= 2:
                target_crew_id = parts[1]
        elif key.startswith("env:"):
            target_crew_id = "all"
        elif key.startswith("packet:"):
            pid = int(key.split(":")[1])
            p = next((x for x in self.store.packets(limit=50) if x["id"] == pid), None)
            if p:
                target_crew_id = p["crew_id"]

        self.store.set_attention_resolved(key, target_crew_id, crew_id, now, note.strip())
        return {
            "ok": True,
            "key": key,
            "state": "resolved",
            "resolved_by": crew_id,
            "resolved_at": now,
            "note": note.strip(),
        }

    # ------------------------------------------------------------------ exercise
    def exercise(self, crew_id: str, env_id: str | None) -> dict[str, Any]:
        """This week's exercise plan and today's session, adjusted for history and today's readings."""
        crew, env = self.crew(crew_id), self.env(env_id)
        now = self.now()
        today = day_of(now)
        readings = self._readings(crew_id, now)
        states = {mid: self._metric_state(crew, mid, self._daily(readings, mid), today)
                  for mid in ("temp", "sleep", "nutrition", "bp", "hydration", "spo2")}
        minutes = {d["day"]: d["value"] for d in self._daily(readings, "exercise")}
        return exercise_plan.build_plan(crew, CREW_PROFILES.get(crew_id, {}), env["id"], today, states, minutes)

    # ------------------------------------------------------------------ dashboard
    def dashboard(self, crew_id: str, env_id: str | None) -> dict[str, Any]:
        crew, env = self.crew(crew_id), self.env(env_id)
        now = self.now()
        today = day_of(now)
        readings = self._readings(crew_id, now)
        states = {m["id"]: self._metric_state(crew, m["id"], self._daily(readings, m["id"]), today)
                  for m in METRICS}
        for k, s in states.items():
            limit = STALE_AFTER_DAYS["weekly" if k in WEEKLY_METRICS else "daily"]
            s["stale"] = not s["has_data"] or (s["age_days"] or 0) > limit
            # A post-exertion reading taken today is shown next to the resting status, not instead of it.
            s["active_reading"] = self._latest_active(readings, k, today) if METRIC_BY_ID[k].get("active") else None
        statuses = {k: s["status"] for k, s in states.items() if s["has_data"]}
        # Each reported symptom raises the system it belongs to (a red flag means act). The symptom check itself
        # no longer marks the immune system for, say, chest pain or a headache.
        felt: dict[str, list[str]] = defaultdict(list)
        sym = states["symptoms"]
        if sym["has_data"] and not sym["stale"]:
            for item in (sym.get("meta") or {}).get("items", []):
                if item in SYMPTOM_BY_ID:
                    felt[SYMPTOM_BY_ID[item]["organ"]].append(item)
        organs = []
        for o in ORGANS:
            own = [statuses.get(k, "ok") for k in o["metrics"] if k != "symptoms"]
            from_symptoms = ["act" if SYMPTOM_BY_ID[i]["red_flag"] else "watch" for i in felt[o["id"]]]
            organs.append({"id": o["id"], "status": rules.worst([*own, *from_symptoms]), "metrics": o["metrics"],
                           "symptoms": felt[o["id"]], "stale": all(states[k]["stale"] for k in o["metrics"])})
        snap: dict[str, Any] = {}
        for k, s in states.items():
            if not s["has_data"]:
                continue
            daily = self._daily(readings, k)
            snap[k] = {"status": s["status"], "value": s["value"], "baseline": s["baseline"], "slope": s["slope"],
                       "recent": [(d["day"], d["value"]) for d in daily if d["day"] > today - 7],
                       "items": (s.get("meta") or {}).get("items", []), "change_pct": s.get("change_pct", 0),
                       "personal": s["personal"]}
        ins = rules.insights(snap)
        routine = self.routine(crew_id, env["id"], readings, now)
        overall = rules.worst(statuses.values())
        comms = self.comms(env["id"], crew_id, limit=6)
        cabin = self.cabin(env["id"])
        if cabin.get("available"):
            # The cabin insight is crew-wide, so it is computed once and appended to the list.
            cabin_ins = rules.cabin_insight(cabin, self._headache_crew(now))
            if cabin_ins:
                ins = [cabin_ins] + [i for i in ins if i["id"] != "cabin_air"]
                ins.sort(key=lambda i: -rules.RANK[i["severity"]])
        rad = self.radiation(crew_id, env["id"], now)
        eva = rules.eva_readiness(statuses, states["sleep"]["value"])
        if rad.get("solar") and rad["solar"].get("status") in ("watch", "act"):
            eva = {
                "status": "nogo",
                "reasons": ["Active solar particle storm: EVA prohibited", *eva.get("reasons", [])],
            }
        attention = self.attention(crew_id, env["id"])
        game = self.game(crew_id, env["id"], readings, now)
        # What each check still to do would pay if finished now (base, timing, streak, Full orbit when it is the
        # last one): the same preview rules as the Progress section, so Today shows the XP where the action is.
        pending = [t for t in routine["tasks"] if t["state"] != "done"]
        orbit_done = self.store.xp_reason_exists(crew_id, honest.full_orbit_reason(day_of(now)))
        for t in pending:
            lines = honest.preview_lines(t, now % DAY_S, game["streak_before_today"], len(pending) == 1, orbit_done)
            t["xp_now"] = sum(amount for amount, _ in lines)
        return {
            "crew": crew, "env": env, "clock": self.clock(),
            "readiness": rules.readiness(statuses, ins, routine["overdue"]),
            "overall": overall, "overall_label": STATUS_LABEL[overall],
            "eva": eva,
            "metrics": states, "organs": organs, "insights": ins, "routine": routine,
            "game": game,
            "radiation": rad,
            "comms": comms,
            "cabin": cabin,
            "attention": attention,
        }

    def crew_overview(self, env_id: str | None) -> dict[str, Any]:
        rows = []
        for c in CREW:
            d = self.dashboard(c["id"], env_id)
            flags = [{"metric": k, "status": s["status"], "display": s["display"]}
                     for k, s in d["metrics"].items() if s["has_data"] and s["status"] != "ok"]
            rows.append({"crew": c, "readiness": d["readiness"], "overall": d["overall"], "eva": d["eva"],
                         "flags": flags, "top_insight": d["insights"][0] if d["insights"] else None,
                         "done": d["routine"]["done"], "total": d["routine"]["total"],
                         "level": d["game"]["level"], "streak": d["game"]["streak"],
                         "organs": d["organs"]})
        return {"clock": self.clock(), "crew": rows, "comms": self.comms(env_id), "ship_sense": self.ship_sense(env_id)}

    # ------------------------------------------------------------------ series
    def series(self, crew_id: str, metric_id: str, days: int = 14) -> dict[str, Any]:
        crew, m = self.crew(crew_id), self.metric(metric_id)
        days = max(7, min(int(days), 30))
        now = self.now()
        today = day_of(now)
        readings = self._readings(crew_id, now)
        daily = self._daily(readings, metric_id)
        ref = self._ref(crew, metric_id)
        b, b2 = self._baselines(metric_id, daily, today)
        points = [{"day": d["day"], "value": d["value"], "value2": d.get("value2"),
                   "status": self._status_of(crew, d), "display": fmt_value(metric_id, d["value"], d.get("value2")),
                   "time": fmt_tod(d["met_s"]), "items": (d.get("meta") or {}).get("items")}
                  for d in daily if d["day"] > today - days]
        axis = rules.axis_for(metric_id, ref)
        vals = [p["value"] for p in points] + [p["value2"] for p in points if p["value2"] is not None]
        if vals:
            pad = (axis[1] - axis[0]) * 0.06
            axis = [min(axis[0], min(vals) - pad), max(axis[1], max(vals) + pad)]
        state = self._metric_state(crew, metric_id, daily, today)
        log = [{"id": r["id"], "day": r["day"], "time": fmt_tod(r["met_s"]),
                "display": fmt_value(metric_id, r["value"], r.get("value2")),
                "status": self._status_of(crew, r), "task_id": r.get("task_id"), "source": r["source"],
                "items": (r.get("meta") or {}).get("items")}
               for r in reversed([r for r in readings if r["metric"] == metric_id])][:12]
        return {
            "metric": metric_id, "unit": m["unit"], "days": days, "today": today, "points": points,
            "baseline": round(b["mean"], 2) if b else None, "baseline2": round(b2["mean"], 2) if b2 else None,
            "band": rules.absolute_band(metric_id, ref), "axis": [round(axis[0], 2), round(axis[1], 2)],
            "state": state, "log": log,
            "stats": {
                "min": min((p["value"] for p in points), default=None),
                "max": max((p["value"] for p in points), default=None),
                "mean": round(sum(p["value"] for p in points) / len(points), 2) if points else None,
                "days_ok": sum(1 for p in points if p["status"] == "ok"),
                "days_watch": sum(1 for p in points if p["status"] == "watch"),
                "days_act": sum(1 for p in points if p["status"] == "act"),
            },
        }

    # ------------------------------------------------------------------ evaluate & save
    def _normalize(self, m: dict[str, Any], value: float | None, value2: float | None,
                   meta: dict[str, Any] | None) -> tuple[float, float | None, dict[str, Any] | None]:
        inp = m["input"]
        if m["id"] == "symptoms":
            items = [s for s in (meta or {}).get("items", []) if s in SYMPTOM_IDS]
            return float(len(items)), None, {"items": sorted(set(items))}
        if value is None:
            raise EngineError(422, f"{m['label']}: a value is required")
        if not (inp["min"] <= value <= inp["max"]):
            raise EngineError(422, f"{m['label']} must be between {inp['min']} and {inp['max']} {m['unit']}".strip())
        if m["id"] == "bp":
            if value2 is None:
                raise EngineError(422, "Blood pressure needs systolic and diastolic values")
            if not (30 <= value2 <= 160) or value2 >= value:
                raise EngineError(422, "Diastolic must be between 30 and 160 and lower than systolic")
        else:
            value2 = None
        if m.get("context_sensitive"):
            ctx = (meta or {}).get("context")
            if ctx is not None and ctx not in CONTEXT_BY_ID:
                raise EngineError(422, f"Unknown measurement context '{ctx}'")
            return float(value), value2, {"context": ctx} if ctx else None
        return float(value), value2, None

    def _context(self, m: dict[str, Any], meta: dict[str, Any] | None, readings: list[dict[str, Any]],
                 now: float, task_id: str | None) -> tuple[dict[str, Any] | None, bool, str | None]:
        """Work out the measurement context: (meta with context, inferred?, note for the crew).

        An explicit choice wins. Without one, a post-EVA routine task means "after an EVA", and an
        exercise session logged in the last 30 minutes means "after exercise"; otherwise resting.
        """
        if not m.get("context_sensitive"):
            return meta, False, None
        last_ex = next((r for r in reversed(readings) if r["metric"] == "exercise"), None)
        since_ex = now - last_ex["met_s"] if last_ex else None
        recent_ex = since_ex is not None and since_ex < RECENT_EXERCISE_S
        mins_ago = int(since_ex // 60) if since_ex is not None else 0
        ctx = (meta or {}).get("context")
        if ctx:
            note = None
            if ctx not in ACTIVE_CONTEXTS and recent_ex:
                note = (f"You logged exercise {mins_ago} min ago. A resting reading needs 30 minutes "
                        "after exercise, so this may read high.")
            return {"context": ctx}, False, note
        if task_id in TASK_CONTEXT:
            ctx = TASK_CONTEXT[task_id]
            return {"context": ctx}, True, f"Read as {CONTEXT_BY_ID[ctx]['label'].lower()}, because it is part of " \
                "the post-EVA check."
        if recent_ex:
            return ({"context": "after_exercise"}, True,
                    f"You logged exercise {mins_ago} min ago, so ASTRA read this as a post-exercise "
                    "reading.")
        return {"context": DEFAULT_CONTEXT}, True, None

    def evaluate(self, crew_id: str, metric_id: str, value: float | None, value2: float | None,
                 meta: dict[str, Any] | None, env_id: str | None, task_id: str | None = None) -> dict[str, Any]:
        crew, m, env = self.crew(crew_id), self.metric(metric_id), self.env(env_id)
        value, value2, meta = self._normalize(m, value, value2, meta)
        now = self.now()
        today = day_of(now)
        readings = self._readings(crew_id, now)
        meta, inferred, context_note = self._context(m, meta, readings, now, task_id)
        active = rules.is_active(metric_id, meta)
        daily = self._daily(readings, metric_id)
        ref = self._ref(crew, metric_id)
        status = rules.classify(metric_id, value, value2, ref, meta)
        flags = rules.red_flags(metric_id, value, value2, meta)
        b, b2 = self._baselines(metric_id, daily, today)
        z = None if active else rules.zscore(value, b)
        personal = False
        if (status == "ok" and z is not None and b and b["n"] >= 5 and abs(z) >= rules.PERSONAL_Z
                and rules.is_worse_direction(metric_id, z)):
            status, personal = "watch", True
        prev = [self._status_of(crew, d) for d in reversed(daily) if d["day"] < today]
        # A post-exertion reading stands alone: it does not extend a run of resting results.
        persist = rules.persistence([status] if active else [status, *prev])
        tier, reasons = rules.escalation_tier(status, flags, persist)
        tier_info = ESCALATION[tier]
        if tier == 2:
            msg = ("Priority packet to the flight surgeon. " + (
                "Live link: the ground team can respond now." if env["delay_s"] < 5 else
                f"It reaches Earth in {fmt_delay(env['delay_s'])}, and the earliest reply is in "
                f"{fmt_delay(2 * env['delay_s'] + REPLY_THINK_S)}. Act on the onboard guidance now."))
        elif tier == 1:
            msg = "The Crew Medical Officer is alerted on board and will review your trend with you."
        else:
            msg = ("Self-care. ASTRA will remind you to measure again later." if status != "ok"
                   else "Self-care. Nothing to do. Next check as scheduled.")
        guidance = m["guide"][status]
        if personal:
            guidance = ("Inside the normal range, but unusual for you compared with your personal baseline. "
                        "Measure again later and note how you feel.")
        ctx_info = CONTEXT_BY_ID.get((meta or {}).get("context") or "") if m.get("context_sensitive") else None
        if active and ctx_info:
            what = ctx_info["label"].lower()
            if status == "ok":
                guidance = (f"Within the expected range {what}. Your body is still recovering, so ASTRA does not "
                            f"compare this with your resting baseline. Sit quietly and measure again in "
                            f"{RECHECK_AFTER_MIN} minutes for your resting value.")
            elif status == "watch":
                guidance = (f"Higher than expected even {what}. Sit and rest for 10 minutes, drink water, then "
                            f"measure again. If it has not come down by {RECHECK_AFTER_MIN} minutes, tell the Crew "
                            "Medical Officer.")
            else:
                guidance = (f"Out of the safe range, even allowing for {what}. Stop all activity, sit or lie "
                            "down and measure again now. If confirmed, call the Crew Medical Officer. " +
                            m["guide"]["act"].split(". ")[-1])
        suggest_emergency = bool(flags) and (metric_id in ("symptoms", "spo2", "hr", "bp", "resp"))
        if active and ctx_info:
            delta_txt = (f"Taken {ctx_info['label'].lower()}, so not compared with your resting baseline" +
                         (f" ({fmt_value(metric_id, b['mean'], b2['mean'] if b2 else None)} {m['unit']})"
                          if b else ""))
        elif ref and m.get("rule") == "relative":
            delta_txt = f"{rules.relative_change(value, ref):+.1f}% vs your mission reference ({ref:.1f} {m['unit']})"
        elif b:
            delta = value - b["mean"]
            delta_txt = f"{delta:+.{max(m['decimals'], 1 if metric_id == 'mood' else 0)}f} {m['unit']} vs your " \
                        f"baseline ({fmt_value(metric_id, b['mean'], b2['mean'] if b2 else None)})".replace("  ", " ")
        else:
            delta_txt = "Not enough history yet for a personal baseline"
        return {
            "metric": metric_id, "label": m["label"], "unit": m["unit"], "value": value, "value2": value2,
            "meta": meta, "display": fmt_value(metric_id, value, value2), "status": status,
            "status_label": STATUS_LABEL[status], "personal": personal, "z": round(z, 2) if z is not None else None,
            "baseline": round(b["mean"], 2) if b else None, "baseline2": round(b2["mean"], 2) if b2 else None,
            "delta_text": delta_txt, "band": rules.absolute_band(metric_id, ref, meta), "persistence": persist,
            "context": ctx_info["id"] if ctx_info else None,
            "context_label": ctx_info["label"] if ctx_info else None,
            "context_inferred": inferred if ctx_info else False,
            "context_note": context_note,
            "active": active,
            "recheck_after_min": RECHECK_AFTER_MIN if active else None,
            "tier": tier, "tier_name": tier_info["name"], "tier_reasons": reasons, "escalation": msg,
            "guidance": guidance, "red_flags": flags, "suggest_emergency": suggest_emergency,
        }

    def save_reading(self, crew_id: str, metric_id: str, value: float | None, value2: float | None,
                     meta: dict[str, Any] | None, task_id: str | None, env_id: str | None) -> dict[str, Any]:
        crew, env = self.crew(crew_id), self.env(env_id)
        ev = self.evaluate(crew_id, metric_id, value, value2, meta, env["id"], task_id)
        now = self.now()
        today = day_of(now)
        readings = self._readings(crew_id, now)
        tasks_today = {t["id"]: t for t in self.tasks_for_day(today, env["id"])}
        if task_id and (task_id not in tasks_today or metric_id not in tasks_today[task_id]["metrics"]):
            task_id = None
        if not task_id:
            task_id = self._attach_task(metric_id, env["id"], readings, now)
        today_r = [r for r in readings if r["day"] == today]
        was_done = bool(task_id) and self._task_done(tasks_today[task_id], today_r)
        goal_before = self._crew_goal(env["id"], now)
        badges_before = self._badges(crew_id, readings, today, set(goal_before["reached_days"]))
        # Value-neutral bonuses, decided before this reading is stored: is this a follow-up of a recent Watch/Act
        # result, and has an extra reading of this measurement already earned XP today?
        closes_loop = honest.open_loop(self, crew, readings, metric_id, now)
        extra_paid_today = any(r["day"] == today and r["metric"] == metric_id and not r.get("task_id")
                               and r.get("source") != "sim" for r in readings)

        self.store.add_reading(crew_id, metric_id, ev["value"], ev["value2"], ev["meta"], now, task_id)

        readings_after = self._readings(crew_id, now + 0.001)
        today_after = [r for r in readings_after if r["day"] == today]
        xp_before = int(crew["base_xp"] + self.store.xp_sum(crew_id))
        # Every XP line this save earns, as (amount, reason): each goes to the ledger on its own, so the XP log, the
        # Alerts log and the result screen show exactly what was earned and why.
        lines: list[tuple[int, str]] = []
        task_info = None
        if task_id:
            task = tasks_today[task_id]
            done = self._task_done(task, today_after)
            remaining = [mm for mm in task["metrics"]
                         if mm not in {r["metric"] for r in today_after if r.get("task_id") == task_id}]
            task_info = {"id": task_id, "title": task["title"], "completed": done and not was_done,
                         "remaining": remaining}
            if done and not was_done:
                # Dynamic XP: the check's base XP (bigger checks earn more), then timing, streak, a fully finished
                # day and coming back after a missed day. None of it depends on what the readings say.
                lines.append((task["xp"], f"Completed {task['title']}"))
                lines += honest.task_bonuses(self, crew_id, task, readings_after, today, now, env["id"])
        elif not extra_paid_today:
            # Only the first extra reading of a measurement per day earns XP, so readings cannot be farmed.
            lines.append((ADHOC_XP, f"Extra {ev['label']} reading"))
        if closes_loop:
            # Re-measuring after a Watch or Act result: the follow-up is what is rewarded, whatever the new value.
            lines.append((LOOP_XP, f"Closed the loop on {ev['label'].lower()}"))
        for amount, reason in lines:
            self.store.add_xp(crew_id, amount, reason, now)
        quests_done = honest.claim_quests(self, crew_id, readings_after, now)
        lines += [(QUEST_XP, f"Quest complete: {title}") for title in quests_done]
        xp = sum(amount for amount, _ in lines)
        level_before, level_after = xp_before // XP_PER_LEVEL + 1, (xp_before + xp) // XP_PER_LEVEL + 1
        level_up = ({"level": level_after, "title": LEVELS[min(level_after - 1, len(LEVELS) - 1)]}
                    if level_after > level_before else None)

        packet = None
        if ev["tier"] >= 1:
            title = f"{ev['label']} {ev['display']} {ev['unit']} · {ev['status_label']}".replace("  ", " ")
            if ev.get("active"):
                title += f" ({ev['context_label'].lower()})"
            reasons = "; ".join(ev["tier_reasons"] or [ev["status_label"]])
            body = f"ASTRA tier-{ev['tier']} alert for {crew['name']}: {reasons}"
            if ev["tier"] == 2:
                reply = (f"Flight surgeon: Received {crew['name']}'s {ev['label'].lower()} reading ({ev['display']} "
                         f"{ev['unit']}). Re-measure now and continue the onboard protocol. The CMO stays your first "
                         "contact, and we are reviewing your telemetry.").replace("  ", " ")
                packet = self._send(crew_id, "alert", 2, title, body, reply, env["id"])
            else:
                packet = self._send(crew_id, "cmo", 1, title, body, "", env["id"])

        goal_after = self._crew_goal(env["id"], now + 0.001)
        badges_after = self._badges(crew_id, readings_after, today, set(goal_after["reached_days"]))
        if goal_after["done"] >= goal_after["target"] and not goal_before["done"] >= goal_before["target"]:
            badges_after.add("crew_keeper")
            self.store.add_badge(crew_id, "crew_keeper", now)
        unlocked = [b for b in BADGES if b["id"] in badges_after - badges_before]
        for b in unlocked:
            # Keep the moment it was earned (for the Alerts log); a badge, once earned, stays earned.
            self.store.add_badge(crew_id, b["id"], now)
        return {"evaluation": ev, "task": task_info, "xp_gained": xp, "badges_unlocked": unlocked, "packet": packet,
                "loop_closed": closes_loop, "quests_completed": quests_done,
                "xp_breakdown": [{"amount": a, "reason": r} for a, r in lines], "level_up": level_up}

    # ------------------------------------------------------------------ emergencies
    def start_emergency(self, crew_id: str, patient_id: str, protocol_id: str, env_id: str | None) -> dict[str, Any]:
        self.crew(crew_id)
        patient = self.crew(patient_id)
        proto = PROTOCOL_BY_ID.get(protocol_id)
        if not proto:
            raise EngineError(404, f"Unknown protocol '{protocol_id}'")
        now = self.now()
        eid = self.store.add_emergency(crew_id, patient_id, protocol_id, None, False, 0.0, [], now)
        packet = self._send(
            patient_id, "emergency", 3, f"EMERGENCY · {proto['name']}",
            f"{proto['name']} protocol started for {patient['name']} at {self.clock()['label']}. Vitals and the "
            "step timeline follow with each update.",
            "Ground medical: Emergency alert received and telemetry reviewed. Continue the onboard protocol. We are "
            "on console and will send guidance with every update.", env_id)
        return {"emergency_id": eid, "packet": packet}

    def finish_emergency(self, emergency_id: int, crew_id: str, track: str | None, completed: bool,
                         duration_s: float, steps: list[dict[str, Any]], is_drill: bool = False,
                         env_id: str | None = None) -> dict[str, Any]:
        self.crew(crew_id)
        row = self.store.finish_emergency(emergency_id, track, completed, duration_s, steps)
        if not row:
            raise EngineError(404, "Unknown emergency")
        unlocked = []
        xp = 0
        if is_drill and completed and self.store.add_badge(crew_id, "drill_ready", self.now()):
            self.store.add_xp(crew_id, DRILL_XP, "Emergency drill completed", self.now())
            unlocked = [b for b in BADGES if b["id"] == "drill_ready"]
            xp = DRILL_XP

        patient = self.crew(row["patient_id"])
        proto = PROTOCOL_BY_ID.get(row["protocol_id"])
        proto_name = proto["name"] if proto else row["protocol_id"]
        status_word = "completed" if completed else "ended early"
        prefix = "DRILL · " if is_drill else "EMERGENCY · "
        title = f"{prefix}{proto_name} ({status_word})"
        body = (
            f"{proto_name} protocol {status_word} for {patient['name']} at {self.clock()['label']}. "
            f"Duration: {round(duration_s)}s · {len(steps)} steps logged in timeline."
        )
        reply = (
            "Ground medical: Emergency timeline and completion record received. Continue monitoring patient."
            if not is_drill else
            "Ground medical: Drill record received and logged. Good training run."
        )
        packet = self._send(row["patient_id"], "emergency", 3 if not is_drill else 1, title, body, reply, env_id)
        return {"ok": True, "badges_unlocked": unlocked, "xp_gained": xp, "packet": packet}
