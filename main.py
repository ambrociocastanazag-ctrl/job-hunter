"""
Job Hunter — entry point CLI
Usage:
  python main.py --mode initial    # Primera corrida, 30 dias atras
  python main.py --mode daily      # Corrida incremental diaria (default)
  python main.py --mode export     # Regenera el digest markdown desde DB
  python main.py --mode stats      # Muestra estadisticas del pipeline

Overrides opcionales (usados por el dashboard para corridas manuales/programadas):
  --hours-old INT
  --results-wanted INT
  --sites-json '["linkedin","indeed"]'
  --keywords-json '["Python Developer"]'
  --locations-json '["Remote"]'
  --no-notify
  --run-id INT   (vincula esta corrida a una fila SearchRun ya creada)
"""

import argparse
import json
import sys
import os
from datetime import date, datetime, timezone

# Allow running from job_hunter/ or from project root
sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import get_logger
from storage.database import init_db
from storage.repository import (
    save_jobs, mark_existing_as_old, get_new_jobs,
    create_search_run, finish_search_run,
)
from storage.models import SearchRun
from core.searcher import run_searches
from core.deduper import dedupe
from core.filters import apply_filters
from core.scorer import score_dataframe
from core.enricher import enrich_dataframe
from exporters.markdown import export_digest
from notifications.telegram import send_digest, send_hot_alert
from config.settings import get_settings

logger = get_logger("main")


def cmd_initial(args):
    logger.info("=== MODE: INITIAL (30-day backfill) ===")
    hours_old = args.hours_old if args.hours_old is not None else get_settings()["search"]["hours_old_initial"]
    _run_search(hours_old=hours_old, notify=False, mode="initial", args=args)


def cmd_daily(args):
    logger.info("=== MODE: DAILY ===")
    hours_old = args.hours_old if args.hours_old is not None else get_settings()["search"]["hours_old_daily"]
    _run_search(hours_old=hours_old, notify=not args.no_notify, mode="daily", args=args)


def _run_search(hours_old: int, notify: bool, mode: str, args):
    trigger = args.trigger or "cli"
    if args.run_id:
        run_id = args.run_id
    else:
        run = SearchRun(
            started_at=datetime.now(timezone.utc),
            params_json={"hours_old": hours_old, "mode": mode, "trigger": trigger},
            mode=mode, trigger=trigger, status="running",
        )
        run_id = create_search_run(run)

    error_count = 0
    total_found = 0
    new_count = 0

    try:
        sites = json.loads(args.sites_json) if args.sites_json else None
        keywords = json.loads(args.keywords_json) if args.keywords_json else None
        locations = json.loads(args.locations_json) if args.locations_json else None

        # 1. Scrape
        raw_df = run_searches(
            keywords=keywords, sites=sites, locations=locations,
            hours_old=hours_old, results_wanted=args.results_wanted,
        )
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

        # 6. Apply minimum score threshold before persisting
        min_score = get_settings()["filters"]["min_score_to_save"]
        above_threshold = scored[scored["score"] >= min_score] if min_score > 0 else scored
        below_threshold = len(scored) - len(above_threshold)
        if below_threshold:
            logger.info(f"Discarded {below_threshold} jobs below min_score_to_save={min_score}")

        # 7. Mark old jobs before inserting new
        mark_existing_as_old()

        # 8. Persist (DB dedupes against existing)
        new_count = save_jobs(above_threshold)

        # 9. Export
        today = date.today()
        md_path = export_digest(today)
        logger.info(f"Digest ready: {md_path}")

        # 10. Notify
        if notify:
            new_jobs = get_new_jobs(today)
            top = new_jobs.sort_values("score", ascending=False).head(10) if not new_jobs.empty else new_jobs
            stats = {
                "date": today.isoformat(),
                "new_count": new_count,
                "total_found": total_found,
                "filtered": total_found - len(filtered),
            }
            score_hot = get_settings()["scoring"]["score_hot"]
            hot = new_jobs[new_jobs["score"] >= score_hot] if not new_jobs.empty else new_jobs
            if not hot.empty:
                send_hot_alert(hot.sort_values("score", ascending=False))
            send_digest(top, stats)

    except Exception as e:
        logger.exception(f"Search run failed: {e}")
        error_count += 1
    finally:
        finish_search_run(
            run_id,
            finished_at=datetime.now(timezone.utc),
            total_found=total_found,
            new_count=new_count,
            error_count=error_count,
            status="failed" if error_count else "ok",
        )


def cmd_export(args):
    logger.info("=== MODE: EXPORT ===")
    today = date.today()
    md_path = export_digest(today)
    logger.info(f"Markdown: {md_path}")


def cmd_stats(args):
    logger.info("=== MODE: STATS ===")
    from storage.repository import get_pipeline_jobs

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
    parser.add_argument("--mode", choices=["daily", "initial", "export", "stats"], default="daily")
    parser.add_argument("--hours-old", type=int, default=None)
    parser.add_argument("--results-wanted", type=int, default=None)
    parser.add_argument("--sites-json", type=str, default=None)
    parser.add_argument("--keywords-json", type=str, default=None)
    parser.add_argument("--locations-json", type=str, default=None)
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument("--trigger", choices=["manual", "schedule", "cli"], default=None)
    args = parser.parse_args()

    init_db()

    dispatch = {
        "daily": cmd_daily,
        "initial": cmd_initial,
        "export": cmd_export,
        "stats": cmd_stats,
    }
    dispatch[args.mode](args)


if __name__ == "__main__":
    main()
