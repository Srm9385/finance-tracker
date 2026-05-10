 Finance-Tracker Django App Architecture Map

 1. Project Structure Overview

 /home/sean/dev/finance-tracker/app/
 ├── __init__.py # Flask app factory; registers
 blueprints
 ├── config.py # Configuration (DB_URL, API keys,
 dirs)
 ├── extensions.py # SQLAlchemy, Migrate, LoginManager,
CSRF
 ├── models.py # Database models
 ├── forms.py# WTForms for all features
 ├── utils.py# Utilities
 ├── blueprints/ # Flask route handlers (views)
 ├── services/ # Business logic & processors
 ├── templates/# Jinja2 HTML templates
 └── static/ # CSS, JS, images, vendor libraries

 ---
 2. Models (Database Schema)

 Located: /home/sean/dev/finance-tracker/app/models.py

 10 Database Models:
 - User - Authentication (username, password_hash, created_at)
 - Institution - Bank/Financial institution (name, is_active)
 - Account - User's bank accounts (type:
 checking/savings/credit/loan/retirement)
 - Mapper - CSV column mappings per institution/account (schema_json)
 - Import - Import job metadata (filename, sha256, row_count, status,
log_json)
 - Transaction - Financial transactions (date, amount_cents,
 description, category)
 - Fields: transfer markers, refund flags, joint transaction
 indicator, running balance
 - Category - Transaction categories (group, name)
 - Rule - Auto-categorization rules (keyword → category mapping)
 - TransferKeyword - Keywords identifying transfers (e.g., "VENMO")
 - RefundKeyword - Keywords identifying refunds (e.g., "REFUND")

 ---
 3. Views/Routes (Flask Blueprints)

 Located: /home/sean/dev/finance-tracker/app/blueprints/

 6 Blueprint Modules:

 auth.py (Authentication)

 - POST/GET /auth/login - Login page
 - GET /auth/logout - Logout

 dashboard.py (Analytics & Reporting)

 - GET /dashboard/ - Main dashboard
 - GET /dashboard/chart-data - JSON data for charts
 - GET /dashboard/income-over-time - Income trends
 - GET /dashboard/income-vs-spending - Income vs spending comparison
 - GET /dashboard/spending-over-time - Spending trends

 transactions.py (Transaction Management)

 - GET /account/<id> - List transactions for account
 - POST /export - Export transactions to CSV
 - POST /delete/<id> - Soft delete transaction
 - POST /<id>/set_category - Categorize transaction
 - GET|POST /account/<id>/add_manual - Add manual transaction
 - POST /toggle_transfer/<id> - Mark/unmark as transfer
 - POST /toggle_refund/<id> - Mark/unmark as refund
 - POST /toggle_joint/<id> - Mark/unmark as joint

 imports.py (CSV Import Pipeline)

 - GET|POST /imports/upload - File upload & mapper selection
 - GET|POST /imports/wizard/<token> - Column mapping wizard
 - GET /imports/accounts-for-institution/<id> - AJAX endpoint
 - GET|POST /imports/review/<id> - Review import before commit
 - GET /imports/log/<id> - View import log
 - GET /imports/history - Import history
 - POST /imports/commit/<id> - Finalize import
 - POST /imports/delete_import_txns/<id> - Rollback import

 admin.py (Admin/Configuration)

 - GET|POST /admin/ - Admin dashboard
 - Mapper Management:
 - GET|POST /admin/mappers/edit/<inst>/<acct> - Edit CSV mapping
 - Institution Management:
 - GET|POST /admin/institution/<id>/edit
 - POST /admin/institution/<id>/toggle_active
 - POST /admin/institution/<id>/delete
 - Account Management:
 - GET|POST /admin/account/<id>/edit
 - POST /admin/account/<id>/toggle_active
 - POST /admin/account/<id>/delete
 - Category Management:
 - GET|POST /admin/categories - List/add categories
 - GET|POST /admin/category/<id>/edit
 - POST /admin/category/<id>/delete
 - Rule Management:
 - GET|POST /admin/rules - List/add rules
 - GET|POST /admin/rule/<id>/edit
 - POST /admin/rule/<id>/delete
 - Keyword Management:
 - GET|POST /admin/transfer-keywords
 - POST /admin/transfer-keyword/<id>/delete
 - GET|POST /admin/refund-keywords
 - POST /admin/refund-keyword/<id>/delete

 ai.py (AI-Powered Features)

 - GET|POST /ai/categorize - AI categorization suggestions
 - GET /ai/review_suggestions - Review AI suggestions
 - POST /ai/apply_suggestions - Apply categorizations
 - GET|POST /ai/refund-finder - Find potential refunds
 - GET /ai/review-refunds - Review refund findings
 - POST /ai/apply-refunds - Apply refund flags
 - GET /ai/accounts-for-institution/<id> - AJAX endpoint

 backup.py (Database Backup/Restore)

 - GET|POST /admin/backup/ - Backup/restore management
 - GET /admin/backup/create - Create backup

 ---
 4. Forms (WTForms)

 Located: /home/sean/dev/finance-tracker/app/forms.py

 13 Form Classes:
 - InstitutionForm
 - AccountForm
 - MappingWizardForm (CSV column config)
 - ImportUploadForm
 - ReviewDecisionForm
 - CSRFOnlyForm
 - AICategorizeForm
 - CategoryForm
 - ManualTransactionForm
 - TransactionExportForm
 - RuleForm
 - TransferKeywordForm
 - RefundKeywordForm
 - RestoreForm
 - RefundFinderForm

 ---
 5. Services (Business Logic)

 Located: /home/sean/dev/finance-tracker/app/services/

 - importer.py (7.7KB) - CSV parsing & import logic
 - ai_categorizer.py (3.3KB) - OpenAI-based categorization
 - mapping.py (2.5KB) - CSV column mapping utilities
 - review.py (6.8KB) - Import review & decision processing
 - archive.py (765B) - Archive file management

 ---
 6. Templates

 Located: /home/sean/dev/finance-tracker/app/templates/

 27 HTML Template Files:

 Base:
 - base.html - Master layout template

 Dashboard:
 - dashboard/index.html - Main dashboard

 Authentication:
 - (Implied in auth.py, likely embedded)

 Imports:
 - imports/upload.html - File upload interface
 - imports/review.html - Review transactions before import
 - imports/history.html - Import history log
 - imports/import_log.html - Detailed import log

 Transactions:
 - transactions/list.html - Transaction list per account
 - transactions/add_manual.html - Manual entry form
 - transactions/export.html - Export form

 Admin Panel:
 - admin/index.html - Admin dashboard
 - admin/institutions.html - Institution list
 - admin/institution_edit.html - Create/edit institution
 - admin/accounts.html - Account list
 - admin/account_edit.html - Create/edit account
 - admin/mapper_edit.html - CSV mapping editor
 - admin/categories.html - Category list
 - admin/category_edit.html - Create/edit category
 - admin/rules.html - Rule list
 - admin/rule_edit.html - Create/edit rule
 - admin/transfer_keywords.html - Transfer keyword list
 - admin/refund_keywords.html - Refund keyword list
 - admin/backup.html - Backup/restore interface

 AI Features:
 - ai/categorize.html - AI categorization UI
 - ai/review.html - Review suggestions
 - ai/refund_finder.html - Refund detection
 - ai/review_refunds.html - Review refund findings

 ---
 7. Frontend Assets

 Located: /home/sean/dev/finance-tracker/app/static/

 CSS:
 - vendor/pico/pico.min.css - Pico CSS framework (minimal CSS)

 JavaScript Libraries:
 - vendor/chartjs/chart.js - Chart.js for data visualization
 - vendor/chartjs-adapter-luxon/chartjs-adapter-luxon.js - Luxon date
