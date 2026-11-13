"""Tests for the official challenge resources (manifest slots A, B and C) and the HRP risk map."""

from __future__ import annotations

from app.catalog import HAZARDS, METRIC_BY_ID, ORGAN_BY_ID
from app.nasa import Registry
from app.official import FILES, official_resources
from app.sources import HAZARD_SOURCES, SOURCES


def _raw(reg: Registry, sid: str) -> dict:
    return reg.json(sid, FILES[sid])


def test_the_three_slots_are_filled_and_on_disk():
    reg = Registry()
    for sid in FILES:
        src = reg.source(sid)
        assert src is not None
        assert src["status"] == "ready" and src["files_ok"] is True
        assert src["role"] == "evidence"
        assert src["url"].startswith("https://")
        assert src["fetched"] == "2026-11-13"


def test_all_five_listed_resources_are_present():
    d = official_resources(Registry())
    assert d["available"] is True
    urls = {r["url"] for r in d["resources"]}
    assert urls == {
        "https://www.nasa.gov/hrp/hazards/",
        "https://www.nasa.gov/hrp/risks/",
        "https://www.nasa.gov/hrp/ongoing-hrp-research/",
        "https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp",
        "https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp",
    }


def test_every_hrp_risk_is_mapped_to_something_astra_does():
    d = official_resources(Registry())
    assert d["coverage"]["total"] == 17
    assert sum(d["coverage"][k] for k in ("monitored", "supported", "partial")) == 17
    for r in d["risks"]:
        assert r["url"].startswith("https://www.nasa.gov/reference/")
        assert r["how"], f"{r['id']} says nothing about what ASTRA does"
        assert r["metrics"] or r["features"], f"{r['id']} points at nothing in ASTRA"
        if r["level"] == "monitored":
            assert r["metrics"], f"{r['id']} is 'monitored' but names no metric"
        if r["level"] == "partial":
            assert "Gap:" in r["how"], f"{r['id']} is 'partial' but does not name the gap"
        assert r["roadmap_source"] in SOURCES


def test_fixture_ids_exist_in_the_catalog():
    # The raw fixture must not name a metric or body system the catalog does not have (the reader would drop it).
    reg = Registry()
    hazard_ids = {h["id"] for h in HAZARDS}
    for r in _raw(reg, "slot-a")["risks"]:
        assert set(r["astra"]["metrics"]) <= set(METRIC_BY_ID), r["id"]
        assert set(r["astra"]["organs"]) <= set(ORGAN_BY_ID), r["id"]
        assert set(r["hazards"]) <= hazard_ids, r["id"]
    risk_ids = {r["id"] for r in _raw(reg, "slot-a")["risks"]}
    for st in _raw(reg, "slot-b")["studies"]:
        assert set(st["astra"]["metrics"]) <= set(METRIC_BY_ID), st["id"]
        assert set(st["risks"]) <= risk_ids, st["id"]
    for eff in _raw(reg, "slot-c")["body_effects"]:
        assert set(eff["organs"]) <= set(ORGAN_BY_ID), eff["system"]


def test_hazard_facts_cover_all_five_hazards_and_link_their_page():
    d = official_resources(Registry())
    assert [h["id"] for h in d["hazards"]] == [h["id"] for h in HAZARDS]
    for h in d["hazards"]:
        assert h["facts"] and h["url"].startswith("https://www.nasa.gov/hrp/hazard-")


def test_each_hazard_cites_its_official_page():
    for hid, page in {"R": "hrp_hz_radiation", "I": "hrp_hz_isolation", "D": "hrp_hz_distance",
                      "G": "hrp_hz_gravity", "E": "hrp_hz_environment"}.items():
        assert page in HAZARD_SOURCES[hid]
        assert page in SOURCES


def test_csa_facts_carry_their_own_url():
    csa = official_resources(Registry())["csa"]
    assert len(csa["radiation_facts"]) >= 4
    for f in csa["radiation_facts"]:
        assert f["url"].startswith("https://www.asc-csa.gc.ca/")


def test_research_studies_are_the_thirteen_ongoing_ones():
    studies = official_resources(Registry())["research"]["studies"]
    assert len(studies) == 13
    assert {"archer", "standard_measures", "zero_t2"} <= {s["id"] for s in studies}


def test_unavailable_without_a_registry():
    assert official_resources(None) == {"available": False}


def test_official_route(client):
    body = client.get("/nasa/official").json()
    assert body["available"] is True
    assert body["coverage"]["total"] == 17
