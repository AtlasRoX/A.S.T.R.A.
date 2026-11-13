"""Tests for the mission simulator: real NASA data in, ASTRA's rules out."""

from __future__ import annotations

import pytest

from app import rules
from app.catalog import CABIN, CONJUNCTION_SOT_DEG
from app.nasa import Registry
from app.sim import Simulator
from app.sources import SOURCES as SOURCE_DOCS

STORY = ["cabin-air", "solar-storm", "conjunction", "inspiration4"]


@pytest.fixture(scope="module")
def sim() -> Simulator:
    return Simulator(Registry())


def test_every_story_scenario_is_ready(sim: Simulator):
    for sid in STORY:
        sc = sim.scenario(sid)
        assert sc is not None and sc["status"] == "ready", sid
        assert sc["frames"] and sc["events"] and sc["charts"], sid


@pytest.mark.parametrize("sid", STORY)
def test_scenario_shape(sim: Simulator, sid: str):
    sc = sim.scenario(sid)
    assert sc is not None
    ts = [f["t"] for f in sc["frames"]]
    assert ts == sorted(ts), "frames must move forward in time"
    for f in sc["frames"]:
        assert f["status"] in ("ok", "watch", "act")
        assert f["label"] and f["gauges"]
    for e in sc["events"]:
        assert 0 <= e["frame"] < len(sc["frames"])
        assert sc["frames"][e["frame"]]["t"] >= e["t"] - 1e-6 or e["frame"] == len(sc["frames"]) - 1
    for sid_doc in sc["sources"]:
        assert sid_doc in SOURCE_DOCS, f"{sid} cites unknown source {sid_doc}"
    assert sc["real"], "every scenario must say which parts are real NASA data"
    for chart in sc["charts"]:
        for series in chart["series"]:
            assert series["points"]


def test_solar_storm_replays_the_real_donki_event(sim: Simulator):
    sc = sim.scenario("solar-storm")
    titles = [e["title"] for e in sc["events"]]
    assert any(t.startswith("X1.0 solar flare") for t in titles), "the real X1.0 flare of 28 Oct 2021"
    act = next(e for e in sc["events"] if e["status"] == "act")
    assert "2021-10-28T16:35:00-SEP-001" in act["detail"]
    assert act["link"].startswith("https://")
    # Earth's reply arrives after the crew is already in the shelter.
    shelter = next(e for e in sc["events"] if e["title"] == "Crew in the shelter")
    reply = next(e for e in sc["events"] if e["title"] == "Earth's reply arrives")
    assert reply["t"] > shelter["t"]
    # The shelter curve ends below the no-shelter curve.
    dose = sc["charts"][0]
    with_astra = next(s for s in dose["series"] if s["id"] == "astra")["points"][-1][1]
    without = next(s for s in dose["series"] if s["id"] == "noshelter")["points"][-1][1]
    assert with_astra < without
    assert sc["illustrative"], "the dose model is illustrative and must say so"


def test_cabin_air_applies_the_nasa_limits_to_the_real_series(sim: Simulator):
    sc = sim.scenario("cabin-air")
    co2 = next(s for s in sc["charts"][0]["series"] if s["id"] == "co2")["points"]
    values = [v for _, v in co2 if v is not None]
    assert max(values) > CABIN["act_1h_mmhg"], "the August 2018 peak is above the 1-hour limit"
    assert any(v is None for _, v in co2), "telemetry gaps stay gaps"
    statuses = {f["status"] for f in sc["frames"]}
    assert {"ok", "act"} <= statuses
    insight = next(e for e in sc["events"] if e["title"].startswith("ASTRA: It's the air"))
    assert insight["status"] in ("watch", "act")
    # Every frame's status is exactly what the cabin rule says for its gauges.
    for f in sc["frames"]:
        g = {x["id"]: x["value"] for x in f["gauges"]}
        assert rules.cabin_status(g["co2"], g["co2_7d"]) == f["status"] or abs(g["co2"] - CABIN["act_1h_mmhg"]) < 0.01


def test_cabin_air_skips_the_sensor_fill_rows(sim: Simulator):
    sc = sim.scenario("cabin-air")
    for f in sc["frames"]:
        ppm = next(x for x in f["gauges"] if x["id"] == "ppm")["value"]
        assert ppm > 200


def test_conjunction_is_the_real_spring_2028_one(sim: Simulator):
    sc = sim.scenario("conjunction")
    act = [f for f in sc["frames"] if f["status"] == "act"]
    assert act, "the Horizons window must reach the 2028 conjunction"
    for f in act:
        sot = next(x for x in f["gauges"] if x["id"] == "sot")["value"]
        assert sot <= CONJUNCTION_SOT_DEG
    assert any(f["status"] == "watch" for f in sc["frames"]), "ASTRA warns ahead of the blackout"
    assert "2028" in next(e for e in sc["events"] if e["title"] == "Radio blackout begins")["detail"]


def test_inspiration4_flags_match_the_lab_rule(sim: Simulator):
    sc = sim.scenario("inspiration4")
    assert len(sc["frames"]) == 7
    flagged = [e for e in sc["events"] if e["title"].startswith("ASTRA flags")]
    assert flagged
    after_landing = [e for e in flagged if e["t"] >= 1]
    assert after_landing, "values move out of range after the flight"


def test_filled_slots_are_not_listed_as_scenarios(sim: Simulator):
    # The official resources are documents (evidence), not a timeline, so a filled slot has nothing to play.
    ids = {s["id"] for s in sim.summaries()}
    for slot in ("slot-a", "slot-b", "slot-c"):
        assert slot not in ids


def test_sim_routes(client):
    body = client.get("/sim/scenarios").json()
    assert [s["id"] for s in body["scenarios"]][:4] == STORY
    sc = client.get("/sim/scenarios/solar-storm").json()["scenario"]
    assert sc["status"] == "ready"
    assert client.get("/sim/scenarios/nope").status_code == 404


def test_playing_a_scenario_does_not_touch_the_live_state(client):
    before = client.get("/clock").json()["met_s"]
    client.get("/sim/scenarios/solar-storm")
    assert client.get("/nasa/solar/events").json()["active"] is None
    assert abs(client.get("/clock").json()["met_s"] - before) < 5
