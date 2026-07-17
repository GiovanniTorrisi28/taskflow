import os

import requests

ACTIVITY_SERVICE_URL = os.environ.get("ACTIVITY_SERVICE_URL", "http://activity-service:5000")


def log_activity(project_id, actor_id, event_type, payload=None, task_id=None):
    body = {
        "project_id": project_id,
        "task_id": task_id,
        "actor_id": actor_id,
        "type": event_type,
        "payload": payload or {},
    }
    try:
        requests.post(f"{ACTIVITY_SERVICE_URL}/activities", json=body, timeout=3)
    except requests.RequestException:
        # il log attività è un effetto collaterale: non deve mai far fallire l'operazione sul task
        pass
