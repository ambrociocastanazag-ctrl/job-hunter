import os
from dotenv import load_dotenv

load_dotenv()

# --- Plataformas ---
# Google removido: timeouts y 0 resultados.
# ZipRecruiter removido: 403 Forbidden en todas las requests (bloqueo duro).
SITES = ["linkedin", "indeed", "glassdoor"]

# --- Keywords de búsqueda ---
PRIMARY_KEYWORDS = [
    "Python Developer",
    "Python Backend Developer",
    "Django Developer",
    "FastAPI Developer",
    "Backend Developer Python",
]

SECONDARY_KEYWORDS = [
    "Junior Python Developer",
    "Full Stack Python",
    "Python Engineer",
    "Software Engineer Python",
]

SPANISH_KEYWORDS = [
    "Desarrollador Python",
    "Programador Python",
    "Desarrollador Django",
    "Desarrollador Backend",
]

ALL_KEYWORDS = PRIMARY_KEYWORDS + SECONDARY_KEYWORDS + SPANISH_KEYWORDS

# --- Locations de búsqueda ---
# LinkedIn acepta strings libres. Indeed/Glassdoor/ZipRecruiter solo aceptan países
# válidos de su lista. "worldwide" funciona en todas las plataformas.
LOCATIONS = ["Remote", "Latin America", "worldwide", "United States"]

# --- Palabras excluidas en el título ---
EXCLUDE_TITLE_WORDS = [
    r"\bsenior\b", r"\blead\b", r"\bstaff\b", r"\bprincipal\b",
    r"\barchitect\b", r"\bmanager\b", r"\bml engineer\b",
    r"\bmachine learning engineer\b", r"\bdata scientist\b",
    r"\bai researcher\b", r"\bmlops\b", r"\bdevops engineer\b",
    r"\bsecurity engineer\b", r"\bcybersecurity\b", r"\bpentester\b",
    r"\bsalesforce\b", r"\bsap abap\b", r"\bservicenow\b",
]

# --- Stack que suma score ---
BONUS_STACK = [
    "django", "fastapi", "flask", "django rest framework", "drf",
    "postgresql", "sqlalchemy", "rest api", "restful", "docker",
    "jwt", "pytest", "unit test",
]

# --- Parámetros de búsqueda ---
RESULTS_WANTED = 25          # por query/plataforma
HOURS_OLD_INITIAL = 720      # 30 días para corrida inicial
HOURS_OLD_DAILY = 168        # 7 días para corridas diarias
MAX_AGE_DAYS = 30            # Descartar vacantes más viejas

# --- Scoring ---
MIN_SCORE = int(os.getenv("MIN_SCORE", "50"))

# --- Base de datos ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/jobs.db")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Rate limiting ---
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5
