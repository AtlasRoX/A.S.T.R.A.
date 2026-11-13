"""Tests for the live telemetry simulator."""


def test_live_sim_lifecycle_and_scenarios(client):
    # 1. Initial status
    status = client.get("/sim/live/status").json()
    assert status["active"] is False
    assert len(status["scenarios"]) == 4

    # 2. Start nominal simulation
    started = client.post(
        "/sim/live/start", json={"scenario": "nominal", "interval_s": 30.0, "crew_id": "kenji"}
    ).json()
    assert started["active"] is True
    assert started["scenario"] == "nominal"
    assert started["step"] >= 1

    # Check dashboard updated
    d = client.get("/crew/kenji/dashboard").json()
    assert d["metrics"]["hr"]["value"] is not None

    # 3. Manual tick
    ticked = client.post("/sim/live/tick").json()
    assert ticked["step"] >= 2

    # 4. Switch to exercise scenario
    ex = client.post("/sim/live/start", json={"scenario": "exercise", "interval_s": 30.0, "crew_id": "kenji"}).json()
    assert ex["scenario"] == "exercise"

    # Step through exercise exertion
    client.post("/sim/live/tick")
    client.post("/sim/live/tick")
    d_ex = client.get("/crew/kenji/dashboard").json()
    assert d_ex["metrics"]["hr"]["active_reading"] is not None

    # 5. Switch to cabin CO2 scenario
    co2 = client.post("/sim/live/start", json={"scenario": "cabin_co2", "interval_s": 30.0, "crew_id": "kenji"}).json()
    assert co2["scenario"] == "cabin_co2"
    client.post("/sim/live/tick")
    client.post("/sim/live/tick")
    d_co2 = client.get("/crew/kenji/dashboard").json()
    assert d_co2["cabin"]["available"] is True

    # 6. Switch to solar storm scenario
    storm = client.post(
        "/sim/live/start", json={"scenario": "solar_storm", "interval_s": 30.0, "crew_id": "kenji"}
    ).json()
    assert storm["scenario"] == "solar_storm"
    client.post("/sim/live/tick")
    client.post("/sim/live/tick")
    d_storm = client.get("/crew/kenji/dashboard").json()
    assert d_storm["radiation"]["rate_msv_day"] > 1.0

    # 7. Stop simulation
    stopped = client.post("/sim/live/stop").json()
    assert stopped["active"] is False


# ---------------------------------------------------------------------------------- rules and labels
def _start(client, scenario, crew="kenji"):
    client.post("/admin/reset")
    return client.post("/sim/live/start", json={"scenario": scenario, "interval_s": 3600.0, "crew_id": crew}).json()


def _sim_packets(client, crew="kenji"):
    return [p for p in client.get("/comms", params={"env": "transit", "crew_id": crew}).json()["cmo"]
            + client.get("/comms", params={"env": "transit", "crew_id": crew}).json()["ground"]
            if "From live telemetry" in p["body"]]


def test_scenarios_start_at_their_first_phase(client):
    started = _start(client, "exercise")
    assert "Warmup" in started["last_event"]
    started = _start(client, "solar_storm")
    assert "0.68" in started["last_event"]
    client.post("/sim/live/stop")
    client.post("/admin/reset")


def test_a_simulated_act_reading_reaches_the_cmo_once_and_is_labelled(client):
    _start(client, "exercise")
    for _ in range(4):  # warmup, aerobic, peak, sprint (154 bpm after exercise is Act)
        client.post("/sim/live/tick")
    packets = _sim_packets(client)
    assert packets, "an Act reading from the simulator must raise a packet"
    assert all("SIMULATED" not in p["title"] for p in packets)  # no "simulated" wording in the app
    assert all(p["body"].endswith("From live telemetry.") for p in packets)
    count = len(packets)
    client.post("/sim/live/tick")  # still above the range: no second packet for the same condition
    assert len(_sim_packets(client)) == count
    client.post("/sim/live/stop")
    client.post("/admin/reset")


def test_simulated_readings_award_no_xp_and_complete_no_tasks(client):
    _start(client, "exercise")
    engine = client.app.state.engine
    xp = engine.store.xp_sum("kenji")
    done = client.get("/crew/kenji/dashboard", params={"env": "transit"}).json()["routine"]["done"]
    for _ in range(5):
        client.post("/sim/live/tick")
    assert engine.store.xp_sum("kenji") == xp
    assert client.get("/crew/kenji/dashboard", params={"env": "transit"}).json()["routine"]["done"] == done
    client.post("/sim/live/stop")
    client.post("/admin/reset")


