"""Honest Orbit: ASTRA's crew-health game.

Design rules, each from research (see docs and the Missions page):
  1. Reward the act, never the reading. XP and badges come from measuring, logging, closing loops, helping
     crewmates and drilling, never from a value being good (or bad). Pilots hide conditions to avoid grounding;
     a game that paid for good numbers would pay crew to do the same. Rewards for completing self-reports raised
     compliance without changing the answers (JMIR 2019, game-motivated ePRO).
  2. One crew, one score. No crewmate rankings: NASA treats crew conflict as a mission risk. Competition still works
     best for durability (STEP UP, JAMA IM 2019), so the crew competes with its own previous week instead.
  3. Paced to the mission's morale curve. Chapters follow the transit; a momentum guard eases goals when a person's
     completion drops (third-quarter phenomenon; Mars-500 inactivity).
  4. Forgiving streaks. Shields absorb a missed day; "Back on track" rewards the repair; the 66-day habit counts
     days done, not an unbroken run (Lally 2010; Silverman & Barasch 2023 on broken streaks).

Everything here is derived from stored data (readings, the XP ledger, acknowledgements), so every number the app
shows can be traced to a record.
"""

from __future__ import annotations

import re
from typing import Any

from .catalog import (
    BADGE_GROUPS,
    BADGES,
    CHAPTERS,
    CLOSE_TIME_BONUS,
    CLOSE_TIME_WINDOW_S,
    COMEBACK_XP,
    CREW,
    CREW_GOAL_RATIO,
    CREW_OPERATIONS,
    CREW_PROFILES,
    FULL_ORBIT_XP,
    HABIT_DAYS,
    LOOP_WINDOW_DAYS,
    METRICS,
    ON_TIME_BONUS,
    ON_TIME_WINDOW_S,
    PERKS,
    QUEST_XP,
    SHIELD_EVERY,
    SHIELD_MAX,
    STREAK_DAY_RATIO,
    STREAK_XP_CAP,
    STREAK_XP_PER_DAY,
    TRANSIT_DAYS,
    XP_RULES,
)
from .store import DAY_S, day_of, hhmm_to_s

LABEL = {m["id"]: m["label"] for m in METRICS}
HISTORY_WINDOW = 120  # days of history the game looks at


def _ok(done: int, total: int) -> bool:
    return total > 0 and done / total >= STREAK_DAY_RATIO


CORE_TASKS = ("morning", "wellbeing")  # the two anchors kept when momentum drops: Morning vitals, Mood & symptoms


def core_done_by_day(engine: Any, readings: list[dict[str, Any]], first: int, today: int,
                     env_id: str | None) -> dict[int, bool]:
    """Whether both core checks were finished on each day."""
    out = {}
    for d in range(first, today + 1):
        day_r = [r for r in readings if r["day"] == d]
        tasks = {t["id"]: t for t in engine.tasks_for_day(d, env_id if d == today else None)}
        out[d] = all(t in tasks and engine._task_done(tasks[t], day_r) for t in CORE_TASKS)
    return out


def completion_by_day(engine: Any, readings: list[dict[str, Any]], first: int, today: int,
                      env_id: str | None) -> dict[int, tuple[int, int]]:
    """(done, total) scheduled checks per day. Today includes location-specific checks, as the routine does."""
    return {d: engine._completion(readings, d, env_id if d == today else None) for d in range(first, today + 1)}


