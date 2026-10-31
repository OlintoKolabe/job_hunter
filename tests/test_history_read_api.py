"""Contract tests for the independent, read-only history API."""
from contextlib import contextmanager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from itsdangerous import URLSafeTimedSerializer
from history_read_api import register_history_read_api


class FakeCursor:
    def __init__(self):
        self.query = ""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, query, params=None):
        self.query = query
    def fetchone(self):
        return (2,)
    def fetchall(self):
        return [
            (4, "https://jobs.example/4", "jobs.example/4", "A", "PM", "Candidatado", "2026-10-30", "LinkedIn", ""),
            (3, "https://jobs.example/3", "jobs.example/3", "B", "PO", "Descartado", "2026-10-29", "Greenhouse", ""),
        ]


class FakeConnection:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def cursor(self):
        return FakeCursor()


class FakeMu:
    enabled = True
    def __init__(self):
        self.context = None
    def get_user(self, database, uid):
        if uid != 7:
            return None
        return (7, "Olinto", "owner@example.test", {}, 4)
    def set_context(self, user):
        self.context = user[0]
    def connect(self, database, **kwargs):
        assert self.context == 7
        return FakeConnection()


def make_client():
    app = FastAPI()
    mu = FakeMu()
    serializer = URLSafeTimedSerializer("test-key")
    def auth(_):
        mu.set_context(mu.get_user("db", 7))
        return 7
    register_history_read_api(app, auth, serializer, "db", lambda: None, mu)
    return TestClient(app), mu


def test_history_requires_bearer_even_when_browser_is_logged_in():
    client, _ = make_client()
    response = client.get("/api/integrations/history")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_issued_token_reads_live_history_and_maps_states():
    client, mu = make_client()
    issuance = client.post("/api/integrations/history-token")
    assert issuance.status_code == 200
    assert issuance.headers["cache-control"] == "no-store"
    token = issuance.json()["token"]
    response = client.get("/api/integrations/history", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    data = response.json()
    assert data["profile"] == "7"
    assert [item["state"] for item in data["items"]] == ["applied", "discarded"]
    assert response.headers["cache-control"] == "no-store"
    assert mu.context == 7


def test_cross_profile_token_is_rejected():
    client, _ = make_client()
    foreign = URLSafeTimedSerializer("test-key").dumps(
        {"scope":"history:read", "identity":"8", "version":4},
        salt="job-hunter-history-read-v1",
    )
    response = client.get("/api/integrations/history", headers={"Authorization": "Bearer " + foreign})
    assert response.status_code == 401


def test_wrong_scope_and_bad_pagination_are_rejected():
    client, _ = make_client()
    token = client.post("/api/integrations/history-token").json()["token"]
    headers = {"Authorization": "Bearer " + token}
    assert client.get("/api/integrations/history?limit=501", headers=headers).status_code == 400
    assert client.get("/api/integrations/history?state=unknown", headers=headers).status_code == 400
    wrong = URLSafeTimedSerializer("test-key").dumps(
        {"scope":"history:write", "identity":"7", "version":4},
        salt="job-hunter-history-read-v1",
    )
    assert client.get("/api/integrations/history", headers={"Authorization": "Bearer " + wrong}).status_code == 401
