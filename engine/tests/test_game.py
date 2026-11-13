"""Honest Orbit: the game's guarantees. XP never depends on what a reading says, cannot be farmed, and rewards
follow-up and helping crewmates; streaks forgive one bad day; the momentum guard turns on when completion drops."""

from app import gamification as honest
from app.catalog import ADHOC_XP, BADGES, BUDDY_XP, LOOP_XP


def _post(client, crew, metric, value, value2=None):
    body = {"metric": metric, "value": value}
    if value2 is not None:
        body["value2"] = value2
    return client.post(f"/crew/{crew}/readings", json=body).json()


def test_xp_never_depends_on_the_value(client):
    _post(client, "ana", "mass", 64.0)  # claims any quest already finished in the seeded history
    normal = _post(client, "ana", "glucose", 88)
    abnormal = _post(client, "ana", "temp", 39.4)  # a fever earns exactly what a normal reading does
    assert normal["evaluation"]["status"] == "ok" and abnormal["evaluation"]["status"] != "ok"
    assert normal["xp_gained"] == abnormal["xp_gained"] == ADHOC_XP


def test_extra_readings_cannot_be_farmed(client):
    _post(client, "sara", "mass", 61.0)
    first = _post(client, "sara", "glucose", 90)
    again = _post(client, "sara", "glucose", 91)
    assert first["xp_gained"] == ADHOC_XP and again["xp_gained"] == 0


def test_following_up_a_watch_result_closes_the_loop(client):
    # Lucas's latest temperature is a Watch result from the last 2 days.
    r = _post(client, "lucas", "temp", 37.2)
    assert r["loop_closed"] is True and r["xp_gained"] >= LOOP_XP
    # The loop is closed now: another reading is a plain extra reading.
    assert _post(client, "lucas", "temp", 37.1)["loop_closed"] is False


def test_buddy_check_pays_once_per_crewmate_alert(client):
    key = next(i["key"] for i in client.get("/attention").json()["items"] if i["crew_id"] == "lucas")
    first = client.post(f"/attention/{key}/ack", json={"crew_id": "ana"}).json()
    again = client.post(f"/attention/{key}/ack", json={"crew_id": "ana"}).json()
    assert first["xp_gained"] == BUDDY_XP and again["xp_gained"] == 0
    own = next(i["key"] for i in client.get("/attention").json()["items"] if i["crew_id"] == "kenji")
    assert client.post(f"/attention/{own}/ack", json={"crew_id": "kenji"}).json()["xp_gained"] == 0


def test_shields_absorb_a_missed_day():
    done, missed = (8, 8), (2, 8)
    comp = {d: done for d in range(1, 8)} | {8: missed} | {9: done, 10: (0, 8)}
    s = honest.streak_state(comp, 10)
    assert s["status"][8] == "shielded" and s["current"] == 8  # 7 days, a shielded miss, then day 9
    comp_no_shield = {1: done, 2: missed, 3: done, 4: (0, 8)}
    s2 = honest.streak_state(comp_no_shield, 4)
    assert s2["status"][2] == "missed" and s2["current"] == 1


def test_momentum_guard_turns_on_when_completion_drops():
    good = {d: (8, 8) for d in range(1, 8)}
    poor = {d: (4, 8) for d in range(8, 15)}
    m = honest.momentum(good | poor, 15)
    assert m["support"] is True and m["trend"] == "down"
    assert honest.momentum({d: (8, 8) for d in range(1, 15)}, 15)["support"] is False


def test_missions_hub_is_complete_and_traceable(client):
    h = client.get("/crew/ana/game").json()
    assert len(h["streak"]["calendar"]) == 28
    assert h["chapter"]["name"] and 0 <= h["chapter"]["index"] < h["chapter"]["count"]
    assert len(h["badges"]) == len(BADGES) and all(0 <= b["value"] <= b["target"] for b in h["badges"])
    assert h["quests"] and all(q["xp"] > 0 for q in h["quests"])
    # The level's XP is exactly the starting XP plus the ledger.
    ledger_total = sum(e["amount"] for e in h["ledger"])
    assert h["level"]["xp"] == h["seed_xp"] + ledger_total
    assert {p["unlocked"] for p in h["crew"]["perks"]} <= {True, False}


