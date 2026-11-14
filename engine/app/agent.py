"""Crew Watch: ASTRA's on-board agent.

The assistant answers questions; Crew Watch acts without being asked. Each run is one loop:

  1. SENSE   read the crew's latest symptom checks.
  2. CHECK   call tools for what could explain them: each affected crew member's vitals, then the cabin air
             (Ship Sense, real ISS CO2 telemetry at the station).
  3. DECIDE  shared cause (the habitat) or separate patients, using ASTRA's own rules.
  4. ACT     tell the crew what to fix, and write the flight-surgeon handover, stamped with when Earth will
             read it and when a reply can come back.

It runs fully on board: no network, no language model. The planner is ASTRA's rules, so every step is
explainable and the loop keeps working through a radio blackout. Each step is recorded with the tool it called
and what it found, so the crew (and Earth) can see why it decided what it did.
"""

from __future__ import annotations

import json
import time
from typing import Any

from . import rules
from .catalog import CREW, STATUS_LABEL
from .services import fmt_delay

LAST_RUN_KEY = "agent_crew_watch_last"
SENT_KEY = "agent_crew_watch_sent"


def _step(trace: list[dict[str, Any]], phase: str, tool: str, summary: str, status: str = "ok",
          data: Any = None) -> None:
    trace.append({"n": len(trace) + 1, "phase": phase, "tool": tool, "summary": summary, "status": status,
                  "data": data})


def _name(cid: str) -> str:
    return next((c["name"] for c in CREW if c["id"] == cid), cid)


def run(engine: Any, env_id: str | None) -> dict[str, Any]:
    """One Crew Watch loop. Returns the trace, the decision and any handover it sent."""
    t0 = time.perf_counter()
    now = engine.now()
    env = engine.env(env_id)
    trace: list[dict[str, Any]] = []

    # 1. SENSE
    aching = engine._headache_crew_ids(now)
    names = [_name(c) for c in aching]
    _step(trace, "sense", "Symptom log · 24 h",
          f"{len(aching)} crew reported a headache: {', '.join(names)}" if aching else "No shared symptom in the last 24 h",
          "watch" if len(aching) >= 2 else "ok", {"crew": aching})

    if len(aching) < 2:
        _step(trace, "decide", "ASTRA rules", "Fewer than two crew with the same symptom: nothing to link",
              "ok")
        return _finish(engine, env, now, trace, None, None, t0)

    # 2. CHECK: each person's own vitals first
    personal = []
    for cid in aching:
        d = engine.dashboard(cid, env["id"])
        flags = [k for k, s in d["metrics"].items() if s["has_data"] and s["status"] != "ok" and k != "symptoms"]
        personal.append({"crew": cid, "overall": d["overall"], "flags": flags})
        _step(trace, "check", f"{_name(cid).split()[0]}'s vitals",
              f"{_name(cid)}: {STATUS_LABEL[d['overall']]}"
              + (f", flagged {', '.join(flags)}" if flags else ", vitals otherwise in range"),
              d["overall"], {"flags": flags})

    # 2. CHECK: the habitat
    cabin = engine.cabin(env["id"])
    if cabin.get("available"):
        src = "real ISS telemetry (NASA OSDR)" if cabin.get("source") == "osdr-eda-iss" else "habitat model"
        _step(trace, "check", "Cabin air",
              f"Cabin CO₂ {cabin['co2_1h_mmhg']:.2f} mmHg (1 h, limit {cabin['act_1h_mmhg']}) · "
              f"{cabin['co2_7d_mmhg']:.2f} mmHg (7 d, limit {cabin['watch_7d_mmhg']}) · {src}",
              cabin["status"], {k: cabin.get(k) for k in ("co2_1h_mmhg", "co2_7d_mmhg", "status", "source")})
    else:
        _step(trace, "check", "Cabin air", "No cabin data here", "ok")

    # 3. DECIDE
    insight = rules.cabin_insight(cabin, names) if cabin.get("available") else None
    if insight:
        decision = {"cause": "habitat", "severity": insight["severity"], "title": insight["title"],
                    "body": insight["body"], "actions": insight["actions"], "sources": insight["sources"]}
        _step(trace, "decide", "ASTRA rules",
              f"Shared cause: cabin CO₂. Same symptom in {len(aching)} crew + air above limit → fix the air, "
              "not the crew", insight["severity"])
    else:
        decision = {"cause": "individual", "severity": "watch", "title": "Separate patients",
                    "body": "No shared cause found in the cabin air, so each headache is followed up on its own.",
                    "actions": ["Each affected crew member repeats the symptom check in 4 hours"], "sources": []}
        why = "Air in range" if cabin.get("available") else "No cabin reading here"
        _step(trace, "decide", "ASTRA rules", f"{why}: treat each crew member on their own", "watch")

    # 4. ACT: crew-facing action
    _step(trace, "act", "Crew", "Crew told: " + "; ".join(decision["actions"][:2]), decision["severity"])

    # 4. ACT: the handover to Earth, once per decision (a repeat run does not resend the same report)
    handover = _handover(engine, env, aching, personal, cabin, decision, trace)
    return _finish(engine, env, now, trace, decision, handover, t0)


