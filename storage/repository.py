import json
from datetime import datetime, date, timezone
import pandas as pd
from sqlalchemy import select, update
from storage.models import Job, Application, SearchRun
from storage.database import get_session
from core.deduper import make_url_hash, make_content_hash
from utils.logger import get_logger

logger = get_logger(__name__)


def is_existing(url_hash: str, content_hash: str) -> bool:
    with get_session() as s:
        result = s.execute(
            select(Job.id).where(
                (Job.url_hash == url_hash) | (Job.content_hash == content_hash)
            ).limit(1)
        ).first()
        return result is not None


def save_jobs(df: pd.DataFrame) -> int:
    """Insert new jobs, skip duplicates. Returns count of new rows inserted."""
    new_count = 0
    with get_session() as s:
        for _, row in df.iterrows():
            url_hash = row.get("url_hash") or make_url_hash(str(row.get("job_url", "")))
            content_hash = row.get("content_hash") or make_content_hash(
                str(row.get("title", "")), str(row.get("company", ""))
            )

            existing = s.execute(
                select(Job.id).where(
                    (Job.url_hash == url_hash) | (Job.content_hash == content_hash)
                ).limit(1)
            ).first()

            if existing:
                continue

            posted_at = None
            if row.get("date_posted") is not None and not pd.isna(row.get("date_posted")):
                try:
                    posted_at = pd.to_datetime(row["date_posted"], utc=True).to_pydatetime()
                except Exception:
                    pass

            stack = row.get("stack_detected", [])
            if not isinstance(stack, list):
                stack = []

            job = Job(
                source=str(row.get("site", "")),
                source_url=str(row.get("job_url", "")),
                url_hash=url_hash,
                content_hash=content_hash,
                title=str(row.get("title", "")),
                company=str(row.get("company", "")),
                location=str(row.get("location", "")),
                is_remote=bool(row.get("is_remote", False)),
                min_amount=row.get("min_amount") if not pd.isna(row.get("min_amount", float("nan"))) else None,
                max_amount=row.get("max_amount") if not pd.isna(row.get("max_amount", float("nan"))) else None,
                currency=str(row.get("currency", "")) or None,
                description=str(row.get("description", "")),
                posted_at=posted_at,
                score=int(row.get("score", 0)),
                stack_detected=stack,
                is_new=True,
            )
            s.add(job)
            new_count += 1

        s.commit()

    logger.info(f"Saved {new_count} new jobs to DB.")
    return new_count


def mark_existing_as_old(before_date: date | None = None) -> None:
    before_date = before_date or date.today()
    with get_session() as s:
        s.execute(
            update(Job)
            .where(Job.is_new == True)
            .where(Job.scraped_at < datetime.combine(before_date, datetime.min.time()).replace(tzinfo=timezone.utc))
            .values(is_new=False)
        )
        s.commit()


def get_new_jobs(run_date: date | None = None) -> pd.DataFrame:
    run_date = run_date or date.today()
    with get_session() as s:
        jobs = s.execute(
            select(Job).where(Job.is_new == True)
        ).scalars().all()

        rows = [_job_to_dict(j) for j in jobs]

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_pipeline_jobs() -> pd.DataFrame:
    with get_session() as s:
        rows = s.execute(
            select(Job, Application)
            .join(Application, Job.id == Application.job_id, isouter=True)
        ).all()

        data = []
        for job, app in rows:
            d = _job_to_dict(job)
            if app:
                d.update({
                    "status": app.status,
                    "applied_at": app.applied_at,
                    "cv_version": app.cv_version,
                    "notes": app.notes,
                    "next_action_at": app.next_action_at,
                    "response_at": app.response_at,
                })
            data.append(d)

    return pd.DataFrame(data) if data else pd.DataFrame()


def save_search_run(run: SearchRun) -> None:
    with get_session() as s:
        s.add(run)
        s.commit()


def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source": job.source,
        "job_url": job.source_url,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "is_remote": job.is_remote,
        "min_amount": job.min_amount,
        "max_amount": job.max_amount,
        "currency": job.currency,
        "description": job.description,
        "date_posted": job.posted_at,
        "scraped_at": job.scraped_at,
        "score": job.score,
        "stack_detected": job.stack_detected or [],
        "is_new": job.is_new,
        "status": None,
        "applied_at": None,
        "cv_version": None,
        "notes": None,
        "next_action_at": None,
        "response_at": None,
    }
