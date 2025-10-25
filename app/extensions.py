# app/extensions.py
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Instantiate extensions (no app bound yet)
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

# Optional: tweak login behaviour
login_manager.login_view = "auth.login"           # where to redirect when auth is required
login_manager.login_message = "Please log in."
login_manager.login_message_category = "info"


def init_app(app):
    """
    Bind extensions to the Flask app.
    Call this once from your app factory (create_app).
    """
    # Initialize each extension with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)   # <-- enables CSRF on all POST/PUT/PATCH/DELETE routes

    # Defer user loader import to avoid circular imports
    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))
