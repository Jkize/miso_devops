"""Opt-in verification against the migrated local PostgreSQL database."""
import os
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

from blacklist_service import create_app
from blacklist_service.extensions import db
from blacklist_service.models import BlacklistEntry


@pytest.mark.skipif(os.getenv("TEST_POSTGRES") != "1", reason="Set TEST_POSTGRES=1 for PostgreSQL integration")
def test_postgres_persists_between_app_instances():
    app = create_app()
    assert db_uri_is_postgres(app)
    email = f"integration-{uuid4()}@example.com"
    app_uuid = uuid4()
    with app.app_context():
        token = create_access_token(identity="integration")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = app.test_client().post("/blacklists", headers=headers, json={
            "email": email, "app_uuid": str(app_uuid), "blocked_reason": "Integration test",
        }, environ_base={"REMOTE_ADDR": "203.0.113.20"})
        assert response.status_code == 201
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        restarted_app = create_app()
        response = restarted_app.test_client().get(f"/blacklists/{email}", headers=headers)
        assert response.status_code == 200
        assert response.json == {"blacklisted": True, "blocked_reason": "Integration test"}
        with restarted_app.app_context():
            entry = db.session.scalar(db.select(BlacklistEntry).filter_by(email=email))
            assert entry.app_uuid == app_uuid
            assert entry.source_ip == "203.0.113.20"
            assert entry.created_at.utcoffset().total_seconds() == 0
    finally:
        with app.app_context():
            db.session.execute(db.delete(BlacklistEntry).where(BlacklistEntry.email == email))
            db.session.commit()
            db.session.remove()
            db.engine.dispose()


def db_uri_is_postgres(app):
    with app.app_context():
        return db.engine.dialect.name == "postgresql"
