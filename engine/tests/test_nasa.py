"""Tests for the NASA data port, the citations, and the real-data features built on them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import rules
from app.catalog import CABIN, ENVIRONMENTS, HAZARDS, METRICS, ORGANS
from app.nasa import Registry, RegistryError
from app.sources import SOURCES as SOURCE_DOCS


# ---------------------------------------------------------------------------------- registry
def test_registry_reads_the_committed_manifest():
    reg = Registry()
    ids = {s["id"] for s in reg.sources()}
    assert {"horizons-mars-lt", "osdr-eda-iss", "osdr-i4-labs"} <= ids
    assert "slot-a" in ids and "slot-b" in ids and "slot-c" in ids


def test_registry_reports_files_ok():
    reg = Registry()
    for src in reg.sources():
        if src["status"] == "ready" and src["files"]:
            assert src["files_ok"] is True, f"{src['id']} is ready but its file is missing"


def test_registry_raises_on_an_unknown_source():
    reg = Registry()
    with pytest.raises(RegistryError):
        reg.json("not-a-source", "whatever.json")


def test_registry_refuses_a_file_that_is_not_listed():
    reg = Registry()
    with pytest.raises(RegistryError):
        reg.json("horizons-mars-lt", "osdr_i4/labs.json")


def test_registry_can_be_pointed_elsewhere(tmp_path: Path, monkeypatch):
    (tmp_path / "manifest.json").write_text(json.dumps({"version": 1, "sources": []}), encoding="utf-8")
    monkeypatch.setenv("ASTRA_NASA_DATA", str(tmp_path))
    reg = Registry()
    assert reg.sources() == []


def test_registry_rejects_an_unknown_role(tmp_path: Path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"version": 1, "sources": [{"id": "x", "role": "nonsense", "status": "ready"}]}),
        encoding="utf-8",
    )
    with pytest.raises(RegistryError):
        Registry(tmp_path)


# ---------------------------------------------------------------------------------- sources
def test_every_metric_has_a_source():
    for m in METRICS:
        assert m["sources"], f"metric {m['id']} has no source"


def test_every_hazard_organ_and_environment_has_a_source():
    for group in (HAZARDS, ORGANS, ENVIRONMENTS):
        for item in group:
            assert item["sources"], f"{item['id']} has no source"


def test_every_source_id_resolves_to_a_real_document():
    for group in (METRICS, HAZARDS, ORGANS, ENVIRONMENTS):
        for item in group:
            for sid in item["sources"]:
                assert sid in SOURCE_DOCS, f"{item['id']} points at unknown source '{sid}'"


def test_every_source_url_is_https():
    for sid, src in SOURCE_DOCS.items():
        assert src["url"].startswith("https://"), f"{sid} has a non-https url: {src['url']}"
        assert src["kind"] in ("evidence_report", "standard", "paper", "web"), sid
        assert src["title"] and src["org"], sid


def test_catalog_publishes_the_sources():
    from app.catalog import public_catalog

    cat = public_catalog()
    assert cat["sources"]
    assert cat["sources"]["std3001v2"]["url"].startswith("https://")


# ---------------------------------------------------------------------------------- thresholds
def test_career_limit_matches_nasa_std_3001():
    from app.catalog import CAREER_LIMIT_MSV

    assert CAREER_LIMIT_MSV == 600.0


def test_cabin_thresholds_match_the_nasa_documents():
    # [V2 6004]: average one-hour CO2 no more than 3 mmHg.
    assert CABIN["act_1h_mmhg"] == 3.0
    # OCHMO-TB-004: 7-day average below 2.5 mmHg keeps headache risk under 1%.
    assert CABIN["watch_7d_mmhg"] == 2.5


def test_radiation_rates_match_the_msl_rad_measurements():
    by_id = {e["id"]: e for e in ENVIRONMENTS}
    # Zeitlin et al. 2013 (cruise) and Hassler et al. 2014 (surface).
    assert by_id["transit"]["radiation_msv_day"] == 1.84
    assert by_id["mars"]["radiation_msv_day"] == 0.64


# ---------------------------------------------------------------------------------- cabin rules
@pytest.mark.parametrize(
    ("co2_1h", "co2_7d", "expected"),
    [
        (2.4, 2.4, "ok"),
        (2.9, 2.4, "ok"),
        (2.4, 2.5, "watch"),
        (2.9, 2.9, "watch"),
        (3.0, 2.0, "act"),
        (3.1, 3.1, "act"),
    ],
)
def test_cabin_status_boundaries(co2_1h: float, co2_7d: float, expected: str):
    assert rules.cabin_status(co2_1h, co2_7d) == expected


def test_cabin_insight_needs_two_headaches_and_bad_air():
    cabin = {"status": "watch", "co2_1h_mmhg": 2.8}
    assert rules.cabin_insight(cabin, ["Ana"]) is None
    assert rules.cabin_insight(cabin, ["Ana", "Sara"]) is not None
    good_air = {"status": "ok", "co2_1h_mmhg": 1.9}
    assert rules.cabin_insight(good_air, ["Ana", "Sara"]) is None


def test_cabin_insight_points_at_the_air_not_at_medicine():
    insight = rules.cabin_insight({"status": "act", "co2_1h_mmhg": 3.4}, ["Ana", "Sara"])
    assert insight is not None
    assert insight["id"] == "cabin_air"
    assert any("scrubber" in a.lower() for a in insight["actions"])
    assert insight["sources"]


# ---------------------------------------------------------------------------------- lab rules
def test_classify_lab_against_the_reference_range():
    assert rules.classify_lab(80, 65, 99) == "ok"
    assert rules.classify_lab(60, 65, 99) == "watch"
    assert rules.classify_lab(50, 65, 99) == "act"
    assert rules.classify_lab(105, 65, 99) == "watch"
    assert rules.classify_lab(120, 65, 99) == "act"


def test_classify_lab_without_a_range_is_nominal():
    assert rules.classify_lab(80, None, None) == "ok"


# ---------------------------------------------------------------------------------- API
def test_nasa_sources_route(client):
    body = client.get("/nasa/sources").json()
    assert body["sources"]
    assert body["counts"]["total"] == len(body["sources"])
    assert body["counts"]["ready"] >= 3
    # The three official slots were filled with the 13 Nov challenge resources.
    assert body["counts"]["slots_pending"] == 0
    for src in body["sources"]:
        assert src["role"] in ("threshold", "context", "replay", "evidence")
        assert src["status"] in ("ready", "pending", "error")


def test_nasa_source_route_rejects_an_unknown_id(client):
    assert client.get("/nasa/sources/nope").status_code == 404


def test_cabin_is_available_on_the_station_only(client):
    station = client.get("/nasa/cabin", params={"env": "station"}).json()
    assert station["available"] is True
    assert station["unit"] == "mmHg"
    assert station["status"] in ("ok", "watch", "act")
    transit = client.get("/nasa/cabin", params={"env": "transit"}).json()
    assert transit["available"] is False


def test_dashboard_includes_cabin_for_the_station(client):
    body = client.get("/crew/ana/dashboard", params={"env": "station"}).json()
    assert body["cabin"]["available"] is True
    transit = client.get("/crew/ana/dashboard", params={"env": "transit"}).json()
    assert transit["cabin"]["available"] is False


def test_cabin_card_carries_the_thresholds_and_their_sources(client):
    cabin = client.get("/nasa/cabin", params={"env": "station"}).json()
    assert cabin["unit"] == "mmHg"
    assert cabin["act_1h_mmhg"] == 3.0
    assert cabin["watch_7d_mmhg"] == 2.5
    assert cabin["sources"], "the cabin card must cite the documents behind its thresholds"
    for sid in cabin["sources"]:
        assert sid in SOURCE_DOCS


def test_the_seeded_demo_shows_the_cabin_air_insight(client):
    """Two crew logged a headache and the real CO2 is in the Watch band, so it must fire."""
    client.post("/admin/reset")
    body = client.get("/crew/ana/dashboard", params={"env": "station"}).json()
    ids = [i["id"] for i in body["insights"]]
    assert "cabin_air" in ids, f"expected the cabin insight, got {ids}"
    insight = next(i for i in body["insights"] if i["id"] == "cabin_air")
    assert insight["sources"]


def test_radiation_rate_carries_its_source(client):
    mars = client.get("/crew/ana/dashboard", params={"env": "mars"}).json()
    assert mars["radiation"]["rate_source"] == "msl-rad"
    station = client.get("/crew/ana/dashboard", params={"env": "station"}).json()
    assert station["radiation"]["rate_source"] == "osdr-eda-iss"


def test_inspiration4_route(client):
    body = client.get("/nasa/inspiration4").json()
    assert body["available"] is True
    assert len(body["subjects"]) == 4
    assert len(body["series"]) >= 8
    for series in body["series"]:
        assert series["ref_low"] is not None or series["ref_high"] is not None
        for point in series["points"]:
            assert point["status"] in ("ok", "watch", "act")


def test_signal_delay_comes_from_horizons(client):
    body = client.get("/crew/ana/dashboard", params={"env": "mars"}).json()
    assert body["env"]["delay_s"] > 0
    assert body["env"]["light_time_source"] == "horizons"
    assert "Horizons" in body["env"]["delay_note"]


def test_solar_replay_is_refused_without_the_donki_fixture(client):
    response = client.post("/nasa/replay/solar", json={"event_id": None})
    # Either the DONKI fixture is present (then it starts) or it is not (then it is a 503).
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert response.json()["event"]["illustrative"] is True
        client.post("/admin/reset")


def test_solar_replay_runs_the_real_donki_event_then_ends(client):
    response = client.post("/nasa/replay/solar", json={"event_id": None})
    assert response.status_code == 200
    event = response.json()["event"]
    assert event["event_id"] == "2021-10-28T16:35:00-SEP-001"

    def radiation():
        return client.get("/crew/ana/dashboard", params={"env": "transit"}).json()["radiation"]

    start = radiation()
    assert start["solar"]["status"] == "act"
    assert start["solar"]["link"].startswith("https://")

    client.post("/clock/advance", json={"seconds": 12 * 3600})
    mid = radiation()
    assert mid["solar"]["status"] == "act"
    assert mid["mission_msv"] > start["mission_msv"]

    client.post("/clock/advance", json={"seconds": 13 * 3600})  # past the 24 h event
    after = radiation()
    assert after["solar"]["status"] == "ok"

    # Once the event is over, its extra dose stops: only the normal daily rate accrues.
    client.post("/clock/advance", json={"seconds": 86400})
    later = radiation()
    assert abs((later["mission_msv"] - after["mission_msv"]) - later["rate_msv_day"]) < 0.15
    client.post("/admin/reset")


def test_reset_clears_the_solar_event(client):
    client.post("/nasa/replay/solar", json={"event_id": None})
    client.post("/admin/reset")
    body = client.get("/nasa/solar/events").json()
    assert body["active"] is None


# ---------------------------------------------------------------------------------- fixes after the UI audit
def test_catalog_environments_carry_the_live_signal_delay(client):
    """Settings, the top bar and Emergency read the catalog; it must match the dashboard."""
    catalog = {e["id"]: e for e in client.get("/catalog").json()["environments"]}
    for env_id in ("transit", "mars"):
        dash = client.get("/crew/ana/dashboard", params={"env": env_id}).json()["env"]
        assert catalog[env_id]["delay_s"] == pytest.approx(dash["delay_s"], abs=1.0)
        assert catalog[env_id]["delay_s"] != 760.0, "the old fixed delay must be gone"
    assert "round-trip today" in catalog["transit"]["tip"]


def test_station_dose_rate_is_the_real_eda_rate_everywhere(client):
    catalog = {e["id"]: e for e in client.get("/catalog").json()["environments"]}
    station = client.get("/crew/ana/dashboard", params={"env": "station"}).json()["radiation"]
    assert catalog["station"]["radiation_msv_day"] == pytest.approx(station["rate_msv_day"], abs=0.01)
    assert catalog["station"]["radiation_source"] == "osdr-eda-iss"
    assert station["rate_docs"] == ["osdr_eda"]


def test_unsourced_lunar_rates_are_marked_as_estimates(client):
    catalog = {e["id"]: e for e in client.get("/catalog").json()["environments"]}
    assert catalog["rover"]["radiation_source"] is None
    assert catalog["lunar"]["radiation_source"] is None
    lunar = client.get("/crew/ana/dashboard", params={"env": "lunar"}).json()["radiation"]
    assert lunar["rate_docs"] == []


def test_a_solar_storm_turns_the_radiation_status_to_act(client):
    client.post("/admin/reset")
    before = client.get("/crew/ana/dashboard", params={"env": "transit"}).json()["radiation"]
    assert before["status"] != "act"
    client.post("/nasa/replay/solar", json={"event_id": None})
    during = client.get("/crew/ana/dashboard", params={"env": "transit"}).json()["radiation"]
    assert during["status"] == "act"
    client.post("/clock/advance", json={"seconds": 25 * 3600})
    after = client.get("/crew/ana/dashboard", params={"env": "transit"}).json()["radiation"]
    assert after["status"] != "act"
    client.post("/admin/reset")


def test_cabin_never_reads_the_sensor_fill_as_air(client):
    """The first days of the EDA series are a constant 200 ppm; the cabin card must skip them."""
    client.post("/admin/reset")
    for _ in range(90):  # walk through every mapped series day
        cabin = client.get("/nasa/cabin", params={"env": "station"}).json()
        assert cabin["co2_1h_mmhg"] > 1.0, "a 200 ppm fill row leaked into the cabin card"
        assert all(v > 1.0 for v in cabin["spark"])
        client.post("/clock/advance", json={"seconds": 86400})
    client.post("/admin/reset")


def test_cabin_seven_day_average_is_a_daily_window(client):
    client.post("/admin/reset")
    cabin = client.get("/nasa/cabin", params={"env": "station"}).json()
    assert len(cabin["spark"]) == 7, "one point per day for the last 7 days"
    assert cabin["spark_label"]
    # The 7-day average sits in the same range as the daily means it summarises.
    assert min(cabin["spark"]) - 0.5 < cabin["co2_7d_mmhg"] < max(cabin["spark"]) + 0.5
    client.post("/admin/reset")


def test_inspiration4_points_carry_their_own_reference_range(client):
    body = client.get("/nasa/inspiration4").json()
    assert body["flight_window"] == {"from": 0, "to": 3}
    hemoglobin = next(s for s in body["series"] if s["id"] == "hemoglobin")
    assert hemoglobin["ranges_differ"] is True
    lows = {p["ref_low"] for p in hemoglobin["points"]}
    assert len(lows) > 1, "men and women have different haemoglobin ranges"
    assert hemoglobin["ref_low"] == min(lows)
    for p in hemoglobin["points"]:
        assert p["status"] == rules.classify_lab(p["value"], p["ref_low"], p["ref_high"])


# ---------------------------------------------------------------------------------- conjunction, stop
def _advance_days(client, days: int) -> None:
    left = days
    while left > 0:
        step = min(7, left)
        client.post("/clock/advance", json={"seconds": step * 86400})
        left -= step


def test_conjunction_warns_a_month_ahead_then_blackout_then_clears(client):
    client.post("/admin/reset")
    assert client.get("/comms", params={"env": "transit"}).json()["conjunction"] is None

    clock = client.post("/clock/skip-to-conjunction").json()
    assert clock["day"] > 400
    warn = client.get("/comms", params={"env": "mars"}).json()["conjunction"]
    assert warn["phase"] == "warning" and warn["status"] == "watch"
    assert 0 < warn["days_until"] <= warn["warning_days"]
    assert str(warn["days_until"]) in warn["label"]
    assert warn["blackout_days"] > 10

    _advance_days(client, warn["days_until"] + 3)
    black = client.get("/comms", params={"env": "mars"}).json()["conjunction"]
    assert black["phase"] == "blackout" and black["status"] == "act"
    assert black["sot_deg"] <= black["threshold_deg"]
    assert black["days_left"] > 0

    _advance_days(client, black["days_left"] + 3)
    assert client.get("/comms", params={"env": "mars"}).json()["conjunction"] is None
    client.post("/admin/reset")


def test_conjunction_is_not_shown_on_the_station_and_skip_refuses_to_go_back(client):
    client.post("/admin/reset")
    client.post("/clock/skip-to-conjunction")
    assert client.get("/comms", params={"env": "station"}).json()["conjunction"] is None
    assert client.post("/clock/skip-to-conjunction").status_code == 409
    client.post("/admin/reset")


def test_stopping_the_solar_replay_keeps_the_rest_of_the_demo(client):
    client.post("/admin/reset")
    client.post("/nasa/replay/solar", json={"event_id": None})
    client.post("/crew/ana/readings", json={"metric": "hr", "value": 61, "env": "transit"})
    before = client.get("/clock").json()["met_s"]
    readings = len(client.get("/crew/ana/series/hr", params={"days": 3}).json()["points"])
    assert client.get("/nasa/solar/events").json()["active"] is not None

    assert client.post("/nasa/replay/solar/stop").status_code == 200
    assert client.get("/nasa/solar/events").json()["active"] is None
    solar = client.get("/crew/ana/dashboard", params={"env": "transit"}).json()["radiation"]["solar"]
    assert solar["status"] == "ok"
    # Unlike a reset, stopping does not move the clock or erase the readings.
    assert abs(client.get("/clock").json()["met_s"] - before) < 10
    assert len(client.get("/crew/ana/series/hr", params={"days": 3}).json()["points"]) == readings
    client.post("/admin/reset")
