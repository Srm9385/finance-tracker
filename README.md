# Local Finance Tracker

A personal finance tracking application built with Python and Flask.  
It is designed to run entirely on a local machine, using manual CSV imports to track transactions without relying on external APIs or cloud services.

---

## Stack
- **Flask** – web framework  
- **Jinja** – templating engine  
- **SQLAlchemy (PostgreSQL)** – ORM & database  
- **Flask‑Migrate** – Alembic migrations  
- **WTForms** – form handling  
- **pandas** – CSV parsing  

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Zero to Running: Quickstart](#zero-to-running-quickstart)
3. [Detailed Setup Guide](#detailed-setup-guide)  
   3.1. [Step 1: PostgreSQL Installation](#step-1-postgresql-installation)  
   &nbsp;&nbsp;• Option A – Arch Linux (fish shell)  
   &nbsp;&nbsp;• Option B – Debian/Ubuntu (bash shell)  
   3.2. [Step 2: Application Setup](#step-2-application-setup)  
   3.3. [Step 3: Database Initialization (First‑time setup)](#step-3-database-initialization-first-time-setup)  
   3.4. [Step 4: Run the Application](#step-4-run-the-application)  
4. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, make sure you have the following installed:

| Item | Minimum Version |
|------|-----------------|
| Python | 3.10 or newer |
| PostgreSQL | 12 or newer |
| git | – |

---

## Zero to Running: Quickstart

For users who already have PostgreSQL set up and just want a fast‑track install:

```bash
# Clone the repository and enter it
git clone https://github.com/Srm9385/finance-tracker.git
cd finance-tracker

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # (fish: source .venv/bin/activate.fish)

# Install dependencies
pip install -r requirements.txt

# Create a database & user in PostgreSQL, grant ownership
# (See the detailed guide for exact commands.)

# Copy example env and fill in your own values
cp .env.example .env
```

Edit `.env`:

```dotenv
FLASK_APP=wsgi.py
FLASK_ENV=development
SECRET_KEY='generate-a-long-random-string'
DATABASE_URL='postgresql://youruser:yourpassword@localhost:5432/yourdbname'
```

Initialize the database (first‑time only):

```bash
rm -rf migrations          # Remove any old/stale migrations
flask db init

# IMPORTANT: Replace migrations/env.py with the correct version below (see detailed guide)
flask db migrate -m "Initial database schema"
flask db upgrade
```

Seed the database and start the server:

```bash
flask seed
flask run
```

The application will be available at `http://127.0.0.1:5000`.  
Login with **admin / admin**.

---

## Detailed Setup Guide

### Step 1: PostgreSQL Installation

#### Option A – Arch Linux (fish shell)

```bash
sudo pacman -S postgresql
sudo -iu postgres initdb --locale=en_US.UTF-8 -D /var/lib/postgres/data
sudo systemctl start postgresql.service
sudo systemctl enable postgresql.service

# Create a user and database
sudo -iu postgres createuser -P fin_user          # set password when prompted
sudo -iu postgres createdb -O fin_user finance_db

# Configure password authentication (CRITICAL)
sudo nano /var/lib/postgres/data/pg_hba.conf
```

In the editor, change the `peer` or `ident` lines to:

```text
local   all             all             scram-sha-256
host    all             all             127.0.0.1/32    scram-sha-256
```

Save and restart PostgreSQL:

```bash
sudo systemctl restart postgresql.service
```

#### Option B – Debian / Ubuntu (bash shell)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create a user and database
sudo -u postgres createuser -P fin_user          # set password when prompted
sudo -u postgres createdb -O fin_user finance_db

# Configure password authentication (CRITICAL)
sudo nano /etc/postgresql/14/main/pg_hba.conf   # path may vary by PG version
```

Change `peer` to `scram-sha-256`:

```text
local   all             all             scram-sha-256
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql.service
```

---

### Step 2: Application Setup

```bash
git clone https://github.com/Srm9385/finance-tracker.git
cd finance-tracker

python -m venv .venv
source .venv/bin/activate      # (fish: source .venv/bin/activate.fish)

pip install -r requirements.txt

# Create a .env file
cp .env.example .env
```

Edit `.env`:

```dotenv
FLASK_APP=wsgi.py
FLASK_ENV=development
SECRET_KEY='generate-a-long-random-string-here'

# PostgreSQL connection string
DATABASE_URL='postgresql://fin_user:your-password-here@localhost:5432/finance_db'
```

---

### Step 3: Database Initialization (First‑time setup)

1. **Reset migration history**

   ```bash
   rm -rf migrations
   ```

2. **Create a new migration environment**

   ```bash
   flask db init
   ```

3. **Replace `migrations/env.py`**  
   The default file must be replaced with the following content (CRITICAL for Flask‑Migrate to find your models):

   ```python
   # migrations/env.py
   from __future__ import with_statement
   import os
   from logging.config import fileConfig
   from alembic import context
   from flask import current_app

   config = context.config

   if config.config_file_name is not None:
       fileConfig(config.config_file_name)

   # --- CRITICAL ---
   # Import models so Alembic sees them
   from app import models
   # ----------------

   target_metadata = current_app.extensions['migrate'].db.metadata

   def run_migrations_offline():
       url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
       context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
       with context.begin_transaction():
           context.run_migrations()

   def run_migrations_online():
       connectable = current_app.extensions['migrate'].db.engine
       with connectable.connect() as connection:
           context.configure(connection=connection, target_metadata=target_metadata)
           with context.begin_transaction():
               context.run_migrations()

   if context.is_offline_mode():
       run_migrations_offline()
   else:
       run_migrations_online()
   ```

4. **Generate and apply the initial migration**

   ```bash
   flask db migrate -m "Initial database schema"
   flask db upgrade
   ```

---

### Step 4: Run the Application

1. **Seed the database** (creates the default admin user)

   ```bash
   flask seed
   ```

2. **Start the Flask development server**

   ```bash
   flask run
   ```

Open your browser at `http://127.0.0.1:5000`.  
Login using **admin / admin**.

---

## Troubleshooting

### How to Reset Everything

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

Then repeat the **Database Initialization** steps from Section 3.

---

*Happy tracking!*