adapter for Chart.js
 - vendor/luxon/luxon.min.js - Luxon.js for date/time handling
 - vendor/tabulator/js/tabulator.min.js - Tabulator.js for data
 tables
 - vendor/tabulator/css/tabulator.min.css - Tabulator CSS

 Images:
 - img/favicon.ico - Favicon

 Framework/Design:
 - Uses Pico CSS (lightweight, minimal design framework)
 - Interactive charts via Chart.js
 - Data tables via Tabulator.js
 - Date handling via Luxon

 ---
 8. App Configuration

 Located: /home/sean/dev/finance-tracker/app/config.py

 Environment Variables Required:
 - DATABASE_URL - PostgreSQL connection
 - SECRET_KEY - Flask secret key
 - ARCHIVE_DIR - CSV archive location (default:
 ~/.finance_tracker_archive)
 - BACKUP_DIR - Database backup location (default:
 ~/.finance_tracker_backup)
 - OPENAI_API_BASE - OpenAI API endpoint
 - OPENAI_API_KEY - OpenAI API key
 - OPENAI_MODEL_NAME - Model (e.g., gpt-4)

 Optional Seeding:
 - DEFAULT_CATEGORIES_JSON - Pre-seed categories
 - DEFAULT_RULES_JSON - Pre-seed categorization rules

 ---
 9. Key Features Summary

 ┌─────────────────────┬─────────────────────────────────────────────
 ──────┐
 │ Feature │Components
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Authentication│ User model, auth blueprint, LoginManager
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Transaction Import│ CSV upload, mapper wizard, review/commit
 pipeline │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Categorization│ Rules (keyword→category), AI-powered
 suggestions│
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Transaction │ Manual entry, soft delete, category
 assignment│
 │ Management│
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Transfer Detection│ TransferKeyword model, toggle UI
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Refund Detection│ RefundKeyword model, AI finder, manual flags
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Joint Transactions│ is_joint flag on transactions
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Analytics │ Dashboard with income/spending charts &
 trends│
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Export│ CSV export with date/account filters
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Admin │ Full CRUD for institutions, accounts,
 categories, │
 │ │rules, keywords
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Backup/Restore│ Database dump/restore functionality
 │
 ├─────────────────────┼─────────────────────────────────────────────
 ──────┤
 │ Multi-Account │ Support for multiple institutions/accounts
 per│
 │ │ user
 │
 └─────────────────────┴─────────────────────────────────────────────
 ──────┘

 ---
 10. Tech Stack

 - Backend: Flask (Python web framework)
 - Database: PostgreSQL (SQLAlchemy ORM)
 - Migrations: Alembic
 - Forms: WTForms with CSRF protection
 - Authentication: Flask-Login
 - AI: OpenAI API
 - Frontend CSS: Pico CSS (minimal)
 - Charting: Chart.js with Luxon
 - Tables: Tabulator.js
 - Templating: Jinja2

 ---
 This is a feature-rich personal finance tracker with:
 - Multi-account bank import (CSV)
 - Intelligent transaction categorization (rules + AI)
 - Spending analytics and reporting
 - Transfer/refund detection
 - Full administrative interface
- Database backup/restore
