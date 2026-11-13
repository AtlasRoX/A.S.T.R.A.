def test_health_and_catalog(client):
    assert client.get("/health").json()["ok"] is True
    cat = client.get("/catalog").json()
    assert {m["id"] for m in cat["metrics"]} >= {"hr", "bp", "glucose", "temp", "sleep", "mood"}
    assert len(cat["hazards"]) == 5
    assert len(cat["faq"]) == 5


def test_seeded_storylines(client):
    ana = client.get("/crew/ana/dashboard", params={"env": "transit"}).json()
    assert ana["clock"]["day"] == 142
    assert ana["metrics"]["sleep"]["status"] == "watch"
    assert ana["insights"][0]["id"] == "sleep_debt"
    kenji = client.get("/crew/kenji/dashboard").json()
    assert kenji["metrics"]["bp"]["status"] == "watch"
    assert kenji["metrics"]["vision"]["status"] == "watch"
    sara = client.get("/crew/sara/dashboard").json()
    assert sara["overall"] == "ok"
    lucas = client.get("/crew/lucas/dashboard").json()
    assert any(i["id"] == "infection" for i in lucas["insights"])
    assert lucas["metrics"]["mass"]["status"] == "watch"


def test_evaluate_does_not_save(client):
    before = client.get("/crew/sara/series/hr").json()["log"][0]
    ev = client.post("/crew/sara/evaluate", json={"metric": "hr", "value": 130}).json()
    assert ev["status"] == "act" and ev["tier"] >= 1
    after = client.get("/crew/sara/series/hr").json()["log"][0]
    assert before == after


def test_save_reading_completes_bundle_and_awards_xp(client):
    client.post("/clock/advance", json={"seconds": 9 * 3600})  # to ~18:12, evening check is due
    xp0 = client.get("/crew/sara/dashboard").json()["game"]["xp"]
    r1 = client.post("/crew/sara/readings", json={"metric": "temp", "value": 36.8, "task_id": "evening"}).json()
    assert r1["task"]["completed"] is False and r1["task"]["remaining"] == ["resp"]
    r2 = client.post("/crew/sara/readings", json={"metric": "resp", "value": 14, "task_id": "evening"}).json()
    assert r2["task"]["completed"] is True and r2["xp_gained"] >= 20
    xp1 = client.get("/crew/sara/dashboard").json()["game"]["xp"]
    # Every award is reported in the response that caused it (task, loop, quest), so the ledger adds up exactly.
    assert xp1 == xp0 + r1["xp_gained"] + r2["xp_gained"]


def test_red_flag_sends_priority_packet_with_delay(client):
    res = client.post("/crew/ana/readings", json={"metric": "spo2", "value": 88, "env": "transit"}).json()
    assert res["evaluation"]["tier"] == 2
    assert res["packet"]["status"] == "in_transit"
    client.post("/clock/advance", json={"seconds": 2 * 760 + 100})
    ground = client.get("/comms", params={"env": "transit"}).json()["ground"]
    pkt = next(p for p in ground if p["id"] == res["packet"]["id"])
    assert pkt["status"] == "replied" and pkt["reply"]


def test_validation_errors(client):
    assert client.post("/crew/ana/readings", json={"metric": "hr", "value": 999}).status_code == 422
    assert client.post("/crew/ana/readings", json={"metric": "bp", "value": 120}).status_code == 422
    assert client.get("/crew/nobody/dashboard").status_code == 404


def test_emergency_drill_unlocks_badge(client):
    start = client.post("/emergencies", json={"crew_id": "ana", "patient_id": "lucas", "protocol_id": "cardiac",
                                              "env": "station"}).json()
    assert start["packet"]["kind"] == "emergency"
    done = client.post(
        f"/emergencies/{start['emergency_id']}/finish",
        json={"crew_id": "ana", "track": "A", "completed": True, "duration_s": 95, "steps": [], "is_drill": True},
    ).json()
    assert done["badges_unlocked"][0]["id"] == "drill_ready"
    assert done["xp_gained"] == 50
    assert done["packet"]["kind"] == "emergency"
    assert "DRILL · " in done["packet"]["title"]


