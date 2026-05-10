## Project Overview

A **personal finance tracking application** built with Python and Flask. Transactions are imported via manual CSV uploads from bank/financial institution exports. Features AI-powered categorization (local LLM via Ollama), spending analytics, transfer/refund detection, and a full admin dashboard.

| Attribute | Value |
|-----------|-------|
| Repository | `Srm9385/finance-tracker` |
| Default branch | `public-main` |
| Languages | Python (~61%), HTML/Jinja2 (~39%) |
| Entry point | `wsgi.py` → `create_app()` |

---

## Architecture

The app uses the **Flask application factory pattern** with a clean separation: routes live in blueprints, business logic lives in services, and models are defined separately.

### Directory Structure (Current)

```
finance-tracker/
├── app/                              # Main application package
│   ├── __init__.py                   # App factory + blueprint registration
│   ├── config.py                     # Configuration (DB_URL, API keys, dirs)
│   ├── extensions.py                 # Flask extension instances (db, migrate, login_manager, csrf)
│   ├── models.py                     # SQLAlchemy ORM models (10 models)
│   ├── forms.py                      # WTForms for all features (15 form classes)
│   ├── utils.py                      # Shared utilities
│   │
│   ├── blueprints/                   # Flask route handlers (views) — 6 modules
│   │   ├── auth.py                   # Login/logout
│   │   ├── dashboard.py              # Analytics & reporting charts/trends
│   │   ├── transactions.py           # Transaction CRUD, export, manual entry
│   │   ├── imports.py                # CSV import pipeline (upload → wizard → review → commit)
│   │   ├── admin.py                  # Admin panel: institutions, accounts, categories, rules, keywords
│   │   └── ai.py                     # AI categorization & refund finder
│   │
│   ├── services/                     # Business logic & processors — 5 modules
│   │   ├── importer.py               # CSV parsing & import orchestration (7.7KB)
│   │   ├── ai_categorizer.py         # OpenAI-compatible API categorization (3.3KB)
│   │   ├── mapping.py                # CSV column mapping utilities (2.5KB)
│   │   ├── review.py                 # Import review & decision processing (6.8KB)
│   │   └── archive.py                # Archive file management (765B)
│   │
│   ├── templates/                    # Jinja2 HTML templates — 27 files
│   │   ├── base.html                 # Master layout
│   │   ├── dashboard/index.html      # Main dashboard with charts
│   │   ├── imports/                  # Upload, review, history, log
│   │   ├── transactions/             # List, add_manual, export
│   │   ├── admin/                    # Full admin panel (institutions, accounts, categories, rules, keywords, backup)
│   │   └── ai/                       # Categorize UI, review suggestions, refund finder
│   │
│   └── static/                       # Frontend assets — all bundled locally
│       ├── css/vendor/pico/pico.min.css
│       ├── js/vendor/tabulator/js/tabulator.min.js
│       ├── js/vendor/luxon/luxon.min.js
│       ├── js/vendor/chartjs/chart.js
│       └── img/favicon.ico
│
├── migrations/                       # Alembic migration versions
├── wsgi.py                           # WSGI entry point
├── manage.py                         # CLI commands (seed)
├── manage_reset.py                   # Full DB reset utility
├── troubleshoot_db.py                # Migration debugging script
├── requirements.txt                  # Python dependencies
├── Requirements.md                   # v1 product specification
└── .env                              # Environment config (not committed)
```

### Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **Blueprints over single routes file** | Domain separation: auth, dashboard, transactions, imports, admin, ai each have their own module |
| **Services layer separate from blueprints** | Business logic (import pipeline, AI categorization) is decoupled from HTTP handling — testable and reusable |
| **Flask app factory (`create_app`)** | Enables testing with different configs; clean extension initialization |
| **Local-first, no CDN** | All CSS/JS bundled in `app/static/`; works fully offline |
| **PostgreSQL only** | No SQLite fallback — full SQL compliance needed for analytics queries |

