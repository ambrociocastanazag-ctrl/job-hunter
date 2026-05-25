import re
from datetime import datetime, timezone, timedelta
import pandas as pd
from config.settings import EXCLUDE_TITLE_WORDS, MAX_AGE_DAYS
from utils.logger import get_logger

logger = get_logger(__name__)

# Países/regiones aceptados en location
ALLOWED_LOCATION_PATTERNS = [
    r"remote", r"worldwide", r"anywhere", r"global",
    r"latin america", r"latam", r"central america",
    r"south america", r"north america",
    r"guatemala", r"mexico", r"colombia", r"argentina",
    r"chile", r"peru", r"ecuador", r"costa rica",
    r"united states", r"usa", r"us\b",
    r"canada",
]

IMPOSSIBLE_YEARS = [
    r"\b[5-9]\+\s*year", r"\b1[0-9]\+\s*year",
    r"\b[5-9]\s*years?\s*of\s*(experience|exp)",
    r"\b1[0-9]\s*years?\s*of\s*(experience|exp)",
]


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.copy()

    # Ensure required columns exist before filtering
    for col in ["title", "description", "location", "is_remote", "date_posted"]:
        if col not in df.columns:
            df[col] = None if col == "date_posted" else ""

    df = _filter_exclude_title(df)
    if df.empty:
        logger.info(f"Filtered: {before} -> 0 (all removed by title filter)")
        return df
    df = _filter_location(df)
    if df.empty:
        logger.info(f"Filtered: {before} -> 0 (all removed by location filter)")
        return df
    df = _filter_age(df)
    if df.empty:
        logger.info(f"Filtered: {before} -> 0 (all removed by age filter)")
        return df
    df = _filter_impossible_years(df)

    after = len(df)
    logger.info(f"Filtered: {before} -> {after} ({before - after} removed)")
    return df.reset_index(drop=True)


def _filter_exclude_title(df: pd.DataFrame) -> pd.DataFrame:
    combined = "|".join(EXCLUDE_TITLE_WORDS)
    mask = df["title"].str.contains(combined, flags=re.IGNORECASE, na=False, regex=True)
    removed = mask.sum()
    if removed:
        logger.debug(f"  Excluded by title keywords: {removed}")
    return df[~mask]


def _filter_location(df: pd.DataFrame) -> pd.DataFrame:
    combined = "|".join(ALLOWED_LOCATION_PATTERNS)

    def is_ok(row) -> bool:
        if row.get("is_remote"):
            return True
        loc = str(row.get("location", ""))
        return bool(re.search(combined, loc, re.IGNORECASE))

    mask = df.apply(is_ok, axis=1)
    removed = (~mask).sum()
    if removed:
        logger.debug(f"  Excluded by location: {removed}")
    return df[mask]


def _filter_age(df: pd.DataFrame) -> pd.DataFrame:
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    def is_recent(val) -> bool:
        if pd.isna(val) or val is None:
            return True  # keep if no date
        try:
            dt = pd.to_datetime(val, utc=True)
            return dt >= cutoff
        except Exception:
            return True

    mask = df["date_posted"].apply(is_recent)
    removed = (~mask).sum()
    if removed:
        logger.debug(f"  Excluded by age: {removed}")
    return df[mask]


def _filter_impossible_years(df: pd.DataFrame) -> pd.DataFrame:
    combined = "|".join(IMPOSSIBLE_YEARS)

    def has_impossible(desc: str) -> bool:
        return bool(re.search(combined, desc or "", re.IGNORECASE))

    mask = df["description"].apply(has_impossible)
    removed = mask.sum()
    if removed:
        logger.debug(f"  Excluded by impossible years req: {removed}")
    return df[~mask]
