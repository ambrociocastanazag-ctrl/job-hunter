"""In-process scheduler: reads config.settings' `schedules` list and fires
RunManager.start() through APScheduler, running inside the dashboard's own
Flask process. sync_schedules() is called once at dashboard startup and again
after every save to the schedules section, so edits take effect without
restarting anything.

This intentionally does NOT touch Windows Task Scheduler for individual
horarios — only a single "start the dashboard at logon" task is registered
(see automation/install_task.ps1), so the trade-off is explicit: schedules
only fire while the dashboard process is running. catch_up_on_start covers
the common case of the dashboard being closed at the scheduled time.
"""
import atexit
import threading
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

_DOW_CODES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def _job_func(schedule_id: str, mode: str, notify: bool) -> None:
    from automation.runner import RunManager

    try:
        rm = RunManager.instance()
        if rm.is_running():
            logger.warning(f"Schedule '{schedule_id}' skipped: a run is already in progress.")
            return
        rm.start(mode=mode, trigger="schedule", overrides={"no_notify": not notify})
    except Exception:
        logger.exception(f"Scheduled run '{schedule_id}' failed to start")


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    with _lock:
        if _scheduler is None:
            _scheduler = BackgroundScheduler()
            _scheduler.start()
            atexit.register(lambda s=_scheduler: s.shutdown(wait=False) if s.running else None)
        return _scheduler


def sync_schedules() -> None:
    """Rebuilds all APScheduler jobs from config.settings' `schedules` list.
    Safe to call repeatedly — it's idempotent (replace_existing=True) and
    prunes jobs for schedules that were deleted or disabled."""
    scheduler = get_scheduler()
    schedules = get_settings().get("schedules", [])

    enabled_ids = {s["id"] for s in schedules if s.get("enabled", True)}
    for job in scheduler.get_jobs():
        if job.id not in enabled_ids:
            scheduler.remove_job(job.id)

    for sched in schedules:
        if not sched.get("enabled", True):
            continue
        hh, mm = (int(x) for x in sched["time"].split(":"))
        trigger = CronTrigger(day_of_week=",".join(sched["days_of_week"]), hour=hh, minute=mm)
        scheduler.add_job(
            _job_func,
            trigger=trigger,
            id=sched["id"],
            replace_existing=True,
            kwargs={"schedule_id": sched["id"], "mode": sched["mode"], "notify": sched.get("notify", True)},
            misfire_grace_time=3600,
        )

    logger.info(f"Scheduler synced: {len(schedules)} horario(s) configurados, {len(scheduler.get_jobs())} activos.")


def get_next_run_times() -> dict[str, datetime | None]:
    scheduler = get_scheduler()
    return {job.id: job.next_run_time for job in scheduler.get_jobs()}


def init_scheduler() -> None:
    """Call once when the dashboard process starts."""
    sync_schedules()
    if get_settings()["dashboard"].get("catch_up_on_start", True):
        _catch_up()


def _catch_up() -> None:
    """If a schedule's time already passed today and nothing matching it
    has run since midnight, fire it once now. Only one catch-up run per
    startup, to avoid launching several runs back to back."""
    from storage.repository import get_search_runs

    schedules = [s for s in get_settings().get("schedules", []) if s.get("enabled", True)]
    if not schedules:
        return

    now = datetime.now(timezone.utc)
    today_code = _DOW_CODES[now.weekday()]
    recent_runs = get_search_runs(limit=50)
    todays_runs = [r for r in recent_runs if r["started_at"] and r["started_at"].date() == now.date()]

    for sched in schedules:
        if today_code not in sched["days_of_week"]:
            continue
        hh, mm = (int(x) for x in sched["time"].split(":"))
        scheduled_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now < scheduled_dt:
            continue
        already_ran = any(
            r["trigger"] == "schedule" and r["mode"] == sched["mode"]
            for r in todays_runs
        )
        if already_ran:
            continue
        logger.info(f"Catch-up: disparando horario '{sched['name']}' que no corrió hoy.")
        _job_func(sched["id"], sched["mode"], sched.get("notify", True))
        return