---

## Database Models (10)

All defined in `app/models.py`.

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **User** | Authentication | username, password_hash, created_at |
| **Institution** | Bank/financial institution | name, is_active |
| **Account** | User's accounts | type (checking/savings/credit/loan/retirement), institution FK, is_active |
| **Mapper** | CSV column mappings per institution+account | schema_json |
| **Import** | Import job metadata | filename, sha256, row_count, status, log_json |
| **Transaction** | Financial transactions | date, amount_cents, description, category, transfer/refund/joint flags, running balance |
| **Category** | Transaction categories (group → sub-category) | group, name |
| **Rule** | Auto-categorization rules | keyword → category mapping |
| **TransferKeyword** | Keywords identifying transfers | e.g., "VENMO" |
| **RefundKeyword** | Keywords identifying refunds | e.g., "REFUND" |

---

## Blueprints & Routes (6)

### `auth` — Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST/GET | `/auth/login` | Login page |
| GET | `/auth/logout` | Logout |

### `dashboard` — Analytics & Reporting
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/` | Main dashboard |
| GET | `/dashboard/chart-data` | JSON data for charts |
| GET | `/dashboard/income-over-time` | Income trends |
| GET | `/dashboard/income-vs-spending` | Income vs spending comparison |
| GET | `/dashboard/spending-over-time` | Spending trends |

### `transactions` — Transaction Management
| Method | Path | Description |
|--------|------|-------------|
| GET | `/account/<id>` | List transactions for account |
| POST | `/export` | Export transactions to CSV |
| POST | `/delete/<id>` | Soft delete transaction |
| POST | `/<id>/set_category` | Categorize transaction |
| GET\|POST | `/account/<id>/add_manual` | Add manual transaction |
| POST | `/toggle_transfer/<id>` | Mark/unmark as transfer |
| POST | `/toggle_refund/<id>` | Mark/unmark as refund |
| POST | `/toggle_joint/<id>` | Mark/unmark as joint |

### `imports` — CSV Import Pipeline
| Method | Path | Description |
|--------|------|-------------|
| GET\|POST | `/imports/upload` | File upload & mapper selection |
| GET\|POST | `/imports/wizard/<token>` | Column mapping wizard |
| GET | `/imports/accounts-for-institution/<id>` | AJAX: get accounts for institution |
| GET\|POST | `/imports/review/<id>` | Review import before commit |
| GET | `/imports/log/<id>` | View import log |
| GET | `/imports/history` | Import history |
| POST | `/imports/commit/<id>` | Finalize import |
| POST | `/imports/delete_import_txns/<id>` | Rollback import transactions |

### `admin` — Admin / Configuration
| Method | Path | Description |
|--------|------|-------------|
| GET\|POST | `/admin/` | Admin dashboard |
| GET\|POST | `/admin/mappers/edit/<inst>/<acct>` | Edit CSV mapping |
| GET\|POST | `/admin/institution/<id>/edit` | Edit institution |
| POST | `/admin/institution/<id>/toggle_active` | Toggle active status |
| POST | `/admin/institution/<id>/delete` | Delete institution |
| GET\|POST | `/admin/account/<id>/edit` | Edit account |
| POST | `/admin/account/<id>/toggle_active` | Toggle active status |
| POST | `/admin/account/<id>/delete` | Delete account |
| GET\|POST | `/admin/categories` | List categories |
| GET\|POST | `/admin/category/<id>/edit` | Edit category |
| POST | `/admin/category/<id>/delete` | Delete category |
| GET\|POST | `/admin/rules` | List rules |
| GET\|POST | `/admin/rule/<id>/edit` | Edit rule |
| POST | `/admin/rule/<id>/delete` | Delete rule |
| GET\|POST | `/admin/transfer-keywords` | Manage transfer keywords |
| POST | `/admin/transfer-keyword/<id>/delete` | Delete transfer keyword |
| GET\|POST | `/admin/refund-keywords` | Manage refund keywords |
| POST | `/admin/refund-keyword/<id>/delete` | Delete refund keyword |

### `ai` — AI-Powered Features
| Method | Path | Description |
|--------|------|-------------|
| GET\|POST | `/ai/categorize` | AI categorization suggestions |
| GET | `/ai/review_suggestions` | Review AI suggestions |
| POST | `/ai/apply_suggestions` | Apply suggested categorizations |
| GET\|POST | `/ai/refund-finder` | Find potential refunds |
| GET | `/ai/review-refunds` | Review refund findings |
| POST | `/ai/apply-refunds` | Apply refund flags |
| GET | `/ai/accounts-for-institution/<id>` | AJAX: get accounts for institution |

### `backup` — Database Backup / Restore
| Method | Path | Description |
|--------|------|-------------|
| GET\|POST | `/admin/backup/` | Backup/restore management |
| GET | `/admin/backup/create` | Create backup |

---

## Services Layer (Business Logic)

Located in `app/services/`. These modules are **decoupled from HTTP** — they can be called directly or tested independently.

| Module | Size | Purpose |
|--------|------|---------|
| `importer.py` | 7.7KB | CSV parsing & import orchestration |
| `ai_categorizer.py` | 3.3KB | OpenAI-compatible API categorization |
| `mapping.py` | 2.5KB | CSV column mapping utilities |
| `review.py` | 6.8KB | Import review & decision processing |
| `archive.py` | 765B | Archive file management |

---

## Forms (15 WTForm Classes)

Defined in `app/forms.py`:

`InstitutionForm`, `AccountForm`, `MappingWizardForm`, `ImportUploadForm`, `ReviewDecisionForm`, `CSRFOnlyForm`, `AICategorizeForm`, `CategoryForm`, `ManualTransactionForm`, `TransactionExportForm`, `RuleForm`, `TransferKeywordForm`, `RefundKeywordForm`, `RestoreForm`, `RefundFinderForm`

---

## Templates (27 HTML Files)

| Area | Files |
|------|-------|
| **Base** | `base.html` — Master layout |
| **Dashboard** | `dashboard/index.html` — Main dashboard with charts |
| **Imports** | `imports/upload.html`, `imports/review.html`, `imports/history.html`, `imports/import_log.html` |
| **Transactions** | `transactions/list.html`, `transactions/add_manual.html`, `transactions/export.html` |
| **Admin** | `admin/index.html`, `admin/institutions.html`, `admin/institution_edit.html`, `admin/accounts.html`, `admin/account_edit.html`, `admin/mapper_edit.html`, `admin/categories.html`, `admin/category_edit.html`, `admin/rules.html`, `admin/rule_edit.html`, `admin/transfer_keywords.html`, `admin/refund_keywords.html`, `admin/backup.html` |
| **AI Features** | `ai/categorize.html`, `ai/review.html`, `ai/refund_finder.html`, `ai/review_refunds.html` |

---

## Configuration

Defined in `app/config.py`. Environment variables loaded via `python-dotenv` from `.env`:

| Variable | Required | Default / Example |
|----------|----------|-------------------|
| `DATABASE_URL` | Yes | `postgresql://fin_user:pass@localhost:5432/finance_db` |
| `SECRET_KEY` | Yes | — |
| `ARCHIVE_DIR` | No | `~/.finance_tracker_archive` |
| `BACKUP_DIR` | No | `~/.finance_tracker_backup` |
| `OPENAI_API_BASE` | Conditional | `http://localhost:11434/v1` (Ollama) or cloud endpoint |
| `OPENAI_API_KEY` | Conditional | `ollama` for local use |
| `OPENAI_MODEL_NAME` | Conditional | `llama3` or `gpt-4` |

