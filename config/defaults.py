"""Valores por defecto de toda la configuración editable desde el dashboard.

Estos valores reproducen exactamente el comportamiento hardcodeado que tenía
la app antes de volverse configurable (ver config/settings.py, core/filters.py,
core/scorer.py, core/enricher.py). config/settings.yaml solo guarda overrides;
lo que falte en el YAML se completa desde aquí.
"""

DEFAULTS: dict = {
    "search": {
        "sites": ["linkedin", "indeed", "glassdoor"],
        "keywords": [
            "Python Developer", "Python Backend Developer", "Django Developer",
            "FastAPI Developer", "Backend Developer Python", "Junior Python Developer",
            "Full Stack Python", "Python Engineer", "Software Engineer Python",
            "Desarrollador Python", "Programador Python", "Desarrollador Django",
            "Desarrollador Backend",
        ],
        "locations": ["Remote", "Latin America", "worldwide", "United States"],
        "bonus_skills": [
            "Django", "FastAPI", "Flask", "PostgreSQL", "SQLAlchemy",
            "Docker", "pytest", "REST API",
        ],
        # "remote", "hybrid", "onsite". Si es exactamente ["remote"] se
        # fuerza is_remote=True en jobspy (comportamiento histórico).
        "work_modes": ["remote"],
        # Cada job_type se mapea 1:1 a un valor de jobspy.model.JobType.
        # Lista vacía = sin filtro (comportamiento histórico: no se pasaba job_type).
        "job_types": [],
        "results_wanted": 25,
        "hours_old_daily": 168,
        "hours_old_initial": 720,
    },
    "filters": {
        "exclude_title_words": [
            r"\bsenior\b", r"\blead\b", r"\bstaff\b", r"\bprincipal\b",
            r"\barchitect\b", r"\bmanager\b", r"\bml engineer\b",
            r"\bmachine learning engineer\b", r"\bdata scientist\b",
            r"\bai researcher\b", r"\bmlops\b", r"\bdevops engineer\b",
            r"\bsecurity engineer\b", r"\bcybersecurity\b", r"\bpentester\b",
            r"\bsalesforce\b", r"\bsap abap\b", r"\bservicenow\b",
        ],
        "allowed_location_patterns": [
            r"remote", r"worldwide", r"anywhere", r"global",
            r"latin america", r"latam", r"central america",
            r"south america", r"north america",
            r"guatemala", r"mexico", r"colombia", r"argentina",
            r"chile", r"peru", r"ecuador", r"costa rica",
            r"united states", r"usa", r"us\b",
            r"canada",
        ],
        "impossible_years_patterns": [
            r"\b[5-9]\+\s*year", r"\b1[0-9]\+\s*year",
            r"\b[5-9]\s*years?\s*of\s*(experience|exp)",
            r"\b1[0-9]\s*years?\s*of\s*(experience|exp)",
        ],
        "max_age_days": 30,
        # MIN_SCORE existía en .env pero nunca se aplicaba en el pipeline.
        # 0 = no descarta nada (comportamiento histórico real).
        "min_score_to_save": 0,
    },
    "scoring": {
        "score_hot": 70,
        "bonus_skill_points": 5,
        "bonus_skill_cap": 20,
        "remote_bonus": 5,
        "rules": [
            {"label": "Django/FastAPI", "pattern": r"\bdjango\b|\bfastapi\b", "points": 30, "field": "description", "enabled": True},
            {"label": "Junior en título", "pattern": r"\bjunior\b|\bentry[\s-]level\b", "points": 20, "field": "title", "enabled": True},
            {"label": "PostgreSQL", "pattern": r"\bpostgresql\b|\bpostgres\b", "points": 10, "field": "description", "enabled": True},
            {"label": "PostgreSQL + Python", "pattern": r"\bpython\b", "all_of": [r"\bpostgresql\b|\bpostgres\b"], "points": 5, "field": "description", "enabled": True},
            {"label": "LATAM (descripción)", "pattern": r"\blatin america\b|\blatam\b|\bamericas timezone\b|\blatam.friendly\b", "points": 15, "field": "description", "enabled": True},
            {"label": "LATAM (ubicación)", "pattern": r"\blatam\b|\blatin america\b", "points": 15, "field": "location", "enabled": True},
            {"label": "Docker", "pattern": r"\bdocker\b", "points": 10, "field": "description", "enabled": True},
            {"label": "pytest / unit test", "pattern": r"\bpytest\b|\bunit test", "points": 5, "field": "description", "enabled": True},
            {"label": "Junior en descripción", "pattern": r"\bjunior\b|\bentry[\s-]level\b", "points": 10, "field": "description", "enabled": True},
        ],
        "penalties": [
            {"label": "3+ años de experiencia", "pattern": r"3\+?\s*years?\s*(of\s*)?(experience|exp)", "points": -20, "field": "description", "enabled": True},
            {"label": "3-9 años de experiencia", "pattern": r"3\s*-\s*[4-9]\s*years?\s*(of\s*)?(experience|exp)", "points": -20, "field": "description", "enabled": True},
            {"label": "Go/Golang", "pattern": r"\bgo\b|\bgolang\b", "points": -15, "field": "description", "enabled": True},
            {"label": "Rust", "pattern": r"\brust\b", "points": -15, "field": "description", "enabled": True},
            {"label": "Kubernetes", "pattern": r"\bkubernetes\b|\bk8s\b", "points": -10, "field": "description", "enabled": True},
            {"label": "Java", "pattern": r"\bjava\b(?!script)", "points": -10, "field": "description", "enabled": True},
            {"label": "Scala/Kotlin", "pattern": r"\bscala\b|\bkotlin\b", "points": -10, "field": "description", "enabled": True},
        ],
    },
    "stack_patterns": {
        "Django": r"\bdjango\b",
        "FastAPI": r"\bfastapi\b",
        "Flask": r"\bflask\b",
        "DRF": r"\b(django rest framework|drf)\b",
        "PostgreSQL": r"\bpostgresql\b|\bpostgres\b",
        "MySQL": r"\bmysql\b",
        "SQLAlchemy": r"\bsqlalchemy\b",
        "REST API": r"\brest(ful)?\s*(api)?\b",
        "Docker": r"\bdocker\b",
        "JWT": r"\bjwt\b",
        "pytest": r"\bpytest\b",
        "Redis": r"\bredis\b",
        "Celery": r"\bcelery\b",
        "AWS": r"\baws\b|\bamazon web services\b",
        "GCP": r"\bgcp\b|\bgoogle cloud\b",
        "Azure": r"\bazure\b",
        "React": r"\breact(\.js|js)?\b",
        "Angular": r"\bangular\b",
        "GraphQL": r"\bgraphql\b",
        "Kubernetes": r"\bkubernetes\b|\bk8s\b",
        "Terraform": r"\bterraform\b",
        "CI/CD": r"\bci/cd\b|\bgithub actions\b|\bjenkins\b",
    },
    "notifications": {
        "digest_enabled": True,
        "hot_alerts_enabled": True,
        "digest_top_n": 10,
    },
    "runtime": {
        "request_delay_min": 2,
        "request_delay_max": 5,
        "retry_delays": [10, 30],
        "country_indeed": "usa",
    },
    "dashboard": {
        "per_page": 25,
        "statuses": ["Pendiente", "Aplicado", "Entrevista 1", "Entrevista Téc", "Oferta", "Rechazado", "Ghosted"],
        "catch_up_on_start": True,
    },
    "schedules": [],
}