def test_a_simulated_dose_rate_and_cabin_co2_say_they_are_simulated(client):
    _start(client, "solar_storm")
    client.post("/sim/live/tick")
    client.post("/sim/live/tick")
    rad = client.get("/crew/kenji/dashboard", params={"env": "transit"}).json()["radiation"]
    assert rad["rate_source"] == "simulator"
    assert rad["rate_docs"] == [], "a simulated rate must not cite a NASA measurement"
    client.post("/sim/live/stop")

    _start(client, "cabin_co2")
    client.post("/sim/live/tick")
    cabin = client.get("/nasa/cabin", params={"env": "station"}).json()
    assert cabin["source"] == "simulator"
    client.post("/sim/live/stop")
    assert client.get("/nasa/cabin", params={"env": "station"}).json()["source"] == "osdr-eda-iss"
    client.post("/admin/reset")


def test_stopping_clears_the_simulated_storm_but_not_a_real_replay(client):
    _start(client, "solar_storm")
    for _ in range(3):
        client.post("/sim/live/tick")
    assert client.get("/nasa/solar/events").json()["active"] is not None
    client.post("/sim/live/stop")
    assert client.get("/nasa/solar/events").json()["active"] is None

    client.post("/admin/reset")
    client.post("/nasa/replay/solar", json={"event_id": None})
    client.post("/sim/live/start", json={"scenario": "nominal", "interval_s": 3600.0, "crew_id": "kenji"})
    client.post("/sim/live/stop")
    active = client.get("/nasa/solar/events").json()["active"]
    assert active is not None and active["event_id"] == "2021-10-28T16:35:00-SEP-001"
    client.post("/admin/reset")


def test_nominal_telemetry_stays_near_the_crew_members_own_baseline(client):
    client.post("/admin/reset")
    before = client.get("/crew/kenji/dashboard", params={"env": "transit"}).json()["metrics"]["bp"]["value"]
    assert before > 125, "Kenji's seeded story is a rising blood pressure"
    client.post("/sim/live/start", json={"scenario": "nominal", "interval_s": 3600.0, "crew_id": "kenji"})
    for _ in range(4):
        client.post("/sim/live/tick")
    after = client.get("/crew/kenji/dashboard", params={"env": "transit"}).json()["metrics"]["bp"]["value"]
    assert abs(after - before) < 15, "generic 116/76 numbers would overwrite Kenji's story"
    client.post("/sim/live/stop")
    client.post("/admin/reset")


def test_background_telemetry_starts_with_the_engine_for_the_whole_crew(tmp_path, monkeypatch):
    """With ASTRA_LIVE_SIM on (the default outside tests), the engine starts nominal telemetry for every crew
    member on the real mission clock, so no page is needed to start it."""
    from app.main import create_app
    from app.store import day_of

    monkeypatch.setenv("ASTRA_LIVE_SIM", "on")
    monkeypatch.setenv("ASTRA_LIVE_SIM_INTERVAL", "3600")
    app = create_app(str(tmp_path / "background.db"))
    sim = app.state.live_sim
    try:
        st = sim.status()
        assert st["active"] is True
        assert st["scenario"] == "nominal"
        assert st["crew_id"] is None
        assert sim.advance_clock is False
        assert sim.raise_alerts is False  # the background feed shows data; it never pages the CMO
        today = day_of(sim.store.met_now())
        for cid in ("ana", "kenji", "sara", "lucas"):
            assert any(r.get("source") == "sim" for r in sim.store.readings(cid, today - 1)), cid
    finally:
        sim.stop()


def test_nominal_telemetry_ignores_one_odd_manual_reading_and_prunes_old_sim_data(tmp_path):
    """The simulator follows a person's usual level (median of recent real readings), so one odd entry such as
    200 bpm does not become minute-by-minute telemetry; simulated readings older than a day are pruned."""
    from app.live_sim import SIM_KEEP_S, LiveSimulatorRunner
    from app.store import Store

    store = Store(str(tmp_path / "s.db"))
    now = store.met_now()
    for i, v in enumerate([70.0, 72.0, 71.0, 69.0]):
        store.add_reading("lucas", "hr", v, None, None, now - 4000 + i * 600, None, source="manual")
    store.add_reading("lucas", "hr", 200.0, None, None, now - 100, None, source="manual")
    sim = LiveSimulatorRunner(store)
    assert sim._baseline("lucas", "hr", 64.0)[0] == 71.0

    store.add_reading("lucas", "hr", 66.0, None, None, now - SIM_KEEP_S - 10, None, source="sim")
    assert store.prune_sim_readings(now - SIM_KEEP_S) == 1
    assert all(r["value"] != 66.0 for r in store.readings("lucas", 0))
    assert any(r["value"] == 200.0 for r in store.readings("lucas", 0))  # real readings are never pruned
