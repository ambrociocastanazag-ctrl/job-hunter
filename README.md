# Job Hunter

Automated job search system built with [python-jobspy](https://github.com/Bunsly/JobSpy). Scrapes LinkedIn, Indeed and Glassdoor, filters and scores vacancies by relevance, sends a Telegram digest, and exposes a web dashboard — all without manual intervention, and **fully configurable from the dashboard itself**, including schedules and manual runs.

Built as a real-world portfolio project by a junior Python developer actively job hunting.

---

## Features

- **Multi-platform scraping** — LinkedIn, Indeed, Glassdoor in parallel
- **Smart filtering** — excludes senior/lead roles, impossible year requirements, irrelevant locations
- **Relevance scoring (0–100)** — bonuses for Django/FastAPI, junior mentions, LATAM-friendly, Docker, etc.
- **Deduplication** — double hash strategy (URL + title+company) eliminates cross-platform duplicates
- **Stack detection** — automatically detects technologies mentioned in job descriptions
- **Web dashboard** — filterable table with collapsible descriptions, stats, and dynamic config
- **Fully configurable from the dashboard** — search targeting, filters, scoring weights (including raw regex), stack detection, and notifications, split into a *Básico* (simple, non-technical) and *Avanzado* (regex, weights, execution parameters) view
- **In-app scheduler** — create/pause/delete recurring runs (which days, what time) from `/schedules`, no Windows Task Scheduler editing required
- **Manual runs with live console** — trigger a run on demand from `/runs`, watch its log stream in real time, cancel mid-run
- **Markdown digest** — configurable-size daily summary
- **Telegram notifications** — sends digest and hot-vacancy alerts to your bot, credentials editable from the dashboard
- **SQLite persistence** — tracks all jobs, the application pipeline, and full run history across runs

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping | python-jobspy |
| Data processing | pandas |
| ORM / DB | SQLAlchemy + SQLite |
| Web dashboard | Flask |
| Notifications | Telegram Bot API (requests) |
| Testing | pytest |
| Scheduling | APScheduler (in-process), one Windows Task Scheduler entry to start the dashboard at logon |

---

## Project Structure

```
job_hunter/
├── config/
│   ├── defaults.py        # DEFAULTS: every configurable value's fallback
│   ├── settings.py        # get_settings()/save_section(): DEFAULTS + settings.yaml, cached
│   ├── settings.yaml      # User overrides only (created on first run/save)
│   ├── validation.py      # Regex/schema validation before any section is saved
│   └── profile.yaml       # Identity only (name, stack, languages) — not search behavior
├── core/
│   ├── searcher.py        # Cartesian product scraper (site × keyword × location × job_type)
│   ├── filters.py         # Exclusion chain (title, location, age, years required)
│   ├── scorer.py          # Score 0-100 from the configurable rules/penalties table
│   ├── deduper.py         # SHA1 hash deduplication
│   └── enricher.py        # Stack detection from descriptions (configurable patterns)
├── storage/
│   ├── models.py          # SQLAlchemy ORM: Job, Application, SearchRun
│   ├── database.py        # SQLite connection + init + migrations
│   ├── migrations.py      # Idempotent ALTER TABLE for columns added after v1
│   └── repository.py      # CRUD operations
├── exporters/
│   └── markdown.py        # Daily digest (configurable size)
├── notifications/
│   └── telegram.py        # Bot digest + hot alerts via requests
├── automation/
│   ├── runner.py          # RunManager: launches main.py as a subprocess, live log tail, cancel
│   ├── scheduler.py       # APScheduler: builds cron jobs from settings.yaml's `schedules`
│   ├── run_dashboard.bat  # Entry point for the "JobHunter Dashboard" at-logon task
│   ├── run_daily.bat      # Fallback manual/CLI entry point
│   └── install_task.ps1   # Installs/removes the at-logon Windows Task
├── dashboard/
│   ├── app.py             # Flask app: dashboard, config (basic/advanced), schedules, runs
│   └── templates/         # base.html + index/config_basic/config_advanced/schedules/runs
├── tests/
│   ├── test_filters.py
│   ├── test_scorer.py
│   ├── test_deduper.py
│   ├── test_settings.py
│   ├── test_validation.py
│   └── test_scheduler.py
├── experiments/
│   └── test_jobspy.py     # Smoke test
├── main.py                # CLI entry point (also invoked as a subprocess by the dashboard)
└── requirements.txt
```

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/your-username/job-hunter.git
cd job-hunter/job_hunter
python -m venv ../venv
../venv/Scripts/activate      # Windows
# source ../venv/bin/activate # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure environment

```bash
copy .env.example .env
```

Edit `.env` — this file only holds secrets and machine-local settings, never search behavior:

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DATABASE_URL=sqlite:///data/jobs.db
LOG_LEVEL=INFO
```

The Telegram token/chat ID can also be set later from the dashboard (**Avanzado → Notificaciones**) — it writes to this same file.

**Getting Telegram credentials:**
1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Send any message to your bot, then visit `https://api.telegram.org/botTOKEN/getUpdates` → copy the `chat.id`

### 3. Run smoke test

```bash
python experiments/test_jobspy.py
```

### 4. First run (30-day backfill)

```bash
python main.py --mode initial
```

Or, once the dashboard is up: `/runs` → mode "inicial" → **Ejecutar ahora**.

---

## Usage

Everything below can also be done from the dashboard — keywords, locations, sites, work mode,
filters, scoring rules/weights, stack detection patterns, notifications, schedules, and manual
runs with a live log. The CLI remains the lower-level entry point the dashboard itself calls.

```bash
# Start the dashboard (config UI + scheduler + manual runs)
python dashboard/app.py
# -> http://127.0.0.1:5000

# Daily incremental search + export + Telegram notification
python main.py --mode daily

# First run: 30-day backfill (no notification)
python main.py --mode initial

# Regenerate markdown digest from existing DB
python main.py --mode export

# Show pipeline statistics
python main.py --mode stats
```

---

## Configuration

All search, filter, scoring, and notification behavior lives in `config/settings.yaml`
(created on first save — only your overrides are stored, everything else falls back to
`config/defaults.py`) and is edited from the dashboard rather than by hand:

- **`/config` (Básico)** — work mode (remote/hybrid/onsite), job type, sites, keywords,
  locations, preferred skills, minimum score to save, "hot" score threshold, notification
  toggles, and your profile (name, stack, languages).
- **`/config/advanced` (Avanzado)** — the raw regex behind every filter (with a live tester),
  the full scoring rules/penalties table (pattern, points, field, on/off), stack-detection
  patterns, request delays/retries, results-per-search and lookback windows, digest size, and
  the Telegram token/chat ID.

Editing a value here takes effect on the **next run** — no restart needed, including for a
daily/initial run already scheduled or launched by another process.

### Scoring logic (defaults)

| Signal | Points |
|---|---|
| Django or FastAPI in description | +30 |
| `junior` or `entry-level` in title | +20 |
| PostgreSQL in description | +10 |
| PostgreSQL + Python in description | +5 |
| LATAM / Latin America / Americas timezone | +15 |
| Docker in description | +10 |
| `junior` / `entry-level` in description | +10 |
| Is remote | +5 |
| pytest / unit tests | +5 |
| `3+ years experience` required | −20 |
| Go / Rust in description | −15 |
| Kubernetes / Java / Scala | −10 |

Every row above is editable (and new ones addable) from **Avanzado → Reglas de scoring**.
Vacancies scoring below **`filters.min_score_to_save`** (Básico, default 25) aren't persisted
to the database at all.

---

## Running Tests

```bash
pytest tests/ -v
```

50 unit tests covering filters, scorer, deduper, settings persistence/validation, and the
scheduler.

---

## Scheduling

Recurring runs (which days, what time, daily vs. initial mode) are created and edited from
**`/schedules`** — no Windows Task Scheduler editing required. They fire from an in-process
APScheduler instance owned by the dashboard, so they only run while the dashboard is open.

To have the dashboard itself open automatically when you log into Windows, install the single
supporting task from `/schedules` (**Instalar**), or manually:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File automation\install_task.ps1 -Action Install
```

This registers **`JobHunter Dashboard`** (At Logon → `automation\run_dashboard.bat`) and removes
any leftover `JobHunter Daily Search` task from an older setup. If the dashboard was closed
through a scheduled time, `catch_up_on_start` (Avanzado → Dashboard, on by default) fires that
missed run once at the next startup.

For a pure CLI/cron-style setup without the dashboard, `automation/run_daily.bat` still runs
`main.py --mode daily` directly.

---

## Notes

- **LinkedIn** is the most reliable source. Indeed and Glassdoor results depend on anti-scraping measures at the time of the request.
- `data/`, `logs/`, and `.env` are excluded from the repo via `.gitignore`. `config/settings.yaml` and `config/profile.yaml` (your search config and identity) are versioned, same as before — `config/defaults.py` is just the fallback for whatever they don't override.
- Expected output: 5–20 relevant new vacancies per day with the default score threshold.

---

## License

MIT