def test_support_mode_eases_the_day_goal_to_the_core_checks():
    good = {d: (8, 8) for d in range(1, 8)}
    poor = {d: (3, 8) for d in range(8, 15)}
    comp = good | poor | {15: (2, 8), 16: (0, 8)}
    core = {15: True}  # day 15: only Morning vitals and Mood & symptoms done, while momentum was down
    s = honest.streak_state(comp, 16, core)
    assert s["status"][15] == "eased"
    # Without the core checks, the same day does not count.
    assert honest.streak_state(comp, 16)["status"][15] in ("missed", "shielded")


def test_crew_operations_count_double_only_in_the_third_quarter():
    assert honest.operation_boost(100) == 2  # day 100 of 180: the third quarter
    assert honest.operation_boost(143) == 1 and honest.operation_boost(20) == 1


def test_only_the_commander_approves_unlocked_rewards(client, monkeypatch):
    week = client.get("/crew/ana/game").json()["crew"]["week"]
    assert client.post("/crew/kenji/perks/approve", json={"week": week, "days": 3}).status_code == 403
    assert client.post("/crew/ana/perks/approve", json={"week": week, "days": 7}).status_code == 409  # still locked
    real = honest.crew_week

    def unlocked(engine, env_id, now):
        cw = real(engine, env_id, now)
        cw["perks"] = [{**p, "unlocked": True} for p in cw["perks"]]
        return cw

    monkeypatch.setattr(honest, "crew_week", unlocked)
    ok = client.post("/crew/ana/perks/approve", json={"week": week, "days": 3}).json()
    assert ok["approved_by"] == "ana"
    perk = next(p for p in client.get("/crew/sara/game").json()["crew"]["perks"] if p["days"] == 3)
    assert perk["approved_by"] == "ana"


def test_buddy_checks_are_capped_per_day(client):
    from app.catalog import BUDDY_DAILY_CAP

    keys = [i["key"] for i in client.get("/attention").json()["items"] if i["crew_id"] in ("lucas", "kenji")]
    assert len(keys) > BUDDY_DAILY_CAP
    paid = [client.post(f"/attention/{k}/ack", json={"crew_id": "ana"}).json()["xp_gained"] for k in keys]
    assert sum(1 for x in paid if x) == BUDDY_DAILY_CAP  # acknowledging a whole queue pays only the daily cap


# ---------------------------------------------------------------------------------- dynamic XP and reward alerts
_VALUES = {
    "hr": (64, None), "bp": (116, 76), "spo2": (98, None), "resp": (14, None), "temp": (36.8, None),
    "glucose": (88, None), "hydration": (2.2, None), "mass": (70.0, None), "nutrition": (100, None),
    "sleep": (7.5, None), "mood": (4, None), "reaction": (260, None), "exercise": (120, None),
    "vision": (0, None), "symptoms": (0, None),
}


def _reading(metric, task_id):
    v, v2 = _VALUES[metric]
    body = {"metric": metric, "value": v, "task_id": task_id, "env": "transit"}
    if v2 is not None:
        body["value2"] = v2
    if metric == "symptoms":
        body["meta"] = {"items": []}
    return body


def _finish_every_check(client, crew):
    results = []
    for t in client.get(f"/crew/{crew}/routine?env=transit").json()["tasks"]:
        if t["state"] == "done":
            continue
        for m in t["metrics"]:
            if m not in t.get("logged", []):
                results.append(client.post(f"/crew/{crew}/readings", json=_reading(m, t["id"])).json())
    return results