Optional seeding env vars: `DEFAULT_CATEGORIES_JSON`, `DEFAULT_RULES_JSON`.

---

## Key Concepts for Agents

### Application Factory

Always create the app via `create_app()`:

```python
from app import create_app
app = create_app()
```

The factory reads config from environment variables (loaded via `python-dotenv` from `.env`). The `FLASK_APP` env var should point to `wsgi.py`.

### Database

PostgreSQL is required. Connection string in `DATABASE_URL` env var. All models in `app/models.py`. Migrations managed with Flask-Migrate (Alembic).

**Critical migration commands:**
| Command | Description |
|---------|-------------|
| `flask db init` | Initialize migration directory (first time only) |
| `flask db migrate -m "message"` | Auto-generate a migration |
| `flask db upgrade` | Apply pending migrations |
| `flask db downgrade` | Revert the last migration |

### Authentication

Single-user local auth via Flask-Login. Default user seeded as `admin/admin`. Passwords hashed with Werkzeug's `generate_password_hash`. Import `User` from `app.models`.

### Services Layer Pattern

Business logic is **decoupled** from route handlers:
- Blueprints handle HTTP (request parsing, response formatting)
- Services contain the actual logic (import pipeline, AI categorization, mapping)
- When adding features, prefer putting business logic in a new service module rather than bloating blueprint files

