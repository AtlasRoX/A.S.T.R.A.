"""ASTRA specialist: a chat assistant that knows the app's live data, answered by NVIDIA Nemotron through NIM.

How an answer is built:
  1. Heuristics read the question: which crew members it is about (names, roles, "me"), which indicators
     (sleep, blood pressure ...), and whether it sounds like an emergency.
  2. Retrieval: only the relevant slices of live data go into the prompt (mission clock and link, crew status,
     the named people's readings, history, alerts and today's exercise, the named indicators' rules), within a
     character budget, so answers stay grounded and fast.
  3. The model answers from that context only, cites what it used, and follows ASTRA's escalation ladder.
  4. Without a key, or when NIM fails, a rules-only answer is built from the same context, so the assistant
     never goes silent.

The key is read from the environment (NVIDIA_API_KEY), or from engine/.env, which git ignores. It is never sent to
the browser.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .catalog import BADGES, CREW, CREW_PROFILES, ESCALATION, LEVELS, METRICS, PROTOCOLS, XP_PER_LEVEL
from .services import fmt_tod, fmt_value

NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
_working_model: str | None = None
CONTEXT_BUDGET = 22_000  # characters of retrieved data per question
HISTORY_TURNS = 8


def _env(name: str) -> str | None:
    """A setting from the process environment, else from engine/.env."""
    value = os.environ.get(name)
    if value:
        return value.strip()
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip() or None
    return None


def _api_key() -> str | None:
    return _env("NVIDIA_API_KEY")


def _models() -> list[str]:
    """Tried in order: NIM_MODEL if set, then the default. A model this account cannot call (HTTP 404) is skipped
    and the one that answers is remembered."""
    forced = _env("NIM_MODEL")
    return [forced, DEFAULT_MODEL] if forced and forced != DEFAULT_MODEL else [DEFAULT_MODEL]


# --------------------------------------------------------------------------------------------
# Heuristics: what the question is about
# --------------------------------------------------------------------------------------------
_EMERGENCY = re.compile(
    r"\b(chest pain|collaps\w*|unconscious|not breathing|can'?t breathe|choking|seizure|bleeding heavily|"
    r"heart attack|stroke|anaphyla\w*|unresponsive|head injury|fainted|emergency)\b", re.I)
_ROLE = {"commander": "ana", "cdr": "ana", "medical officer": "kenji", "cmo": "kenji", "doctor": "kenji",
         "engineer": "sara", "flight engineer": "sara", "specialist": "lucas", "mission specialist": "lucas",
         "geologist": "lucas"}
_METRIC_WORDS: dict[str, tuple[str, ...]] = {
    "hr": ("heart rate", "pulse", "hr"), "bp": ("blood pressure", "bp", "hypertension"),
    "spo2": ("oxygen", "spo2", "saturation"), "resp": ("breathing rate", "respiration", "breathing"),
    "temp": ("temperature", "fever", "temp"), "glucose": ("glucose", "sugar"),
    "hydration": ("fluid", "water", "hydration", "drink", "kidney"), "mass": ("weight", "mass", "body mass"),
    "nutrition": ("food", "eat", "calorie", "nutrition", "appetite"), "sleep": ("sleep", "tired", "fatigue"),
    "mood": ("mood", "stress", "anxious", "depress"), "reaction": ("reaction", "alertness", "attention"),
    "exercise": ("exercise", "workout", "training", "ared", "treadmill", "cycle", "squat", "deadlift"),
    "vision": ("vision", "eye", "sans", "blur"), "symptoms": ("symptom", "headache", "nausea", "pain"),
}


def page_context(page: str | None) -> dict[str, Any]:
    """What the user is looking at, from the app path: a crew profile, a metric's trend or measure page, exercise."""
    out: dict[str, Any] = {"crew": None, "metric": None, "area": None}
    if not page:
        return out
    if m := re.match(r"^/crew/(\w+)", page):
        out["crew"] = m.group(1) if any(c["id"] == m.group(1) for c in CREW) else None
        out["area"] = "profile"
    elif m := re.match(r"^/(?:measure|trends)(?:/(\w+)|.*[?&]m=(\w+))?", page):
        out["metric"] = m.group(1) or m.group(2)
        out["area"] = "metric"
    elif page.startswith("/exercise"):
        out["area"] = "exercise"
    elif page.startswith("/missions"):
        out["area"] = "missions"
    return out


