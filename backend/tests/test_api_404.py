"""The SPA catch-all must never answer an /api/* path.

A stale deploy is the motivating case: if the server is running code that
predates a route, the catch-all used to return the SPA's index.html with a 200,
so the frontend got HTML where it expected JSON and the feature it powered just
vanished from the UI with no error anywhere. That is how the weight widget went
missing (issue #13) rather than failing loudly.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_unknown_api_path_is_json_404():
    resp = client.get("/api/analytics/definitely-not-a-route")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert "text/html" not in resp.headers["content-type"]


def test_unknown_api_path_does_not_return_spa_html():
    resp = client.get("/api/analytics/weight-progress-typo")
    assert "<!doctype html>" not in resp.text.lower()


def test_unknown_nested_api_path_is_404():
    for path in ("/api/", "/api/nope", "/api/a/b/c"):
        resp = client.get(path)
        assert resp.status_code == 404, path
        assert resp.headers["content-type"].startswith("application/json"), path


def test_real_api_route_still_works():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
