import hashlib, os, gzip
from datetime import datetime

def sha256_of_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def archive_csv(raw_bytes: bytes, original_name: str, archive_root: str, institution: str, account: str):
    sha = sha256_of_bytes(raw_bytes)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_inst = institution.replace("/", "_")
    safe_acct = account.replace("/", "_")
    subdir = os.path.join(os.path.expanduser(archive_root), safe_inst, safe_acct, datetime.utcnow().strftime("%Y-%m"))
    os.makedirs(subdir, exist_ok=True)
    gz_path = os.path.join(subdir, f"{ts}__{original_name}.gz")
    with gzip.open(gz_path, "wb") as f:
        f.write(raw_bytes)
    return gz_path, sha