def _handover(engine: Any, env: dict[str, Any], aching: list[str], personal: list[dict[str, Any]],
              cabin: dict[str, Any], decision: dict[str, Any], trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    sig = f"{decision['cause']}:{decision['severity']}:{','.join(sorted(aching))}"
    if engine.store.meta_get(SENT_KEY) == sig:
        _step(trace, "act", "Flight surgeons", "Report already sent for this finding: not sent twice", "ok")
        return None
    lines = [f"ASTRA Crew Watch · {decision['title']}",
             f"Symptom: headache in {len(aching)} crew ({', '.join(_name(c) for c in aching)}).",
             *(f"- {_name(p['crew'])}: {STATUS_LABEL[p['overall']]}"
               + (f", flagged {', '.join(p['flags'])}" if p['flags'] else "") for p in personal)]
    if cabin.get("available"):
        lines.append(f"Cabin CO2: {cabin['co2_1h_mmhg']:.2f} mmHg 1 h / {cabin['co2_7d_mmhg']:.2f} mmHg 7 d.")
    lines.append("Done on board: " + "; ".join(decision["actions"]) + ".")
    lines.append("Request: confirm the plan. The crew is not waiting for this reply.")
    cmo = next((c["id"] for c in CREW if c.get("is_cmo")), aching[0])
    reply = ("Flight surgeon: Agree it is the cabin air. Continue the scrubber and airflow actions and repeat "
             "symptom checks after CO2 is back in range.")
    pkt = engine._send(cmo, "alert", 2 if decision["severity"] == "act" else 1, decision["title"],
                       "\n".join(lines), reply, env["id"])
    engine.store.meta_set(SENT_KEY, sig)
    one_way, round_trip = fmt_delay(env["delay_s"]), fmt_delay(2 * env["delay_s"])
    live = env["delay_s"] < 5
    _step(trace, "act", "Flight surgeons",
          "Report sent to flight surgeons · live link, they see it now" if live else
          f"Report sent to flight surgeons · Earth reads it in {one_way}, a reply in about {round_trip}",
          decision["severity"], {"packet_id": pkt.get("id")})
    return {"packet": pkt, "live": live, "one_way_label": one_way, "round_trip_label": round_trip, "text": "\n".join(lines)}


def _finish(engine: Any, env: dict[str, Any], now: float, trace: list[dict[str, Any]],
            decision: dict[str, Any] | None, handover: dict[str, Any] | None, t0: float) -> dict[str, Any]:
    out = {"agent": "crew_watch", "env_id": env["id"], "met_s": now, "on_board": True, "network_used": False,
           "delay_label": fmt_delay(env["delay_s"]), "steps": trace, "decision": decision, "handover": handover,
           "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
    engine.store.meta_set(LAST_RUN_KEY, json.dumps(out, default=str))
    return out


def last(engine: Any) -> dict[str, Any] | None:
    raw = engine.store.meta_get(LAST_RUN_KEY)
    try:
        return json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return None
