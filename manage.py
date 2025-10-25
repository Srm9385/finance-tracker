import click
from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

@app.cli.command("seed")
def seed():
    """Seed a dev admin user: admin/admin"""
    print("Seeding")
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(username="admin", password_hash=generate_password_hash("admin")))
            db.session.commit()
            click.echo("Seeded admin/admin")
        else:
            click.echo("Admin user already exists")
