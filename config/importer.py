"""Importa la configuración que arma una IA a partir del prompt de /ayuda.

La IA entrevista a la persona y devuelve un YAML en palabras simples (sin
regex, claves en español). Aquí se traduce a las secciones internas de
settings.yaml y profile.yaml y se valida con los mismos validadores que el
resto del dashboard. parse_import() no guarda nada: devuelve un ImportPlan
con el resumen que se muestra antes de aplicar; apply_import() lo persiste.

Lo que el YAML no menciona se deja como está.
"""
import copy
import re
import unicodedata
from dataclasses import dataclass, field

import yaml

from config.settings import (
    get_profile, get_settings, new_schedule_id, save_profile, save_section, save_section_partial,
)
from config.validation import VALID_SITES, ValidationError, validate_section


class ImportConfigError(Exception):
    """El YAML no se puede importar. errors: mensajes para la persona."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass
class ImportPlan:
    sections: dict = field(default_factory=dict)        # sección completa -> save_section
    runtime_patch: dict = field(default_factory=dict)   # save_section_partial("runtime")
    profile: dict | None = None
    summary: list[tuple[str, list[str]]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_TOP_LEVEL = {"perfil", "busqueda", "filtros", "puntaje", "tecnologias_a_detectar", "horarios", "notificaciones"}

_WORK_MODES = {"remoto": "remote", "remote": "remote", "hibrido": "hybrid", "hybrid": "hybrid",
               "presencial": "onsite", "onsite": "onsite", "on-site": "onsite"}
_JOB_TYPES = {"tiempo_completo": "fulltime", "tiempo completo": "fulltime", "fulltime": "fulltime",
              "full-time": "fulltime", "medio_tiempo": "parttime", "medio tiempo": "parttime",
              "parttime": "parttime", "part-time": "parttime", "practicas": "internship",
              "pasantia": "internship", "internship": "internship", "contrato": "contract",
              "freelance": "contract", "contract": "contract"}
_FIELDS = {"titulo": "title", "title": "title", "descripcion": "description",
           "description": "description", "ubicacion": "location", "location": "location"}
_DAYS = {"lun": "mon", "lunes": "mon", "mon": "mon", "mar": "tue", "martes": "tue", "tue": "tue",
         "mie": "wed", "miercoles": "wed", "wed": "wed", "jue": "thu", "jueves": "thu", "thu": "thu",
         "vie": "fri", "viernes": "fri", "fri": "fri", "sab": "sat", "sabado": "sat", "sat": "sat",
         "dom": "sun", "domingo": "sun", "sun": "sun"}
_DAY_LABELS = {"mon": "lun", "tue": "mar", "wed": "mié", "thu": "jue", "fri": "vie", "sat": "sáb", "sun": "dom"}
_LEVELS = {"junior": "junior", "trainee": "junior", "practicante": "junior", "sin experiencia": "junior",
           "entry": "junior", "entry level": "junior", "mid": "mid", "semi-senior": "mid",
           "semisenior": "mid", "semi senior": "mid", "ssr": "mid", "intermedio": "mid",
           "senior": "senior", "sr": "senior"}
_COUNTRY_ALIASES = {"mexico": "mexico", "espana": "spain", "peru": "peru", "estados unidos": "usa",
                    "eeuu": "usa", "ee.uu.": "usa", "brasil": "brazil", "panama": "panama",
                    "reino unido": "uk", "alemania": "germany", "francia": "france", "italia": "italy",
                    "canada": "canada", "paises bajos": "netherlands", "holanda": "netherlands",
                    "republica checa": "czech republic", "suiza": "switzerland", "suecia": "sweden",
                    "japon": "japan", "corea del sur": "south korea", "sudafrica": "south africa",
                    "todo el mundo": "worldwide", "mundial": "worldwide"}

# Medido en corridas reales: ~20 s por combinación (scraping + pausa entre
# búsquedas). Por encima de _MAX_COMBINATIONS las corridas pasan de ~40 min.
_SECONDS_PER_COMBINATION = 20
_MAX_COMBINATIONS = 120

_ACCENT_CLASSES = {"a": "[aá]", "e": "[eé]", "i": "[ií]", "o": "[oó]", "u": "[uúü]", "n": "[nñ]"}


def _plain(text: str) -> str:
    """minúsculas y sin acentos (ñ -> n), para comparar claves y valores."""
    decomposed = unicodedata.normalize("NFKD", str(text).strip().lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def word_pattern(word: str) -> str:
    """Una palabra o frase -> regex que la encuentra entera, sin importar
    acentos ni si va separada por espacio o guion ('entry level' = 'entry-level')."""
    parts = []
    for ch in " ".join(_plain(word).split()):
        if ch in _ACCENT_CLASSES:
            parts.append(_ACCENT_CLASSES[ch])
        elif ch == " ":
            parts.append(r"[\s-]+")
        else:
            parts.append(re.escape(ch))
    return r"(?<!\w)" + "".join(parts) + r"(?!\w)"


def years_patterns(max_years: int) -> list[str]:
    """Patrones que detectan vacantes que piden más de max_years años."""
    if max_years >= 20:
        return []
    nums = "|".join(str(n) for n in range(max_years + 1, 21))
    unit = r"(?:years?|yrs?|a[ñn]os)"
    return [
        rf"\b(?:{nums})\s*\+\s*{unit}",
        rf"\b(?:{nums})\s*{unit}\s*(?:of\s*)?(?:experience|exp\b|de\s+experiencia)",
        rf"\b(?:m[aá]s\s+de|at\s+least|minimum(?:\s+of)?|m[ií]nimo(?:\s+de)?)\s*(?:{nums})\s*{unit}",
    ]


def _strip_fences(text: str) -> str:
    """Las IA suelen envolver el YAML en ```yaml ... ```; se quita."""
    match = re.search(r"```(?:ya?ml)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else text


def _as_list(value, where: str, errors: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        errors.append(f"{where}: debe ser una lista.")
        return []
    return [str(v).strip() for v in value if v is not None and str(v).strip()]


def _as_int(value, where: str, lo: int, hi: int, errors: list[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        errors.append(f"{where}: debe ser un número.")
        return None
    try:
        number = int(str(value).strip())
    except ValueError:
        errors.append(f"{where}: debe ser un número entero (llegó {value!r}).")
        return None
    if not lo <= number <= hi:
        errors.append(f"{where}: debe estar entre {lo} y {hi}.")
        return None
    return number


def _as_bool(value, where: str, errors: list[str]) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    text = _plain(value)
    if text in ("si", "yes", "true", "1"):
        return True
    if text in ("no", "false", "0"):
        return False
    errors.append(f"{where}: debe ser sí o no.")
    return None


def _map_values(values: list[str], mapping: dict, where: str, errors: list[str]) -> list[str]:
    out = []
    for v in values:
        mapped = mapping.get(_plain(v))
        if mapped is None:
            valid = sorted({k for k in mapping if k.isascii() and "_" not in k and " " not in k})
            errors.append(f"{where}: no reconozco '{v}' (usa: {', '.join(valid)}).")
        elif mapped not in out:
            out.append(mapped)
    return out


def _parse_time(value, where: str, errors: list[str]) -> str | None:
    # YAML 1.1 lee `hora: 09:00` sin comillas como 540 (base 60).
    if isinstance(value, int) and not isinstance(value, bool):
        hours, minutes = divmod(value, 60)
    else:
        match = re.fullmatch(r"(\d{1,2})[:.](\d{2})", str(value or "").strip())
        if not match:
            errors.append(f"{where}: hora en formato HH:MM, por ejemplo \"09:00\".")
            return None
        hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        errors.append(f"{where}: hora inválida.")
        return None
    return f"{hours:02d}:{minutes:02d}"


def _country(value: str, plan: ImportPlan) -> str:
    from jobspy.model import Country

    name = _COUNTRY_ALIASES.get(_plain(value), _plain(value))
    try:
        Country.from_string(name)
        return name
    except ValueError:
        plan.warnings.append(
            f"Indeed y Glassdoor no tienen sitio para '{value}': se usará 'worldwide' (búsqueda internacional)."
        )
        return "worldwide"


def _rules(entries, sign: int, where: str, errors: list[str]) -> list[dict]:
    if entries is None:
        return []
    if not isinstance(entries, list):
        errors.append(f"{where}: debe ser una lista.")
        return []
    rules = []
    for i, entry in enumerate(entries):
        if isinstance(entry, str):
            entry = {"palabra": entry}
        if not isinstance(entry, dict):
            errors.append(f"{where}[{i + 1}]: debe tener 'palabra' y 'puntos'.")
            continue
        entry = {_plain(k): v for k, v in entry.items()}
        word = str(entry.get("palabra") or "").strip()
        if not word:
            errors.append(f"{where}[{i + 1}]: falta 'palabra'.")
            continue
        points = _as_int(entry.get("puntos", 10), f"{where} ({word}): puntos", -100, 100, errors)
        field_name = _FIELDS.get(_plain(entry.get("donde") or "descripcion"))
        if field_name is None:
            errors.append(f"{where} ({word}): 'donde' debe ser titulo, descripcion o ubicacion.")
            continue
        if points is None:
            continue
        rules.append({"label": word, "pattern": word_pattern(word), "points": sign * abs(points),
                      "field": field_name, "enabled": True})
    return rules


def parse_import(text: str) -> ImportPlan:
    """Lee el YAML y arma el plan de cambios. Lanza ImportConfigError si algo
    no se puede usar; no guarda nada."""
    try:
        data = yaml.safe_load(_strip_fences(text or ""))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (línea {mark.line + 1})" if mark else ""
        raise ImportConfigError([f"El archivo no es un YAML válido{where}. Pídele a la IA que lo revise."])
    if not isinstance(data, dict) or not data:
        raise ImportConfigError(["El archivo está vacío o no tiene el formato del prompt de Job Hunter."])

    data = {_plain(k): v for k, v in data.items()}
    errors: list[str] = []
    plan = ImportPlan()
    settings = get_settings()

    for key in data:
        if key not in _TOP_LEVEL:
            plan.warnings.append(f"Se ignoró la sección '{key}' (no la conozco).")

    def section(name: str) -> dict:
        value = data.get(name) or {}
        if not isinstance(value, dict):
            errors.append(f"'{name}' debe tener campos debajo.")
            return {}
        return {_plain(k): v for k, v in value.items()}

    # --- perfil ---
    perfil = section("perfil")
    if perfil:
        profile = get_profile() or {}
        stack = dict(profile.get("stack") or {})
        lines = []
        for key, target, label in (("nombre", "name", "Nombre"), ("ubicacion", "location", "Ubicación"),
                                   ("zona_horaria", "timezone", "Zona horaria")):
            if perfil.get(key) is not None:
                profile[target] = str(perfil[key]).strip()
                lines.append(f"{label}: {profile[target]}")
        if perfil.get("nivel") is not None:
            level = _LEVELS.get(_plain(perfil["nivel"]))
            if level:
                profile["level"] = level
                lines.append(f"Nivel: {'semi-senior' if level == 'mid' else level}")
            else:
                plan.warnings.append(f"Nivel '{perfil['nivel']}' no reconocido: se dejó el actual.")
        if perfil.get("idiomas") is not None:
            profile["languages"] = _as_list(perfil["idiomas"], "perfil.idiomas", errors)
            lines.append("Idiomas: " + ", ".join(profile["languages"]))
        for key, target in (("habilidades_principales", "primary"), ("habilidades_secundarias", "secondary")):
            if perfil.get(key) is not None:
                stack[target] = _as_list(perfil[key], f"perfil.{key}", errors)
                lines.append(f"{key.replace('_', ' ').capitalize()}: " + ", ".join(stack[target]))
        profile["stack"] = stack
        plan.profile = profile
        plan.summary.append(("Perfil", lines))

    # --- búsqueda ---
    busqueda = section("busqueda")
    search = copy.deepcopy(settings["search"])
    if busqueda:
        lines = []
        if busqueda.get("puestos") is not None:
            search["keywords"] = _as_list(busqueda["puestos"], "busqueda.puestos", errors)
            lines.append("Puestos: " + ", ".join(search["keywords"]))
        if busqueda.get("ubicaciones") is not None:
            search["locations"] = _as_list(busqueda["ubicaciones"], "busqueda.ubicaciones", errors)
            lines.append("Ubicaciones: " + ", ".join(search["locations"]))
        if busqueda.get("modalidad") is not None:
            modes = _as_list(busqueda["modalidad"], "busqueda.modalidad", errors)
            search["work_modes"] = _map_values(modes, _WORK_MODES, "busqueda.modalidad", errors)
            lines.append("Modalidad: " + ", ".join(modes))
        if busqueda.get("jornada") is not None:
            job_types = _as_list(busqueda["jornada"], "busqueda.jornada", errors)
            search["job_types"] = _map_values(job_types, _JOB_TYPES, "busqueda.jornada", errors)
            lines.append("Jornada: " + (", ".join(job_types) or "cualquiera"))
        if busqueda.get("sitios") is not None:
            sites = [_plain(s) for s in _as_list(busqueda["sitios"], "busqueda.sitios", errors)]
            bad = [s for s in sites if s not in VALID_SITES]
            if bad:
                errors.append(f"busqueda.sitios: no reconozco {', '.join(bad)} (usa: linkedin, indeed, glassdoor).")
            search["sites"] = [s for s in sites if s in VALID_SITES]
            lines.append("Sitios: " + ", ".join(search["sites"]))
        if busqueda.get("habilidades_extra") is not None:
            search["bonus_skills"] = _as_list(busqueda["habilidades_extra"], "busqueda.habilidades_extra", errors)
            lines.append("Habilidades que suman puntos: " + ", ".join(search["bonus_skills"]))
        if busqueda.get("pais") is not None:
            plan.runtime_patch["country_indeed"] = _country(str(busqueda["pais"]), plan)
            lines.append(f"País para Indeed/Glassdoor: {plan.runtime_patch['country_indeed']}")
        plan.sections["search"] = search
        plan.summary.append(("Búsqueda", lines))
        search_lines = lines

    # --- filtros ---
    filtros = section("filtros")
    filters = copy.deepcopy(settings["filters"])
    excluded_labels: dict[str, str] = {}
    lines = []
    if filtros.get("excluir_en_titulo") is not None:
        words = _as_list(filtros["excluir_en_titulo"], "filtros.excluir_en_titulo", errors)
        filters["exclude_title_words"] = [word_pattern(w) for w in words]
        excluded_labels = {word_pattern(w): w for w in words}
        lines.append("Descartar si el título dice: " + (", ".join(words) or "(nada)"))
    if filtros.get("ubicaciones_aceptadas") is not None:
        places = _as_list(filtros["ubicaciones_aceptadas"], "filtros.ubicaciones_aceptadas", errors)
        filters["allowed_location_patterns"] = [word_pattern(p) for p in places]
        lines.append("Aceptar vacantes en: " + (", ".join(places) or "cualquier lugar"))
    elif busqueda.get("ubicaciones") is not None:
        # Sin esta lista se quedaría el filtro por defecto (LATAM/EE. UU.),
        # que descartaría casi todo lo de otras regiones.
        places = list(search["locations"])
        if "remote" in search["work_modes"]:
            places.append("remote")
        filters["allowed_location_patterns"] = [word_pattern(p) for p in places]
        lines.append("Aceptar vacantes en: " + ", ".join(places) + " (tomado de las ubicaciones de búsqueda)")
    if filtros.get("anios_experiencia_maximos") is not None:
        max_years = _as_int(filtros["anios_experiencia_maximos"], "filtros.anios_experiencia_maximos", 0, 50, errors)
        if max_years is not None:
            filters["impossible_years_patterns"] = years_patterns(max_years)
            lines.append(f"Descartar si piden más de {max_years} años de experiencia")
    if filtros.get("puntaje_minimo") is not None:
        min_score = _as_int(filtros["puntaje_minimo"], "filtros.puntaje_minimo", 0, 100, errors)
        if min_score is not None:
            filters["min_score_to_save"] = min_score
            lines.append(f"Guardar solo vacantes con puntaje de {min_score} o más")
    if lines:
        plan.sections["filters"] = filters
        plan.summary.append(("Filtros", lines))

    # --- puntaje ---
    puntaje = section("puntaje")
    scoring = copy.deepcopy(settings["scoring"])
    lines = []
    if puntaje.get("suman") is not None:
        scoring["rules"] = _rules(puntaje["suman"], 1, "puntaje.suman", errors)
        lines.append("Suman: " + ", ".join(f"{r['label']} (+{r['points']})" for r in scoring["rules"]))
    if puntaje.get("restan") is not None:
        scoring["penalties"] = _rules(puntaje["restan"], -1, "puntaje.restan", errors)
        lines.append("Restan: " + ", ".join(f"{r['label']} ({r['points']})" for r in scoring["penalties"]))
    if puntaje.get("destacada") is not None:
        hot = _as_int(puntaje["destacada"], "puntaje.destacada", 0, 100, errors)
        if hot is not None:
            scoring["score_hot"] = hot
            lines.append(f"Vacante destacada desde {hot} puntos")
    if lines:
        plan.sections["scoring"] = scoring
        plan.summary.append(("Puntaje", lines))

    # --- tecnologías ---
    if data.get("tecnologias_a_detectar") is not None:
        techs = _as_list(data["tecnologias_a_detectar"], "tecnologias_a_detectar", errors)
        plan.sections["stack_patterns"] = {t: word_pattern(t) for t in techs}
        plan.summary.append(("Herramientas a detectar en las vacantes", [", ".join(techs)]))

    # --- horarios (reemplazan a los actuales) ---
    if data.get("horarios") is not None:
        horarios = data["horarios"]
        if not isinstance(horarios, list):
            errors.append("horarios: debe ser una lista.")
            horarios = []
        schedules, lines = [], []
        for i, h in enumerate(horarios):
            where = f"horarios[{i + 1}]"
            if not isinstance(h, dict):
                errors.append(f"{where}: debe tener dias y hora.")
                continue
            h = {_plain(k): v for k, v in h.items()}
            days = _map_values(_as_list(h.get("dias"), f"{where}.dias", errors), _DAYS, f"{where}.dias", errors)
            time = _parse_time(h.get("hora"), f"{where}.hora", errors)
            mode = {"diaria": "daily", "daily": "daily", "inicial": "initial", "initial": "initial"}.get(
                _plain(h.get("busqueda") or "diaria"))
            if mode is None:
                errors.append(f"{where}.busqueda: debe ser diaria o inicial.")
            if not days or not time or not mode:
                if not days:
                    errors.append(f"{where}.dias: indica al menos un día.")
                continue
            day_text = ", ".join(_DAY_LABELS[d] for d in days)
            schedules.append({"id": new_schedule_id(), "name": str(h.get("nombre") or f"Búsqueda {day_text} {time}"),
                              "mode": mode, "days_of_week": days, "time": time, "enabled": True,
                              "notify": _as_bool(h.get("avisar", True), f"{where}.avisar", errors) is not False})
            lines.append(f"{day_text} a las {time} ({'diaria' if mode == 'daily' else 'inicial'})")
        current = len(settings["schedules"])
        if current:
            lines.append(f"Reemplaza {'el horario actual' if current == 1 else f'los {current} horarios actuales'}")
        plan.sections["schedules"] = schedules
        plan.summary.append(("Horarios", lines or ["Sin horarios"]))

    # --- notificaciones ---
    notificaciones = section("notificaciones")
    if notificaciones:
        notifications = copy.deepcopy(settings["notifications"])
        lines = []
        for key, target, label in (("resumen_diario", "digest_enabled", "Resumen diario por Telegram"),
                                   ("alertas_destacadas", "hot_alerts_enabled", "Aviso de vacantes destacadas")):
            value = _as_bool(notificaciones.get(key), f"notificaciones.{key}", errors)
            if value is not None:
                notifications[target] = value
                lines.append(f"{label}: {'sí' if value else 'no'}")
        plan.sections["notifications"] = notifications
        plan.summary.append(("Notificaciones", lines))

    # --- chequeos de cómo se comporta la búsqueda en las plataformas ---
    if "search" in plan.sections:
        combos = (len(search["sites"]) * len(search["keywords"]) * len(search["locations"])
                  * max(1, len(search["job_types"])))
        minutes = max(1, round(combos * _SECONDS_PER_COMBINATION / 60))
        search_lines.append(f"≈ {combos} búsquedas por corrida (unos {minutes} min)")
        if combos > _MAX_COMBINATIONS:
            plan.warnings.append(
                f"Son {combos} búsquedas por corrida (unos {minutes} min) y los sitios pueden bloquear tantas "
                f"seguidas. Pídele a la IA menos puestos, ubicaciones o jornadas (ideal: {_MAX_COMBINATIONS} o menos)."
            )
    if "search" in plan.sections or "filters" in plan.sections:
        excluded = filters["exclude_title_words"]
        for keyword in search["keywords"]:
            for pattern in excluded:
                if re.search(pattern, keyword, re.IGNORECASE):
                    word = excluded_labels.get(pattern, pattern)
                    errors.append(f"El puesto '{keyword}' quedaría descartado porque '{word}' está en excluir_en_titulo.")

    # Con errores de lectura los validadores internos solo repetirían lo mismo
    # con nombres técnicos (search.work_modes…); se corren al final como red.
    for name, value in plan.sections.items() if not errors else ():
        try:
            validate_section(name, value)
        except ValidationError as e:
            errors.extend(f"{name}.{k}: {v}" for k, v in e.errors.items())

    if errors:
        raise ImportConfigError(errors)
    if not plan.summary:
        raise ImportConfigError(["No encontré ninguna sección que importar (perfil, busqueda, filtros…)."])
    return plan


def apply_import(plan: ImportPlan) -> None:
    for name, value in plan.sections.items():
        save_section(name, value)
    if plan.runtime_patch:
        save_section_partial("runtime", plan.runtime_patch)
    if plan.profile is not None:
        save_profile(plan.profile)
