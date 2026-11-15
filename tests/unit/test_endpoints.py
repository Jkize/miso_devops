"""Endpoint contracts with persistence mocked by tests/unit/conftest.py."""
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from blacklist_service.models import BlacklistEntry


def test_post_blacklist_returns_201(client, headers, payload, session):
    response = client.post(
        "/blacklists", json=payload, headers=headers,
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
    )

    assert response.status_code == 201
    assert response.json == {"message": "Correo agregado a la lista negra."}
    session.add.assert_called_once()
    entry = session.add.call_args.args[0]
    assert entry.email == payload["email"]
    assert entry.app_uuid == UUID(payload["app_uuid"])
    assert entry.blocked_reason == payload["blocked_reason"]
    assert entry.source_ip == "203.0.113.10"
    session.commit.assert_called_once()


def test_post_invalid_email_does_not_save(client, headers, payload, session):
    response = client.post(
        "/blacklists", json={**payload, "email": "invalid"}, headers=headers,
    )
    assert response.status_code == 400
    assert "email" in response.json["errors"]
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_post_duplicate_returns_409(client, headers, payload, session):
    session.commit.side_effect = IntegrityError("INSERT", {}, Exception("duplicate"))
    session.scalar.return_value = 1

    response = client.post("/blacklists", json=payload, headers=headers)

    assert response.status_code == 409
    assert response.json == {"message": "El correo ya esta en la lista negra."}
    session.rollback.assert_called_once()


@pytest.mark.parametrize("found", [True, False], ids=["blocked", "not-blocked"])
def test_get_blacklist_returns_membership(client, headers, payload, session, found):
    session.scalar.return_value = BlacklistEntry(**payload) if found else None

    response = client.get("/blacklists/customer@example.com", headers=headers)

    assert response.status_code == 200
    assert response.json == {
        "blacklisted": found,
        "blocked_reason": payload["blocked_reason"] if found else None,
    }
    session.scalar.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.parametrize("method,path", [
    ("post", "/blacklists"),
    ("get", "/blacklists/customer@example.com"),
])
def test_business_endpoints_require_token(client, session, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == 401
    session.add.assert_not_called()
    session.scalar.assert_not_called()


def test_health_returns_200_when_database_responds(client, session):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok", "version": "unit-test"}
    session.execute.assert_called_once()


def test_health_returns_503_when_database_fails(client, session):
    session.execute.side_effect = SQLAlchemyError("Simulated database unavailable")

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json == {"status": "unavailable"}
    session.rollback.assert_called_once()
