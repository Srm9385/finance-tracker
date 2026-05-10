# AGENTS.md — Local Finance Tracker

## Project Overview

This is a **personal finance tracking application** built with Python and Flask, designed to run entirely on a local machine. It uses manual CSV imports to track transactions without relying on external APIs or cloud services. The application includes AI-powered transaction categorization via a local LLM (Ollama) and a full admin dashboard for managing institutions, accounts, categories, and rules.

**Repository:** `Srm9385/finance-tracker`  
**Default branch:** `public-main`  
**Languages:** Python (~61%), HTML/Jinja2 (~39%)

---

## Architecture

The application follows a standard **Flask application factory pattern** with the entry point at `wsgi.py`, which calls `create_app()` from the `app` package.

### Directory Structure

```
finance-tracker/
├── app/                        # Main application package
│   ├── __init__.py             # App factory (create_app) + blueprint registration
│   ├── extensions.py           # Flask extension instances (db, migrate, login_manager)
│   ├── models.py               # SQLAlchemy ORM models (User, Transaction, Account, Institution, Category, Rule, etc.)
│   ├── routes/                 # Blueprint route modules
│   │   ├── auth.py             # Authentication routes (login, logout)
│   │   ├── main.py             # Main dashboard and transaction views
│   │   ├── admin.py            # Admin panel routes (institutions, accounts, categories, rules, backup/restore)
│   │   └── import_csv.py       # CSV import workflow routes
│   ├── forms.py                # WTForms form definitions
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html           # Base layout template
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── transactions.html
│   │   └── admin/              # Admin panel templates
│   └── static/                 # Static assets (CSS, JS — bundled locally for offline use)
│       ├── css/                # Pico.css and custom styles
│       └── js/                 # Tabulator.js, Luxon.js, and custom scripts
├── migrations/                 # Alembic/Flask-Migrate migration versions
├── manage.py                   # CLI commands: `flask seed` (creates admin/admin user)
├── manage_reset.py             # Full database reset utility (drops schema, re-runs migrations)
├── troubleshoot_db.py          # Diagnostic script for migration debugging
├── wsgi.py                     # WSGI entry point: `from app import create_app; app = create_app()`
├── requirements.txt            # Python dependencies
├── Requirements.md             # Detailed product requirements document (v1 spec)
├── .python-version             # pyenv Python version
└── .env                        # Environment config (not committed — see .env.example)
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | Flask 3.0.3 |
| ORM | SQLAlchemy 2.0.35 |
| Database | PostgreSQL 12+ (via psycopg2-binary) |
| Migrations | Flask-Migrate 4.0.7 (Alembic) |
| Auth | Flask-Login 0.6.3 |
| Forms | Flask-WTF / WTForms |
| Templating | Jinja2 |
| Frontend CSS | Pico.css (bundled locally) |
| Frontend JS | Tabulator.js, Luxon.js (bundled locally) |
| CSV parsing | pandas 2.2.2 |
| AI categorization | openai SDK → local LLM endpoint (Ollama, llama3) |
| Env config | python-dotenv |

---

## Key Concepts for Agents

### Application Factory

The app uses Flask's factory pattern. Always create the app via `create_app()`:

```python
from app import create_app
app = create_app()
```

The factory reads config from environment variables (loaded via `python-dotenv` from `.env`). The `FLASK_APP` env var should point to `wsgi.py`.

### Database

PostgreSQL is required (not SQLite). The database connection string is in `DATABASE_URL` env var, typically:
```
postgresql://fin_user:<password>@localhost:5432/finance_db
```

All database operations go through SQLAlchemy. Models are defined in `app/models.py`. Migrations are managed with Flask-Migrate (Alembic). The `migrations/` directory must exist and contain valid version scripts.

**Critical migration commands:**
- `flask db init` — Initialize migration directory (first time only)
- `flask db migrate -m "message"` — Auto-generate a migration
- `flask db upgrade` — Apply pending migrations
- `flask db downgrade` — Revert the last migration

### Authentication

Single-user local auth using Flask-Login. The default user is seeded via `flask seed` as `admin/admin`. Passwords are hashed with Werkzeug's `generate_password_hash`. The `User` model is imported from `app.models`.

### AI Categorization

The app integrates with a local LLM for transaction categorization using the OpenAI-compatible API format. Configuration env vars:
- `OPENAI_API_BASE` — Local endpoint (e.g., `http://localhost:11434/v1` for Ollama)
- `OPENAI_API_KEY` — Typically `ollama` for local use
- `OPENAI_MODEL_NAME` — Model to use (e.g., `llama3`)

The AI categorization is optional; the app functions without it using rule-based categorization.

