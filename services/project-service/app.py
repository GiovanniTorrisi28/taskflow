import os

from flask import Flask, request

from activity_client import log_activity
from auth import get_authenticated_user_id
from models import TASK_STATUSES, Project, ProjectMember, Task, db
from user_client import get_user, get_user_by_username


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # testa ogni connessione presa dal pool con un ping leggero prima di usarla: senza questo,
    # una connessione lasciata inattiva troppo a lungo (tipico con RDS) fallisce con un errore
    # SSL sul primo utilizzo invece di essere trasparentemente sostituita
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/projects")
    def create_project():
        user_id, err = get_authenticated_user_id(request)
        if err:
            return err
        data = request.get_json(force=True)
        name = (data.get("name") or "").strip()
        if not name:
            return {"error": "name è obbligatorio"}, 400

        project = Project(name=name, description=data.get("description", ""), owner_id=user_id)
        db.session.add(project)
        db.session.flush()
        db.session.add(ProjectMember(project_id=project.id, user_id=user_id, role="owner"))
        db.session.commit()
        return project.to_dict(), 201

    @app.get("/projects")
    def list_projects():
        user_id, err = get_authenticated_user_id(request)
        if err:
            return err
        project_ids = [m.project_id for m in ProjectMember.query.filter_by(user_id=user_id)]
        projects = Project.query.filter(Project.id.in_(project_ids)).all()
        return {"projects": [p.to_dict() for p in projects]}

    @app.get("/projects/<int:project_id>")
    def get_project(project_id):
        _, err = get_authenticated_user_id(request)
        if err:
            return err
        project = db.session.get(Project, project_id)
        if not project:
            return {"error": "progetto non trovato"}, 404
        return project.to_dict()

    @app.get("/projects/<int:project_id>/members")
    def list_members(project_id):
        _, err = get_authenticated_user_id(request)
        if err:
            return err
        if not db.session.get(Project, project_id):
            return {"error": "progetto non trovato"}, 404

        members = ProjectMember.query.filter_by(project_id=project_id).all()
        enriched = []
        for member in members:
            user = get_user(member.user_id)
            enriched.append(
                {
                    "user_id": member.user_id,
                    "role": member.role,
                    "username": user["username"] if user else None,
                }
            )
        return {"members": enriched}

    @app.post("/projects/<int:project_id>/members")
    def add_member(project_id):
        user_id, err = get_authenticated_user_id(request)
        if err:
            return err
        project = db.session.get(Project, project_id)
        if not project:
            return {"error": "progetto non trovato"}, 404
        if project.owner_id != user_id:
            return {"error": "solo il proprietario può gestire i membri del progetto"}, 403

        data = request.get_json(force=True)
        new_user_id = data.get("user_id")
        username = data.get("username")
        if not new_user_id and username:
            user = get_user_by_username(username)
            if not user:
                return {"error": "utente non trovato"}, 404
            new_user_id = user["id"]
        if not new_user_id:
            return {"error": "user_id o username è obbligatorio"}, 400

        exists = ProjectMember.query.filter_by(project_id=project_id, user_id=new_user_id).first()
        if exists:
            return {"error": "utente già membro del progetto"}, 409

        member = ProjectMember(project_id=project_id, user_id=new_user_id, role="member")
        db.session.add(member)
        db.session.commit()
        return member.to_dict(), 201

    @app.delete("/projects/<int:project_id>/members/<int:member_user_id>")
    def remove_member(project_id, member_user_id):
        user_id, err = get_authenticated_user_id(request)
        if err:
            return err
        project = db.session.get(Project, project_id)
        if not project:
            return {"error": "progetto non trovato"}, 404
        if project.owner_id != user_id:
            return {"error": "solo il proprietario può gestire i membri del progetto"}, 403
        if project.owner_id == member_user_id:
            return {"error": "non puoi rimuovere il proprietario del progetto"}, 400

        member = ProjectMember.query.filter_by(project_id=project_id, user_id=member_user_id).first()
        if not member:
            return {"error": "utente non è membro del progetto"}, 404

        db.session.delete(member)
        db.session.commit()
        return "", 204

    @app.get("/projects/<int:project_id>/tasks")
    def list_tasks(project_id):
        _, err = get_authenticated_user_id(request)
        if err:
            return err
        tasks = Task.query.filter_by(project_id=project_id).all()
        return {"tasks": [t.to_dict() for t in tasks]}

    @app.post("/projects/<int:project_id>/tasks")
    def create_task(project_id):
        user_id, err = get_authenticated_user_id(request)
        if err:
            return err
        if not db.session.get(Project, project_id):
            return {"error": "progetto non trovato"}, 404

        data = request.get_json(force=True)
        title = (data.get("title") or "").strip()
        if not title:
            return {"error": "title è obbligatorio"}, 400

        task = Task(
            project_id=project_id,
            title=title,
            description=data.get("description", ""),
            assignee_id=data.get("assignee_id"),
        )
        db.session.add(task)
        db.session.commit()

        log_activity(project_id, user_id, "task_created", {"task_id": task.id, "title": task.title}, task_id=task.id)
        return task.to_dict(), 201

    @app.patch("/tasks/<int:task_id>")
    def update_task(task_id):
        user_id, err = get_authenticated_user_id(request)
        if err:
            return err
        task = db.session.get(Task, task_id)
        if not task:
            return {"error": "task non trovato"}, 404

        data = request.get_json(force=True)
        if "status" in data:
            if data["status"] not in TASK_STATUSES:
                return {"error": f"status deve essere uno tra {TASK_STATUSES}"}, 400
            old_status = task.status
            task.status = data["status"]
            if old_status != task.status:
                log_activity(
                    task.project_id,
                    user_id,
                    "status_changed",
                    {"task_id": task.id, "from": old_status, "to": task.status},
                    task_id=task.id,
                )
        if "assignee_id" in data:
            old_assignee_id = task.assignee_id
            task.assignee_id = data["assignee_id"]
            if old_assignee_id != task.assignee_id:
                log_activity(
                    task.project_id,
                    user_id,
                    "assignee_changed",
                    {"task_id": task.id, "from": old_assignee_id, "to": task.assignee_id},
                    task_id=task.id,
                )
        if "title" in data:
            task.title = data["title"]
        if "description" in data:
            task.description = data["description"]

        db.session.commit()
        return task.to_dict()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