def test_finished_checks_earn_dynamic_xp_with_a_traceable_breakdown(client):
    xp0 = client.get("/crew/sara/game?env=transit").json()["level"]["xp"]
    results = _finish_every_check(client, "sara")
    finished = [r for r in results if r["task"] and r["task"]["completed"]]
    assert finished, "at least one scheduled check was finished"
    for r in results:
        # The breakdown is exactly what was paid, line by line.
        assert r["xp_gained"] == sum(line["amount"] for line in r["xp_breakdown"])
    for r in finished:
        reasons = [line["reason"] for line in r["xp_breakdown"]]
        assert reasons[0] == f"Completed {r['task']['title']}"
    # Finishing the whole day pays the Full orbit bonus exactly once.
    orbit = [line for r in results for line in r["xp_breakdown"] if line["reason"].startswith("Full orbit")]
    assert len(orbit) == 1 and orbit[0]["amount"] == 40
    xp1 = client.get("/crew/sara/game?env=transit").json()["level"]["xp"]
    assert xp1 == xp0 + sum(r["xp_gained"] for r in results)


def test_rewards_show_in_the_alerts_log(client):
    r = client.post("/crew/lucas/readings", json=_reading("mood", None)).json()
    assert r["xp_gained"] > 0
    items = client.get("/assistant/notifications?crew_id=lucas&env=transit").json()["items"]
    rewards = [n for n in items if n["kind"] == "reward"]
    assert rewards and rewards[0]["title"].startswith(f"+{r['xp_gained']} XP")
    assert rewards[0]["href"] == "/missions"


def test_task_bonuses_never_look_at_values(client):
    """Same check, same moment, opposite values: the bonuses are identical."""
    from app.gamification import task_bonuses
    from app.store import day_of

    engine = client.app.state.engine
    task = {"id": "evening", "time": "18:00", "title": "Evening check", "metrics": ["temp", "resp"], "xp": 20}
    now = engine.now()
    today = day_of(now)
    readings = engine._readings("kenji", now)
    high = [dict(r, value=r["value"] * 3) for r in readings]
    assert task_bonuses(engine, "kenji", task, readings, today, now, "transit") == \
        task_bonuses(engine, "kenji", task, high, today, now, "transit")


def test_missions_today_previews_what_the_next_check_pays(client):
    t = client.get("/crew/sara/game?env=transit").json()["today"]
    assert t["total"] > 0 and t["next"] is not None
    nxt = t["next"]
    assert nxt["worth"] == sum(line["amount"] for line in nxt["lines"])
    assert nxt["href"].startswith("/measure/") and f"task={nxt['id']}" in nxt["href"]
    _finish_every_check(client, "sara")
    done = client.get("/crew/sara/game?env=transit").json()["today"]
    assert done["done"] == done["total"] and done["next"] is None and done["orbit_done"] is True
    assert done["xp"] > t["xp"]


def test_today_shows_what_each_check_still_pays(client):
    d = client.get("/crew/sara/dashboard?env=transit").json()
    pending = [t for t in d["routine"]["tasks"] if t["state"] != "done"]
    assert pending and all(t["xp_now"] >= t["xp"] for t in pending)
    assert "xp_today" in d["game"] and "streak_before_today" in d["game"]


def test_ship_sense_links_shared_headaches_to_the_cabin_air(client):
    """Two crew members log a headache while the real ISS cabin CO2 is above its 7-day limit: Ship Sense says
    it is the air, not them. With one headache it only watches."""
    sense = client.get("/crew?env=station").json()["ship_sense"]
    assert sense["available"] is True and sense["cabin"]["source"] == "osdr-eda-iss"
    for crew in ("ana", "kenji"):
        client.post(f"/crew/{crew}/readings",
                    json={"metric": "symptoms", "value": 1, "meta": {"items": ["headache"]}, "env": "station"})
    sense = client.get("/crew?env=station").json()["ship_sense"]
    assert {"ana", "kenji"} <= set(sense["symptom_crew"])
    if sense["cabin"]["status"] != "ok":
        assert sense["insight"] and sense["insight"]["title"] == "It's the air, not you"
    # Away from the station there is no cabin telemetry, so Ship Sense stays quiet.
    assert client.get("/crew?env=transit").json()["ship_sense"]["available"] is False
