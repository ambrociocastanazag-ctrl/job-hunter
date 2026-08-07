"""Acceso a la configuración editable desde el dashboard.

config/settings.yaml guarda solo los overrides del usuario; lo que falte se
completa con config/defaults.DEFAULTS. get_settings() cachea el resultado y
lo invalida comparando el mtime del YAML, así que un proceso de larga vida
(el dashboard) ve los cambios guardados por otro proceso (una corrida en
subproceso, o el propio dashboard) sin necesidad de reiniciarse.
"""
import copy
import os
import threading

import yaml
from dotenv import load_dotenv, set_key

from config.defaults import DEFAULTS
from config.validation import ValidationError, validate_section

load_dotenv()

_CONFIG_DIR = os.path.dirname(__file__)
_BASE_DIR = os.path.dirname(_CONFIG_DIR)

SETTINGS_PATH = os.path.join(_CONFIG_DIR, "settings.yaml")
PROFILE_PATH = os.path.join(_CONFIG_DIR, "profile.yaml")
ENV_PATH = os.path.join(_BASE_DIR, ".env")

_lock = threading.RLock()
_cache: dict | None = None
_cache_mtime: float | None = None
_migrated = False


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_yaml(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def _write_yaml_atomic(path: str, data: dict) -> None:
    tmp_path = f"{path}.tmp"
    if os.path.exists(path):
        try:
            os.replace(path, f"{path}.bak")
        except OSError:
            pass
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    os.replace(tmp_path, path)


def _migrate_profile_search_once() -> None:
    """One-time migration: seed settings.yaml from profile.yaml's `search:`
    block (and the historical MIN_SCORE env var), then strip `search:` out
    of profile.yaml so it holds only identity data."""
    global _migrated
    if _migrated or os.path.exists(SETTINGS_PATH):
        _migrated = True
        return

    profile = _read_yaml(PROFILE_PATH)
    seed: dict = {}
    changed_profile = False

    search_block = profile.pop("search", None) if profile else None
    if search_block:
        changed_profile = True
        seed["search"] = {
            k: v for k, v in search_block.items()
            if k in ("keywords", "locations", "bonus_skills")
        }

    legacy_job_types = profile.pop("job_types", None) if profile else None
    if legacy_job_types:
        changed_profile = True
        seed.setdefault("search", {})["job_types"] = legacy_job_types

    legacy_min_score = os.getenv("MIN_SCORE")
    if legacy_min_score:
        try:
            seed.setdefault("filters", {})["min_score_to_save"] = int(legacy_min_score)
        except ValueError:
            pass

    if seed:
        _write_yaml_atomic(SETTINGS_PATH, seed)
    if changed_profile and profile:
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            yaml.dump(profile, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    _migrated = True


# Sections whose value is a user-authored collection (record set), not a
# config sub-schema with named keys — an override replaces it wholesale
# instead of being deep-merged key-by-key with DEFAULTS. Without this,
# saving stack_patterns with a technology removed would silently bring it
# back, because the recursive merge treats every dict-shaped section like
# `search` or `scoring`, where missing sub-keys should fall back to DEFAULTS.
_ATOMIC_SECTIONS = {"stack_patterns"}


def get_settings(force_reload: bool = False) -> dict:
    """Returns DEFAULTS deep-merged with config/settings.yaml. Cached and
    invalidated automatically when settings.yaml's mtime changes."""
    global _cache, _cache_mtime

    _migrate_profile_search_once()

    with _lock:
        mtime = os.path.getmtime(SETTINGS_PATH) if os.path.exists(SETTINGS_PATH) else 0
        if force_reload or _cache is None or mtime != _cache_mtime:
            overrides = _read_yaml(SETTINGS_PATH)
            _cache = copy.deepcopy(DEFAULTS)
            for key, value in overrides.items():
                if key in _ATOMIC_SECTIONS or not isinstance(_cache.get(key), dict):
                    _cache[key] = copy.deepcopy(value)
                else:
                    _cache[key] = _deep_merge(_cache[key], value)
            _cache_mtime = mtime
        return copy.deepcopy(_cache)


def save_section(name: str, data: dict) -> None:
    """Validates and persists a top-level section, merged into settings.yaml."""
    if name not in DEFAULTS:
        raise KeyError(f"Sección desconocida: {name}")

    validate_section(name, data)

    with _lock:
        overrides = _read_yaml(SETTINGS_PATH)
        overrides[name] = data
        _write_yaml_atomic(SETTINGS_PATH, overrides)
    get_settings(force_reload=True)


def save_section_partial(name: str, patch: dict) -> None:
    """Deep-merges `patch` into the section's current value and saves it.
    Used so that Básico and Avanzado, which each own a different subset of
    keys within the same section (e.g. `search` or `scoring`), don't clobber
    each other's fields when saving independently."""
    current = get_settings()[name]
    merged = _deep_merge(current, patch) if isinstance(current, dict) else patch
    save_section(name, merged)


def reset_section(name: str) -> None:
    if name not in DEFAULTS:
        raise KeyError(f"Sección desconocida: {name}")
    with _lock:
        overrides = _read_yaml(SETTINGS_PATH)
        overrides.pop(name, None)
        _write_yaml_atomic(SETTINGS_PATH, overrides)
    get_settings(force_reload=True)


def reset_section_keys(name: str, keys: list[str]) -> None:
    """Resets only the given keys of a section to their DEFAULTS values,
    leaving sibling keys untouched. Needed because Básico and Avanzado each
    own a different subset of keys within sections like `search` or
    `scoring` — a full reset_section() there would also wipe the other
    page's fields."""
    if name not in DEFAULTS:
        raise KeyError(f"Sección desconocida: {name}")
    patch = {k: copy.deepcopy(DEFAULTS[name][k]) for k in keys if k in DEFAULTS[name]}
    save_section_partial(name, patch)


# --- Horarios ---

def save_schedules(schedules: list[dict]) -> None:
    save_section("schedules", schedules)


def new_schedule_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def add_schedule(sched: dict) -> None:
    schedules = get_settings()["schedules"]
    schedules.append(sched)
    save_schedules(schedules)


def update_schedule(schedule_id: str, patch: dict) -> None:
    schedules = get_settings()["schedules"]
    for sched in schedules:
        if sched["id"] == schedule_id:
            sched.update(patch)
            break
    else:
        raise KeyError(f"Horario no encontrado: {schedule_id}")
    save_schedules(schedules)


def delete_schedule(schedule_id: str) -> None:
    schedules = [s for s in get_settings()["schedules"] if s["id"] != schedule_id]
    save_schedules(schedules)


# --- Perfil (config/profile.yaml: identidad, no comportamiento de búsqueda) ---

def get_profile() -> dict:
    return _read_yaml(PROFILE_PATH)


def save_profile(data: dict) -> None:
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


# --- Secretos (.env, nunca en settings.yaml) ---

def get_secrets() -> dict:
    return {
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    }


def save_secrets(**kwargs: str) -> None:
    """Writes given keys to .env and refreshes them into os.environ."""
    key_map = {
        "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "TELEGRAM_CHAT_ID",
    }
    if not os.path.exists(ENV_PATH):
        open(ENV_PATH, "a", encoding="utf-8").close()
    with _lock:
        for key, value in kwargs.items():
            env_key = key_map.get(key)
            if not env_key or value is None:
                continue
            set_key(ENV_PATH, env_key, value)
            os.environ[env_key] = value


def get_or_create_flask_secret() -> str:
    secret = os.getenv("FLASK_SECRET_KEY")
    if secret:
        return secret
    import secrets as _secrets
    secret = _secrets.token_hex(32)
    if not os.path.exists(ENV_PATH):
        open(ENV_PATH, "a", encoding="utf-8").close()
    set_key(ENV_PATH, "FLASK_SECRET_KEY", secret)
    os.environ["FLASK_SECRET_KEY"] = secret
    return secret


# --- Compat shim: usado por core/scorer.py y dashboard/app.py ---

def load_search_config() -> tuple[list[str], list[str], list[str]]:
    """Returns (keywords, locations, bonus_skills)."""
    search = get_settings()["search"]
    return search["keywords"], search["locations"], search["bonus_skills"]


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/jobs.db")
