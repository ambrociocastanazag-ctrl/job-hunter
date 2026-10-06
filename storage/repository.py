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


def update_job_scores(scores: dict) -> int:
    """Bulk-update scores. scores = {job_id: new_score}. Returns count updated."""
    with get_session() as s:
        for job_id, score in scores.items():
            s.execute(update(Job).where(Job.id == job_id).values(score=int(score)))
        s.commit()
    return len(scores)


def upsert_status(job_id: int, status: str) -> bool:
    """Create or update the Application record for a job. Returns True on success."""
    with get_session() as s:
        app = s.execute(
            select(Application).where(Application.job_id == job_id)
        ).scalar_one_or_none()
        if app:
            app.status = status
        else:
            app = Application(job_id=job_id, status=status)
            s.add(app)
        s.commit()
    return True


def create_search_run(run: SearchRun) -> int:
    """Persists a SearchRun at the start of a run (status='running'). Returns its id."""
    with get_session() as s:
        s.add(run)
        s.commit()
        return run.id


def update_search_run(run_id: int, **fields) -> None:
    """Generic partial update. None-valued kwargs are ignored."""
    values = {k: v for k, v in fields.items() if v is not None}
    if not values:
        return
    with get_session() as s:
        s.execute(update(SearchRun).where(SearchRun.id == run_id).values(**values))
        s.commit()


def finish_search_run(
    run_id: int,
    finished_at,
    total_found: int = 0,
    new_count: int = 0,
    error_count: int = 0,
    status: str = "ok",
) -> None:
    update_search_run(
        run_id,
        finished_at=finished_at,
        total_found=total_found,
        new_count=new_count,
        error_count=error_count,
        status=status,
    )


def get_search_run(run_id: int) -> dict | None:
    with get_session() as s:
        run = s.get(SearchRun, run_id)
        return _run_to_dict(run) if run else None


def get_running_search_run() -> dict | None:
    with get_session() as s:
        run = s.execute(
            select(SearchRun).where(SearchRun.status == "running").order_by(SearchRun.started_at.desc())
        ).scalars().first()
        return _run_to_dict(run) if run else None


def close_orphaned_runs() -> int:
    """Marks as cancelled the dashboard-launched runs left as 'running' by a
    dashboard that was closed mid-run (closing its window kills the run's
    subprocess too, so nothing else would ever close the row). CLI runs are
    left alone: they may legitimately be running in another process."""
    with get_session() as s:
        result = s.execute(
            update(SearchRun)
            .where(SearchRun.status == "running", SearchRun.trigger != "cli")
            .values(status="cancelled", finished_at=datetime.now(timezone.utc))
        )
        s.commit()
        return result.rowcount


def get_search_runs(limit: int = 30) -> list[dict]:
    with get_session() as s:
        runs = s.execute(
            select(SearchRun).order_by(SearchRun.started_at.desc()).limit(limit)
        ).scalars().all()
        return [_run_to_dict(r) for r in runs]


def _run_to_dict(r: SearchRun) -> dict:
    return {
        "id": r.id,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "total_found": r.total_found or 0,
        "new_count": r.new_count or 0,
        "error_count": r.error_count or 0,
        "hours_old": (r.params_json or {}).get("hours_old", "—"),
        "mode": r.mode or "daily",
        "trigger": r.trigger or "cli",
        "status": r.status or "ok",
        "log_path": r.log_path,
        "duration_s": int((r.finished_at - r.started_at).total_seconds())
                      if r.finished_at and r.started_at else None,
    }


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
        "is_favorite": bool(job.is_favorite),
        "status": None,
        "applied_at": None,
        "cv_version": None,
        "notes": None,
        "next_action_at": None,
        "response_at": None,
    }


def set_favorite(job_id: int, favorite: bool) -> bool:
    """Set an explicit value so retries cannot accidentally toggle a favorite."""
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            return False
        job.is_favorite = favorite
        session.commit()
    return True
