# app/__init__.py
from __future__ import annotations

from flask import Flask
from .extensions import init_app as init_extensions
from .config import Config


def create_app() -> Flask:
    """Application factory function."""
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config())

    # Bind extensions (DB, Migrate, LoginManager, CSRF, etc.)
    init_extensions(app)

    # --- START: Register CLI Commands ---
    # By defining commands here, they are attached to the app instance
    # and become available to the 'flask' command-line tool.
    from .extensions import db
    from .models import User
    from werkzeug.security import generate_password_hash
    import click

    @app.cli.command("seed")
    def seed_command():
        """Seeds the database with a default admin user."""
        if User.query.filter_by(username="admin").first():
            click.echo("Admin user already exists. Skipping seed.")
            return

        hashed_password = generate_password_hash("admin")
        admin_user = User(username="admin", password_hash=hashed_password)
        db.session.add(admin_user)
        db.session.commit()
        click.echo("Successfully seeded admin user (admin/admin).")
    # --- END: Register CLI Commands ---

    # Register blueprints for web routes
    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.imports import bp as imports_bp
    from .blueprints.transactions import bp as transactions_bp
    from .blueprints.auth import bp as auth_bp

    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(imports_bp, url_prefix="/imports")
    app.register_blueprint(transactions_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")

    # Root redirect
    @app.route("/")
    def _root():
        from flask import redirect, url_for
        return redirect(url_for("dashboard.index"))

    return app