def test_real_emergency_no_gamification_and_sends_packet(client):
    start = client.post("/emergencies", json={"crew_id": "ana", "patient_id": "lucas", "protocol_id": "cardiac",
                                              "env": "station"}).json()
    assert start["packet"]["kind"] == "emergency"
    done = client.post(
        f"/emergencies/{start['emergency_id']}/finish",
        json={"crew_id": "ana", "track": "A", "completed": True, "duration_s": 95, "steps": [], "is_drill": False},
    ).json()
    assert done["badges_unlocked"] == []
    assert done["xp_gained"] == 0
    assert done["packet"]["kind"] == "emergency"
    assert "EMERGENCY · Chest pain / collapse (completed)" in done["packet"]["title"]


def test_crew_overview_and_reset(client):
    rows = client.get("/crew").json()["crew"]
    assert len(rows) == 4
    client.post("/clock/advance", json={"seconds": 3600})
    assert client.post("/admin/reset").json()["clock"]["time"] == "09:12"


def test_parallel_requests_share_the_database_safely(client):
    from concurrent.futures import ThreadPoolExecutor

    paths = ["/clock", "/crew/ana/dashboard", "/crew/kenji/routine", "/crew", "/comms", "/crew/sara/series/hr"] * 6
    with ThreadPoolExecutor(max_workers=12) as pool:
        codes = list(pool.map(lambda p: client.get(p).status_code, paths))
    assert set(codes) == {200}


def test_symptoms_raise_their_own_system(client):
    client.post("/crew/sara/readings", json={"metric": "symptoms", "value": 1, "meta": {"items": ["chest_pain"]}})
    organs = {o["id"]: o for o in client.get("/crew/sara/dashboard").json()["organs"]}
    assert organs["heart"]["status"] == "act" and organs["heart"]["symptoms"] == ["chest_pain"]
    assert organs["immune"]["status"] == "ok"


def test_hazard_links_are_consistent(client):
    cat = client.get("/catalog").json()
    metric_hazards = {m["id"]: set(m["hazards"]) for m in cat["metrics"]}
    for h in cat["hazards"]:
        assert set(h["metrics"]) == {k for k, hz in metric_hazards.items() if h["id"] in hz}
    for o in cat["organs"]:
        for k in o["metrics"]:
            assert metric_hazards[k] <= set(o["hazards"])
    names = {o["id"]: o["name"] for o in cat["organs"]}
    assert all(m["category"] == names.get(m["organ"], "General") for m in cat["metrics"])


def test_freshness_is_reported(client):
    d = client.get("/crew/sara/dashboard").json()
    assert all("stale" in s for s in d["metrics"].values())
    assert all("stale" in o for o in d["organs"])
    for _ in range(2):  # the endpoint advances at most 7 days per call
        client.post("/clock/advance", json={"seconds": 6 * 86400})
    later = client.get("/crew/sara/dashboard").json()
    assert later["metrics"]["hr"]["stale"] is True


def test_protocols_and_optional_cue(client):
    cat = client.get("/catalog").json()
    protocols = cat["protocols"]
    assert len(protocols) == 4
    for proto in protocols:
        assert {"id", "name", "icon", "summary", "pre", "tracks", "post"} <= set(proto.keys())
        all_steps = list(proto["pre"]) + list(proto["post"])
        for tr in proto["tracks"]:
            all_steps.extend(tr["steps"])
        for st in all_steps:
            assert {"id", "title", "detail"} <= set(st.keys())
            if "cue" in st and st["cue"] is not None:
                assert "rate_per_min" in st["cue"] and st["cue"]["rate_per_min"] > 0
                assert "source" in st["cue"] and isinstance(st["cue"]["source"], str)

    cardiac = next(p for p in protocols if p["id"] == "cardiac")
    track_a = next(t for t in cardiac["tracks"] if t["id"] == "A")
    step_a1 = next(s for s in track_a["steps"] if s["id"] == "a1")
    assert "cue" in step_a1
    assert step_a1["cue"] is None


