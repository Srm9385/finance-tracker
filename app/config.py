# srm9385/finance-tracker/finance-tracker-b6479a0b9b4b550a18703e80c76c724f6985583c/app/config.py
import os
from dotenv import load_dotenv, find_dotenv

dotenv_path = find_dotenv()
if not dotenv_path:
    print("WARNING: .env file not found. Relying on system environment variables.")
load_dotenv(dotenv_path)


class Config:
    def __init__(self):

        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", os.path.expanduser("~/.finance_tracker_archive"))

        # --- START MODIFICATION ---
        self.BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.expanduser("~/.finance_tracker_backup"))
        # --- END MODIFICATION ---

        self.OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME")

        if not self.SQLALCHEMY_DATABASE_URI:
            raise ValueError("DATABASE_URL is not set in your .env file or environment variables. "
                             "The application cannot start without it.")
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY is not set in your .env file or environment variables.")