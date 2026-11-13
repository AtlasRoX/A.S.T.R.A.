import json

from app import assistant


def test_heuristics_find_people_indicators_and_emergencies():
    a = assistant.analyse("How is Kenji's blood pressure?", "ana")
    assert a["crew"] == ["kenji"] and "bp" in a["metrics"] and not a["emergency"]
    assert assistant.analyse("my sleep has been bad", "sara")["crew"] == ["sara"]
    assert assistant.analyse("the commander looks tired", "sara")["crew"] == ["ana"]
    assert assistant.analyse("Lucas collapsed with chest pain", "ana")["emergency"]


def test_answers_without_a_key_from_rules(client, monkeypatch):
    monkeypatch.setattr(assistant, "_api_key", lambda: None)
    r = client.post("/assistant/chat", json={"crew_id": "ana", "question": "Lucas has chest pain"})
    events = [json.loads(line) for line in r.text.splitlines() if line]
    assert r.status_code == 200 and events[0]["type"] == "meta" and events[-1]["type"] == "done"
    text = "".join(e.get("text", "") for e in events)
    assert "on-board rules" in text and "Emergency protocols" in text
    assert client.post("/assistant/chat", json={"crew_id": "nobody", "question": "hi"}).status_code == 404


def test_notification_log_is_timestamped_and_scoped(client):
    n = client.get("/assistant/notifications", params={"crew_id": "ana"}).json()
    assert n["now_label"].startswith("Day ")
    for it in n["items"]:
        # Own alerts, everyone's Act alerts, and ground replies only; every entry has an exact mission time.
        assert it["at_label"].startswith("Day ") and it["ago"].endswith("ago")
        if it["kind"] == "alert" and it["crew_id"] != "ana":
            assert it["severity"] == "act"
    times = [it["at"] for it in n["items"]]
    assert times == sorted(times, reverse=True)


def test_questions_follow_the_page_being_viewed():
    on_lucas = "/crew/lucas"
    assert assistant.analyse("why is he on act?", "ana", on_lucas)["crew"] == ["lucas"]
    assert assistant.analyse("what about my sleep", "ana", on_lucas)["crew"] == ["ana"]
    assert assistant.analyse("how is kenji", "ana", on_lucas)["crew"] == ["kenji"]
    assert assistant.analyse("explain this trend", "ana", "/trends?m=sleep")["metrics"] == ["sleep"]
    assert "exercise" in assistant.analyse("why was it changed", "ana", "/exercise")["metrics"]


def test_game_questions_bring_in_the_game_state():
    assert assistant.analyse("how do I level up?", "ana")["game"]
    assert assistant.analyse("anything", "ana", "/missions")["game"]
    assert not assistant.analyse("how is my sleep", "ana")["game"]
