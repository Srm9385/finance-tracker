# manage_reset.py
from __future__ import annotations

import sys
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.extensions import db
from flask_migrate import upgrade


def main():
    app = create_app()
    with app.app_context():
        engine = db.engine
        insp = inspect(engine)

        try:
            # Before: show existing tables
            before_tables = insp.get_table_names(schema="public")
            print(f"[reset] Tables before reset ({len(before_tables)}): {before_tables}")

            # 1) Drop and recreate schema 'public'
            print("[reset] Dropping schema 'public' (CASCADE)…")
            db.session.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
            db.session.execute(text("CREATE SCHEMA public;"))
            # Optional but nice: ensure default privileges on schema
            db.session.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            # (If you use a dedicated DB role, also grant to it here.)
            db.session.commit()
            print("[reset] Schema 'public' recreated.")

            # 2) Run migrations fresh
            print("[reset] Running migrations to HEAD…")
            upgrade()
            print("[reset] Migrations complete.")

            # After: list tables again
            insp = inspect(engine)  # re-instantiate to refresh cache
            after_tables = insp.get_table_names(schema="public")
            print(f"[reset] Tables after reset ({len(after_tables)}): {after_tables}")

            if not after_tables:
                print("[reset] WARNING: no tables found after upgrade. "
                      "Check your migrations folder and Alembic configuration.", file=sys.stderr)

            print("[reset] Done ✅")

        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"[reset] ERROR: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()