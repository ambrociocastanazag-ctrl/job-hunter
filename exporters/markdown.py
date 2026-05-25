import os
from datetime import date
import pandas as pd
from storage.repository import get_new_jobs
from utils.logger import get_logger

logger = get_logger(__name__)

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "exports")


def export_digest(run_date: date | None = None, top_n: int = 10) -> str:
    run_date = run_date or date.today()
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    filepath = os.path.join(EXPORTS_DIR, f"daily_digest_{run_date.isoformat()}.md")

    new_jobs = get_new_jobs(run_date)

    if new_jobs.empty:
        content = f"## No new jobs found — {run_date.isoformat()}\n"
    else:
        top = new_jobs.sort_values("score", ascending=False).head(top_n)
        total = len(new_jobs)
        content = _build_digest(top, total, run_date)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Markdown digest exported: {filepath}")
    return filepath


def _build_digest(top: pd.DataFrame, total: int, run_date: date) -> str:
    lines = [
        f"## TOP {len(top)} — {run_date.isoformat()} ({total} nuevas vacantes)\n"
    ]

    for i, (_, row) in enumerate(top.iterrows(), 1):
        score = row.get("score", 0)
        title = row.get("title", "N/A")
        company = row.get("company", "N/A")
        location = row.get("location", "")
        stack = row.get("stack_detected", [])
        if isinstance(stack, list):
            stack_str = ", ".join(stack) if stack else "N/A"
        else:
            stack_str = str(stack)

        posted = row.get("date_posted")
        posted_str = _humanize_date(posted)
        url = row.get("job_url", "#")

        lines.append(f"### [{score}] {title} @ {company}")
        lines.append(f"- **Location**: {location or 'Remote'}")
        lines.append(f"- **Stack detectado**: {stack_str}")
        lines.append(f"- **Posted**: {posted_str}")
        lines.append(f"- [Ver vacante]({url})\n")

    return "\n".join(lines)


def _humanize_date(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    try:
        dt = pd.to_datetime(val, utc=True)
        delta = (pd.Timestamp.now(tz="UTC") - dt).days
        if delta == 0:
            return "hoy"
        elif delta == 1:
            return "ayer"
        else:
            return f"hace {delta} días"
    except Exception:
        return str(val)
