# app/services/review.py
from __future__ import annotations

import os
import gzip
import hashlib
from datetime import date, datetime
from typing import Any, Dict, List

from dateutil import parser as dtp

from ..extensions import db
from ..models import Import, Transaction


# ----- helpers ---------------------------------------------------------------

def _ensure_date(d: Any) -> date:
    """Accept datetime.date already, or parse ISO/string to date."""
    if isinstance(d, date):
        return d
    return dtp.parse(str(d)).date()


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _archive_csv(
    raw_bytes: bytes,
    archive_dir: str,
    institution_name: str,
    account_name: str,
    original_filename: str,
) -> str:
    """
    Gzip the raw CSV into archive_dir/<institution>/<account>/YYYY/MM/<timestamp>_<sha8>_<filename>.gz
    Returns the *relative* archive path (useful to store in DB and to move roots later).
    """
    now = datetime.utcnow()
    y, m = now.strftime("%Y"), now.strftime("%m")
    sha8 = hashlib.sha256(raw_bytes).hexdigest()[:8]

    # Build dirs and filename
    rel_dir = os.path.join(institution_name, account_name, y, m)
    abs_dir = os.path.join(os.path.expanduser(archive_dir), rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    rel_name = f"{now.strftime('%Y%m%dT%H%M%S')}_{sha8}_{original_filename}.gz"
    rel_path = os.path.join(rel_dir, rel_name)
    abs_path = os.path.join(abs_dir, rel_name)

    # Write gzip
    with gzip.open(abs_path, "wb") as f:
        f.write(raw_bytes)

    return rel_path


def _revive_if_deleted(imp: Import, rows: List[Dict[str, Any]]) -> int:
    """
    For each row in rows, if a *soft-deleted* exact match exists, un-delete it and
    drop that row from the list so we don't insert a duplicate. Returns count revived.
    Matching rule: same account_id, txn_date, description_raw, amount_cents.
    """
    revived = 0
    # iterate a copy so we can remove from original list
    for row in list(rows):
        t = (
            db.session.query(Transaction)
            .filter(
                Transaction.account_id == imp.account_id,
                Transaction.is_deleted == True,  # previously soft-deleted
                Transaction.txn_date == _ensure_date(row["txn_date"]),
                Transaction.description_raw == row["description_raw"],
                Transaction.amount_cents == _safe_int(row["amount_cents"]),
            )
            .first()
        )
        if t:
            t.is_deleted = False
            t.deleted_at = None
            # provenance: link revived row to this import
            t.import_id = imp.id
            db.session.add(t)
            rows.remove(row)
            revived += 1
    return revived


# ----- main entrypoint -------------------------------------------------------

# ----- main entrypoint -------------------------------------------------------

def commit_import(
    imp: Import,
    raw_bytes: bytes,
    archive_dir: str,
    institution_name: str,
    account_name: str,
    decisions: Dict[str, Any],
) -> None:
    """
    Finalize an import:
      - handle user decisions on secondary duplicates.
      - optionally revive soft-deleted matches.
      - mark accepted transfers as is_transfer=True.
      - insert remaining rows.
      - gzip/archive the original CSV.
      - update Import counters/status/log.
    """
    review = imp.log_json.get("review", {}) if imp.log_json else {}
    to_insert: List[Dict[str, Any]] = list(review.get("to_insert", []))
    row_count = int(review.get("row_count") or len(to_insert) or 0)


    # --- MODIFICATION START ---
    # Handle user-approved secondary duplicates
    approved_dup_indices = set(decisions.get("accepted_secondary_duplicates") or [])
    if approved_dup_indices:
        secondary_duplicates = list(review.get("dup_secondary", []))
        for idx in approved_dup_indices:
            # Check index is valid
            if 0 <= idx < len(secondary_duplicates):
                # Add the 'new' transaction from the duplicate pair to our insert list
                to_insert.append(secondary_duplicates[idx]["new"])
    # Optional: revive previously soft-deleted duplicates instead of inserting
    revived = 0
    if decisions.get("revive_deleted"):
        revived = _revive_if_deleted(imp, to_insert)

    # Mark accepted transfers by index (indices refer to positions in to_insert)
    accepted = set(decisions.get("accepted_transfers") or [])
    for i, row in enumerate(to_insert):
        if i in accepted:
            row["is_transfer"] = True
            # Optional grouping token to correlate both sides of the transfer
            row["transfer_group"] = f"imp{imp.id}-{_safe_int(row.get('amount_cents'),0)}-{str(_ensure_date(row['txn_date']))}"

    # Insert remaining rows
    inserted = 0
    for row in to_insert:
        t = Transaction(
            account_id=imp.account_id,
            import_id=imp.id,
            txn_date=_ensure_date(row["txn_date"]),
            description_raw=row["description_raw"],
            merchant_normalized=row.get("merchant_normalized"),
            amount_cents=_safe_int(row["amount_cents"]),
            running_balance_cents=(
                None
                if row.get("running_balance_cents") in (None, "")
                else _safe_int(row["running_balance_cents"])
            ),
            is_transfer=bool(row.get("is_transfer", False)),
            is_joint=bool(row.get("is_joint", False)),
            transfer_group=row.get("transfer_group"),
            explain_json=row.get("explain_json"),
        )
        db.session.add(t)
        inserted += 1

    # Write archive (gzip) and store relative path
    archived_rel_path = _archive_csv(
        raw_bytes,
        archive_dir=archive_dir,
        institution_name=institution_name or "UnknownInstitution",
        account_name=account_name or "UnknownAccount",
        original_filename=imp.original_filename or "upload.csv",
    )

    # Update Import row
    duplicate_count = int(imp.duplicate_count or 0)
    error_count = 0

    imp.archived_path = archived_rel_path
    imp.added_count = inserted + revived
    imp.row_count = row_count
    imp.error_count = error_count
    imp.status = "success"
    # Enrich log_json with a commit stamp/summary
    log = imp.log_json or {}
    log["committed_at"] = datetime.utcnow().isoformat() + "Z"
    log["commit_summary"] = {
        "inserted": inserted,
        "revived": revived,
        "row_count": row_count,
        "duplicate_count_at_parse": duplicate_count,
        "accepted_transfers": sorted(list(accepted)),
    }
    imp.log_json = log

    db.session.commit()
