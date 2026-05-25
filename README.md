# Job Hunter

Automated job search system built with [python-jobspy](https://github.com/Bunsly/JobSpy). Scrapes LinkedIn, Indeed and Glassdoor daily, filters and scores vacancies by relevance, exports results to Excel, and sends a Telegram digest — all without manual intervention.

Built as a real-world portfolio project by a junior Python developer actively job hunting.

---

## Features

- **Multi-platform scraping** — LinkedIn, Indeed, Glassdoor in parallel
- **Smart filtering** — excludes senior/lead roles, impossible year requirements, irrelevant locations
- **Relevance scoring (0–100)** — bonuses for Django/FastAPI, junior mentions, LATAM-friendly, Docker, etc.
- **Deduplication** — double hash strategy (URL + title+company) eliminates cross-platform duplicates
- **Stack detection** — automatically detects technologies mentioned in job descriptions
- **Excel export** — 3-sheet workbook with color-coded scores (green/yellow/red), auto-filter, freeze panes
- **Markdown digest** — TOP 10 daily summary
- **Telegram notifications** — sends digest to your bot after each run
- **SQLite persistence** — tracks all jobs and application pipeline across runs
- **Windows Task Scheduler** — runs automatically every weekday at 8 AM

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping | python-jobspy |
| Data processing | pandas |
| ORM / DB | SQLAlchemy + SQLite |
| Excel export | openpyxl |
| Notifications | Telegram Bot API (requests) |
| Testing | pytest |
| Scheduling | Windows Task Scheduler |

---

## Project Structure

```
job_hunter/
├── config/
│   ├── settings.py        # Keywords, sites, scoring thresholds
│   └── profile.yaml       # User stack (data-driven scoring)
├── core/
│   ├── searcher.py        # Cartesian product scraper (site × keyword × location)
│   ├── filters.py         # Exclusion chain (title, location, age, years required)
│   ├── scorer.py          # Score 0-100 by relevance signals
│   ├── deduper.py         # SHA1 hash deduplication
│   └── enricher.py        # Stack detection from descriptions
├── storage/
│   ├── models.py          # SQLAlchemy ORM: Job, Application, SearchRun
│   ├── database.py        # SQLite connection + init
│   └── repository.py      # CRUD operations
├── exporters/
│   ├── excel.py           # XLSX: NEW / ALL / TRACK sheets
│   └── markdown.py        # Daily digest TOP 10
├── notifications/
│   └── telegram.py        # Bot digest via requests
├── automation/
│   └── run_daily.bat      # Windows Task Scheduler entry point
├── tests/
│   ├── test_filters.py
│   ├── test_scorer.py
│   └── test_deduper.py
├── experiments/
│   └── test_jobspy.py     # Smoke test
├── main.py                # CLI entry point
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

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DATABASE_URL=sqlite:///data/jobs.db
MIN_SCORE=25
LOG_LEVEL=INFO
```

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

---

## Usage

```bash
# Daily incremental search + export + Telegram notification
python main.py --mode daily

# First run: 30-day backfill (no notification)
python main.py --mode initial

# Regenerate Excel from existing DB (e.g. after changing MIN_SCORE)
python main.py --mode export

# Show pipeline statistics
python main.py --mode stats
```

---

## Excel Output

**Sheet `NEW`** — new vacancies with `score >= MIN_SCORE`, sorted by score descending.
Color coding on score column: green (≥70), yellow (25–69).

**Sheet `ALL`** — all new vacancies without score filter (for auditing).

**Sheet `TRACK`** — application pipeline with status dropdown:
`Pendiente / Aplicado / Entrevista 1 / Entrevista Téc / Oferta / Rechazado / Ghosted`

---

## Scoring Logic

| Signal | Points |
|---|---|
| Django or FastAPI in description | +30 |
| `junior` or `entry-level` in title | +20 |
| PostgreSQL + Python in description | +15 |
| LATAM / Latin America / Americas timezone | +15 |
| Docker in description | +10 |
| `junior` / `entry-level` in description | +10 |
| Is remote | +5 |
| pytest / unit tests | +5 |
| `3+ years experience` required | −20 |
| Go / Rust in description | −15 |
| Kubernetes / Java / Scala | −10 |

Threshold: `MIN_SCORE=25` (configurable in `.env`).

---

## Running Tests

```bash
pytest tests/ -v
```

19 unit tests covering filters, scorer, and deduper.

---

## Scheduling (Windows)

The task `JobHunter Daily Search` runs every weekday at 8:00 AM via Windows Task Scheduler.
To register it manually:

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\path\to\job_hunter\automation\run_daily.bat"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "08:00AM"
Register-ScheduledTask -TaskName "JobHunter Daily Search" -Action $action -Trigger $trigger -Force
```

---

## Notes

- **LinkedIn** is the most reliable source. Indeed and Glassdoor results depend on anti-scraping measures at the time of the request.
- `data/`, `logs/`, and `.env` are excluded from the repo via `.gitignore`.
- Expected output: 5–20 relevant new vacancies per day with `MIN_SCORE=25`.

---

## License

MIT
