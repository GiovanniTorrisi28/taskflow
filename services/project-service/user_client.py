import os

import requests

USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://user-service:5000")


def get_user(user_id):
    try:
        resp = requests.get(f"{USER_SERVICE_URL}/users/{user_id}", timeout=3)
    except requests.RequestException:
        return None
    return resp.json() if resp.status_code == 200 else None


def get_user_by_username(username):
    try:
        resp = requests.get(f"{USER_SERVICE_URL}/users/lookup", params={"username": username}, timeout=3)
    except requests.RequestException:
        return None
    return resp.json() if resp.status_code == 200 else None
