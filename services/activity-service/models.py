from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False, index=True)
    task_id = db.Column(db.Integer, nullable=True)
    actor_id = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.JSON, default=dict)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "actor_id": self.actor_id,
            "type": self.type,
            "payload": self.payload or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, nullable=False, index=True)
    author_id = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "author_id": self.author_id,
            "body": self.body,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
