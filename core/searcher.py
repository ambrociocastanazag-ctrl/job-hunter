import itertools
import time
import random
import pandas as pd
from jobspy import scrape_jobs
from utils.logger import get_logger
from config.settings import (
    SITES, ALL_KEYWORDS, LOCATIONS,
    RESULTS_WANTED, HOURS_OLD_DAILY, HOURS_OLD_INITIAL,
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX,
)

logger = get_logger(__name__)

NORMALIZED_COLUMNS = [
    "site", "job_url", "title", "company", "location",
    "is_remote", "min_amount", "max_amount", "currency",
    "description", "date_posted",
]


def run_searches(
    keywords: list[str] | None = None,
    sites: list[str] | None = None,
    locations: list[str] | None = None,
    hours_old: int = HOURS_OLD_DAILY,
    results_wanted: int = RESULTS_WANTED,
) -> pd.DataFrame:
    keywords = keywords or ALL_KEYWORDS
    sites = sites or SITES
    locations = locations or LOCATIONS

    all_frames: list[pd.DataFrame] = []
    combos = list(itertools.product(sites, keywords, locations))
    total = len(combos)
    logger.info(f"Starting search: {total} combinations ({len(sites)} sites × {len(keywords)} keywords × {len(locations)} locations)")

    for i, (site, keyword, location) in enumerate(combos, 1):
        logger.info(f"[{i}/{total}] {site} | '{keyword}' | {location}")
        try:
            extra = {}
            if site in ("indeed", "glassdoor", "zip_recruiter"):
                extra["country_indeed"] = "usa"
            if site == "linkedin":
                # Sin esto LinkedIn devuelve descripciones vacías
                extra["linkedin_fetch_description"] = True

            df = scrape_jobs(
                site_name=[site],
                search_term=keyword,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                is_remote=True,
                **extra,
            )
            if df is not None and not df.empty:
                df["_search_keyword"] = keyword
                df["_search_location"] = location
                all_frames.append(df)
                logger.info(f"  -> {len(df)} results")
            else:
                logger.info("  -> 0 results")
        except Exception as e:
            logger.warning(f"  -> ERROR: {e}")

        if i < total:
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

    if not all_frames:
        logger.warning("No results from any combination.")
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)

    combined = pd.concat(all_frames, ignore_index=True)
    logger.info(f"Total raw results: {len(combined)}")
    return _normalize(combined)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {
        "site": "site",
        "job_url": "job_url",
        "title": "title",
        "company": "company",
        "location": "location",
        "is_remote": "is_remote",
        "min_amount": "min_amount",
        "max_amount": "max_amount",
        "currency": "currency",
        "description": "description",
        "date_posted": "date_posted",
    }
    existing = {k: v for k, v in col_map.items() if k in df.columns}
    out = df[list(existing.keys())].rename(columns=existing)

    for col in NORMALIZED_COLUMNS:
        if col not in out.columns:
            out[col] = None

    out["description"] = out["description"].fillna("")
    out["title"] = out["title"].fillna("").str.strip()
    out["company"] = out["company"].fillna("").str.strip()
    out["location"] = out["location"].fillna("").str.strip()
    out["is_remote"] = out["is_remote"].fillna(False).astype(bool)

    return out[NORMALIZED_COLUMNS].copy()
