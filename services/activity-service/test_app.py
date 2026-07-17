import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import jwt
import pytest

from app import create_app
from models import db


def make_token(user_id=1, username="mario"):
    return jwt.encode({"sub": user_id, "username": username}, os.environ["JWT_SECRET"], algorithm="HS256")


def auth_headers(user_id=1):
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as test_client:
        yield test_client


def test_health(client):
    assert client.get("/health").status_code == 200


def test_create_activity_without_auth(client):
    # /activities in scrittura è una chiamata interna service-to-service (project-service -> activity-service),
    # quindi non richiede token: chi la protegge è la rete interna del cluster, non l'API.
    resp = client.post(
        "/activities",
        json={"project_id": 1, "actor_id": 1, "type": "task_created", "payload": {"title": "x"}},
    )
    assert resp.status_code == 201


def test_create_activity_missing_field(client):
    resp = client.post("/activities", json={"project_id": 1, "actor_id": 1})
    assert resp.status_code == 400


def test_list_activities_requires_auth(client):
    resp = client.get("/activities?project_id=1")
    assert resp.status_code == 401


def test_list_activities_requires_project_id(client):
    resp = client.get("/activities", headers=auth_headers())
    assert resp.status_code == 400


def test_list_activities_requires_valid_project_id(client):
    resp = client.get("/activities?project_id=abc", headers=auth_headers())
    assert resp.status_code == 400


def test_create_and_list_activities(client):
    client.post("/activities", json={"project_id": 1, "actor_id": 1, "type": "task_created"})
    client.post("/activities", json={"project_id": 1, "actor_id": 1, "type": "status_changed"})
    client.post("/activities", json={"project_id": 2, "actor_id": 1, "type": "task_created"})

    resp = client.get("/activities?project_id=1", headers=auth_headers())
    assert resp.status_code == 200
    activities = resp.get_json()["activities"]
    assert len(activities) == 2
    assert activities[0]["type"] == "task_created"


def test_create_and_list_comments(client):
    resp = client.post("/comments/42", json={"body": "ciao a tutti"}, headers=auth_headers())
    assert resp.status_code == 201

    resp = client.get("/comments/42", headers=auth_headers())
    assert resp.status_code == 200
    comments = resp.get_json()["comments"]
    assert len(comments) == 1
    assert comments[0]["body"] == "ciao a tutti"


def test_create_comment_requires_body(client):
    resp = client.post("/comments/42", json={"body": "  "}, headers=auth_headers())
    assert resp.status_code == 400
