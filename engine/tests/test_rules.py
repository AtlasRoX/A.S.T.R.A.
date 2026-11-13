from app import rules


def test_heart_rate_bands():
    assert rules.classify("hr", 64) == "ok"
    assert rules.classify("hr", 45) == "watch"
    assert rules.classify("hr", 110) == "watch"
    assert rules.classify("hr", 125) == "act"
    assert rules.classify("hr", 38) == "act"


def test_blood_pressure_uses_worst_of_both_values():
    assert rules.classify("bp", 118, 76) == "ok"
    assert rules.classify("bp", 134, 80) == "watch"
    assert rules.classify("bp", 118, 87) == "watch"
    assert rules.classify("bp", 146, 80) == "act"
    assert rules.classify("bp", 120, 95) == "act"


def test_body_mass_is_relative_to_reference():
    assert rules.classify("mass", 63.0, ref=64.0) == "ok"  # -1.6 %
    assert rules.classify("mass", 61.5, ref=64.0) == "watch"  # -3.9 %
    assert rules.classify("mass", 60.0, ref=64.0) == "act"  # -6.3 %


def test_red_flag_symptom_forces_act_and_tier_two():
    meta = {"items": ["chest_pain"]}
    assert rules.classify("symptoms", 1, meta=meta) == "act"
    flags = rules.red_flags("symptoms", 1, meta=meta)
    tier, _ = rules.escalation_tier("act", flags, {"watch_days": 1, "act_days": 1})
    assert tier == 2


def test_escalation_ladder():
    assert rules.escalation_tier("ok", [], {"watch_days": 0, "act_days": 0})[0] == 0
    assert rules.escalation_tier("watch", [], {"watch_days": 2, "act_days": 0})[0] == 0
    assert rules.escalation_tier("watch", [], {"watch_days": 3, "act_days": 0})[0] == 1
    assert rules.escalation_tier("act", [], {"watch_days": 1, "act_days": 1})[0] == 1
    assert rules.escalation_tier("act", [], {"watch_days": 2, "act_days": 2})[0] == 2


def test_persistence_counts_from_newest():
    assert rules.persistence(["watch", "watch", "ok", "watch"]) == {"watch_days": 2, "act_days": 0}
    assert rules.persistence(["act", "act", "watch"]) == {"watch_days": 3, "act_days": 2}


def test_trend_quality_respects_direction():
    pts = [(d, 7.6 - 0.2 * d) for d in range(7)]  # sleep falling
    slope = rules.slope_per_day(pts)
    assert rules.trend_label("sleep", slope, 0.3) == {"direction": "falling", "quality": "worsening"}
    pts = [(d, 120 + 3 * d) for d in range(7)]  # exercise rising
    assert rules.trend_label("exercise", rules.slope_per_day(pts), 8)["quality"] == "improving"


def test_personal_flag_only_in_worse_direction():
    assert rules.is_worse_direction("spo2", -3.5)
    assert not rules.is_worse_direction("spo2", 3.5)
    assert rules.is_worse_direction("hr", 3.5) and rules.is_worse_direction("hr", -3.5)


def test_sleep_debt_insight_detected():
    snap = {
        "sleep": {"status": "watch", "value": 6.2, "baseline": 7.6, "slope": -0.2,
                  "recent": [(140, 6.4), (141, 6.3), (142, 6.2)]},
        "mood": {"status": "watch", "value": 3, "baseline": 4.3, "slope": -0.2, "recent": []},
        "reaction": {"status": "watch", "value": 338, "baseline": 262, "slope": 9, "recent": []},
    }
    ids = [i["id"] for i in rules.insights(snap)]
    assert ids[0] == "sleep_debt"


def test_all_clear_insight_when_nominal():
    snap = {"hr": {"status": "ok", "value": 64, "baseline": 64, "slope": 0, "recent": []}}
    assert rules.insights(snap)[0]["id"] == "all_clear"


def test_readiness_and_eva():
    assert rules.readiness({"hr": "ok", "bp": "ok"}, [], 0) == 100
    assert rules.readiness({"hr": "act", "bp": "watch"}, [], 2) == 100 - 14 - 5 - 2
    assert rules.eva_readiness({"spo2": "act"}, 7.5)["status"] == "nogo"
    assert rules.eva_readiness({"hr": "ok"}, 6.2)["status"] == "caution"
    assert rules.eva_readiness({"hr": "ok"}, 7.5)["status"] == "go"
