import os

from flask import Flask, request

from auth import get_authenticated_user_id
from models import Activity, Comment, db


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

    @app.post("/activities")
    def create_activity():
        data = request.get_json(force=True)
        for field in ("project_id", "actor_id", "type"):
            if not data.get(field):
                return {"error": f"{field} è obbligatorio"}, 400

        activity = Activity(
            project_id=data["project_id"],
            task_id=data.get("task_id"),
            actor_id=data["actor_id"],
            type=data["type"],
            payload=data.get("payload", {}),
        )
        db.session.add(activity)
        db.session.commit()
        return activity.to_dict(), 201

    @app.get("/activities")
    def list_activities():
        _, err = get_authenticated_user_id(request)
        if err:
            return err
        project_id_raw = request.args.get("project_id")
        if not project_id_raw:
            return {"error": "project_id è obbligatorio come query param"}, 400
        try:
            project_id = int(project_id_raw)
        except ValueError:
            return {"error": "project_id deve essere un intero"}, 400

        activities = Activity.query.filter_by(project_id=project_id).order_by(Activity.timestamp.asc()).all()
        return {"activities": [a.to_dict() for a in activities]}

    @app.post("/comments/<int:task_id>")
    def create_comment(task_id):
        user_id, err = get_authenticated_user_id(request)
        if err:
            return err
        data = request.get_json(force=True)
        body = (data.get("body") or "").strip()
        if not body:
            return {"error": "body è obbligatorio"}, 400

        comment = Comment(task_id=task_id, author_id=user_id, body=body)
        db.session.add(comment)
        db.session.commit()
        return comment.to_dict(), 201

    @app.get("/comments/<int:task_id>")
    def list_comments(task_id):
        _, err = get_authenticated_user_id(request)
        if err:
            return err
        comments = Comment.query.filter_by(task_id=task_id).order_by(Comment.timestamp.asc()).all()
        return {"comments": [c.to_dict() for c in comments]}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
