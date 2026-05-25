"""
Job Hunter — entry point CLI
Usage:
  python main.py --mode initial    # Primera corrida, 30 dias atras
  python main.py --mode daily      # Corrida incremental diaria (default)
  python main.py --mode export     # Solo regenera Excel desde DB
  python main.py --mode stats      # Muestra estadisticas del pipeline
"""

import argparse
import sys
import os
from datetime import date, datetime, timezone

# Allow running from job_hunter/ or from project root
sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import get_logger
from storage.database import init_db
from storage.repository import save_jobs, mark_existing_as_old, get_new_jobs
from storage.models import SearchRun
from core.searcher import run_searches
from core.deduper import dedupe
from core.filters import apply_filters
from core.scorer import score_dataframe
from core.enricher import enrich_dataframe
from exporters.excel import export_daily
from exporters.markdown import export_digest
from notifications.telegram import send_digest
from config.settings import HOURS_OLD_INITIAL, HOURS_OLD_DAILY, MIN_SCORE

logger = get_logger("main")


def cmd_initial():
    logger.info("=== MODE: INITIAL (30-day backfill) ===")
    _run_search(hours_old=HOURS_OLD_INITIAL, notify=False)


def cmd_daily():
    logger.info("=== MODE: DAILY ===")
    _run_search(hours_old=HOURS_OLD_DAILY, notify=True)


def _run_search(hours_old: int, notify: bool):
    started = datetime.now(timezone.utc)
    run = SearchRun(started_at=started, params_json={"hours_old": hours_old})
    error_count = 0

    try:
        # 1. Scrape
        raw_df = run_searches(hours_old=hours_old)
        total_found = len(raw_df)

        if raw_df.empty:
            logger.warning("No results found. Aborting.")
            return

        # 2. Dedupe (batch)
        deduped = dedupe(raw_df)

        # 3. Filter
        filtered = apply_filters(deduped)

        # 4. Enrich
        enriched = enrich_dataframe(filtered)

        # 5. Score
        scored = score_dataframe(enriched)

        # 6. Mark old jobs before inserting new
        mark_existing_as_old()

        # 7. Persist (DB dedupes against existing)
        new_count = save_jobs(scored)

        # 8. Export
        today = date.today()
        excel_path = export_daily(today)
        md_path = export_digest(today)
        logger.info(f"Exports ready: {excel_path} | {md_path}")

        # 9. Notify
        if notify:
            new_jobs = get_new_jobs(today)
            top = new_jobs.sort_values("score", ascending=False).head(10) if not new_jobs.empty else new_jobs
            stats = {
                "date": today.isoformat(),
                "new_count": new_count,
                "total_found": total_found,
                "filtered": total_found - len(filtered),
            }
            send_digest(top, stats)

        run.total_found = total_found
        run.new_count = new_count
        run.error_count = error_count

    except Exception as e:
        logger.exception(f"Search run failed: {e}")
        error_count += 1
    finally:
        run.finished_at = datetime.now(timezone.utc)
        run.error_count = error_count


def cmd_export():
    logger.info("=== MODE: EXPORT ===")
    today = date.today()
    excel_path = export_daily(today)
    md_path = export_digest(today)
    logger.info(f"Excel: {excel_path}")
    logger.info(f"Markdown: {md_path}")


def cmd_stats():
    logger.info("=== MODE: STATS ===")
    from storage.repository import get_pipeline_jobs
    import pandas as pd

    all_jobs = get_pipeline_jobs()
    if all_jobs.empty:
        print("No jobs in DB yet.")
        return

    total = len(all_jobs)
    scored = all_jobs[all_jobs["score"].notna()]
    applied = all_jobs[all_jobs["status"].notna() & (all_jobs["status"] != "Pendiente")]

    print(f"\n{'='*40}")
    print(f"  JOB HUNTER STATS")
    print(f"{'='*40}")
    print(f"  Total jobs in DB   : {total}")
    print(f"  Mean score         : {scored['score'].mean():.1f}" if not scored.empty else "  Mean score: N/A")
    print(f"  Jobs scored >=50   : {len(scored[scored['score'] >= 50])}")
    print(f"  Jobs scored >=70   : {len(scored[scored['score'] >= 70])}")
    print(f"  Applied            : {len(applied)}")
    if not applied.empty and "status" in applied.columns:
        print("\n  Status breakdown:")
        for status, count in applied["status"].value_counts().items():
            print(f"    {status:<20}: {count}")
    print(f"{'='*40}\n")


def main():
    parser = argparse.ArgumentParser(description="Job Hunter — automated job search with JobSpy")
    parser.add_argument(
        "--mode",
        choices=["daily", "initial", "export", "stats"],
        default="daily",
        help="Execution mode",
    )
    args = parser.parse_args()

    init_db()

    dispatch = {
        "daily": cmd_daily,
        "initial": cmd_initial,
        "export": cmd_export,
        "stats": cmd_stats,
    }
    dispatch[args.mode]()


if __name__ == "__main__":
    main()
