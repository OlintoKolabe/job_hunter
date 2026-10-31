"""Contract tests for scoped Caçador integrations."""
import unittest
from fastapi import FastAPI, Request
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
    def fake_search(request: Request):
        app.state.integration_auth(request, "jobs:search")
        return {"items": [{"url": "https://jobs.example/4", "title": "PM"}]}
    def fake_disposition(request: Request):
        app.state.integration_auth(request, "jobs:disposition")
        return {"saved": True, "state": "Candidatado"}
    register_history_read_api(app, auth, serializer, "db", lambda: None, mu,
                              search_jobs=fake_search, mark_job_disposition=fake_disposition)
    return TestClient(app), mu


class HistoryReadApiTests(unittest.TestCase):
    def test_history_requires_bearer_even_when_browser_is_logged_in(self):
        client, _ = make_client()
        response = client.get("/api/integrations/history")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_issued_token_reads_live_history_and_maps_states(self):
        client, mu = make_client()
        issuance = client.post("/api/integrations/history-token")
        self.assertEqual(issuance.status_code, 200)
        self.assertEqual(issuance.headers["cache-control"], "no-store")
        token = issuance.json()["token"]
        response = client.get("/api/integrations/history", headers={"Authorization": "Bearer " + token})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["profile"], "7")
        self.assertEqual([item["state"] for item in data["items"]], ["applied", "discarded"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(mu.context, 7)

    def test_cross_profile_token_is_rejected(self):
        client, _ = make_client()
        foreign = URLSafeTimedSerializer("test-key").dumps(
            {"scope":"history:read", "identity":"8", "version":4},
            salt="job-hunter-history-read-v1",
        )
        response = client.get("/api/integrations/history", headers={"Authorization": "Bearer " + foreign})
        self.assertEqual(response.status_code, 401)

    def test_wrong_scope_and_bad_pagination_are_rejected(self):
        client, _ = make_client()
        token = client.post("/api/integrations/history-token").json()["token"]
        headers = {"Authorization": "Bearer " + token}
        self.assertEqual(client.get("/api/integrations/history?limit=501", headers=headers).status_code, 400)
        self.assertEqual(client.get("/api/integrations/history?state=unknown", headers=headers).status_code, 400)
        wrong = URLSafeTimedSerializer("test-key").dumps(
            {"scope":"history:write", "identity":"7", "version":4},
            salt="job-hunter-history-read-v1",
        )
        self.assertEqual(
            client.get("/api/integrations/history", headers={"Authorization": "Bearer " + wrong}).status_code,
            401,
        )

    def test_applicator_token_searches_and_updates_using_scoped_bearer(self):
        client, _ = make_client()
        issued = client.post("/api/integrations/applicator-token")
        self.assertEqual(issued.status_code, 200)
        self.assertEqual(issued.json()["scopes"],
                         ["history:read", "jobs:search", "jobs:disposition"])
        bearer = {"Authorization": "Bearer " + issued.json()["token"]}
        self.assertEqual(client.get("/api/integrations/history", headers=bearer).status_code, 200)
        found = client.post("/api/integrations/jobs/search", headers=bearer)
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json()["items"][0]["title"], "PM")
        marked = client.post("/api/integrations/jobs/disposition", headers=bearer)
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.json()["saved"])

    def test_previous_history_read_token_cannot_search_or_mark(self):
        client, _ = make_client()
        token = client.post("/api/integrations/history-token").json()["token"]
        bearer = {"Authorization": "Bearer " + token}
        self.assertEqual(client.post("/api/integrations/jobs/search", headers=bearer).status_code, 401)
        self.assertEqual(client.post("/api/integrations/jobs/disposition", headers=bearer).status_code, 401)

    def test_applicator_rejects_foreign_profile_and_unauthenticated_calls(self):
        client, _ = make_client()
        self.assertEqual(client.post("/api/integrations/jobs/search").status_code, 401)
        self.assertEqual(client.post("/api/integrations/jobs/disposition").status_code, 401)
        foreign = URLSafeTimedSerializer("test-key").dumps(
            {"scopes":["history:read", "jobs:search", "jobs:disposition"],
             "identity":"8", "version":4}, salt="job-hunter-history-read-v1"
        )
        self.assertEqual(client.post("/api/integrations/jobs/search",
            headers={"Authorization":"Bearer " + foreign}).status_code, 401)
