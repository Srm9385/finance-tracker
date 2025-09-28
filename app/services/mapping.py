from ..extensions import db
from ..models import Mapper

COMMON_DATE = {"date", "posted date", "transaction date", "posting date"}
COMMON_DESC = {"description", "memo", "details", "name", "payee"}
COMMON_AMOUNT = {"amount", "amt", "transaction amount"}
COMMON_DEBIT = {"debit", "withdrawal", "outflow", "charge"}
COMMON_CREDIT = {"credit", "deposit", "inflow", "payment"}
COMMON_BAL = {"balance", "running balance", "available balance", "current balance"}

# NEW: common indicator names
COMMON_INDICATOR = {
    "credit debit indicator", "credit/debit indicator",
    "dr/cr", "cr/dr", "transaction type", "type", "debit/credit"
}

def _normalize_header(h: str) -> str:
    return h.strip().lower().replace("-", " ").replace("_", " ")

def latest_mapper_for(account_id: int, institution_id: int):
    q = Mapper.query.filter_by(account_id=account_id, institution_id=institution_id).order_by(Mapper.version.desc())
    return q.first()

def create_mapper(institution_id: int, account_id: int | None, schema_json: dict) -> Mapper:
    q = Mapper.query.filter_by(institution_id=institution_id, account_id=account_id)
    latest = q.order_by(Mapper.version.desc()).first()
    next_version = 1 if not latest else latest.version + 1
    m = Mapper(institution_id=institution_id, account_id=account_id, version=next_version, schema_json=schema_json)
    db.session.add(m)
    db.session.commit()
    return m

def _normalize_header(h: str) -> str:
    return h.strip().lower().replace("-", " ").replace("_", " ")

def guess_mapping_from_headers(headers: list[str]) -> dict:
    H = [_normalize_header(h) for h in headers]

    def find(candidates):
        for i, h in enumerate(H):
            if h in candidates:
                return headers[i]
        return None

    date_col = find(COMMON_DATE) or headers[0]
    desc_col = find(COMMON_DESC) or (headers[1] if len(headers) > 1 else headers[0])

    amount_col = find(COMMON_AMOUNT)
    debit_col = None if amount_col else find(COMMON_DEBIT)
    credit_col = None if amount_col else find(COMMON_CREDIT)
    balance_col = find(COMMON_BAL)

    # NEW: try to find indicator col
    indicator_col = find(COMMON_INDICATOR)

    return {
        "date_col": date_col,
        "date_fmt": "%m/%d/%Y",
        "desc_col": desc_col,
        "amount_col": amount_col,
        "indicator_col": indicator_col,   # <— NEW
        "debit_col": debit_col,
        "credit_col": credit_col,
        "balance_col": balance_col,
        "exclude_pending": False,
    }