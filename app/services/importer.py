# app/services/importer.py
import io
import pandas as pd
from datetime import timedelta, date
from copy import deepcopy

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


def _normalize_frame(df: pd.DataFrame, schema: dict):
    date_col = schema["date_col"]
    date_fmt = schema.get("date_fmt")
    desc_col = schema["desc_col"]

    # Optional: indicator (Credit/Debit) column
    indicator_col = schema.get("indicator_col")

    amount_col = schema.get("amount_col")
    debit_col = schema.get("debit_col")
    credit_col = schema.get("credit_col")
    balance_col = schema.get("balance_col")
    exclude_pending = schema.get("exclude_pending", False)  # (placeholder, unused for now)

    rows = []
    for _, row in df.iterrows():
        raw_date = str(row[date_col])
        raw_desc = str(row[desc_col])

        # Determine amount
        if amount_col:
            try:
                amount = float(row[amount_col])
            except Exception:
                amount = 0.0

            # Apply sign from indicator if present
            if indicator_col and indicator_col in row and row[indicator_col] not in (None, ""):
                ind = str(row[indicator_col]).strip().lower()
                if ind.startswith("credit") or ind in {"cr", "c", "credit memo"}:
                    amount = +abs(amount)
                elif ind.startswith("debit") or ind in {"dr", "d", "debit memo"}:
                    amount = -abs(amount)
                # else: leave as-is
        else:
            # Debit/Credit split style
            debit = float(row[debit_col]) if debit_col and row.get(debit_col) not in (None, "") else 0.0
            credit = float(row[credit_col]) if credit_col and row.get(credit_col) not in (None, "") else 0.0
            amount = credit - debit

        run_bal = None
        if balance_col and balance_col in row and row[balance_col] not in (None, ""):
            try:
                run_bal = float(row[balance_col])
            except Exception:
                run_bal = None

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
            Transaction.is_deleted == False,  # ignore soft-deleted
            Transaction.txn_date == txn["txn_date"],
            Transaction.description_raw == txn["description_raw"],
            Transaction.amount_cents == txn["amount_cents"],
        )
        .first()
    )


def detect_duplicates(account_id: int, normalized_rows: list[dict]):
    dup_exact = []
    dup_secondary = []
    to_insert = []

    for row in normalized_rows:
        # 1) exact dupe?
        ex = _find_exact_dupe(account_id, row)
        if ex:
            dup_exact.append((row, ex))  # for review info
            continue

        # 2) secondary dupe: same amount within ±N days, not deleted
        q = (
            db.session.query(Transaction.id)
            .filter(
                Transaction.account_id == account_id,
                Transaction.is_deleted == False,  # ignore soft-deleted
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
    """
    Find potential transfers among rows we plan to insert.
    Rule: negative amount (outflow) in this account within ±TRANSFER_WINDOW_DAYS
    has an equal and opposite amount in any *other* account (not soft-deleted).
    Returns list of dicts: {"new_index": idx, "new": row, "existing_id": match.id}
    """
    transfers = []
    for idx, it in enumerate(candidate_rows):
        amt = it["amount_cents"]
        if amt >= 0:
            continue  # only look for outflows here; inflow-side will be captured on the other account
        lo = it["txn_date"] - timedelta(days=TRANSFER_WINDOW_DAYS)
        hi = it["txn_date"] + timedelta(days=TRANSFER_WINDOW_DAYS)
        match = (
            Transaction.query
            .filter(
                Transaction.account_id != account_id,
                Transaction.is_deleted == False,                 # ignore soft-deleted
                Transaction.txn_date >= lo,
                Transaction.txn_date <= hi,
                Transaction.amount_cents == -amt,               # equal & opposite
            )
            .first()
        )
        if match:
            transfers.append({"new_index": idx, "new": it, "existing_id": match.id})
    return transfers


def run_import(user, file_storage, institution, account, mapper, app_config):
    raw = file_storage.read()

    # Compute SHA now and dedupe at the Import row level
    sha = sha256_of_bytes(raw)

    # Parse the CSV
    data = pd.read_csv(io.BytesIO(raw))
    normalized = _normalize_frame(data, mapper.schema_json)

    to_insert, dup_exact, dup_secondary = detect_duplicates(account.id, normalized)
    transfer_candidates = detect_transfers(to_insert, account.id)

    review = {
        "to_insert": to_insert,
        "dup_exact": [{"new": n, "existing_id": e.id} for (n, e) in dup_exact],
        "dup_secondary": [{"new": n, "existing_id": e.id} for (n, e) in dup_secondary],
        # keep the dicts with new_index so the UI can point back into to_insert
        "transfer_candidates": transfer_candidates,
        "row_count": len(normalized),
        "parse_errors": [],
    }

    # If an Import with same sha+account already exists, REUSE it
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

    # Otherwise create a fresh Import row with the correct sha
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
