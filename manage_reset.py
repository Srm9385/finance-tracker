# manage_reset.py
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path  # ADDED: For cleaner path manipulation
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db


def main():
    """Drops/recreates schema, then runs 'flask db upgrade' using the correct virtualenv executable."""

    if not os.getenv("DATABASE_URL"):
        print("[reset] ERROR: DATABASE_URL not found. Ensure .env file is correct.", file=sys.stderr)
        sys.exit(1)

    # --- START: The key fix for the silent failure ---
    # Find the absolute path to the python interpreter running this script
    python_executable = Path(sys.executable)
    # The 'flask' executable is in the same directory (e.g., .venv/bin/)
    flask_executable = python_executable.parent / "flask"

    if not flask_executable.is_file():
        print(f"[reset] ERROR: Cannot find flask executable at {flask_executable}", file=sys.stderr)
        print("[reset] Please ensure you are running this script from within your activated virtual environment.",
              file=sys.stderr)
        sys.exit(1)

    print(f"[reset] Using flask executable: {flask_executable}")
    # --- END: The key fix ---

    app = create_app()
    with app.app_context():
        engine = db.engine
        insp = inspect(engine)

        try:
            before_tables = insp.get_table_names(schema="public")
            print(f"[reset] Tables before reset ({len(before_tables)}): {before_tables}")

            print("[reset] Dropping schema 'public' (CASCADE)…")
            db.session.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
            db.session.execute(text("CREATE SCHEMA public;"))
            db.session.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            db.session.commit()
            print("[reset] Schema 'public' recreated.")

            print(f"[reset] Running '{flask_executable} db upgrade'…")
            # MODIFIED: Use the absolute path to the flask executable
            result = subprocess.run(
                [str(flask_executable), "db", "upgrade"],
                capture_output=True,
                text=True,
                env=os.environ
            )

            if result.returncode != 0:
                print("[reset] ERROR: flask db upgrade failed.", file=sys.stderr)
                print("\n--- STDOUT ---", file=sys.stderr)
                print(result.stdout, file=sys.stderr)
                print("\n--- STDERR ---", file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                sys.exit(1)

            print("--- Command STDOUT ---")
            print(result.stdout)
            if result.stderr:
                print("--- Command STDERR (contains INFO logs) ---")
                print(result.stderr)

            print("[reset] Migrations complete.")

            insp = inspect(engine)
            after_tables = insp.get_table_names(schema="public")
            print(f"[reset] Tables after reset ({len(after_tables)}): {after_tables}")

            if 'accounts' not in after_tables:
                print("[reset] CRITICAL WARNING: 'accounts' table not found after upgrade!", file=sys.stderr)

            print("[reset] Done ✅")

        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"[reset] ERROR during DB operation: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()