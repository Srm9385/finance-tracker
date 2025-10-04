# srm9385/finance-tracker/finance-tracker-b6479a0b9b4b550a18703e80c76c724f6985583c/app/blueprints/backup.py
import os
import subprocess
import tempfile
import tarfile
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, send_from_directory)
from werkzeug.utils import secure_filename
from ..forms import RestoreForm

bp = Blueprint("backup", __name__, url_prefix="/backup")


def get_db_connection_args():
    # (This helper function remains the same)
    db_url = current_app.config["SQLALCHEMY_DATABASE_URI"]
    try:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        return {"user": parsed.username, "password": parsed.password, "host": parsed.hostname,
                "port": str(parsed.port or 5432), "dbname": parsed.path.lstrip('/')}
    except Exception as e:
        flash(f"Could not parse DATABASE_URL: {e}", "error")
        return None


@bp.route("/", methods=["GET", "POST"])
def index():
    form = RestoreForm()
    if form.validate_on_submit():
        file = form.backup_file.data
        filename = secure_filename(file.filename)

        if not filename.endswith(".tar.gz"):
            flash("Invalid file type. Please upload a .tar.gz file.", "error")
            return redirect(url_for(".index"))

        conn_args = get_db_connection_args()
        if not conn_args:
            return redirect(url_for(".index"))

        # --- START MODIFICATION: Handle tar.gz extraction ---
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_archive_path = os.path.join(temp_dir, filename)
            file.save(temp_archive_path)

            try:
                # Extract the archive
                with tarfile.open(temp_archive_path, "r:gz") as tar:
                    # Look for the .sql file within the archive
                    sql_file_member = next((m for m in tar.getmembers() if m.name.endswith(".sql")), None)
                    if not sql_file_member:
                        raise ValueError("No .sql file found in the backup archive.")

                    tar.extract(sql_file_member, path=temp_dir)
                    temp_sql_path = os.path.join(temp_dir, sql_file_member.name)

                # Restore the database from the extracted .sql file
                psql_cmd = ["psql", "-h", conn_args["host"], "-p", conn_args["port"],
                            "-U", conn_args["user"], "-d", conn_args["dbname"], "-f", temp_sql_path]

                env = os.environ.copy()
                env["PGPASSWORD"] = conn_args["password"]

                subprocess.run(psql_cmd, env=env, capture_output=True, text=True, check=True)

                flash("Database restored successfully.", "success")
                flash(
                    "IMPORTANT: Remember to manually place the .env file from your backup and restart the application.",
                    "info")

            except subprocess.CalledProcessError as e:
                flash("An error occurred during the database restore.", "error")
                flash(f"STDERR: {e.stderr}", "error")
            except Exception as e:
                flash(f"An unexpected error occurred: {e}", "error")
        # --- END MODIFICATION ---

        return redirect(url_for(".index"))

    return render_template("admin/backup.html", form=form)


@bp.route("/create")
def create_backup():
    conn_args = get_db_connection_args()
    if not conn_args:
        return redirect(url_for(".index"))

    backup_dir = current_app.config["BACKUP_DIR"]
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # --- START MODIFICATION: Handle tar.gz creation ---
    archive_filename = f"financetracker_backup_{timestamp}.tar.gz"
    archive_filepath = os.path.join(backup_dir, archive_filename)

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 1. Dump the database to a .sql file inside the temp directory
            sql_filename = f"database_{timestamp}.sql"
            sql_filepath = os.path.join(temp_dir, sql_filename)

            pgdump_cmd = ["pg_dump", "-h", conn_args["host"], "-p", conn_args["port"],
                          "-U", conn_args["user"], "-d", conn_args["dbname"],
                          "--exclude-table=alembic_version",
                          "--clean", "--if-exists", "-f", sql_filepath]

            env = os.environ.copy()
            env["PGPASSWORD"] = conn_args["password"]

            subprocess.run(pgdump_cmd, env=env, check=True)

            # 2. Copy the .env file into the temp directory
            env_filepath = os.path.join(current_app.root_path, '..', '.env')
            if os.path.exists(env_filepath):
                subprocess.run(["cp", env_filepath, temp_dir])

            # 3. Create the tar.gz archive from the temp directory's contents
            with tarfile.open(archive_filepath, "w:gz") as tar:
                tar.add(temp_dir, arcname=os.path.basename(f"backup_{timestamp}"))

            flash(f"Backup archive created: {archive_filename}", "success")
            return send_from_directory(directory=backup_dir, path=archive_filename, as_attachment=True)

        except subprocess.CalledProcessError as e:
            flash("An error occurred during the backup process.", "error")
            flash(f"STDERR: {e.stderr}", "error")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "error")
    # --- END MODIFICATION ---

    return redirect(url_for(".index"))