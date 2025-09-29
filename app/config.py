import os
from dotenv import load_dotenv, find_dotenv


dotenv_path = find_dotenv()
if not dotenv_path:
    print("WARNING: .env file not found. Relying on system environment variables.")
load_dotenv(dotenv_path)
# --- End of Fix ---

class Config:
    def __init__(self):

        # Set instance attributes from the now-loaded environment
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", os.path.expanduser("~/.finance_tracker_archive"))

        # --- ADDED: Optional AI Settings ---
        self.OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME")

        # --- ADDED: A "Guard Clause" to prevent silent failures ---
        # If the database URI is still missing after trying to load it,
        # raise an exception with a helpful message.
        if not self.SQLALCHEMY_DATABASE_URI:
            raise ValueError("DATABASE_URL is not set in your .env file or environment variables. "
                             "The application cannot start without it.")
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY is not set in your .env file or environment variables.")