"""HTTP unit tests: real routing/JWT/validation, mocked persistence, no database I/O."""
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event

from blacklist_service import create_app
from blacklist_service.extensions import db


@pytest.fixture
def session():
    return MagicMock(spec=["add", "commit", "rollback", "scalar", "execute", "remove"])


@pytest.fixture
def app(monkeypatch, session):
    # Do not load local credentials, create tables or use the parent SQLite fixture.
    monkeypatch.setattr("blacklist_service.load_dotenv", lambda: None)
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "0")
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "unit-test-only-secret-at-least-32-bytes",
        "APP_VERSION": "unit-test",
        "TRUSTED_PROXY_HOPS": 0,
    })
    with app.app_context():
        engine = db.engine

    def forbid_connection(*args, **kwargs):
        raise AssertionError("Unit tests must not open a database connection")

    event.listen(engine, "do_connect", forbid_connection)
    monkeypatch.setattr(db, "session", session)
    yield app
    engine.dispose()
