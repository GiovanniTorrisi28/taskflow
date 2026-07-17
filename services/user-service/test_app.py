import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest

from app import create_app
from models import db


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as test_client:
        yield test_client


def register(client, username="mario", email="mario@test.it", password="secret123"):
    return client.post("/register", json={"username": username, "email": email, "password": password})


def test_health(client):
    assert client.get("/health").status_code == 200


def test_register_and_login(client):
    resp = register(client)
    assert resp.status_code == 201
    assert resp.get_json()["username"] == "mario"

    resp = client.post("/login", json={"username": "mario", "password": "secret123"})
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_register_missing_fields(client):
    resp = client.post("/register", json={"username": "mario"})
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register(client, username="luigi", email="luigi@test.it")
    resp = register(client, username="luigi", email="altra@test.it")
    assert resp.status_code == 409


def test_login_wrong_password(client):
    register(client, username="peach", email="peach@test.it")
    resp = client.post("/login", json={"username": "peach", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/users/me").status_code == 401


def test_me_with_valid_token(client):
    register(client, username="yoshi", email="yoshi@test.it")
    login = client.post("/login", json={"username": "yoshi", "password": "secret123"}).get_json()

    resp = client.get("/users/me", headers={"Authorization": f"Bearer {login['token']}"})
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "yoshi"


def test_me_with_invalid_token(client):
    resp = client.get("/users/me", headers={"Authorization": "Bearer invalid-token"})
    assert resp.status_code == 401


def test_get_user_public_profile_has_no_email(client):
    created = register(client, username="bowser", email="bowser@test.it").get_json()

    resp = client.get(f"/users/{created['id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "bowser"
    assert "email" not in data


def test_get_user_not_found(client):
    resp = client.get("/users/999")
    assert resp.status_code == 404


def test_lookup_user_by_username(client):
    register(client, username="toad", email="toad@test.it")

    resp = client.get("/users/lookup?username=toad")
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "toad"
    assert "email" not in resp.get_json()


def test_lookup_user_not_found(client):
    resp = client.get("/users/lookup?username=nonexistent")
    assert resp.status_code == 404


def test_lookup_user_missing_query_param(client):
    resp = client.get("/users/lookup")
    assert resp.status_code == 400