def analyse(question: str, viewer: str, page: str | None = None) -> dict[str, Any]:
    q = question.lower()
    here = page_context(page)
    crew: list[str] = []
    for c in CREW:
        first, last = c["name"].lower().split()[0], c["name"].lower().split()[-1]
        if re.search(rf"\b({first}|{last}|{c['id']})\b", q):
            crew.append(c["id"])
    for word, cid in _ROLE.items():
        if re.search(rf"\b{word}\b", q) and cid not in crew:
            crew.append(cid)
    everyone = bool(re.search(r"\b(crew|everyone|all of us|team|who)\b", q))
    me = bool(re.search(r"\b(i|me|my|mine)\b", q))
    # On a profile page, "he", "she", "they" (or a question naming nobody) mean the person on that page.
    if not crew and here["crew"] and not everyone and not me:
        crew.append(here["crew"])
    if not crew and (me or not everyone):
        crew.append(viewer)
    metrics = [m for m, words in _METRIC_WORDS.items() if any(re.search(rf"\b{re.escape(w)}", q) for w in words)]
    # On a metric's trend or measure page, a question about "it" or "this trend" is about that metric.
    if not metrics and here["metric"] in _METRIC_WORDS:
        metrics.append(here["metric"])
    if here["area"] == "exercise" and "exercise" not in metrics:
        metrics.append("exercise")
    return {
        "crew": crew[:4], "everyone": everyone, "metrics": metrics,
        "emergency": bool(_EMERGENCY.search(q)),
        "exercise": "exercise" in metrics,
        "radiation": bool(re.search(r"radiation|dose|solar|shelter|msv", q)),
        "comms": bool(re.search(r"earth|delay|link|comms|ground|flight surgeon|message", q)),
        "game": here["area"] == "missions"
        or bool(re.search(r"\b(xp|level|badges?|streaks?|quests?|missions?|rewards?|perks?|points?|shields?)\b", q)),
    }


# --------------------------------------------------------------------------------------------
# Retrieval: the relevant slices of live data
# --------------------------------------------------------------------------------------------
def _crew_line(r: dict[str, Any]) -> str:
    issue = r.get("top_insight") or {}
    flags = ", ".join(f"{f['metric']} {f['status']}" for f in r.get("flags", [])[:6])
    return (f"- {r['crew']['title']} {r['crew']['name']} ({r['crew']['role']}, id {r['crew']['id']}): overall "
            f"{r['overall']}, EVA {r['eva']['status']}, checks {r['done']}/{r['total']}"
            f"{'; top issue: ' + issue['title'] if issue.get('title') and issue.get('severity') != 'ok' else ''}"
            f"{'; flagged: ' + flags if flags else ''}")


def _ago(seconds: float) -> str:
    s = max(0, int(seconds))
    if s < 3600:
        return f"{max(1, s // 60)} min ago"
    if s < 86400:
        return f"{s // 3600} h ago"
    return f"{s // 86400} d ago"


def _at_label(met_s: float) -> str:
    return f"Day {int(met_s // 86400) + 1} · {fmt_tod(met_s)}"


