# app/services/importer.py
import io
import pandas as pd
from datetime import timedelta, date
from copy import deepcopy
import re # Import the regular expression module

from ..extensions import db
from ..models import Import, Transaction
from ..utils import parse_date, to_cents
from .archive import sha256_of_bytes

SECONDARY_DUP_WINDOW_DAYS = 10
TRANSFER_WINDOW_DAYS = 2


def _json_safe_review(r):
    """Convert any date objects to ISO strings so JSONB can store them; keep new_index on transfers."""
    def fix_txn(d):
        d = dict(d)
        if isinstance(d.get("txn_date"), (date,)):
            d["txn_date"] = d["txn_date"].isoformat()
        return d

    out = deepcopy(r)
    out["to_insert"] = [fix_txn(x) for x in r.get("to_insert", [])]
    out["dup_exact"] = [
        {"new": fix_txn(p["new"]), "existing_id": p["existing_id"]}
        for p in r.get("dup_exact", [])
    ]
    out["dup_secondary"] = [
        {"new": fix_txn(p["new"]), "existing_id": p["existing_id"]}
        for p in r.get("dup_secondary", [])
    ]
    # Preserve new_index here
    out["transfer_candidates"] = [
        {"new_index": p["new_index"], "new": fix_txn(p["new"]), "existing_id": p["existing_id"]}
        for p in r.get("transfer_candidates", [])
    ]
    return out

# --- START MODIFICATION ---
def _clean_amount(value):
    """Helper function to remove currency symbols, commas, and handle NaN."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, str):
        # Remove any character that is not a digit, a decimal point, or a minus sign
        cleaned_value = re.sub(r'[^\d.-]', '', value)
        return cleaned_value if cleaned_value else 0.0
    return value
# --- END MODIFICATION ---

def _normalize_frame(df: pd.DataFrame, schema: dict):
    date_col = schema["date_col"]
    date_fmt = schema.get("date_fmt")
    desc_col = schema["desc_col"]

    indicator_col = schema.get("indicator_col")
    amount_col = schema.get("amount_col")
    debit_col = schema.get("debit_col")
    credit_col = schema.get("credit_col")
    balance_col = schema.get("balance_col")
    exclude_pending = schema.get("exclude_pending", False)

    rows = []
    for _, row in df.iterrows():
        raw_date = str(row[date_col])
        raw_desc = str(row[desc_col])

        # --- START MODIFICATION ---
        try:
            if amount_col:
                amount = float(_clean_amount(row.get(amount_col)))
                if indicator_col and row.get(indicator_col) not in (None, ""):
                    ind = str(row[indicator_col]).strip().lower()
                    if ind.startswith("credit") or ind in {"cr", "c", "credit memo"}:
                        amount = +abs(amount)
                    elif ind.startswith("debit") or ind in {"dr", "d", "debit memo"}:
                        amount = -abs(amount)
            else:
                debit = float(_clean_amount(row.get(debit_col)))
                credit = float(_clean_amount(row.get(credit_col)))
                amount = credit - debit

            run_bal = float(_clean_amount(row.get(balance_col))) if balance_col else None
        except (ValueError, TypeError) as e:
            # Skip rows that have unparsable amount fields
            print(f"Skipping row due to amount parsing error: {e}, row: {row}")
            continue
        # --- END MODIFICATION ---

        rows.append({
            "txn_date": parse_date(raw_date, date_fmt),
            "description_raw": raw_desc,
            "merchant_normalized": None,
            "amount_cents": to_cents(amount),
            "running_balance_cents": None if run_bal is None else to_cents(run_bal),
        })
    return rows


def _find_exact_dupe(account_id, txn):
    return (
        db.session.query(Transaction.id)
        .filter(
            Transaction.account_id == account_id,
            Transaction.is_deleted == False,
            Transaction.txn_date == txn["txn_date"],
            Transaction.description_raw == txn["description_raw"],
            Transaction.amount_cents == txn["amount_cents"],
        )
        .first()
    )


def detect_duplicates(account_id: int, normalized_rows: list[dict]):
    # (This function remains the same)
    dup_exact = []
    dup_secondary = []
    to_insert = []

    for row in normalized_rows:
        ex = _find_exact_dupe(account_id, row)
        if ex:
            dup_exact.append((row, ex))
            continue

        q = (
            db.session.query(Transaction.id)
            .filter(
                Transaction.account_id == account_id,
                Transaction.is_deleted == False,
                Transaction.amount_cents == row["amount_cents"],
                Transaction.txn_date >= row["txn_date"] - timedelta(days=SECONDARY_DUP_WINDOW_DAYS),
                Transaction.txn_date <= row["txn_date"] + timedelta(days=SECONDARY_DUP_WINDOW_DAYS),
            )
        )
        sec = q.first()
        if sec:
            dup_secondary.append((row, sec))
            continue

        to_insert.append(row)

    return to_insert, dup_exact, dup_secondary


def detect_transfers(candidate_rows: list[dict], account_id: int):
    # (This function remains the same)
    transfers = []
    for idx, it in enumerate(candidate_rows):
        amt = it["amount_cents"]
        if amt >= 0:
            continue
        lo = it["txn_date"] - timedelta(days=TRANSFER_WINDOW_DAYS)
        hi = it["txn_date"] + timedelta(days=TRANSFER_WINDOW_DAYS)
        match = (
            Transaction.query
            .filter(
                Transaction.account_id != account_id,
                Transaction.is_deleted == False,
                Transaction.txn_date >= lo,
                Transaction.txn_date <= hi,
                Transaction.amount_cents == -amt,
            )
            .first()
        )
        if match:
            transfers.append({"new_index": idx, "new": it, "existing_id": match.id})
    return transfers


def run_import(user, file_storage, institution, account, mapper, app_config):
    # (This function remains the same)
    raw = file_storage.read()
    sha = sha256_of_bytes(raw)
    data = pd.read_csv(io.BytesIO(raw))
    normalized = _normalize_frame(data, mapper.schema_json)

    to_insert, dup_exact, dup_secondary = detect_duplicates(account.id, normalized)
    transfer_candidates = detect_transfers(to_insert, account.id)

    review = {
            "to_insert": to_insert,
            "dup_exact": [{"new": n, "existing_id": e.id} for (n, e) in dup_exact],
            "dup_secondary": [{"new": n, "existing_id": e.id} for (n, e) in dup_secondary],
            "transfer_candidates": transfer_candidates,
            "row_count": len(normalized),
            "parse_errors": [],
    }

    existing = Import.query.filter_by(original_sha256=sha, account_id=account.id).first()
    if existing:
        existing.mapper_id = mapper.id
        existing.log_json = {"review": _json_safe_review(review)}
        existing.row_count = len(normalized)
        existing.added_count = 0
        existing.duplicate_count = len(dup_exact) + len(dup_secondary)
        existing.error_count = 0
        existing.status = "partial"
        db.session.commit()
        return existing, raw, review

    imp = Import(
        institution_id=institution.id,
        account_id=account.id,
        mapper_id=mapper.id,
        original_filename=file_storage.filename,
        original_sha256=sha,
        status="partial",
        log_json={"review": _json_safe_review(review)},
        row_count=len(normalized),
        added_count=0,
        duplicate_count=len(dup_exact) + len(dup_secondary),
        error_count=0,
    )
    db.session.add(imp)
    db.session.commit()
    return imp, raw, review