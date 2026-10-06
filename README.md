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
- **Web dashboard** — filterable table with a keyboard-accessible detail drawer, persistent favorites, stats, and dynamic config
- **Fully configurable from the dashboard** — search targeting, filters, scoring weights (including raw regex), stack detection, and notifications, split into a *Básico* (simple, non-technical) and *Avanzado* (regex, weights, execution parameters) view
- **In-app scheduler** — create/pause/delete recurring runs (which days, what time) from `/schedules`, no Windows Task Scheduler editing required
- **Manual runs with live console** — trigger a run on demand from `/runs`, watch its log stream in real time, cancel mid-run
- **One-command Windows install** — `irm … | iex` sets up its own Python, a desktop shortcut, and updates in place without touching user data
- **AI-assisted setup** — `/ayuda` hands out a prompt for any AI assistant; the YAML it returns is previewed, validated and imported in one step, plus a first-run welcome dialog
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
│   ├── settings.yaml      # User overrides only (created on first save, not versioned)
│   ├── validation.py      # Regex/schema validation before any section is saved
│   ├── importer.py        # /ayuda: AI-written YAML (plain words) -> validated settings + profile
│   ├── ayuda_prompt.md    # The prompt users paste into an AI assistant
│   └── profile.yaml       # Identity only (name, stack, languages) — not search behavior (not versioned)
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
│   ├── run_dashboard.bat  # At-logon task: opens JobHunter.bat minimized, without browser
│   ├── run_daily.bat      # Fallback manual/CLI entry point
│   └── install_task.ps1   # Installs/removes the at-logon Windows Task
├── dashboard/
│   ├── app.py             # Flask app: dashboard, config (basic/advanced), schedules, runs
│   └── templates/         # base.html + index/config_basic/config_advanced/schedules/runs/ayuda
├── tests/
│   ├── test_filters.py
│   ├── test_scorer.py
│   ├── test_deduper.py
│   ├── test_settings.py
│   ├── test_validation.py
│   ├── test_scheduler.py
│   └── test_importer.py
├── experiments/
│   └── test_jobspy.py     # Smoke test
├── assets/jobhunter.ico   # Shortcut icon
├── install.ps1            # One-command installer/updater (irm | iex)
├── JobHunter.bat          # Desktop-shortcut launcher: server in a window + browser
├── main.py                # CLI entry point (also invoked as a subprocess by the dashboard)
└── requirements.txt
```

---

## Setup

### One-command install (Windows)

No Python, Git or terminal knowledge needed. Open **PowerShell** (`Win` + `R` → type `powershell` → Enter) and paste:

```powershell
irm https://raw.githubusercontent.com/ambrociocastanazag-ctrl/job-hunter/main/install.ps1 | iex
```

[`install.ps1`](install.ps1) downloads the project to `%USERPROFILE%\JobHunter`, fetches
[uv](https://docs.astral.sh/uv/) into `JobHunter\tools\` (which brings its own Python 3.12 —
nothing is installed system-wide and `PATH` is untouched), installs the dependencies into
`JobHunter\.venv`, creates a **Job Hunter** shortcut on the desktop and in the Start menu, and opens it.

- **The shortcut** runs [`JobHunter.bat`](JobHunter.bat): a console window that hosts the server and
  opens the browser. Closing the window stops Job Hunter (and any search in progress). Double-clicking
  it while it's already open just opens the browser.
- **Updating:** close Job Hunter and paste the same command again. User data (`data/`, `logs/`, `.env`,
  `config/settings.yaml`, `config/profile.yaml`) isn't in the repo, so updates never overwrite it.
- **Uninstalling:** disable "start with Windows" in `/schedules` if enabled, then delete
  `%USERPROFILE%\JobHunter` and the two shortcuts.
- From CMD instead of PowerShell: `powershell -c "irm https://raw.githubusercontent.com/ambrociocastanazag-ctrl/job-hunter/main/install.ps1 | iex"`.

A step-by-step guide in Spanish for non-technical users lives in [`index.html`](index.html).

### First steps after installing

On first launch a welcome dialog points to **`/ayuda`**: it gives a prompt to paste into any AI
assistant (ChatGPT, Claude, Gemini…), which interviews the person — role, experience, skills, roles
to avoid, locations, remote/hybrid/onsite, job type, languages, schedule — and returns a
`jobhunter.yaml`. Dropping that file on `/ayuda` shows a summary of every change before applying it.
The prompt encodes the same platform constraints as the hand-tuned defaults (short LinkedIn-style
titles in Spanish and English, English country names for Indeed/Glassdoor, ≤ ~120 combinations per
run, the default scoring scale), and the importer ([`config/importer.py`](config/importer.py))
enforces them: plain words are turned into accent-insensitive whole-word regexes, everything goes
through the regular validators, an excluded title word that would discard one of the searched roles
is rejected, and runs estimated above ~40 minutes are flagged.

Then: `/runs` → mode "inicial" → **Ejecutar ahora** for the 30-day backfill.

### Manual install (development)

Python 3.12 is required: python-jobspy pins `numpy==1.26.3`, which has no wheels for 3.13+.

```bash
git clone https://github.com/ambrociocastanazag-ctrl/job-hunter.git
cd job-hunter
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe dashboard/app.py --open-browser
```

`.env` (Flask secret, Telegram token/chat ID) is created on first start; see [`.env.example`](.env.example).
The Telegram credentials are set from the dashboard (**Avanzado → Notificaciones**):
1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Send any message to your bot, then visit `https://api.telegram.org/botTOKEN/getUpdates` → copy the `chat.id`

Set `JOBHUNTER_PORT` to serve on a port other than 5000.

---

## Usage

Everything below can also be done from the dashboard — keywords, locations, sites, work mode,
filters, scoring rules/weights, stack detection patterns, notifications, schedules, and manual
runs with a live log. The CLI remains the lower-level entry point the dashboard itself calls.

```bash
# Start the dashboard (config UI + scheduler + manual runs)
python dashboard/app.py --open-browser
# -> http://127.0.0.1:5000 (or double-click the Job Hunter shortcut)

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

72 unit tests covering filters, scorer, deduper, favorites, settings persistence/validation, the
scheduler, and the `/ayuda` YAML importer (including that the prompt's own example imports cleanly).

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
- `data/`, `logs/`, and `.env` are excluded from the repo via `.gitignore`. `config/settings.yaml` and `config/profile.yaml` (each user's search config and identity) are excluded too, so every install starts from `config/defaults.py` and updates never overwrite them.
- Expected output: 5–20 relevant new vacancies per day with the default score threshold.

---

## License

MIT

### Vacancy details and favorites

Open a vacancy row (or press Enter) to inspect its detail drawer. Escape closes it and returns focus to the table. The drawer supports previous/next navigation, status updates, and favorites. Stars are stored in SQLite; use **Mis favoritos** to combine them with search and other filters. The `jobs.is_favorite` column is added automatically by `init_db()` on normal dashboard startup.
