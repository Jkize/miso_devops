import pytest
from flask_jwt_extended import create_access_token

from blacklist_service import create_app
from blacklist_service.extensions import db


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "test-only-secret-with-at-least-32-bytes",
        "TRUSTED_PROXY_HOPS": 0,
    })
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def headers(app):
    with app.app_context():
        token = create_access_token(identity="tests")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def payload():
    return {
        "email": "customer@example.com",
        "app_uuid": "94b8097c-e7ab-4e50-9035-eabda6514e81",
        "blocked_reason": "Solicitud del cliente",
    }
