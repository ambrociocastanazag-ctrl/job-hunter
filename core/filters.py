import re
from datetime import datetime, timezone, timedelta
import pandas as pd
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.copy()
    filters_cfg = get_settings()["filters"]

    # Ensure required columns exist before filtering
    for col in ["title", "description", "location", "is_remote", "date_posted"]:
        if col not in df.columns:
            df[col] = None if col == "date_posted" else ""

    df = _filter_exclude_title(df, filters_cfg["exclude_title_words"])
    if df.empty:
        logger.info(f"Filtered: {before} -> 0 (all removed by title filter)")
        return df
    df = _filter_location(df, filters_cfg["allowed_location_patterns"])
    if df.empty:
        logger.info(f"Filtered: {before} -> 0 (all removed by location filter)")
        return df
    df = _filter_age(df, filters_cfg["max_age_days"])
    if df.empty:
        logger.info(f"Filtered: {before} -> 0 (all removed by age filter)")
        return df
    df = _filter_impossible_years(df, filters_cfg["impossible_years_patterns"])

    after = len(df)
    logger.info(f"Filtered: {before} -> {after} ({before - after} removed)")
    return df.reset_index(drop=True)


def _filter_exclude_title(df: pd.DataFrame, patterns: list[str]) -> pd.DataFrame:
    if not patterns:
        return df
    combined = "|".join(patterns)
    mask = df["title"].str.contains(combined, flags=re.IGNORECASE, na=False, regex=True)
    removed = mask.sum()
    if removed:
        logger.debug(f"  Excluded by title keywords: {removed}")
    return df[~mask]


def _filter_location(df: pd.DataFrame, patterns: list[str]) -> pd.DataFrame:
    if not patterns:
        return df
    combined = "|".join(patterns)

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


def _filter_age(df: pd.DataFrame, max_age_days: int) -> pd.DataFrame:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

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


def _filter_impossible_years(df: pd.DataFrame, patterns: list[str]) -> pd.DataFrame:
    if not patterns:
        return df
    combined = "|".join(patterns)

    def has_impossible(desc: str) -> bool:
        return bool(re.search(combined, desc or "", re.IGNORECASE))

    mask = df["description"].apply(has_impossible)
    removed = mask.sum()
    if removed:
        logger.debug(f"  Excluded by impossible years req: {removed}")
    return df[~mask]
