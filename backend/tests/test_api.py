from fastapi.testclient import TestClient


def test_api_end_to_end(settings, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main.settings, "ask_per_hour", 3)
    with TestClient(main.app) as client:
        assert client.get("/api/health").json()["ok"] is True
        r = client.post("/api/ask", json={"question": "Northgate City xG this season?"})
        assert r.status_code == 200 and "answer" in r.json()
        client.post("/api/ask", json={"question": "Mori goals?"})
        client.post("/api/ask", json={"question": "Ekwueme goals?"})
        limited = client.post("/api/ask", json={"question": "Ferraro goals?"})
        assert limited.status_code == 429
        bad_goal = client.post("/api/challenge", json={"post": "x", "question": "hi there", "goal": "nope"})
        assert bad_goal.status_code == 422
        assert "live" in client.get("/api/numbers").json()
