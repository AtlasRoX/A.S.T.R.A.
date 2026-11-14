def test_crew_watch_runs_on_board_and_sends_one_handover(client):
    r = client.post("/agent/crew-watch/run", params={"env": "station"}).json()
    assert r["on_board"] is True and r["network_used"] is False
    phases = [s["phase"] for s in r["steps"]]
    assert phases[0] == "sense"
    if r["decision"]:
        assert {"check", "decide", "act"} <= set(phases)
        assert r["handover"] and r["handover"]["packet"]["id"]
        again = client.post("/agent/crew-watch/run", params={"env": "station"}).json()
        assert again["handover"] is None  # the same finding is not reported twice
    assert client.get("/agent/crew-watch").json()["last"]["agent"] == "crew_watch"
