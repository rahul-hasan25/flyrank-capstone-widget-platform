import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.rate_limiter import rate_limiter
from seed import seed_database

@pytest.fixture(autouse=True)
def setup_test_environment():
    seed_database()
    rate_limiter.reset()

@pytest.fixture
def client():
    return TestClient(app)

def test_cross_origin_submission_flow(client):
    headers = {
        "Origin": "http://localhost:5500",
        "Content-Type": "application/json",
        "X-Mock-Provider-A": "success"
    }
    payload = {
        "widget_id": "wgt_demo_signup",
        "data": {
            "name": "Jane Developer",
            "email": "jane@example.com"
        }
    }
    
    resp = client.post("/api/v1/public/submissions", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "success"
    assert data["enriched"] is True
    assert "submission_id" in data
    submission_id = data["submission_id"]

    assert resp.headers.get("access-control-allow-origin") == "*"

    dash_resp = client.get(
        "/api/v1/dashboard/submissions",
        headers={"X-API-Key": "sk_live_demo_12345"}
    )
    assert dash_resp.status_code == 200
    items = dash_resp.json()["items"]
    matching = [s for s in items if s["id"] == submission_id]
    assert len(matching) == 1
    assert matching[0]["payload"]["email"] == "jane@example.com"

def test_invalid_and_oversized_payload_rejections(client):
    raw_bad_json = b"{\"widget_id\": \"wgt_demo_signup\", \"data\": {bad_json"
    resp_bad = client.post(
        "/api/v1/public/submissions",
        content=raw_bad_json,
        headers={"Content-Type": "application/json"}
    )
    assert resp_bad.status_code == 400
    assert resp_bad.json()["code"] == "INVALID_JSON"

    resp_missing = client.post(
        "/api/v1/public/submissions",
        json={"widget_id": "wgt_demo_signup", "data": {"name": "Only Name"}}
    )
    assert resp_missing.status_code == 400
    assert resp_missing.json()["code"] == "MISSING_REQUIRED_FIELD"

    resp_no_widget = client.post(
        "/api/v1/public/submissions",
        json={"data": {"email": "test@example.com"}}
    )
    assert resp_no_widget.status_code == 400
    assert resp_no_widget.json()["code"] == "MISSING_WIDGET_ID"

    huge_data = {"email": "big@example.com", "huge": "x" * 70000}
    resp_huge = client.post(
        "/api/v1/public/submissions",
        json={"widget_id": "wgt_demo_signup", "data": huge_data}
    )
    assert resp_huge.status_code == 413
    assert resp_huge.json()["code"] == "PAYLOAD_TOO_LARGE"

def test_rate_limiting_throttling(client):
    rate_limiter.reset()
    headers = {"X-Forwarded-For": "203.0.113.42"}
    payload = {
        "widget_id": "wgt_demo_signup",
        "data": {"name": "Test User", "email": "test@example.com"}
    }

    for _ in range(10):
        res = client.post("/api/v1/public/submissions", json=payload, headers=headers)
        assert res.status_code in (201, 200)

    blocked_res = client.post("/api/v1/public/submissions", json=payload, headers=headers)
    assert blocked_res.status_code == 429
    assert blocked_res.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in blocked_res.headers

    other_headers = {"X-Forwarded-For": "198.51.100.99"}
    legit_res = client.post("/api/v1/public/submissions", json=payload, headers=other_headers)
    assert legit_res.status_code == 201

def test_geolocation_provider_fallback_chain(client):
    payload = {
        "widget_id": "wgt_demo_signup",
        "data": {"name": "Fallback Tester", "email": "fallback@example.com"}
    }

    # Provider A down -> Provider B succeeds
    resp_b = client.post(
        "/api/v1/public/submissions",
        json=payload,
        headers={"X-Mock-Provider-A": "down", "X-Mock-Provider-B": "success"}
    )
    assert resp_b.status_code == 201
    body_b = resp_b.json()
    assert body_b["enriched"] is True
    assert "provider_b" in body_b["geo"]["provider"]
    assert body_b["geo"]["country"] == "Canada"

    # Both down -> Degrades gracefully
    resp_none = client.post(
        "/api/v1/public/submissions",
        json=payload,
        headers={"X-Mock-Provider-A": "down", "X-Mock-Provider-B": "down"}
    )
    assert resp_none.status_code == 201
    body_none = resp_none.json()
    assert body_none["status"] == "success"
    assert body_none["enriched"] is False
    assert body_none["geo"]["country"] is None

def test_safe_side_effects_tolerance(client):
    payload = {
        "widget_id": "wgt_demo_signup",
        "data": {"name": "Safe Worker", "email": "safe@example.com"}
    }

    resp = client.post(
        "/api/v1/public/submissions",
        json=payload,
        headers={"X-Mock-Side-Effect": "fail"}
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "success"

def test_honeypot_spam_blocking(client):
    payload = {
        "widget_id": "wgt_demo_signup",
        "data": {"name": "Spam Bot", "email": "bot@spam.com"},
        "_hp_trap": "https://spam-link.example.com"
    }

    resp = client.post("/api/v1/public/submissions", json=payload)
    assert resp.status_code == 400
    assert resp.json()["code"] == "SPAM_REJECTED"

def test_tenant_boundary_isolation(client):
    res_a = client.get("/api/v1/admin/widgets", headers={"X-API-Key": "sk_live_demo_12345"})
    assert res_a.status_code == 200
    ids_a = [w["id"] for w in res_a.json()]
    assert "wgt_demo_signup" in ids_a
    assert "wgt_globex_contact" not in ids_a

    res_b = client.get("/api/v1/admin/widgets", headers={"X-API-Key": "sk_live_globex_99999"})
    assert res_b.status_code == 200
    ids_b = [w["id"] for w in res_b.json()]
    assert "wgt_globex_contact" in ids_b
    assert "wgt_demo_signup" not in ids_b

    cross_read = client.get(
        "/api/v1/admin/widgets/wgt_globex_contact",
        headers={"X-API-Key": "sk_live_demo_12345"}
    )
    assert cross_read.status_code == 404

    cross_update = client.put(
        "/api/v1/admin/widgets/wgt_globex_contact",
        json={"title": "Hacked Title"},
        headers={"X-API-Key": "sk_live_demo_12345"}
    )
    assert cross_update.status_code == 404

    cross_delete = client.delete(
        "/api/v1/admin/widgets/wgt_globex_contact",
        headers={"X-API-Key": "sk_live_demo_12345"}
    )
    assert cross_delete.status_code == 404

    unauth = client.get("/api/v1/admin/widgets")
    assert unauth.status_code == 401

def test_cdn_caching_and_preflight_headers(client):
    js_resp = client.get("/static/widget.v1.js")
    assert js_resp.status_code == 200
    assert "public" in js_resp.headers.get("cache-control", "")
    assert "max-age=86400" in js_resp.headers.get("cache-control", "")
    assert js_resp.headers.get("access-control-allow-origin") == "*"

    cfg_resp = client.get("/api/v1/public/widgets/wgt_demo_signup/config")
    assert cfg_resp.status_code == 200
    assert "max-age=60" in cfg_resp.headers.get("cache-control", "")
    assert cfg_resp.headers.get("access-control-allow-origin") == "*"
    cfg_data = cfg_resp.json()
    assert cfg_data["id"] == "wgt_demo_signup"
    assert "tenant_id" not in cfg_data

    opt_resp = client.options("/api/v1/public/submissions")
    assert opt_resp.status_code == 204
    assert opt_resp.headers.get("access-control-allow-origin") == "*"
    assert "POST" in opt_resp.headers.get("access-control-allow-methods", "")

def test_idempotency_replay_protection(client):
    idempotency_key = "idemp_test_key_abc_123"
    headers = {
        "Idempotency-Key": idempotency_key,
        "X-Mock-Provider-A": "success"
    }
    payload = {
        "widget_id": "wgt_demo_signup",
        "data": {"name": "Idempotent User", "email": "idemp@example.com"}
    }

    res1 = client.post("/api/v1/public/submissions", json=payload, headers=headers)
    assert res1.status_code == 201
    sub_id_1 = res1.json()["submission_id"]

    res2 = client.post("/api/v1/public/submissions", json=payload, headers=headers)
    assert res2.status_code == 200
    sub_id_2 = res2.json()["submission_id"]
    assert sub_id_1 == sub_id_2