def test_attention_queue_comprehensive(client):
    # 1. Dashboard counts match /crew/{id}/attention
    dash = client.get("/crew/ana/dashboard?env=station").json()
    assert "attention" in dash
    q = client.get("/crew/ana/attention?env=station").json()
    assert dash["attention"]["counts"] == q["counts"]

    # 2. Counts invariant: total active items = open + acknowledged == act + watch
    counts = q["counts"]
    assert counts["open"] + counts["acknowledged"] == counts["act"] + counts["watch"]
    assert len(q["items"]) == counts["act"] + counts["watch"]

    # 3. Derivation for metric reading & stable keys
    mood_item = next((i for i in q["items"] if "metric:ana:mood" in i["key"]), None)
    assert mood_item is not None
    assert mood_item["severity"] in ("watch", "act")
    assert mood_item["crew_id"] == "ana"
    assert "Mood" in mood_item["title"]
    assert mood_item["state"] == "open"
    key = mood_item["key"]

    # Verify stable key on repeated query
    q2 = client.get("/crew/ana/attention?env=station").json()
    mood_item2 = next((i for i in q2["items"] if i["key"] == key), None)
    assert mood_item2 is not None

    # 4. Derivation of cross-metric insight
    sleep_debt = next((i for i in q["items"] if i["key"] == "insight:ana:sleep_debt"), None)
    if sleep_debt:
        assert sleep_debt["severity"] in ("watch", "act")
        assert sleep_debt["action"]["label"] == "View trend"

    # 5. Derivation of packet (trigger CMO alert or ground packet)
    client.post("/crew/ana/evaluate", json={"metric": "temp", "value": 39.5, "env": "station"})
    # Or trigger a CMO message
    client.post("/comms/messages", json={"crew_id": "ana", "text": "Report to ground", "env": "station"})
    all_q = client.get("/attention?env=station").json()
    assert any(i["key"].startswith("metric:") or i["key"].startswith("insight:") for i in all_q["items"])

    # 6. Acknowledge persists
    ack_res = client.post(f"/attention/{key}/ack", json={"crew_id": "ana"})
    assert ack_res.status_code == 200
    assert ack_res.json()["state"] == "acknowledged"

    q_after_ack = client.get("/crew/ana/attention?env=station").json()
    acked_item = next(i for i in q_after_ack["items"] if i["key"] == key)
    assert acked_item["state"] == "acknowledged"
    assert acked_item["acknowledged_by"] == "ana"
    assert q_after_ack["counts"]["acknowledged"] >= 1

    # 7. Resolve requires CMO and a note
    # Ana is not CMO -> 403
    res_403 = client.post(f"/attention/{key}/resolve", json={"crew_id": "ana", "note": "Fine now"})
    assert res_403.status_code == 403

    # Kenji is CMO, but missing note -> 422
    res_422 = client.post(f"/attention/{key}/resolve", json={"crew_id": "kenji", "note": "   "})
    assert res_422.status_code == 422

    # Kenji is CMO with note -> 200
    res_ok = client.post(f"/attention/{key}/resolve", json={"crew_id": "kenji", "note": "Reviewed with Ana. Resting."})
    assert res_ok.status_code == 200
    assert res_ok.json()["state"] == "resolved"

    # Item is now removed from active queue
    q_after_resolve = client.get("/crew/ana/attention?env=station").json()
    assert not any(i["key"] == key for i in q_after_resolve["items"])
    assert any(h["key"] == key for h in q_after_resolve["history"])

    # 8. Auto-resolve when reading returns to Nominal
    # Lucas has early infection (temp/resp) or Kenji has high BP
    kenji_q = client.get("/crew/kenji/attention?env=station").json()
    bp_item = next((i for i in kenji_q["items"] if "metric:kenji:bp" in i["key"]), None)
    assert bp_item is not None
    bp_key = bp_item["key"]

    # Now Kenji logs a Nominal BP reading (116/76)
    client.post("/crew/kenji/readings", json={"metric": "bp", "value": 116.0, "value2": 76.0, "env": "station"})
    kenji_q2 = client.get("/crew/kenji/attention?env=station").json()
    # bp_item disappears from active items and is auto-resolved
    assert not any(i["key"] == bp_key for i in kenji_q2["items"])
    auto_resolved = next((h for h in kenji_q2["history"] if h["key"] == bp_key), None)
    assert auto_resolved is not None
    assert auto_resolved["resolved_by"] == "auto"

    # 9. Stale Watch/Act stays listed as stale
    # Fast forward clock 5 days and check stale items stay listed
    client.post("/clock/advance", json={"seconds": 5 * 86400})
    advanced_q = client.get("/crew/ana/attention?env=station").json()
    stale_items = [i for i in advanced_q["items"] if i.get("stale")]
    assert len(stale_items) > 0
    for st_item in stale_items:
        assert st_item["action"]["label"] == "Re-measure"

    # 10. Admin reset clears acks
    client.post("/admin/reset")
    reset_q = client.get("/crew/ana/attention?env=station").json()
    # Acks are cleared
    assert reset_q["counts"]["acknowledged"] == 0
    assert len(reset_q["history"]) == 0




