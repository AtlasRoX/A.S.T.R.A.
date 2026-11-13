"""Measurement context: resting ranges at rest, recovery ranges after exercise or an EVA."""

from __future__ import annotations

import pytest

from app import rules


def _ev(client, metric: str, value: float, value2: float | None = None, context: str | None = None,
        task_id: str | None = None, env: str = "transit"):
    body = {"metric": metric, "value": value, "value2": value2, "env": env, "task_id": task_id,
            "meta": {"context": context} if context else None}
    return client.post("/crew/sara/evaluate", json=body)


# ---------------------------------------------------------------------------------- pure rules
@pytest.mark.parametrize(
    ("value", "context", "expected"),
    [
        (64, None, "ok"),
        (110, None, "watch"),
        (125, None, "act"),
        (125, "after_exercise", "ok"),
        (125, "after_eva", "ok"),
        (125, "just_woke", "act"),  # just woke up is a resting context
        (140, "after_exercise", "watch"),
        (155, "after_exercise", "act"),
    ],
)
def test_heart_rate_is_graded_for_its_context(value: float, context: str | None, expected: str):
    meta = {"context": context} if context else None
    assert rules.classify("hr", value, meta=meta) == expected


def test_red_flags_move_with_the_context():
    assert rules.red_flags("hr", 150)  # above 140 at rest: straight to the flight surgeon
    assert not rules.red_flags("hr", 150, meta={"context": "after_exercise"})
    assert rules.red_flags("hr", 185, meta={"context": "after_exercise"})
    assert rules.red_flags("hr", 35, meta={"context": "after_exercise"})  # too slow is never recovery


def test_blood_pressure_and_breathing_have_recovery_bands():
    assert rules.classify("bp", 150, 85) == "act"
    assert rules.classify("bp", 150, 85, meta={"context": "after_exercise"}) == "ok"
    assert rules.classify("resp", 26) == "act"
    assert rules.classify("resp", 26, meta={"context": "after_eva"}) == "ok"


def test_metrics_without_recovery_bands_ignore_the_context():
    assert rules.classify("temp", 38.6, meta={"context": "after_exercise"}) == rules.classify("temp", 38.6)
    assert not rules.is_active("spo2", {"context": "after_exercise"})


# ---------------------------------------------------------------------------------- evaluation
def test_post_exercise_reading_is_not_compared_with_the_resting_baseline(client):
    client.post("/admin/reset")
    ev = _ev(client, "hr", 125, context="after_exercise").json()
    assert ev["status"] == "ok"
    assert ev["active"] is True and ev["context"] == "after_exercise"
    assert ev["personal"] is False and ev["z"] is None
    assert ev["band"]["ok"] == [50, 130]
    assert ev["recheck_after_min"] == 30
    assert "30 minutes" in ev["guidance"]
    assert "not compared with your resting baseline" in ev["delta_text"]
    rest = _ev(client, "hr", 125, context="rest").json()
    assert rest["status"] == "act" and rest["active"] is False


def test_exercise_logged_in_the_last_30_minutes_is_inferred(client):
    client.post("/admin/reset")
    client.post("/crew/sara/readings", json={"metric": "exercise", "value": 120, "env": "transit"})
    client.post("/clock/advance", json={"seconds": 10 * 60})
    ev = _ev(client, "hr", 118).json()
    assert ev["context"] == "after_exercise" and ev["context_inferred"] is True
    assert "10 min ago" in ev["context_note"]
    assert ev["status"] == "ok"

    # Saying "resting" explicitly is respected, with a warning that it is too soon.
    explicit = _ev(client, "hr", 118, context="rest").json()
    assert explicit["context"] == "rest" and explicit["context_inferred"] is False
    assert "30 minutes" in explicit["context_note"]
    assert explicit["status"] == "watch"

    # 40 minutes after the workout ASTRA assumes rest again.
    client.post("/clock/advance", json={"seconds": 30 * 60})
    later = _ev(client, "hr", 118).json()
    assert later["context"] == "rest" and later["context_note"] is None
    client.post("/admin/reset")


def test_the_post_eva_check_is_read_as_after_an_eva(client):
    client.post("/admin/reset")
    ev = _ev(client, "resp", 26, task_id="post_eva", env="rover").json()
    assert ev["context"] == "after_eva" and ev["context_inferred"] is True
    assert ev["status"] == "ok"
    client.post("/admin/reset")


def test_an_unknown_context_is_refused(client):
    assert _ev(client, "hr", 64, context="dancing").status_code == 422


def test_an_act_after_exercise_goes_to_the_cmo_not_straight_to_earth(client):
    client.post("/admin/reset")
    ev = _ev(client, "hr", 160, context="after_exercise").json()
    assert ev["status"] == "act"
    assert ev["red_flags"] == []
    assert ev["tier"] == 1


# ---------------------------------------------------------------------------------- dashboard
def test_a_post_exercise_reading_leaves_the_resting_status_alone(client):
    client.post("/admin/reset")
    before = client.get("/crew/sara/dashboard", params={"env": "transit"}).json()["metrics"]["hr"]
    client.post("/crew/sara/readings", json={"metric": "hr", "value": 128, "env": "transit",
                                              "meta": {"context": "after_exercise"}})
    after = client.get("/crew/sara/dashboard", params={"env": "transit"}).json()["metrics"]["hr"]
    assert after["value"] == before["value"], "the resting value still drives the card"
    assert after["status"] == before["status"]
    assert after["baseline"] == before["baseline"], "the baseline is built from resting readings only"
    assert after["active_reading"]["display"] == "128"
    assert after["active_reading"]["context_label"] == "After exercise"

    # A later resting reading takes over again.
    client.post("/clock/advance", json={"seconds": 40 * 60})
    client.post("/crew/sara/readings", json={"metric": "hr", "value": 60, "env": "transit",
                                              "meta": {"context": "rest"}})
    rested = client.get("/crew/sara/dashboard", params={"env": "transit"}).json()["metrics"]["hr"]
    assert rested["value"] == 60
    assert rested["active_reading"] is None
    client.post("/admin/reset")


def test_the_catalog_publishes_the_contexts(client):
    cat = client.get("/catalog").json()
    ids = [c["id"] for c in cat["contexts"]]
    assert ids == ["rest", "just_woke", "after_exercise", "after_eva"]
    hr = next(m for m in cat["metrics"] if m["id"] == "hr")
    assert hr["context_sensitive"] is True and hr["active"]["ok"] == [50, 130]