### CSV Import Flow

Transactions are imported from bank CSV exports. The flow involves: selecting an institution and account, uploading the CSV, mapping columns, deduplication review, and committing. Import logs track added/updated/skipped/duplicate/error entries.

### Backup & Restore

The admin panel provides backup creation (`.tar.gz` archive containing SQL dump + `.env`) and restore functionality. Backups are created from the Admin panel and can be restored on fresh installations.

---

## Environment Setup

### Prerequisites
- Python 3.10+
- PostgreSQL 12+
- (Optional) Ollama with llama3 for AI categorization

### Quick Start

```bash
git clone https://github.com/Srm9385/finance-tracker.git
cd finance-tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create PostgreSQL database
sudo -u postgres createuser -P fin_user
sudo -u postgres createdb -O fin_user finance_db

# Copy and edit .env
cp .env.example .env
# Edit .env with your DATABASE_URL and SECRET_KEY

# Initialize database
flask db init
flask db migrate -m "Initial schema"
flask db upgrade

# Seed admin user and default data
flask seed
flask seed-categories
flask seed-rules

# Run
flask run
```

Access at `http://127.0.0.1:5000` with credentials `admin / admin`.

---

## Coding Conventions & Guidelines

### Python Style
- Standard Python 3.10+ syntax with type hints where present
- Imports use the `from __future__ import annotations` pattern in some modules
- Flask blueprints organize routes by domain (auth, main, admin, import)
- Database sessions are managed through `db.session` from `app.extensions`

### Template Style
- Jinja2 templates extend `base.html`
- Frontend is self-contained — all CSS and JS are bundled in `app/static/` for offline operation
- No CDN dependencies; the app must work without internet

### Error Handling
- Database errors should use SQLAlchemy exception handling with rollbacks
- Import operations log results (added, skipped, duplicates, errors)
- The `troubleshoot_db.py` script demonstrates the pattern for debugging migration issues

### Security Considerations
- All data stays local — never send financial data to external services
- The AI endpoint must be a local LLM (Ollama), not a cloud API
- No encryption at rest in v1
- Single-user authentication only

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `flask run` | Start the development server |
| `flask seed` | Create the default admin user (admin/admin) |
| `flask seed-categories` | Seed default transaction categories |
| `flask seed-rules` | Seed default categorization rules |
| `flask db upgrade` | Apply database migrations |
| `flask db migrate -m "msg"` | Generate a new migration |
| `python manage_reset.py` | Full database reset (drops and recreates schema) |
| `python troubleshoot_db.py` | Debug migration issues with verbose output |

---

## Database Reset Procedure

If the database gets into a bad state:

1. Stop the Flask server
2. Run `python manage_reset.py` (drops the `public` schema and re-runs all migrations), **OR**
3. Manually reset via psql:
   ```sql
   DROP DATABASE finance_db;
   CREATE DATABASE finance_db OWNER fin_user;
   ```
4. Re-run `flask db upgrade`, then `flask seed`, `flask seed-categories`, `flask seed-rules`

---

## Important Files for Context

When working on this codebase, prioritize reading these files:

- `app/__init__.py` — App factory, blueprint registration, configuration loading
- `app/models.py` — All database models and relationships
- `app/extensions.py` — Shared Flask extension instances
- `app/routes/` — All route handlers organized by blueprint
- `Requirements.md` — The full v1 product specification with detailed feature requirements
- `requirements.txt` — Python dependencies and their pinned versions

---

## Categories Structure

The app uses a two-level category system (Group → Sub-category):

| Group | Sub-categories |
|-------|---------------|
| Housing & Utilities | Rent/Mortgage, Utilities, Internet/Phone, Home Maintenance |
| Transportation | Fuel, Public Transit/Rideshare, Auto Maintenance/Repairs, Insurance (Auto) |
| Food & Dining | Groceries, Dining Out, Coffee/Snacks |
| Personal & Lifestyle | Clothing, Health & Fitness, Subscriptions/Streaming, Entertainment |
| Financial & Obligations | Loan Payments, Credit Card Payments, Insurance (Non-Auto), Bank Fees/Interest |
| Giving & Special | Gifts, Donations |
| Work & Education | Professional Expenses, Education |
| Income | Salary/Wages, Bonus/Commission, Other Income |
| Savings & Investments | Emergency Fund, Retirement Contributions, Other Savings/Investments |

---

## Planned but Not Yet Implemented (v2+)

These features are documented in `Requirements.md` but are not part of the current codebase: auto-watch folders, regex normalization rules, dark mode, retirement holdings/returns breakdown, investment trend analytics, push alerts, NAS backups, and encryption at rest.
