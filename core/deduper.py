import hashlib
import re
import pandas as pd
from utils.logger import get_logger

logger = get_logger(__name__)


def _norm_url(url: str) -> str:
    url = (url or "").strip().lower()
    url = re.sub(r"[?&].*$", "", url)   # strip query params
    url = url.rstrip("/")
    return url


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def make_url_hash(url: str) -> str:
    return hashlib.sha1(_norm_url(url).encode()).hexdigest()


def make_content_hash(title: str, company: str) -> str:
    key = _norm_text(title) + "|" + _norm_text(company)
    return hashlib.sha1(key.encode()).hexdigest()


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove in-batch duplicates by url_hash and content_hash."""
    before = len(df)

    df = df.copy()
    df["url_hash"] = df["job_url"].apply(make_url_hash)
    df["content_hash"] = df.apply(
        lambda r: make_content_hash(r["title"], r["company"]), axis=1
    )

    # Drop duplicate url_hash first, then content_hash
    df = df.drop_duplicates(subset=["url_hash"])
    df = df.drop_duplicates(subset=["content_hash"])

    after = len(df)
    logger.info(f"Deduped: {before} -> {after} ({before - after} duplicates removed)")
    return df.reset_index(drop=True)