# --------------------------------------------------------------------------------------------
# Streak with shields
# --------------------------------------------------------------------------------------------
def streak_state(comp: dict[int, tuple[int, int]], today: int, core: dict[int, bool] | None = None) -> dict[str, Any]:
    """Walk forward through the days: a done day extends the streak (and every 7th earns a shield, at most 2);
    a missed day spends a shield instead of breaking the streak; with no shield it resets. Today never breaks it.
    Support mode really eases the goal: on a day when momentum had dropped (as of that day), finishing the two core
    checks counts as a done day ("eased")."""
    core = core or {}

    def eased(d: int) -> bool:
        return bool(core.get(d)) and momentum(comp, d)["support"]

    streak = best = shields = 0
    status: dict[int, str] = {}
    days = sorted(d for d in comp if d < today)
    # Days before the crew's first logged day are not "missed": the record starts with the first check.
    started = next((d for d in days if comp[d][0] > 0), None)
    for d in days:
        if started is None or d < started:
            continue
        done, total = comp[d]
        if total == 0:
            continue
        if _ok(done, total) or eased(d):
            streak += 1
            best = max(best, streak)
            if streak % SHIELD_EVERY == 0:
                shields = min(SHIELD_MAX, shields + 1)
            status[d] = "done" if _ok(done, total) else "eased"
        elif shields > 0:
            shields -= 1
            status[d] = "shielded"
        else:
            streak = 0
            status[d] = "missed"
    t_done, t_total = comp.get(today, (0, 0))
    if _ok(t_done, t_total) or eased(today):
        streak += 1
        best = max(best, streak)
        status[today] = "done" if _ok(t_done, t_total) else "eased"
    else:
        status[today] = "today"
    calendar = [{"day": d, "status": status.get(d, "none"), "done": comp.get(d, (0, 0))[0],
                 "total": comp.get(d, (0, 0))[1]} for d in range(today - 27, today + 1)]
    return {"current": streak, "best": best, "shields": shields, "shield_max": SHIELD_MAX,
            "shield_every": SHIELD_EVERY, "calendar": calendar, "status": status}


# --------------------------------------------------------------------------------------------
# Dynamic XP for a finished check
# --------------------------------------------------------------------------------------------
def full_orbit_reason(day: int) -> str:
    return f"Full orbit: every check on Day {day}"


def comeback_reason(day: int) -> str:
    return f"Welcome back after a missed day (Day {day})"


def task_bonuses(engine: Any, crew_id: str, task: dict[str, Any], readings: list[dict[str, Any]], today: int,
                 now: float, env_id: str | None) -> list[tuple[int, str]]:
    """XP on top of a just-finished check's base XP, as (amount, reason) lines for the ledger: when it was done,
    the streak it extends, a fully finished day, and coming back after a missed day. Like everything in Honest
    Orbit, none of it depends on what the readings say. `readings` already include the reading that finished it."""
    lines: list[tuple[int, str]] = []
    late = (now % DAY_S) - hhmm_to_s(task["time"])  # negative when done early
    if late <= ON_TIME_WINDOW_S:
        lines.append((ON_TIME_BONUS, f"On time: {task['title']}"))
    elif late <= CLOSE_TIME_WINDOW_S:
        lines.append((CLOSE_TIME_BONUS, f"Close to time: {task['title']}"))

    comp = completion_by_day(engine, readings, today - 60, today, env_id)
    core = core_done_by_day(engine, readings, today - 60, today, env_id)
    st = streak_state(comp, today, core)
    # The streak this check extends: days before today (today only counts once its checks are done).
    before = st["current"] - (1 if st["status"].get(today) in ("done", "eased") else 0)
    if before > 0:
        lines.append((min(STREAK_XP_CAP, STREAK_XP_PER_DAY * before), f"{before}-day streak"))

    done, total = comp.get(today, (0, 0))
    if total and done >= total and not engine.store.xp_reason_exists(crew_id, full_orbit_reason(today)):
        lines.append((FULL_ORBIT_XP, full_orbit_reason(today)))
    if st["status"].get(today - 1) == "missed" and not engine.store.xp_reason_exists(crew_id, comeback_reason(today)):
        lines.append((COMEBACK_XP, comeback_reason(today)))
    return lines


def preview_lines(task: dict[str, Any], tod: float, streak_before: int, last_pending: bool,
                  orbit_done: bool) -> list[tuple[int, str]]:
    """What finishing `task` at time-of-day `tod` would pay, line by line (the same rules as task_bonuses):
    its base XP, timing, the streak it extends, and Full orbit when it is the last check of the day."""
    lines: list[tuple[int, str]] = [(task["xp"], task["title"])]
    late = tod - hhmm_to_s(task["time"])
    if late <= ON_TIME_WINDOW_S:
        lines.append((ON_TIME_BONUS, "On time"))
    elif late <= CLOSE_TIME_WINDOW_S:
        lines.append((CLOSE_TIME_BONUS, "Close to time"))
    if streak_before > 0:
        lines.append((min(STREAK_XP_CAP, STREAK_XP_PER_DAY * streak_before), f"{streak_before}-day streak"))
    if last_pending and not orbit_done:
        lines.append((FULL_ORBIT_XP, "Full orbit"))
    return lines


