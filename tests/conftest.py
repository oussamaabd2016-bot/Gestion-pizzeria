import pytest

from app import create_app
from app.extensions import db
from app.models import Role, User


class TestConfig:
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def user(app):
    user = User(nom="Caissier", email="cash@test.local", role=Role.CAISSIER)
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()
    return user
