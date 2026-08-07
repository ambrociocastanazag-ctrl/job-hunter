import itertools
import time
import random
import pandas as pd
from jobspy import scrape_jobs
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

NORMALIZED_COLUMNS = [
    "site", "job_url", "title", "company", "location",
    "is_remote", "min_amount", "max_amount", "currency",
    "description", "date_posted",
]


def count_combinations(sites, keywords, locations, job_types=None) -> int:
    job_type_dim = job_types or [None]
    return len(sites) * len(keywords) * len(locations) * len(job_type_dim)


def run_searches(
    keywords: list[str] | None = None,
    sites: list[str] | None = None,
    locations: list[str] | None = None,
    hours_old: int | None = None,
    results_wanted: int | None = None,
    job_types: list[str] | None = None,
    work_modes: list[str] | None = None,
) -> pd.DataFrame:
    settings = get_settings()
    search_cfg = settings["search"]
    runtime_cfg = settings["runtime"]

    keywords = keywords or search_cfg["keywords"]
    sites = sites or search_cfg["sites"]
    locations = locations or search_cfg["locations"]
    hours_old = hours_old if hours_old is not None else search_cfg["hours_old_daily"]
    results_wanted = results_wanted if results_wanted is not None else search_cfg["results_wanted"]
    job_types = job_types if job_types is not None else search_cfg["job_types"]
    work_modes = work_modes if work_modes is not None else search_cfg["work_modes"]

    # Comportamiento histórico: is_remote=True siempre. Ahora solo se fuerza
    # cuando "remote" es la única modalidad activa; con híbrido/presencial en
    # la mezcla no se restringe el parámetro y se deja que el filtro de
    # ubicación (core/filters.py) decida.
    force_remote = work_modes == ["remote"]
    job_type_dim = job_types or [None]

    all_frames: list[pd.DataFrame] = []
    combos = list(itertools.product(sites, keywords, locations, job_type_dim))
    total = len(combos)
    logger.info(
        f"Starting search: {total} combinations "
        f"({len(sites)} sites × {len(keywords)} keywords × {len(locations)} locations"
        + (f" × {len(job_type_dim)} job types)" if job_types else ")")
    )

    retry_delays = runtime_cfg["retry_delays"]
    delay_min = runtime_cfg["request_delay_min"]
    delay_max = runtime_cfg["request_delay_max"]
    country_indeed = runtime_cfg["country_indeed"]

    for i, (site, keyword, location, job_type) in enumerate(combos, 1):
        suffix = f" | {job_type}" if job_type else ""
        logger.info(f"[{i}/{total}] {site} | '{keyword}' | {location}{suffix}")

        extra = {}
        if site in ("indeed", "glassdoor", "zip_recruiter"):
            extra["country_indeed"] = country_indeed
        if site == "linkedin":
            extra["linkedin_fetch_description"] = True
        if job_type:
            extra["job_type"] = job_type

        df = None
        for attempt in range(len(retry_delays) + 1):
            try:
                df = scrape_jobs(
                    site_name=[site],
                    search_term=keyword,
                    location=location,
                    results_wanted=results_wanted,
                    hours_old=hours_old,
                    is_remote=force_remote,
                    **extra,
                )
                break
            except Exception as e:
                if attempt < len(retry_delays):
                    delay = retry_delays[attempt]
                    logger.warning(f"  -> ERROR (intento {attempt + 1}/{len(retry_delays) + 1}): {e}. Reintentando en {delay}s...")
                    time.sleep(delay)
                else:
                    logger.warning(f"  -> ERROR tras {len(retry_delays) + 1} intentos: {e}")

        if df is not None and not df.empty:
            df["_search_keyword"] = keyword
            df["_search_location"] = location
            all_frames.append(df)
            logger.info(f"  -> {len(df)} results")
        else:
            logger.info("  -> 0 results")

        if i < total:
            time.sleep(random.uniform(delay_min, delay_max))

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