def today_summary(engine: Any, crew_id: str, readings: list[dict[str, Any]], st: dict[str, Any], today: int,
                  now: float, env_id: str | None, support: bool) -> dict[str, Any]:
    """Today at a glance for the Missions page: checks done, XP earned today, the Full orbit bonus, and the next
    check with what it pays if done now (base, timing, streak, and Full orbit when it is the last one). Uses the
    same rules as task_bonuses, so the preview matches what saving will pay. With momentum support on, the core
    checks come first."""
    tasks = sorted(engine.tasks_for_day(today, env_id), key=lambda t: hhmm_to_s(t["time"]))
    day_r = [r for r in readings if r["day"] == today]
    pending = [t for t in tasks if not engine._task_done(t, day_r)]
    if support:
        pending.sort(key=lambda t: t["id"] not in CORE_TASKS)  # stable: keeps time order within each group
    xp_today = sum(e["amount"] for e in engine.store.xp_events(crew_id, 400) if day_of(e["met_s"]) == today)
    orbit_done = engine.store.xp_reason_exists(crew_id, full_orbit_reason(today))
    nxt = None
    if pending:
        t = pending[0]
        late = (now % DAY_S) - hhmm_to_s(t["time"])
        before = st["current"] - (1 if st["status"].get(today) in ("done", "eased") else 0)
        lines = preview_lines(t, now % DAY_S, before, len(pending) == 1, orbit_done)
        logged = {r["metric"] for r in day_r if r.get("task_id") == t["id"]}
        first = next((m for m in t["metrics"] if m not in logged), t["metrics"][0])
        nxt = {"id": t["id"], "title": t["title"], "time": t["time"], "overdue": late > CLOSE_TIME_WINDOW_S,
               "worth": sum(a for a, _ in lines), "lines": [{"amount": a, "reason": r} for a, r in lines],
               "href": f"/measure/{first}?task={t['id']}"}
    return {"done": len(tasks) - len(pending), "total": len(tasks), "xp": xp_today, "orbit_done": orbit_done,
            "orbit_xp": FULL_ORBIT_XP, "next": nxt}


# --------------------------------------------------------------------------------------------
# Momentum (the third-quarter guard)
# --------------------------------------------------------------------------------------------
def momentum(comp: dict[int, tuple[int, int]], today: int) -> dict[str, Any]:
    def rate(days: range) -> float | None:
        done = sum(comp.get(d, (0, 0))[0] for d in days)
        total = sum(comp.get(d, (0, 0))[1] for d in days)
        return done / total if total else None

    last, prev = rate(range(today - 7, today)), rate(range(today - 14, today - 7))
    support = last is not None and (last < 0.6 or (prev is not None and prev - last >= 0.15))
    trend = "steady"
    if last is not None and prev is not None:
        trend = "up" if last - prev >= 0.05 else "down" if prev - last >= 0.05 else "steady"
    if support:
        message = ("Momentum dipped this week, so the goal eases: until it recovers, a day counts for your streak "
                   "once your core checks are done (Morning vitals and Mood & symptoms).")
    elif trend == "down":
        message = "Slightly fewer checks than the week before. Keep the morning and evening anchors."
    else:
        message = "Momentum is holding. Keep the rhythm."
    return {"last7": None if last is None else round(100 * last), "prev7": None if prev is None else round(100 * prev),
            "trend": trend, "support": support, "message": message, "core_tasks": list(CORE_TASKS)}


