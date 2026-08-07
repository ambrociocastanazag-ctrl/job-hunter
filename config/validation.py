"""Validadores usados antes de persistir una sección de configuración.

Ningún patrón regex llega a settings.yaml sin pasar por re.compile: un
regex roto en, por ejemplo, filters.exclude_title_words rompería silenciosamente
todas las corridas futuras (ver core/filters.py).
"""
import re

VALID_SITES = {"linkedin", "indeed", "glassdoor"}
VALID_WORK_MODES = {"remote", "hybrid", "onsite"}
VALID_JOB_TYPES = {"fulltime", "parttime", "internship", "contract"}
VALID_FIELDS = {"title", "description", "location"}
VALID_TRIGGERS = {"manual", "schedule", "cli"}
DAYS_OF_WEEK = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


class ValidationError(Exception):
    """Errores de validación por campo. errors: {field_path: message}"""

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


def validate_regex(pattern: str) -> str | None:
    """Returns an error message, or None if the pattern compiles."""
    try:
        re.compile(pattern)
        return None
    except re.error as e:
        return f"regex inválido: {e}"


def validate_regex_list(patterns: list, field_prefix: str, errors: dict) -> None:
    if not isinstance(patterns, list):
        errors[field_prefix] = "debe ser una lista"
        return
    for i, p in enumerate(patterns):
        if not isinstance(p, str) or not p.strip():
            errors[f"{field_prefix}[{i}]"] = "patrón vacío"
            continue
        err = validate_regex(p)
        if err:
            errors[f"{field_prefix}[{i}]"] = f"{err} ({p!r})"


def validate_rules(rules: list, field_prefix: str, errors: dict) -> None:
    if not isinstance(rules, list):
        errors[field_prefix] = "debe ser una lista"
        return
    for i, rule in enumerate(rules):
        prefix = f"{field_prefix}[{i}]"
        if not isinstance(rule, dict):
            errors[prefix] = "cada regla debe ser un objeto"
            continue
        pattern = rule.get("pattern", "")
        if not pattern or not isinstance(pattern, str):
            errors[f"{prefix}.pattern"] = "patrón requerido"
        else:
            err = validate_regex(pattern)
            if err:
                errors[f"{prefix}.pattern"] = err
        for j, extra in enumerate(rule.get("all_of", []) or []):
            err = validate_regex(extra) if isinstance(extra, str) and extra else "patrón vacío"
            if err:
                errors[f"{prefix}.all_of[{j}]"] = err
        points = rule.get("points")
        if not isinstance(points, int):
            errors[f"{prefix}.points"] = "debe ser un entero"
        field = rule.get("field")
        if field not in VALID_FIELDS:
            errors[f"{prefix}.field"] = f"debe ser uno de {sorted(VALID_FIELDS)}"


def validate_time_hhmm(value: str) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        return "formato esperado HH:MM (24h)"
    return None


def validate_int_range(value, lo: int, hi: int) -> str | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return "debe ser un entero"
    if not (lo <= value <= hi):
        return f"debe estar entre {lo} y {hi}"
    return None


def validate_schedule(sched: dict) -> dict:
    """Returns {field: message} errors for a single schedule dict."""
    errors: dict[str, str] = {}
    if not sched.get("id"):
        errors["id"] = "id requerido"
    if not sched.get("name", "").strip():
        errors["name"] = "nombre requerido"
    if sched.get("mode") not in ("daily", "initial"):
        errors["mode"] = "debe ser 'daily' o 'initial'"
    days = sched.get("days_of_week", [])
    if not isinstance(days, list) or not days or any(d not in DAYS_OF_WEEK for d in days):
        errors["days_of_week"] = f"debe ser una lista no vacía de {sorted(DAYS_OF_WEEK)}"
    err = validate_time_hhmm(sched.get("time", ""))
    if err:
        errors["time"] = err
    return errors


def validate_schedules_section(schedules: list) -> dict:
    errors: dict[str, str] = {}
    if not isinstance(schedules, list):
        return {"_": "debe ser una lista"}
    seen_ids = set()
    for i, sched in enumerate(schedules):
        if not isinstance(sched, dict):
            errors[f"[{i}]"] = "cada horario debe ser un objeto"
            continue
        for field, message in validate_schedule(sched).items():
            errors[f"[{i}].{field}"] = message
        sid = sched.get("id")
        if sid in seen_ids:
            errors[f"[{i}].id"] = "id duplicado"
        seen_ids.add(sid)
    return errors


def validate_search(section: dict) -> dict:
    errors: dict[str, str] = {}
    sites = section.get("sites", [])
    if not isinstance(sites, list) or not sites:
        errors["sites"] = "debe haber al menos un sitio"
    elif any(s not in VALID_SITES for s in sites):
        errors["sites"] = f"sitios válidos: {sorted(VALID_SITES)}"
    if not section.get("keywords"):
        errors["keywords"] = "debe haber al menos un keyword"
    if not section.get("locations"):
        errors["locations"] = "debe haber al menos una localización"
    work_modes = section.get("work_modes", [])
    if not isinstance(work_modes, list) or not work_modes:
        errors["work_modes"] = "debe haber al menos una modalidad"
    elif any(m not in VALID_WORK_MODES for m in work_modes):
        errors["work_modes"] = f"modalidades válidas: {sorted(VALID_WORK_MODES)}"
    job_types = section.get("job_types", [])
    if not isinstance(job_types, list) or any(t not in VALID_JOB_TYPES for t in job_types):
        errors["job_types"] = f"tipos válidos: {sorted(VALID_JOB_TYPES)}"
    err = validate_int_range(section.get("results_wanted"), 1, 100)
    if err:
        errors["results_wanted"] = err
    for key in ("hours_old_daily", "hours_old_initial"):
        err = validate_int_range(section.get(key), 1, 24 * 365)
        if err:
            errors[key] = err
    return errors


def validate_filters(section: dict) -> dict:
    errors: dict[str, str] = {}
    validate_regex_list(section.get("exclude_title_words", []), "exclude_title_words", errors)
    validate_regex_list(section.get("allowed_location_patterns", []), "allowed_location_patterns", errors)
    validate_regex_list(section.get("impossible_years_patterns", []), "impossible_years_patterns", errors)
    err = validate_int_range(section.get("max_age_days"), 1, 3650)
    if err:
        errors["max_age_days"] = err
    err = validate_int_range(section.get("min_score_to_save"), 0, 100)
    if err:
        errors["min_score_to_save"] = err
    return errors


def validate_scoring(section: dict) -> dict:
    errors: dict[str, str] = {}
    for key in ("score_hot", "bonus_skill_points", "bonus_skill_cap", "remote_bonus"):
        err = validate_int_range(section.get(key), 0, 100)
        if err:
            errors[key] = err
    validate_rules(section.get("rules", []), "rules", errors)
    validate_rules(section.get("penalties", []), "penalties", errors)
    return errors


def validate_stack_patterns(section: dict) -> dict:
    errors: dict[str, str] = {}
    if not isinstance(section, dict):
        return {"_": "debe ser un objeto {nombre: patrón}"}
    for name, pattern in section.items():
        err = validate_regex(pattern)
        if err:
            errors[name] = err
    return errors


SECTION_VALIDATORS = {
    "search": validate_search,
    "filters": validate_filters,
    "scoring": validate_scoring,
    "stack_patterns": validate_stack_patterns,
    "schedules": validate_schedules_section,
}


def validate_section(name: str, data: dict) -> None:
    validator = SECTION_VALIDATORS.get(name)
    if validator is None:
        return
    errors = validator(data)
    if errors:
        raise ValidationError(errors)
