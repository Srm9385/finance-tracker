from datetime import datetime
from dateutil import parser as dtp

def parse_date(value: str, fmt: str | None):
    if fmt:
        return datetime.strptime(value.strip(), fmt).date()
    return dtp.parse(value).date()

def to_cents(value: float | str) -> int:
    f = float(value)
    return int(round(f * 100))

def coalesce(*vals):
    for v in vals:
        if v not in (None, ""):
            return v
    return None
