
# Local Finance Tracker

A personal finance tracking application built with Python and Flask. It is designed to run entirely on a local machine, using manual CSV imports to track transactions without relying on external APIs or cloud services. The application is enhanced with a local AI-powered categorization assistant and a robust set of administrative tools.

## Features ✨

  * **CSV Import:** Manually import transactions from your bank's CSV exports.
  * **Interactive Transaction Table:** View, sort, and resize columns on the fly with a powerful, client-side rendered table.
  * **AI-Powered Categorization:** Get intelligent category suggestions for your transactions using a local language model.
  * **Rule-Based Categorization:** Create custom rules to automatically categorize transactions based on keywords in the description.
  * **Manual Override:** Easily override AI and rule-based suggestions to ensure your data is always accurate.
  * **Admin Dashboard:** A central place to manage:
      * Institutions and accounts
      * Transaction categories
      * Categorization rules
  * **Backup and Restore:** Create a complete backup of your database and configuration, and restore it on a new or existing installation.
  * **Self-Contained:** All necessary JavaScript libraries and CSS are stored locally, so the application can run entirely offline.

## Tech Stack 🛠️

  * **Backend:** Python, Flask, SQLAlchemy
  * **Database:** PostgreSQL
  * **Frontend:** Jinja2, Pico.css, Tabulator.js, Luxon.js
  * **Migrations:** Flask-Migrate (Alembic)
  * **Forms:** WTForms

## Setup and Installation 🚀

### 1\. Prerequisites

Before you begin, make sure you have the following installed:

| Item         | Minimum Version |
|--------------|-----------------|
| Python       | 3.10 or newer   |
| PostgreSQL   | 12 or newer     |
| git          | –               |

### 2\. PostgreSQL Setup

You need to create a database and a user for the application.

```bash
# Create a user (you will be prompted for a password)
sudo -u postgres createuser -P fin_user

# Create the database and assign ownership
sudo -u postgres createdb -O fin_user finance_db
```

Next, ensure PostgreSQL is configured for password authentication by editing `pg_hba.conf` and changing `peer` to `scram-sha-256` for `local` connections.

### 3\. Application Setup

Clone the repository, create a virtual environment, and install the dependencies.

```bash
git clone https://github.com/Srm9385/finance-tracker.git
cd finance-tracker

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 4\. Environment Configuration (`.env`)

Create a `.env` file in the root of the project by copying the example file:

```bash
cp .env.example .env
```

Now, edit the `.env` file with your specific configuration:

```dotenv
# Flask Settings
FLASK_APP=wsgi.py
FLASK_ENV=development
SECRET_KEY='generate-a-long-random-string-here'

# Database Connection
DATABASE_URL='postgresql://fin_user:your-password-here@localhost:5432/finance_db'

# AI Categorization (Optional)
OPENAI_API_BASE='http://localhost:11434/v1' # Your local LLM API endpoint
OPENAI_API_KEY='ollama'
OPENAI_MODEL_NAME='llama3'

# Default Categories and Rules (Optional, for seeding)
DEFAULT_CATEGORIES_JSON='[{"group": "Housing & Utilities", "name": "Rent/Mortgage"}, ...]'
DEFAULT_RULES_JSON='{"Entertainment": ["AMAZON", "AMZN"], ...}'
```

### 5\. Database Initialization

This step creates the necessary tables in your database.

```bash
# Initialize the database
flask db init
flask db migrate -m "Initial database schema"
flask db upgrade


# Seed the database with an admin user and default data
flask seed
flask seed-categories
flask seed-rules
```

### 6\. Run the Application

You're all set\! Start the Flask development server:

```bash
flask run
```

Open your browser to `http://127.0.0.1:5000` and log in with the credentials **admin / admin**.

## Backup and Restore 💾

The application includes a powerful backup and restore feature to keep your data safe.

### Creating a Backup

1.  Navigate to the **Admin** page.
2.  Click on **Go to Backup/Restore**.
3.  Click the **Create and Download Backup** button.

This will generate a `.tar.gz` archive containing a complete SQL dump of your database and a copy of your `.env` file.

### Restoring from a Backup

1.  **On a fresh installation, make sure you have completed all the setup steps up to and including database initialization (`flask db upgrade`).**
2.  Navigate to the **Admin -\> Backup/Restore** page.
3.  Under "Restore from Backup," choose your `.tar.gz` backup file and click "Restore from Backup."
4.  **Important:** After the restore is complete, manually replace the `.env` file in your project with the one from your backup archive and restart the application.

## Troubleshooting 🔩

If you encounter persistent database issues and want a completely clean slate:

```bash
# Stop the Flask server (Ctrl+C)

# Drop and recreate the database in psql
sudo -u postgres psql
```

Inside the `psql` shell:

```sql
DROP DATABASE finance_db;
CREATE DATABASE finance_db OWNER fin_user;
\q
```

Then, repeat the **Database Initialization** steps from Section 5.