def chapter_index(today: int) -> int:
    return min(len(CHAPTERS) - 1, max(0, (today - 1) * len(CHAPTERS) // TRANSIT_DAYS))


THIRD_QUARTER = 2


def operation_boost(today: int) -> int:
    """Crew operations count double in the third quarter, when morale tends to dip."""
    return 2 if chapter_index(today) == THIRD_QUARTER else 1


def chapter(today: int, support: bool) -> dict[str, Any]:
    idx = chapter_index(today)
    per = TRANSIT_DAYS // len(CHAPTERS)
    c = CHAPTERS[idx]
    return {**c, "index": idx, "count": len(CHAPTERS), "day": today, "transit_days": TRANSIT_DAYS,
            "start": idx * per + 1, "end": (idx + 1) * per,
            "progress": round(100 * min(today, TRANSIT_DAYS) / TRANSIT_DAYS),
            "guard": idx == THIRD_QUARTER or support, "boost": operation_boost(today),
            "chapters": [{"id": x["id"], "name": x["name"], "start": i * per + 1, "end": (i + 1) * per}
                         for i, x in enumerate(CHAPTERS)]}


# --------------------------------------------------------------------------------------------
# Loops: re-measuring after a Watch or Act result
# --------------------------------------------------------------------------------------------
def closed_loops(engine: Any, crew: dict[str, Any], readings: list[dict[str, Any]],
                 since_day: int | None = None) -> list[dict[str, Any]]:
    """Each Watch/Act reading followed by another reading of the same measurement within the window."""
    own = sorted((r for r in readings if r.get("source") != "sim"), key=lambda r: r["met_s"])
    out = []
    for i, r in enumerate(own):
        if engine._status_of(crew, r) == "ok":
            continue
        nxt = next((x for x in own[i + 1:] if x["metric"] == r["metric"]), None)
        if nxt and nxt["met_s"] - r["met_s"] <= LOOP_WINDOW_DAYS * DAY_S:
            if since_day is None or nxt["day"] >= since_day:
                out.append({"metric": r["metric"], "flagged_day": r["day"], "closed_day": nxt["day"]})
    return out


def open_loop(engine: Any, crew: dict[str, Any], readings: list[dict[str, Any]], metric: str, now: float) -> bool:
    """True when the latest reading of this measurement was Watch/Act within the window and not yet followed up."""
    own = [r for r in readings if r["metric"] == metric and r.get("source") != "sim" and r["met_s"] <= now]
    if not own:
        return False
    last = max(own, key=lambda r: r["met_s"])
    return engine._status_of(crew, last) != "ok" and now - last["met_s"] <= LOOP_WINDOW_DAYS * DAY_S


# --------------------------------------------------------------------------------------------
# Personal quests: countermeasures from the person's own medical history
# --------------------------------------------------------------------------------------------
def _days_logged(readings: list[dict[str, Any]], metric: str) -> set[int]:
    return {r["day"] for r in readings if r["metric"] == metric and r.get("source") != "sim"}


def _run(days: set[int], today: int) -> int:
    """Consecutive days logged ending today (or yesterday, when today is not logged yet)."""
    end = today if today in days else today - 1
    n = 0
    while end - n in days:
        n += 1
    return n


# The catalog's history notes speak about the person ("With her history", "push his pressure"), as the crew profile
# shows them. A quest is only ever shown to its owner, so its reason speaks to them: possessive her/his before a
# word becomes "your", the remaining her/him "you".
_SECOND_PERSON = (
    (re.compile(r"\b(?:Her|His)\b"), "Your"),
    (re.compile(r"\b(?:her|his)\b(?=\s+[a-z])"), "your"),
    (re.compile(r"\b(?:her|him)\b"), "you"),
)


def _to_you(text: str) -> str:
    for pattern, word in _SECOND_PERSON:
        text = pattern.sub(word, text)
    return text


def quests(engine: Any, crew_id: str, readings: list[dict[str, Any]], today: int) -> list[dict[str, Any]]:
    week = (today - 1) // 7 + 1
    out = []
    for h in CREW_PROFILES.get(crew_id, {}).get("history", []):
        metric = h["watch"][0]
        target = 5
        run = _run(_days_logged(readings, metric), today)
        title = f"Log {LABEL.get(metric, metric).lower()} {target} days in a row"
        reason = f"{h['condition']}, {h['year']}. {_to_you(h['influence'])}"
        claimed = engine.store.xp_reason_exists(crew_id, quest_reason(title, week))
        out.append({"id": f"{crew_id}:{metric}", "title": title, "metric": metric, "reason": reason,
                    "progress": min(run, target), "target": target, "xp": QUEST_XP,
                    "done": run >= target, "claimed": claimed, "href": f"/measure/{metric}"})
    return out


def quest_reason(title: str, week: int) -> str:
    return f"Quest: {title} (week {week})"


def claim_quests(engine: Any, crew_id: str, readings: list[dict[str, Any]], now: float) -> list[str]:
    """Credit every finished quest once per mission week. Idempotent (keyed on the ledger reason), so it is safe to
    run whenever a reading is saved or the Missions page is opened."""
    today = day_of(now)
    week = (today - 1) // 7 + 1
    done = []
    for q in quests(engine, crew_id, readings, today):
        if q["done"] and not q["claimed"]:
            engine.store.add_xp(crew_id, QUEST_XP, quest_reason(q["title"], week), now)
            done.append(q["title"])
    return done


# --------------------------------------------------------------------------------------------
# Badges, value-neutral
# --------------------------------------------------------------------------------------------
def badge_progress(engine: Any, crew: dict[str, Any], readings: list[dict[str, Any]],
                   comp: dict[int, tuple[int, int]], streak: dict[str, Any], today: int,
                   crew_days_reached: set[int]) -> dict[str, dict[str, Any]]:
    """Progress (value, target) and earned state for every badge, from actions only."""
    cid = crew["id"]
    stored = engine.store.stored_badges(cid)
    runs = {m: _run(_days_logged(readings, m), today) for m in ("hr", "exercise", "sleep", "hydration", "reaction")}
    vision_weeks = len({r["day"] // 7 for r in readings if r["metric"] == "vision" and r["day"] > today - 28
                        and r.get("source") != "sim"})
    days_done = sum(1 for dn, tt in comp.values() if _ok(dn, tt))
    loops = len(closed_loops(engine, crew, readings))
    comeback = any(s == "missed" and streak["status"].get(d + 1) in ("done", "eased")
                   for d, s in streak["status"].items())
    buddy = sum(1 for a in engine.store.attention_acks() if a.get("by_crew_id") == cid
                and a.get("crew_id") not in (cid, "all"))
    first_light = any(r.get("task_id") and r["met_s"] % DAY_S < 8 * 3600 and r.get("source") != "sim"
                      for r in readings)
    p: dict[str, tuple[int, int]] = {
        "first_light": (int(first_light), 1),
        "steady_pulse": (runs["hr"], 10),
        "iron_orbit": (runs["exercise"], 7),
        "night_watch": (runs["sleep"], 7),
        "hydro_hero": (runs["hydration"], 7),
        "mind_sharp": (runs["reaction"], 7),
        "clear_sight": (vision_weeks, 4),
        "habit_locked": (days_done, HABIT_DAYS),
        "loop_closer": (loops, 3),
        "comeback": (int(comeback), 1),
        "drill_ready": (int("drill_ready" in stored), 1),
        "buddy_check": (min(buddy, 1), 1),
        "crew_keeper": (int(bool(crew_days_reached) or "crew_keeper" in stored), 1),
    }
    return {bid: {"value": min(v, t), "target": t, "earned": v >= t or bid in stored} for bid, (v, t) in p.items()}


# --------------------------------------------------------------------------------------------
# Crew: weekly operation, crew vs last week, perks
# --------------------------------------------------------------------------------------------
def crew_week(engine: Any, env_id: str | None, now: float) -> dict[str, Any]:
    today = day_of(now)
    week = (today - 1) // 7 + 1
    start = (week - 1) * 7 + 1
    op = CREW_OPERATIONS[(week - 1) % len(CREW_OPERATIONS)]
    days = range(start, today + 1)
    per: dict[str, int] = {}
    crew_comp: dict[int, list[int]] = {d: [0, 0] for d in range(start - 7, today + 1)}
    for c in CREW:
        rs = engine._readings(c["id"], now, days=16)
        own = [r for r in rs if r.get("source") != "sim"]
        for d in range(start - 7, today + 1):
            dn, tt = engine._completion(rs, d, env_id if d == today else None)
            crew_comp[d][0] += dn
            crew_comp[d][1] += tt
        if op["id"] == "roll_call":
            n = len({r["day"] for r in own if r["day"] in days and r.get("task_id") == "morning"
                     and r["met_s"] % DAY_S < 8 * 3600})
        elif op["id"] == "night_log":
            n = len({r["day"] for r in own if r["day"] in days and r["metric"] == "sleep"})
        elif op["id"] == "steady_hands":
            n = len({r["day"] for r in own if r["day"] in days and r["metric"] == "reaction"})
        elif op["id"] == "loop_sweep":
            n = len(closed_loops(engine, c, rs, since_day=start))
        else:
            n = 0
        per[c["id"]] = n
    reached = [d for d in days if crew_comp[d][1] and crew_comp[d][0] >= CREW_GOAL_RATIO * crew_comp[d][1]]
    boost = operation_boost(today)
    raw = len(reached) if op["id"] == "full_logbook" else sum(per.values())
    value = raw * boost

    def pct(ds: range) -> int | None:
        dn = sum(crew_comp[d][0] for d in ds)
        tt = sum(crew_comp[d][1] for d in ds)
        return round(100 * dn / tt) if tt else None

    # Compare finished days only: today is still under way, so counting it would always look like a drop.
    full = range(start, today)
    this_week = pct(full) if len(full) else None
    last_week = pct(range(start - 7, start - 7 + len(full))) if len(full) else None
    return {
        "week": week, "start_day": start, "end_day": start + 6,
        "operation": {**op, "value": min(value, op["target"]), "done": value >= op["target"], "raw": raw,
                      "boost": boost,
                      "per_crew": [{"crew_id": c["id"], "name": c["name"].split()[0],
                                    "value": per[c["id"]] if op["id"] != "full_logbook" else None} for c in CREW]},
        "versus": {"this_week": this_week, "last_week": last_week, "days": len(full),
                   "ahead": this_week is not None and last_week is not None and this_week >= last_week},
        "goal_days": len(reached),
        "perks": [{**pk, "unlocked": len(reached) >= pk["days"],
                   "approved_by": engine.store.meta_get(perk_key(week, pk["days"]))} for pk in PERKS],
    }


def perk_key(week: int, days: int) -> str:
    return f"perk_approved:{week}:{days}"


def approve_perk(engine: Any, crew_id: str, week: int, days: int) -> dict[str, Any]:
    """Only the Commander approves an unlocked crew reward for the current mission week."""
    from .services import EngineError  # local import: services imports this module

    crew = engine.crew(crew_id)
    if crew["role"] != "Commander":
        raise EngineError(403, "Only the Commander approves crew rewards")
    cw = crew_week(engine, None, engine.now())
    perk = next((p for p in cw["perks"] if p["days"] == days), None)
    if week != cw["week"] or perk is None:
        raise EngineError(404, "No such reward this week")
    if not perk["unlocked"]:
        raise EngineError(409, "This reward is not unlocked yet")
    engine.store.meta_set(perk_key(week, days), crew_id)
    return {"ok": True, "week": week, "days": days, "approved_by": crew_id}


def hub(engine: Any, crew_id: str, env_id: str | None) -> dict[str, Any]:
    """Everything the Missions page shows for one person."""
    crew = engine.crew(crew_id)
    now = engine.now()
    today = day_of(now)
    readings = engine._readings(crew_id, now, days=HISTORY_WINDOW)
    claim_quests(engine, crew_id, readings, now)
    comp = completion_by_day(engine, readings, today - HISTORY_WINDOW + 1, today, env_id)
    core = core_done_by_day(engine, readings, today - HISTORY_WINDOW + 1, today, env_id)
    streak = streak_state(comp, today, core)
    mom = momentum(comp, today)
    goal = engine._crew_goal(env_id, now)
    progress = badge_progress(engine, crew, readings, comp, streak, today, set(goal["reached_days"]))
    game = engine.game(crew_id, env_id, readings=readings, now=now)
    badges = [{**b, **progress.get(b["id"], {"value": 0, "target": 1, "earned": False})} for b in BADGES]
    ledger = [{"id": e["id"], "amount": e["amount"], "reason": e["reason"], "at": e["met_s"],
               "at_label": f"Day {day_of(e['met_s'])} · {int(e['met_s'] % DAY_S) // 3600:02d}:"
                           f"{int(e['met_s'] % DAY_S) % 3600 // 60:02d}"}
              for e in engine.store.xp_events(crew_id, limit=100)]
    return {
        "crew_id": crew_id, "day": today,
        "today": today_summary(engine, crew_id, readings, streak, today, now, env_id, mom["support"]),
        "level": {k: game[k] for k in ("xp", "level", "title", "level_xp", "xp_per_level")},
        "streak": {k: v for k, v in streak.items() if k != "status"},
        "momentum": mom,
        "chapter": chapter(today, mom["support"]),
        "quests": quests(engine, crew_id, readings, today),
        "badges": badges, "badge_groups": BADGE_GROUPS,
        "earned_count": sum(1 for b in badges if b["earned"]),
        "crew": crew_week(engine, env_id, now),
        "ledger": ledger,
        "rules": XP_RULES,
        "seed_xp": crew["base_xp"],
        "can_approve": crew["role"] == "Commander",
    }
