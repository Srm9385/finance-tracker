from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .extensions import db

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Institution(db.Model):
    __tablename__ = "institutions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    accounts = db.relationship("Account", backref="institution", lazy=True)

class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"))
    name = db.Column(db.Text, nullable=False)
    type = db.Column(db.Text, nullable=False)
    currency = db.Column(db.Text, default="USD")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Mapper(db.Model):
    __tablename__ = "mappers"
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"))
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    version = db.Column(db.Integer, nullable=False)
    schema_json = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Import(db.Model):
    __tablename__ = "imports"
    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"))
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    mapper_id = db.Column(db.Integer, db.ForeignKey("mappers.id"))
    original_filename = db.Column(db.Text, nullable=False)
    original_sha256 = db.Column(db.Text, nullable=False)
    archived_path = db.Column(db.Text)
    row_count = db.Column(db.Integer)
    added_count = db.Column(db.Integer)
    duplicate_count = db.Column(db.Integer)
    error_count = db.Column(db.Integer)
    status = db.Column(db.Text, nullable=False)
    log_json = db.Column(JSONB)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    institution = db.relationship("Institution", lazy="joined")
    account = db.relationship("Account", lazy="joined")
    mapper = db.relationship("Mapper", lazy="joined")

class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), index=True)
    import_id = db.Column(db.Integer, db.ForeignKey("imports.id"), index=True)
    txn_date = db.Column(db.Date, nullable=False, index=True)
    description_raw = db.Column(db.Text, nullable=False)
    merchant_normalized = db.Column(db.Text)
    amount_cents = db.Column(db.BigInteger, nullable=False)
    running_balance_cents = db.Column(db.BigInteger)
    is_transfer = db.Column(db.Boolean, default=False)
    transfer_group = db.Column(db.Text)
    explain_json = db.Column(JSONB)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    is_refund = db.Column(db.Boolean, default=False)
    is_joint = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True, nullable=True)
    category = db.relationship("Category", lazy="joined")
    account = db.relationship("Account", backref="transactions")

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    group = db.Column(db.Text, nullable=False)
    name = db.Column(db.Text, nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Rule(db.Model):
    __tablename__ = "rules"
    id = db.Column(db.Integer, primary_key=True)
    # The keyword to search for in the transaction description (e.g., "AMAZON")
    keyword = db.Column(db.Text, nullable=False, unique=True, index=True)
    # The category to assign if the keyword is found
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Establish a relationship to the Category model
    category = db.relationship("Category", lazy="joined")

class TransferKeyword(db.Model):
    __tablename__ = "transfer_keywords"
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.Text, nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RefundKeyword(db.Model):
    __tablename__ = "refund_keywords"
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.Text, nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
