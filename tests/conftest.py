import pytest

from app import create_app
from app.models import db

VALID = {
    "roll_number": "CSA2026099",
    "name": "Test Student",
    "email": "test@example.edu",
    "course": "Cloud Computing",
    "year": 2,
}


@pytest.fixture()
def make_app():
    apps = []

    def factory(**overrides):
        config = {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "APP_VERSION": "test-123",
        }
        config.update(overrides)
        app = create_app(config)
        apps.append(app)
        return app

    yield factory
    for app in apps:
        with app.app_context():
            db.drop_all()
            db.session.remove()
            db.engine.dispose()


@pytest.fixture()
def seeded_app(make_app):
    return make_app()


@pytest.fixture()
def seeded(seeded_app):
    return seeded_app.test_client()


@pytest.fixture()
def empty(make_app):
    return make_app(SEED_DATA=False).test_client()