def test_crew_profile(client):
    metrics = {m["id"] for m in client.get("/catalog").json()["metrics"]}
    for crew_id in ("ana", "kenji", "sara", "lucas"):
        p = client.get(f"/crew/{crew_id}/profile").json()
        assert p["crew"]["id"] == crew_id
        assert p["history"], crew_id
        for h in p["history"]:
            # Every watched indicator must exist, or the profile cannot link it to today's readings.
            assert set(h["watch"]) <= metrics, (crew_id, h["condition"])
            assert h["status"] in {"resolved", "managed", "monitoring"}
    assert client.get("/crew/nobody/profile").status_code == 404


def test_exercise_plan(client):
    for env in ("station", "transit", "mars"):
        for crew_id in ("ana", "kenji", "sara", "lucas"):
            p = client.get(f"/crew/{crew_id}/exercise", params={"env": env}).json()
            assert len(p["week"]) == 7 and sum(w["today"] for w in p["week"]) == 1
            assert p["today"]["items"], (env, crew_id)
            for it in p["today"]["items"]:
                # Every exercise must exist and use hardware that this location has.
                assert it["id"] in p["exercises"] and it["device"] in p["devices"], (env, crew_id, it)
            for ex in p["exercises"].values():
                v = ex["video"]
                # Every exercise has real footage: a real time range, a playable source and a full citation.
                assert v, (env, crew_id, ex["id"])
                assert 0 <= v["start"] < v["end"], (ex["id"], v)
                assert v["youtube"] or v["mp4"], (ex["id"], v)
                for k in ("title", "channel", "published", "url", "license", "license_url", "shows", "who"):
                    assert v[k], (ex["id"], k)
            if env == "transit":
                assert all(it["device"] in {"flywheel", "cycle"} for it in p["today"]["items"])
    assert client.get("/crew/nobody/exercise").status_code == 404


def test_every_exercise_has_footage():
    from app.exercise import LOCATION_DEVICES, VIDEOS

    for env, devices in LOCATION_DEVICES.items():
        for exercise, device in devices.items():
            v = VIDEOS.get(device, {}).get(exercise)
            assert v, (env, exercise, device)
            assert v["start"] < v["end"] and (v["youtube"] or v["mp4"]), (env, exercise)


def test_engine_token_guards_every_route_but_health(tmp_path, monkeypatch):
    # A deployed engine is reachable only by the web server, which sends ASTRA_ENGINE_TOKEN as x-astra-token.
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setenv("ASTRA_ENGINE_TOKEN", "s3cret")
    monkeypatch.setenv("ASTRA_LIVE_SIM", "off")
    c = TestClient(create_app(str(tmp_path / "t.db")))
    assert c.get("/health").status_code == 200
    assert c.get("/crew").status_code == 401
    assert c.post("/admin/reset").status_code == 401
    assert c.get("/crew", headers={"x-astra-token": "wrong"}).status_code == 401
    assert c.get("/crew", headers={"x-astra-token": "s3cret"}).status_code == 200