def build_context(engine: Any, crew_id: str, env_id: str | None, a: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Context text for the model, and the entities its answer may show as live UI (readings, crew, actions,
    protocols). Each entity is listed in the text with its token, so the model can only place real data."""
    parts: list[str] = []
    ents: dict[str, dict[str, Any]] = {"reading": {}, "crew": {}, "action": {}, "protocol": {}}
    dash_viewer = engine.dashboard(crew_id, env_id)
    env, clock, comms = dash_viewer["env"], dash_viewer["clock"], dash_viewer["comms"]
    viewer = next(c for c in CREW if c["id"] == crew_id)
    parts.append(
        f"MISSION: day {clock['day']}, {clock['label']}. Location: {env['name']} ({env['gravity']}). "
        f"Earth one-way delay {round(env['delay_s'])} s (a reply takes at least {round(2 * env['delay_s'] / 60)} min). "
        f"The user is {viewer['title']} {viewer['name']}, {viewer['role']} (id {crew_id}).")

    overview = engine.crew_overview(env_id)
    lines = []
    for r in overview["crew"]:
        c = r["crew"]
        issue = r.get("top_insight") or {}
        ents["crew"][c["id"]] = {
            "id": c["id"], "name": f"{c['title']} {c['name']}", "role": c["role"], "overall": r["overall"],
            "eva": r["eva"]["status"],
            "issue": issue.get("title") if issue.get("severity") not in (None, "ok") else None,
            "href": f"/crew/{c['id']}",
        }
        lines.append(f"{_crew_line(r)} [[crew:{c['id']}]]")
    parts.append("CREW STATUS NOW:\n" + "\n".join(lines))

    metric_def = {m["id"]: m for m in METRICS}
    for cid in a["crew"]:
        d = dash_viewer if cid == crew_id else engine.dashboard(cid, env_id)
        c = d["crew"]
        lines = [f"PERSON: {c['title']} {c['name']} ({c['role']}, id {cid})"]
        prof = CREW_PROFILES.get(cid, {})
        if prof:
            lines.append(f"  Profile: age {prof['age']}, {prof['nationality']}, blood {prof['blood_type']}, "
                         f"allergies {', '.join(prof['allergies']) or 'none known'}, medication "
                         f"{', '.join(prof['medications']) or 'none'}.")
            for h in prof["history"]:
                lines.append(f"  History {h['year']}: {h['condition']} ({h['status']}). Affects "
                             f"{', '.join(h['watch'])}. {h['influence']}")
        wanted = set(a["metrics"]) or {k for k, v in d["metrics"].items() if v.get("status") != "ok"}
        for mid, st in d["metrics"].items():
            if not st.get("has_data") or (mid not in wanted and st.get("status") == "ok"):
                continue
            m = metric_def.get(mid, {})
            b1, b2 = st.get("baseline"), st.get("baseline2")
            base = f"; personal baseline {fmt_value(mid, b1, b2)}" if b1 is not None else ""
            token = f"{cid}.{mid}"
            unit = "" if mid in ("vision", "symptoms") else m.get("unit", "")
            ents["reading"][token] = {
                "crew_id": cid, "crew": c["name"].split()[0], "metric": mid, "label": m.get("label", mid),
                "value": st["display"], "unit": unit, "status": st["status"], "age_days": st.get("age_days"),
                "href": f"/trends?m={mid}" if cid == crew_id else f"/crew/{cid}",
            }
            lines.append(f"  Reading {m.get('label', mid)} = {st['display']} {unit} (status {st['status']}, "
                         f"{st.get('age_days', 0)} day(s) old{base}) [[reading:{token}]]")
            if cid == crew_id:
                ents["action"][f"measure:{mid}"] = {"label": f"Measure {m.get('label', mid).lower()}",
                                                    "href": f"/measure/{mid}"}
        for it in (d.get("attention") or {}).get("items", [])[:8]:
            lines.append(f"  Open alert ({it['severity']}): {it['title']}. {it.get('reason', '')}")
        rad = d["radiation"]
        lines.append(f"  Radiation: mission {rad['mission_msv']} mSv, career {rad['career_msv']} mSv of the "
                     f"{rad['limit_msv']} mSv limit ({rad['percent']} %).")
        if a["exercise"] or not a["metrics"]:
            plan = engine.exercise(cid, env_id)
            items = "; ".join(f"{i['id']} {i['minutes']} min ({i['intensity']}) on {i['device']}"
                              for i in plan["today"]["items"])
            lines.append(f"  Exercise today ({plan['today']['title']}, {plan['time']}): {items}.")
            for adj in plan["adjustments"]:
                lines.append(f"  Exercise change: {adj['title']}. {adj['reason']}")
        parts.append("\n".join(lines))

    for mid in a["metrics"]:
        m = metric_def.get(mid)
        if not m:
            continue
        guide = m.get("guide", {})
        parts.append(f"INDICATOR {m['label']} ({m['unit']}): normal range {m.get('ok')}, watch range {m.get('watch')}. "
                     f"Why it matters: {m.get('why', '')} In space: {m.get('space', '')} If watch: "
                     f"{guide.get('watch', '')} If act: {guide.get('act', '')} Escalate: {m.get('escalate', '')}")

    if a["emergency"]:
        rows = []
        for p in PROTOCOLS:
            ents["protocol"][p["id"]] = {"name": p["name"], "steps": [
                {"title": st["title"], "detail": st["detail"]} for st in p["pre"][:6]]}
            rows.append(f"- {p['name']} ({p['summary']}) [[protocol:{p['id']}]]: "
                        + " / ".join(f"{st['title']}: {st['detail']}" for st in p["pre"][:6]))
        parts.append("EMERGENCY PROTOCOLS ON BOARD:\n" + "\n".join(rows))
    if a["game"]:
        g = engine.game_hub(crew_id, env_id)
        quests_txt = "; ".join(
            f"{q['title']} ({q['progress']}/{q['target']}, "
            + ("already claimed this week, earns nothing more" if q["claimed"] else f"+{q['xp']} XP when finished")
            + ")" for q in g["quests"])
        locked = [b for b in g["badges"] if not b["earned"]]
        parts.append(
            f"GAME (Honest Orbit, the user's own): level {g['level']['level']} {g['level']['title']}, "
            f"{g['level']['xp']} XP, {g['level']['xp_per_level'] - g['level']['level_xp']} XP to the next level. "
            f"Streak {g['streak']['current']} days (best {g['streak']['best']}), {g['streak']['shields']} shield(s). "
            f"Momentum last 7 days {g['momentum']['last7']}% vs {g['momentum']['prev7']}% before; "
            f"support mode {'on' if g['momentum']['support'] else 'off'}. Chapter {g['chapter']['name']} "
            f"(day {g['day']} of {g['chapter']['transit_days']}). Quests: {quests_txt}. "
            f"Closest badges: " + "; ".join(f"{b['name']} {b['value']}/{b['target']} ({b['description']})"
                                           for b in sorted(locked, key=lambda b: b['value'] / b['target'],
                                                           reverse=True)[:3]) + ". "
            f"Crew operation this week: {g['crew']['operation']['name']} {g['crew']['operation']['value']}/"
            f"{g['crew']['operation']['target']} {g['crew']['operation']['unit']}. "
            "Rules: XP comes only from actions (checks, extra readings, closing loops, buddy checks, quests, drills); "
            "it never depends on what a reading says, so never suggest changing a value to earn XP.")

    if a["comms"]:
        g = [f"- {x['crew_name']}: {x['title']} ({x['status']}, sent {x['created']})"
             for x in comms.get("ground", [])[:6]]
        parts.append(f"EARTH LINK: one-way {comms.get('delay_label')}, round trip {comms.get('round_trip_label')}, "
                     f"next window {(comms.get('next_window') or {}).get('time')}.\n" + "\n".join(g))
    parts.append("ESCALATION LADDER:\n" + "\n".join(f"- Tier {t['tier']} {t['name']}: {t['when']}" for t in ESCALATION))

    # Navigation the answer may offer as buttons.
    ents["action"].update({
        "emergency": {"label": "Open Emergency protocols", "href": "/emergency", "tone": "danger"},
        "exercise": {"label": "Open today's exercise plan", "href": "/exercise"},
        "crew": {"label": "Open the Crew page", "href": "/crew"},
        "missions": {"label": "Open your progress", "href": "/missions"},
        "measure": {"label": "Go to Measure", "href": "/measure"},
    })
    for c in CREW:
        ents["action"][f"profile:{c['id']}"] = {"label": f"Open {c['name'].split()[0]}'s profile",
                                               "href": f"/crew/{c['id']}"}
    parts.append("ACTION TOKENS AVAILABLE: " + ", ".join(f"[[action:{k}]]" for k in ents["action"]))

    return "\n\n".join(parts)[:CONTEXT_BUDGET], ents


SYSTEM = """You are ASTRA, the crew health specialist on board a crewed spacecraft. You explain the crew's own \
health data, each other's status, exercise plans, radiation, the Earth link and the emergency protocols.

ACCURACY (most important):
1. Use only facts in DATA. Never use outside knowledge for any number, date, status, name or plan. General \
physiology may only explain why something matters, never supply a value.
2. Never estimate, round differently or invent a reading. To show a reading, place its token (for example \
[[reading:kenji.bp]]) instead of typing the number; the app renders the exact value, status and age. A reading \
token always means the latest value: use each one at most once, and never use it for a baseline, target or past \
value (write those in words exactly as DATA gives them). Everywhere else, including bullets, name a reading without \
its number ("your fluid intake", not "your fluid intake of 1.8 L"): only the token may show a current value.
3. If DATA does not contain the answer, say "ASTRA has no data on that" and name the measurement that would \
answer it. Do not guess.
4. Keep statuses exactly as given (ok means nominal, watch, act). Never upgrade or downgrade them.
5. Before answering, check every claim against DATA. If two facts conflict, say so.

SAFETY:
- You are not a doctor and do not diagnose. Explain what a reading means and what the ladder says to do.
- Escalation: Tier 0 self-care; Tier 1 Crew Medical Officer (any act, a watch lasting 3 days, or very unusual for \
the person); Tier 2 flight surgeon (red flags, act lasting 2 days, or any emergency). Say who to tell when it applies.
- Earth replies take minutes: on-board action comes first.
- If the message describes a medical emergency, the first line is [[action:emergency]] and the next line is the \
matching [[protocol:<id>]] token. Nothing before them.

FORMAT (the app turns tokens into live UI):
- Structure: one sentence that answers the question; then the token cards; then at most 3 short bullets that add \
what the cards do not already show (cause, what to do, who to tell). Never restate what a card shows (names, \
statuses, top issues). No headings, tables or code blocks.
- With crew cards, the opening sentence summarises across them in one line (for example "One crew member is Act, \
two are Watch and one is Nominal; Lucas needs attention first.") and never describes each person.
- After crew cards, bullets are only next actions (who should do what, and who to tell), at most 2, and never one \
bullet per person: the cards already show each person's status and top issue.
- Show at most 3 reading tokens: the ones that matter most for the question, worst status first.
- Status words: write Nominal, Watch and Act exactly (never "on watch", "requires action" or "ok").
- For questions about XP, levels, streaks, quests or badges, answer from GAME: say how much XP is still needed and \
the 2-3 quickest actions (with their XP), use no reading or crew tokens, and end with [[action:missions]].
- Tokens: [[reading:<crew>.<metric>]] value chip, [[crew:<id>]] status card, [[action:<id>]] button, \
[[protocol:<id>]] steps card. Use only tokens listed in DATA, spelled exactly as listed.
- Put [[crew:...]] and [[protocol:...]] tokens on a line of their own; reading tokens can sit inside a sentence.
- When useful, end with up to 2 [[action:...]] tokens on one line (for example measure again, open a profile).
- Plain words. Explain any medical term in a few words. Address the user as "you"."""


def notifications(engine: Any, crew_id: str, env_id: str | None) -> dict[str, Any]:
    """The notification log for this person: their own open alerts, everyone's Act alerts, and ground replies.
    Each entry carries the exact mission time it happened (reading time, or ground packet time)."""
    now = engine.now()
    crew_name = {c["id"]: c["name"] for c in CREW}
    out: list[dict[str, Any]] = []
    for it in engine.attention(None, env_id)["items"]:
        if it.get("state") != "open":
            continue
        mine = it.get("crew_id") == crew_id
        if not mine and it["severity"] != "act":
            continue
        at = now - float(it.get("age") or 0)
        out.append({
            "id": it["key"], "kind": "alert", "severity": it["severity"], "crew_id": it.get("crew_id"),
            "crew": crew_name.get(it.get("crew_id"), "Habitat"), "title": it["title"], "detail": it.get("reason", ""),
            "at": at, "at_label": _at_label(at), "ago": _ago(now - at),
            "href": (it.get("action") or {}).get("href") if mine else f"/crew/{it.get('crew_id')}",
        })
    for g in engine.comms(env_id, crew_id).get("ground", []):
        if g.get("status") != "replied" or (g.get("crew_id") != crew_id and g.get("kind") != "emergency"):
            continue
        sent = now - float(g.get("elapsed_s") or 0)
        out.append({
            "id": f"ground:{g['id']}", "kind": "ground", "severity": "info", "crew_id": g.get("crew_id"),
            "crew": g.get("crew_name", ""), "title": f"Ground replied: {g['title']}", "detail": g.get("reply") or "",
            "at": sent, "at_label": _at_label(sent), "ago": _ago(now - sent), "href": "/crew",
        })
    out += _reward_notices(engine, crew_id, now)
    out.sort(key=lambda n: n["at"], reverse=True)
    return {"now_label": _at_label(now), "items": out[:40]}


REWARD_WINDOW_S = 2 * 86400.0  # rewards from the last two mission days


def _reward_notices(engine: Any, crew_id: str, now: float) -> list[dict[str, Any]]:
    """This person's rewards: the XP each action earned (one entry per action, with every line that made it up),
    a level reached, and badges earned. Read from the XP ledger and badge records, so they match the XP log."""
    crew = engine.crew(crew_id)
    since = now - REWARD_WINDOW_S
    events = [e for e in engine.store.xp_events(crew_id, 400) if e["met_s"] >= since]  # newest first
    groups: list[list[dict[str, Any]]] = []
    for e in events:  # one action writes its lines at the same mission time
        if groups and abs(groups[-1][0]["met_s"] - e["met_s"]) < 1.0:
            groups[-1].append(e)
        else:
            groups.append([e])
    running = int(crew["base_xp"] + engine.store.xp_sum(crew_id))  # total after the newest group
    out: list[dict[str, Any]] = []
    for g in groups:
        rows = sorted(g, key=lambda e: e["id"])  # in the order they were awarded
        gained = sum(e["amount"] for e in rows)
        before, running = running - gained, running - gained
        at = rows[0]["met_s"]
        head = f"+{gained} XP · {rows[0]['reason']}"
        detail = " · ".join(f"{e['reason']} +{e['amount']}" for e in rows[1:])
        level_before, level_after = before // XP_PER_LEVEL + 1, (before + gained) // XP_PER_LEVEL + 1
        if level_after > level_before:
            title = f"Level {level_after} reached: {LEVELS[min(level_after - 1, len(LEVELS) - 1)]}"
            detail = head + (f" · {detail}" if detail else "")
        else:
            title = head
        out.append({"id": f"xp:{rows[0]['id']}", "kind": "reward", "severity": "info", "crew_id": crew_id,
                    "crew": crew["name"], "title": title, "detail": detail, "at": at, "at_label": _at_label(at),
                    "ago": _ago(now - at), "href": "/missions"})
    names = {b["id"]: b for b in BADGES}
    for b in engine.store.badge_events(crew_id, since):
        badge = names.get(b["badge_id"])
        if not badge:
            continue
        out.append({"id": f"badge:{b['badge_id']}", "kind": "reward", "severity": "info", "crew_id": crew_id,
                    "crew": crew["name"], "title": f"Badge earned: {badge['name']}", "detail": badge["description"],
                    "at": b["met_s"], "at_label": _at_label(b["met_s"]), "ago": _ago(now - b["met_s"]),
                    "href": "/missions"})
    return out


def _messages(context: str, history: list[dict[str, str]], question: str) -> list[dict[str, str]]:
    msgs = [{"role": "system", "content": f"{SYSTEM}\n\nDATA:\n{context}"}]
    for m in history[-HISTORY_TURNS:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            msgs.append({"role": m["role"], "content": str(m["content"])[:4000]})
    msgs.append({"role": "user", "content": question[:4000]})
    return msgs


def _stream_nim(key: str, model: str, messages: list[dict[str, str]]) -> Iterator[str]:
    body = {"model": model, "messages": messages, "temperature": 0.6, "top_p": 0.9, "max_tokens": 1200,
            "stream": True, "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(NIM_URL, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=90) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
            except (ValueError, KeyError, IndexError):
                continue
            if delta:
                yield delta


def _fallback(engine: Any, env_id: str | None, a: dict[str, Any], why: str) -> str:
    """A rules-only answer from the same data, so the assistant still helps without the model."""
    out = [f"_{why} This answer comes from ASTRA's on-board rules only._", ""]
    if a["emergency"]:
        out += ["**Open Emergency protocols now (red button, top right).**", ""]
    for cid in a["crew"]:
        d = engine.dashboard(cid, env_id)
        c = d["crew"]
        out.append(f"**{c['title']} {c['name']}**: overall {d['overall_label']}, EVA {d['eva']['status']}.")
        for it in (d.get("attention") or {}).get("items", [])[:4]:
            out.append(f"- {it['title']} ({it['severity']})")
    return "\n".join(out)


def chat(engine: Any, crew_id: str, env_id: str | None, question: str,
         history: list[dict[str, str]], page: str | None = None) -> Iterator[str]:
    """NDJSON events: meta (entities, model, emergency), delta (text), done."""
    global _working_model
    a = analyse(question, crew_id, page)
    context, ents = build_context(engine, crew_id, env_id, a)

    def ev(obj: dict[str, Any]) -> str:
        return json.dumps(obj) + "\n"

    key = _api_key()
    if not key:
        yield ev({"type": "meta", "model": None, "entities": ents, "emergency": a["emergency"]})
        yield ev({"type": "delta", "text": _fallback(engine, env_id, a, "No NVIDIA API key is set.")})
        yield ev({"type": "done"})
        return

    messages = _messages(context, history, question)
    candidates = [_working_model] if _working_model else _models()
    for model in candidates:
        try:
            stream = _stream_nim(key, model, messages)
            first = next(stream, None)  # surfaces HTTP errors before anything is sent to the user
        except urllib.error.HTTPError as e:
            if e.code == 404 and model != candidates[-1]:
                continue  # this account cannot call this model: try the next one
            yield ev({"type": "meta", "model": None, "entities": ents, "emergency": a["emergency"]})
            yield ev({"type": "delta", "text": _fallback(engine, env_id, a,
                                                         f"The AI service answered with an error ({e.code}).")})
            yield ev({"type": "done"})
            return
        except (urllib.error.URLError, TimeoutError, OSError):
            yield ev({"type": "meta", "model": None, "entities": ents, "emergency": a["emergency"]})
            yield ev({"type": "delta", "text": _fallback(engine, env_id, a, "The AI service is unreachable.")})
            yield ev({"type": "done"})
            return
        _working_model = model
        yield ev({"type": "meta", "model": model, "entities": ents, "emergency": a["emergency"]})
        if first:
            yield ev({"type": "delta", "text": first})
        try:
            for chunk in stream:
                yield ev({"type": "delta", "text": chunk})
        except (urllib.error.URLError, TimeoutError, OSError):
            yield ev({"type": "delta", "text": "\n\n_(The connection dropped; the answer may be incomplete.)_"})
        yield ev({"type": "done"})
        return
