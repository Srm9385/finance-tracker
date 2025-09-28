# app/__init__.py
from __future__ import annotations

from flask import Flask
from .extensions import init_app as init_extensions
from .config import Config  # your Config loads .env (via find_dotenv/load_dotenv as we fixed earlier)


def create_app() -> Flask:
    app = Flask(__name__)

    # Load configuration (Config should read .env before evaluating attributes)
    app.config.from_object(Config())

    # Bind extensions (DB, Migrate, LoginManager, CSRF, etc.)
    init_extensions(app)

    # Register blueprints
    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.imports import bp as imports_bp
    from .blueprints.transactions import bp as transactions_bp  # you added this
    from .blueprints.auth import bp as auth_bp                  # if present

    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(imports_bp, url_prefix="/imports")
    app.register_blueprint(transactions_bp)  # already has url_prefix="/transactions"
    app.register_blueprint(auth_bp, url_prefix="/auth")        # if present

    # Root redirect (optional): send "/" to dashboard
    @app.route("/")
    def _root():
        from flask import redirect, url_for
        return redirect(url_for("dashboard.index"))

    return app