### CSV Import Flow

```
Select institution + account → Upload CSV → Column mapping wizard → Review transactions → Commit to DB
```

Import logs track added/updated/skipped/duplicate/error entries. Rollbacks available via `delete_import_txns`.

### AI Categorization

Optional feature using OpenAI-compatible API (local Ollama or cloud). Configuration:
- `OPENAI_API_BASE` — Local endpoint (`http://localhost:11434/v1`) or cloud URL
- `OPENAI_API_KEY` — Typically `ollama` for local use
- `OPENAI_MODEL_NAME` — Model name (e.g., `llama3`, `gpt-4`)

The app functions without AI using rule-based categorization.

### Backup & Restore

Admin panel creates `.tar.gz` archives containing SQL dump + `.env`. Backups stored in `BACKUP_DIR` (default: `~/.finance_tracker_backup`). Restorable on fresh installations.

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
- Some modules use `from __future__ import annotations`
- **Blueprints** organize routes by domain (auth, dashboard, transactions, imports, admin, ai)
- **Services** contain business logic decoupled from HTTP
- Database sessions managed through `db.session` from `app.extensions`

### Template Style
- Jinja2 templates extend `base.html`
- Frontend is self-contained — all CSS/JS bundled in `app/static/` for offline operation
- No CDN dependencies; the app must work without internet

### Error Handling
- Database errors: use SQLAlchemy exception handling with rollbacks
- Import operations log results (added, skipped, duplicates, errors)
- `troubleshoot_db.py` demonstrates debugging migration issues

### Security Considerations
- All data stays local — never send financial data to external services
- AI endpoint should be a local LLM (Ollama), not a cloud API
- No encryption at rest in v1
- Single-user authentication only

---

## Feature Summary

| Feature | Components |
|---------|-----------|
| Authentication | User model, auth blueprint, LoginManager |
| CSV Import Pipeline | Upload → mapping wizard → review/commit pipeline |
| Categorization | Rules (keyword→category) + AI-powered suggestions |
| Transaction Management | Manual entry, soft delete, category assignment |
| Transfer Detection | TransferKeyword model, toggle UI |
| Refund Detection | RefundKeyword model, AI finder, manual flags |
| Joint Transactions | `is_joint` flag on transactions |
| Analytics | Dashboard with income/spending charts & trends |
| Export | CSV export with date/account filters |
| Admin Panel | Full CRUD for institutions, accounts, categories, rules, keywords |
| Backup/Restore | Database dump/restore functionality |
| Multi-Account | Multiple institutions/accounts per user |

---

## Categories Structure

Two-level system (Group → Sub-category):

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

Documented in `Requirements.md`: auto-watch folders, regex normalization rules, dark mode, retirement holdings/returns breakdown, investment trend analytics, push alerts, NAS backups, encryption at rest.
