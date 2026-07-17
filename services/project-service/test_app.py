import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ACTIVITY_SERVICE_URL", "http://activity-service-test:5000")

import jwt
import pytest

from app import create_app
from models import db


def make_token(user_id=1, username="mario"):
    return jwt.encode({"sub": user_id, "username": username}, os.environ["JWT_SECRET"], algorithm="HS256")


def auth_headers(user_id=1):
    return {"Authorization": f"Bearer {make_token(user_id)}"}


FAKE_USERS = {1: "mario", 2: "luigi", 3: "peach"}


def fake_get_user(user_id):
    username = FAKE_USERS.get(user_id)
    return {"id": user_id, "username": username} if username else None


def fake_get_user_by_username(username):
    for user_id, existing_username in FAKE_USERS.items():
        if existing_username == username:
            return {"id": user_id, "username": username}
    return None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.log_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.get_user", fake_get_user)
    monkeypatch.setattr("app.get_user_by_username", fake_get_user_by_username)
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as test_client:
        yield test_client


def test_health(client):
    assert client.get("/health").status_code == 200


def test_create_project_requires_auth(client):
    resp = client.post("/projects", json={"name": "Progetto Test"})
    assert resp.status_code == 401


def test_create_and_list_project(client):
    resp = client.post("/projects", json={"name": "Progetto Test"}, headers=auth_headers())
    assert resp.status_code == 201
    project_id = resp.get_json()["id"]

    resp = client.get("/projects", headers=auth_headers())
    assert resp.status_code == 200
    assert len(resp.get_json()["projects"]) == 1

    resp = client.get(f"/projects/{project_id}", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Progetto Test"


def test_list_projects_only_shows_member_projects(client):
    client.post("/projects", json={"name": "Progetto di Mario"}, headers=auth_headers(user_id=1))
    client.post("/projects", json={"name": "Progetto di Luigi"}, headers=auth_headers(user_id=2))

    resp = client.get("/projects", headers=auth_headers(user_id=1))
    projects = resp.get_json()["projects"]
    assert len(projects) == 1
    assert projects[0]["name"] == "Progetto di Mario"


def test_add_member(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers()).get_json()
    resp = client.post(f"/projects/{project['id']}/members", json={"user_id": 2}, headers=auth_headers())
    assert resp.status_code == 201

    resp = client.post(f"/projects/{project['id']}/members", json={"user_id": 2}, headers=auth_headers())
    assert resp.status_code == 409


def test_add_member_by_username(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers()).get_json()
    resp = client.post(f"/projects/{project['id']}/members", json={"username": "peach"}, headers=auth_headers())
    assert resp.status_code == 201
    assert resp.get_json()["user_id"] == 3


def test_add_member_unknown_username(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers()).get_json()
    resp = client.post(f"/projects/{project['id']}/members", json={"username": "nonexistent"}, headers=auth_headers())
    assert resp.status_code == 404


def test_add_member_requires_owner(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers(user_id=1)).get_json()
    resp = client.post(
        f"/projects/{project['id']}/members", json={"user_id": 3}, headers=auth_headers(user_id=2)
    )
    assert resp.status_code == 403


def test_list_members(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers(user_id=1)).get_json()
    client.post(f"/projects/{project['id']}/members", json={"user_id": 2}, headers=auth_headers(user_id=1))

    resp = client.get(f"/projects/{project['id']}/members", headers=auth_headers(user_id=1))
    assert resp.status_code == 200
    members = resp.get_json()["members"]
    assert len(members) == 2
    roles = {m["user_id"]: m["role"] for m in members}
    assert roles[1] == "owner"
    assert roles[2] == "member"
    usernames = {m["user_id"]: m["username"] for m in members}
    assert usernames[2] == "luigi"


def test_remove_member(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers(user_id=1)).get_json()
    client.post(f"/projects/{project['id']}/members", json={"user_id": 2}, headers=auth_headers(user_id=1))

    resp = client.delete(f"/projects/{project['id']}/members/2", headers=auth_headers(user_id=1))
    assert resp.status_code == 204

    resp = client.get(f"/projects/{project['id']}/members", headers=auth_headers(user_id=1))
    assert len(resp.get_json()["members"]) == 1


def test_cannot_remove_owner(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers(user_id=1)).get_json()
    resp = client.delete(f"/projects/{project['id']}/members/1", headers=auth_headers(user_id=1))
    assert resp.status_code == 400


def test_remove_member_requires_owner(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers(user_id=1)).get_json()
    client.post(f"/projects/{project['id']}/members", json={"user_id": 2}, headers=auth_headers(user_id=1))

    resp = client.delete(f"/projects/{project['id']}/members/2", headers=auth_headers(user_id=2))
    assert resp.status_code == 403


def test_remove_nonexistent_member(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers(user_id=1)).get_json()
    resp = client.delete(f"/projects/{project['id']}/members/999", headers=auth_headers(user_id=1))
    assert resp.status_code == 404


def test_create_and_update_task(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers()).get_json()

    resp = client.post(f"/projects/{project['id']}/tasks", json={"title": "Fai qualcosa"}, headers=auth_headers())
    assert resp.status_code == 201
    task = resp.get_json()
    assert task["status"] == "todo"

    resp = client.patch(f"/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_headers())
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "in_progress"

    resp = client.patch(f"/tasks/{task['id']}", json={"status": "invalid"}, headers=auth_headers())
    assert resp.status_code == 400

    resp = client.get(f"/projects/{project['id']}/tasks", headers=auth_headers())
    assert len(resp.get_json()["tasks"]) == 1


def test_update_task_assignee(client):
    project = client.post("/projects", json={"name": "P"}, headers=auth_headers()).get_json()
    task = client.post(
        f"/projects/{project['id']}/tasks", json={"title": "Fai qualcosa"}, headers=auth_headers()
    ).get_json()
    assert task["assignee_id"] is None

    resp = client.patch(f"/tasks/{task['id']}", json={"assignee_id": 2}, headers=auth_headers())
    assert resp.status_code == 200
    assert resp.get_json()["assignee_id"] == 2

    resp = client.patch(f"/tasks/{task['id']}", json={"assignee_id": None}, headers=auth_headers())
    assert resp.status_code == 200
    assert resp.get_json()["assignee_id"] is None


def test_update_nonexistent_task(client):
    resp = client.patch("/tasks/999", json={"status": "done"}, headers=auth_headers())
    assert resp.status_code == 404
