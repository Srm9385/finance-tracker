# app/blueprints/backup.py
import os
import subprocess
import tempfile
import tarfile
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, send_from_directory)
from werkzeug.utils import secure_filename
from ..extensions import db
from ..forms import RestoreForm

bp = Blueprint("backup", __name__, url_prefix="/backup")


def get_db_connection_args():
    db_url = current_app.config["SQLALCHEMY_DATABASE_URI"]
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(db_url)
        return {"user": unquote(parsed.username or ""),
                "password": unquote(parsed.password or ""),
                "host": parsed.hostname,
                "port": str(parsed.port or 5432),
                "dbname": parsed.path.lstrip('/')}
    except Exception as e:
        flash(f"Could not parse DATABASE_URL: {e}", "error")
        return None


def _pg_env(conn_args):
    env = os.environ.copy()
    env["PGPASSWORD"] = conn_args["password"] or ""
    return env


@bp.route("/", methods=["GET", "POST"])
def index():
    form = RestoreForm()
    if form.validate_on_submit():
        file = form.backup_file.data
        filename = secure_filename(file.filename) or "upload.tar.gz"

        conn_args = get_db_connection_args()
        if not conn_args:
            return redirect(url_for(".index"))

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_archive_path = os.path.join(temp_dir, filename)
            file.save(temp_archive_path)

            try:
                # Open with "r:*" so a .tar, .tar.gz or .tgz all work. Browsers
                # (notably Safari with "open safe files") transparently gunzip
                # downloads, so the archive we get back is often a plain tar.
                try:
                    tar = tarfile.open(temp_archive_path, "r:*")
                except tarfile.ReadError:
                    raise ValueError(
                        "That file is not a readable tar archive. Upload the "
                        "archive produced by 'Create Backup'."
                    )

                extract_dir = os.path.join(temp_dir, "extracted")
                with tar:
                    sql_file_member = next(
                        (m for m in tar.getmembers()
                         if m.isfile() and m.name.endswith(".sql")), None)
                    if not sql_file_member:
                        raise ValueError("No .sql file found in the backup archive.")

                    # filter="data" strips absolute/".." paths and unsafe metadata.
                    tar.extract(sql_file_member, path=extract_dir, filter="data")

                temp_sql_path = os.path.join(extract_dir, sql_file_member.name)

                # Release pooled connections first: the dump's DROP TABLE
                # statements need an ACCESS EXCLUSIVE lock and will block
                # forever behind an idle SQLAlchemy connection.
                db.session.remove()
                db.engine.dispose()

                # ON_ERROR_STOP + single-transaction: without these psql exits 0
                # even when every statement fails, so a broken restore was being
                # reported as a success.
                psql_cmd = ["psql", "-h", conn_args["host"], "-p", conn_args["port"],
                            "-U", conn_args["user"], "-d", conn_args["dbname"],
                            "-v", "ON_ERROR_STOP=1", "--single-transaction",
                            "-f", temp_sql_path]

                subprocess.run(psql_cmd, env=_pg_env(conn_args),
                               capture_output=True, text=True, check=True)

                flash("Database restored successfully.", "success")
                flash(
                    "IMPORTANT: Remember to manually place the .env file from your backup and restart the application.",
                    "info")

            except subprocess.CalledProcessError as e:
                flash("An error occurred during the database restore.", "error")
                flash(f"STDERR: {(e.stderr or '').strip() or 'no output'}", "error")
            except Exception as e:
                flash(f"An unexpected error occurred: {e}", "error")

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

            subprocess.run(pgdump_cmd, env=_pg_env(conn_args),
                           capture_output=True, text=True, check=True)

            # 2. Copy the .env file into the temp directory
            env_filepath = os.path.join(current_app.root_path, '..', '.env')
            if os.path.exists(env_filepath):
                subprocess.run(["cp", env_filepath, temp_dir], check=True)

            # 3. Create the tar.gz archive from the temp directory's contents
            with tarfile.open(archive_filepath, "w:gz") as tar:
                tar.add(temp_dir, arcname=os.path.basename(f"backup_{timestamp}"))

            # mimetypes guesses "application/x-tar" + gzip encoding for a
            # .tar.gz name, which makes browsers decompress the download and
            # hand back a plain .tar. Declaring it as gzip keeps it intact.
            return send_from_directory(directory=backup_dir, path=archive_filename,
                                       as_attachment=True,
                                       mimetype="application/gzip")

        except subprocess.CalledProcessError as e:
            flash("An error occurred during the backup process.", "error")
            flash(f"STDERR: {(e.stderr or '').strip() or 'no output'}", "error")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "error")

    return redirect(url_for(".index"))
