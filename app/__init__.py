# srm9385/finance-tracker/finance-tracker-b6479a0b9b4b550a18703e80c76c724f6985583c/app/__init__.py
# app/__init__.py
from __future__ import annotations
from flask import Flask, g
from .extensions import init_app as init_extensions
from .config import Config
from .blueprints.ai import bp as ai_bp
from .blueprints.backup import bp as backup_bp
# --- START MODIFICATION ---
import os
import json
# --- END MODIFICATION ---


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
    from .models import User, Category, Rule
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
    app.register_blueprint(ai_bp)
    app.register_blueprint(backup_bp, url_prefix="/admin/backup")

    # --- START MODIFICATION ---
    @app.cli.command("seed-categories")
    def seed_categories_command():
        """Seeds categories from the DEFAULT_CATEGORIES_JSON env var."""
        categories_json = os.getenv("DEFAULT_CATEGORIES_JSON")

        if not categories_json:
            click.echo("Warning: DEFAULT_CATEGORIES_JSON environment variable not set. No categories seeded.")
            return

        try:
            default_categories = json.loads(categories_json)
            if not isinstance(default_categories, list):
                raise ValueError("JSON must be an array of category objects.")
        except (json.JSONDecodeError, ValueError) as e:
            click.echo(f"Error: Could not parse DEFAULT_CATEGORIES_JSON. Please ensure it is a valid JSON array. Details: {e}")
            return

        count = 0
        for cat_data in default_categories:
            # Basic validation for each category object
            if not isinstance(cat_data, dict) or "group" not in cat_data or "name" not in cat_data:
                click.echo(f"Warning: Skipping invalid category entry: {cat_data}")
                continue

            # Check if a category with this name already exists
            exists = Category.query.filter_by(name=cat_data["name"]).first()
            if not exists:
                new_cat = Category(group=cat_data["group"], name=cat_data["name"])
                db.session.add(new_cat)
                count += 1

        if count > 0:
            db.session.commit()
            click.echo(f"Successfully seeded {count} new categories.")
        else:
            click.echo("All categories from the environment variable already exist. Nothing to seed.")

    @app.cli.command("seed-rules")
    def seed_rules_command():
        """Seeds categorization rules from the DEFAULT_RULES_JSON env var."""
        rules_json = os.getenv("DEFAULT_RULES_JSON")

        if not rules_json:
            click.echo("Warning: DEFAULT_RULES_JSON not set. No rules seeded.")
            return

        try:
            default_rules = json.loads(rules_json)
            if not isinstance(default_rules, dict):
                raise ValueError("JSON must be an object.")
        except (json.JSONDecodeError, ValueError) as e:
            click.echo(f"Error: Could not parse DEFAULT_RULES_JSON. Details: {e}")
            return

        # Fetch all existing categories and rules for efficiency
        all_categories = {c.name: c for c in Category.query.all()}
        existing_rules = {r.keyword for r in Rule.query.all()}

        count = 0
        for category_name, keywords in default_rules.items():
            if category_name not in all_categories:
                click.echo(f"Warning: Category '{category_name}' not found. Skipping rules: {keywords}")
                continue

            category = all_categories[category_name]

            if not isinstance(keywords, list):
                click.echo(f"Warning: Keywords for '{category_name}' is not a list. Skipping.")
                continue

            for keyword in keywords:
                if keyword not in existing_rules:
                    new_rule = Rule(keyword=keyword, category_id=category.id)
                    db.session.add(new_rule)
                    existing_rules.add(keyword)  # Add to our set to prevent re-adding
                    count += 1

        if count > 0:
            db.session.commit()
            click.echo(f"Successfully seeded {count} new rules.")
        else:
            click.echo("All rules from the environment variable already exist.")

    # Root redirect
    @app.route("/")
    def _root():
        from flask import redirect, url_for
        return redirect(url_for("dashboard.index"))

    @app.before_request
    def before_request():
        from .services.ai_categorizer import is_ai_configured
        g.ai_configured = is_ai_configured()

    return app