# troubleshoot_db.py
# A script to force the database migration and expose any hidden errors.

import os
from dotenv import load_dotenv

print("[DEBUG] Loading .env file...")
load_dotenv()

# Verify that the DATABASE_URL was loaded
db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("[ERROR] DATABASE_URL not found in environment. Halting.")
    exit(1)
print(f"[DEBUG] DATABASE_URL found: {db_url}")

print("[DEBUG] Importing Flask-Migrate and the app factory...")
from flask_migrate import upgrade
from app import create_app

try:
    print("[DEBUG] Creating Flask app instance...")
    app = create_app()

    # The 'with app.app_context()' is crucial. It makes the application
    # and its configuration available to the upgrade command.
    with app.app_context():
        print("[DEBUG] App context created. Calling upgrade()...")
        # The upgrade() function will apply all migrations to the database.
        upgrade()
        print("\n[SUCCESS] Database migration upgrade() command completed without errors.")
        print("[SUCCESS] Tables should now be created.")

except Exception as e:
    print("\n" + "=" * 80)
    print("[ERROR] An exception occurred during the upgrade process!")
    print("=" * 80)
    import traceback

    traceback.print_exc()
    print("=" * 80)
    print("[ERROR] The traceback above is the root cause of the problem.")