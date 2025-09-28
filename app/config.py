import os
from dotenv import load_dotenv, find_dotenv

class Config:
    def __init__(self):
        # Load .env now…
        load_dotenv(find_dotenv(), override=False)
        # …and set INSTANCE attributes (not class attrs)
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
        self.SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", "~/AI/finance_tracker/archive")