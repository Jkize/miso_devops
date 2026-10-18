from datetime import datetime, timedelta, timezone

import pytest
from flask_jwt_extended import create_access_token

from blacklist_service.extensions import db
from blacklist_service.models import BlacklistEntry


def test_create_query_and_audit_data(app, client, headers, payload):
    assert client.get("/blacklists/customer@example.com", headers=headers).json == {
        "blacklisted": False, "blocked_reason": None,
    }
    response = client.post("/blacklists", json=payload, headers=headers,
                           environ_base={"REMOTE_ADDR": "203.0.113.10"})
    assert response.status_code == 201
    assert client.get("/blacklists/customer@example.com", headers=headers).json == {
        "blacklisted": True, "blocked_reason": payload["blocked_reason"],
    }
    with app.app_context():
        entry = db.session.scalar(db.select(BlacklistEntry))
        assert entry.source_ip == "203.0.113.10"
        assert str(entry.app_uuid) == payload["app_uuid"]
        # SQLite drops tzinfo; PostgreSQL integration is verified separately.
        assert abs((datetime.now(timezone.utc) - entry.created_at.replace(tzinfo=timezone.utc)).total_seconds()) < 30


@pytest.mark.parametrize("method,path", [("post", "/blacklists"), ("get", "/blacklists/a@example.com")])
@pytest.mark.parametrize("auth", [None, "Bearer invalid"])
def test_authorization_required(client, method, path, auth):
    response = getattr(client, method)(path, headers={"Authorization": auth} if auth else {})
    assert response.status_code == 401


def test_expired_token(app, client):
    with app.app_context():
        token = create_access_token(identity="tests", expires_delta=timedelta(seconds=-1))
    assert client.get("/blacklists/a@example.com", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("change", [
    {"email": "invalid"}, {"email": None}, {"app_uuid": "invalid"},
    {"app_uuid": None}, {"blocked_reason": "x" * 256},
    {"blocked_reason": 123}, {"extra": "unexpected"},
])
def test_invalid_payload(client, headers, payload, change):
    assert client.post("/blacklists", json={**payload, **change}, headers=headers).status_code == 400


@pytest.mark.parametrize("field", ["email", "app_uuid"])
def test_missing_required_field(client, headers, payload, field):
    payload.pop(field)
    assert client.post("/blacklists", json=payload, headers=headers).status_code == 400


@pytest.mark.parametrize("reason", [None, "", "x" * 255])
def test_reason_boundaries(client, headers, payload, reason):
    payload["blocked_reason"] = reason
    assert client.post("/blacklists", json=payload, headers=headers).status_code == 201


def test_reason_can_be_omitted(client, headers, payload):
    payload.pop("blocked_reason")
    assert client.post("/blacklists", json=payload, headers=headers).status_code == 201


def test_case_normalization_and_duplicate(client, headers, payload):
    payload["email"] = " CUSTOMER@EXAMPLE.COM "
    assert client.post("/blacklists", json=payload, headers=headers).status_code == 201
    assert client.get("/blacklists/CUSTOMER@example.com", headers=headers).json["blacklisted"] is True
    assert client.post("/blacklists", json=payload, headers=headers).status_code == 409


@pytest.mark.parametrize("body", ["{broken", "[]", "null"])
def test_invalid_json(client, headers, body):
    assert client.post("/blacklists", data=body, content_type="application/json", headers=headers).status_code == 400


def test_invalid_query_email(client, headers):
    assert client.get("/blacklists/invalid", headers=headers).status_code == 400


def test_forwarded_ip_not_trusted_locally(app, client, headers, payload):
    client.post("/blacklists", json=payload, headers={**headers, "X-Forwarded-For": "1.2.3.4"})
    with app.app_context():
        assert db.session.scalar(db.select(BlacklistEntry)).source_ip == "127.0.0.1"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"
