# app/__init__.py
from __future__ import annotations
from flask import Flask, g
from .extensions import init_app as init_extensions
from .config import Config
from .blueprints.ai import bp as ai_bp


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
    from .models import User, Category
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

    @app.cli.command("seed-categories")
    def seed_categories_command():
        """Seeds the database with a default set of categories."""

        default_categories = [
            {"group": "Housing & Utilities", "name": "Rent/Mortgage"},
            {"group": "Housing & Utilities", "name": "Utilities"},
            {"group": "Housing & Utilities", "name": "Internet/Phone"},
            {"group": "Housing & Utilities", "name": "Home Maintenance"},
            {"group": "Transportation", "name": "Fuel"},
            {"group": "Transportation", "name": "Public Transit/Rideshare"},
            {"group": "Transportation", "name": "Auto Maintenance/Repairs"},
            {"group": "Transportation", "name": "Insurance (Auto)"},
            {"group": "Food & Dining", "name": "Groceries"},
            {"group": "Food & Dining", "name": "Dining Out"},
            {"group": "Food & Dining", "name": "Coffee/Snacks"},
            {"group": "Personal & Lifestyle", "name": "Clothing"},
            {"group": "Personal & Lifestyle", "name": "Health & Fitness"},
            {"group": "Personal & Lifestyle", "name": "Subscriptions/Streaming"},
            {"group": "Personal & Lifestyle", "name": "Entertainment"},
            {"group": "Financial & Obligations", "name": "Loan Payments"},
            {"group": "Financial & Obligations", "name": "Credit Card Payments"},
            {"group": "Financial & Obligations", "name": "Insurance (Non-Auto)"},
            {"group": "Financial & Obligations", "name": "Bank Fees/Interest"},
            {"group": "Giving & Special", "name": "Gifts"},
            {"group": "Giving & Special", "name": "Donations"},
            {"group": "Work & Education", "name": "Professional Expenses"},
            {"group": "Work & Education", "name": "Education"},
            {"group": "Income", "name": "Salary/Wages"},
            {"group": "Income", "name": "Bonus/Commission"},
            {"group": "Income", "name": "Other Income"},
            {"group": "Savings & Investments", "name": "Emergency Fund"},
            {"group": "Savings & Investments", "name": "Retirement Contributions"},
            {"group": "Savings & Investments", "name": "Other Savings/Investments"},
        ]

        count = 0
        for cat_data in default_categories:
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
            click.echo("All default categories already exist. Nothing to seed.")

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