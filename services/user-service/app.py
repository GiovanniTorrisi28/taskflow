import os

from flask import Flask, request
from werkzeug.security import check_password_hash, generate_password_hash

from auth import create_token, get_authenticated_user_id
from models import User, db


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/register")
    def register():
        data = request.get_json(force=True)
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip()
        password = data.get("password") or ""
        if not username or not email or not password:
            return {"error": "username, email e password sono obbligatori"}, 400

        exists = User.query.filter((User.username == username) | (User.email == email)).first()
        if exists:
            return {"error": "username o email già in uso"}, 409

        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return user.to_dict(), 201

    @app.post("/login")
    def login():
        data = request.get_json(force=True)
        username = data.get("username") or ""
        password = data.get("password") or ""

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return {"error": "credenziali non valide"}, 401

        token = create_token(user.id, user.username)
        return {"token": token, "user": user.to_dict()}

    @app.get("/users/me")
    def get_me():
        user_id, err = get_authenticated_user_id(request)
        if err:
            return err
        user = db.session.get(User, user_id)
        if not user:
            return {"error": "utente non trovato"}, 404
        return user.to_dict()

    @app.get("/users/<int:user_id>")
    def get_user(user_id):
        # profilo pubblico: usato da altri servizi (es. project-service) per risolvere un user_id
        # in un nome visualizzabile, senza richiedere un token di quell'utente specifico.
        user = db.session.get(User, user_id)
        if not user:
            return {"error": "utente non trovato"}, 404
        return user.to_public_dict()

    @app.get("/users/lookup")
    def lookup_user():
        username = request.args.get("username", "")
        if not username:
            return {"error": "username è obbligatorio come query param"}, 400
        user = User.query.filter_by(username=username).first()
        if not user:
            return {"error": "utente non trovato"}, 404
        return user.to_public_dict()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
