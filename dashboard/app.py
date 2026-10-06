import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from markdownify import markdownify
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

from automation.runner import RunManager
from config.settings import (
    get_settings, get_secrets, get_profile, get_or_create_flask_secret,
    save_section, save_section_partial, reset_section, reset_section_keys,
    save_secrets, save_profile,
    new_schedule_id, add_schedule, update_schedule, delete_schedule,
)
from config.validation import ValidationError, validate_regex
from storage.database import init_db
from storage.repository import (
    set_favorite, get_pipeline_jobs, upsert_status, get_search_runs, get_search_run, update_job_scores,
)

app = Flask(__name__)
app.secret_key = get_or_create_flask_secret()

_TASK_NAME = "JobHunter Dashboard"
_INSTALL_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "automation", "install_task.ps1")


# --- Helpers ---

def _lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _flash_validation_error(e: ValidationError) -> None:
    for field, message in e.errors.items():
        flash(f"{field}: {message}", "danger")


def _fmt_date(val) -> str:
    if val is None or (hasattr(pd, "isnull") and pd.isnull(val)):
        return ""
    try:
        return val.strftime("%d/%m/%y")
    except Exception:
        return ""


def _clean_description(text: str) -> str:
    if not text:
        return ""
    if "<" in text:
        text = markdownify(text, strip=["a", "img"])
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- Dashboard principal ---

@app.route("/")
def index():
    settings = get_settings()
    score_hot = settings["scoring"]["score_hot"]
    statuses = settings["dashboard"]["statuses"]
    per_page = settings["dashboard"]["per_page"]

    score_min = request.args.get("score_min", "", type=str)
    is_new = request.args.get("is_new", "")
    favorites = request.args.get("favorites", "") == "1"
    status_filter = request.args.get("status", "")
    q = request.args.get("q", "").strip().lower()
    page = request.args.get("page", 1, type=int)

    df = get_pipeline_jobs()

    if df.empty:
        return render_template(
            "index.html", jobs=[], stats=_empty_stats(),
            filters=_filters(score_min, is_new, status_filter, q, favorites),
            statuses=statuses, page=1, total_pages=1, total_count=0,
            score_hot=score_hot, active_nav="dashboard",
        )

    stats = {
        "total": len(df),
        "new": int(df["is_new"].sum()),
        "hot": int((df["score"] >= score_hot).sum()),
        "applied": int((df["status"].notna() & (df["status"] != "Pendiente")).sum()),
    }

    if favorites:
        df = df[df["is_favorite"] == True]
    if score_min != "":
        df = df[df["score"] >= int(score_min)]
    if is_new:
        df = df[df["is_new"] == True]
    if status_filter:
        df = df[df["status"] == status_filter]
    if q:
        mask = (
            df["title"].str.lower().str.contains(q, na=False) |
            df["company"].str.lower().str.contains(q, na=False)
        )
        df = df[mask]

    df = df.sort_values("score", ascending=False)

    total_count = len(df)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    df_page = df.iloc[start:start + per_page]

    jobs = []
    for row in df_page.to_dict("records"):
        stack = row.get("stack_detected") or []
        posted = row.get("date_posted")
        scraped = row.get("scraped_at")
        jobs.append({
            "id": row.get("id"),
            "score": row.get("score", 0),
            "title": row.get("title", ""),
            "company": row.get("company", ""),
            "location": row.get("location", ""),
            "is_remote": row.get("is_remote", False),
            "is_new": row.get("is_new", False),
            "is_favorite": bool(row.get("is_favorite", False)),
            "stack": stack[:6],
            "job_url": row.get("job_url", ""),
            "posted": _fmt_date(posted),
            "scraped": _fmt_date(scraped),
            "status": row.get("status") or "Pendiente",
            "source": row.get("source", ""),
            "description": _clean_description(row.get("description") or ""),
        })

    return render_template(
        "index.html",
        jobs=jobs, stats=stats,
        filters=_filters(score_min, is_new, status_filter, q, favorites),
        statuses=statuses, page=page, total_pages=total_pages, total_count=total_count,
        score_hot=score_hot, active_nav="dashboard",
    )


@app.route("/job/<int:job_id>/favorite", methods=["POST"])
def update_favorite(job_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or type(data.get("favorite")) is not bool:
        return jsonify({"ok": False, "error": "Favorito inválido"}), 400
    if not set_favorite(job_id, data["favorite"]):
        return jsonify({"ok": False, "error": "Vacante no encontrada"}), 404
    return jsonify({"ok": True, "favorite": data["favorite"]})


@app.route("/job/<int:job_id>/status", methods=["POST"])
def update_status(job_id):
    data = request.get_json()
    statuses = get_settings()["dashboard"]["statuses"]
    status = (data or {}).get("status", "").strip()
    if not status or status not in statuses:
        return jsonify({"ok": False, "error": "Estado inválido"}), 400
    upsert_status(job_id, status)
    return jsonify({"ok": True})


def _empty_stats():
    return {"total": 0, "new": 0, "hot": 0, "applied": 0}


def _filters(score_min, is_new, status, q, favorites=False):
    return {"score_min": score_min, "is_new": is_new, "status": status, "q": q, "favorites": "1" if favorites else ""}


@app.route("/rescore", methods=["POST"])
def rescore():
    from core.scorer import score_dataframe

    df = get_pipeline_jobs()
    if df.empty:
        flash("No hay vacantes en la DB.", "warning")
        return redirect(url_for("config_basic"))

    scored = score_dataframe(df)
    scores = {int(row["id"]): int(row["score"]) for _, row in scored[["id", "score"]].iterrows()}
    count = update_job_scores(scores)
    flash(f"{count} vacantes re-scoreadas con la configuración actual.", "success")
    return redirect(url_for("config_basic"))


# --- Configuración: Básico ---

@app.route("/config", methods=["GET", "POST"])
def config_basic():
    if request.method == "POST":
        try:
            save_section_partial("search", {
                "work_modes": request.form.getlist("work_modes"),
                "job_types": request.form.getlist("job_types"),
                "sites": request.form.getlist("sites"),
                "keywords": _lines(request.form.get("keywords", "")),
                "locations": _lines(request.form.get("locations", "")),
                "bonus_skills": _lines(request.form.get("bonus_skills", "")),
            })
            save_section_partial("filters", {
                "min_score_to_save": request.form.get("min_score_to_save", type=int),
            })
            save_section_partial("scoring", {
                "score_hot": request.form.get("score_hot", type=int),
            })
            save_section_partial("notifications", {
                "digest_enabled": "digest_enabled" in request.form,
                "hot_alerts_enabled": "hot_alerts_enabled" in request.form,
            })
            save_profile({
                "name": request.form.get("name", "").strip(),
                "level": request.form.get("level", "").strip(),
                "location": request.form.get("location", "").strip(),
                "timezone": request.form.get("timezone", "").strip(),
                "languages": _lines(request.form.get("languages", "")),
                "stack": {
                    "primary": _lines(request.form.get("stack_primary", "")),
                    "secondary": _lines(request.form.get("stack_secondary", "")),
                },
                "salary_expectation_usd_monthly": request.form.get("salary", type=int),
            })
            flash("Configuración guardada. Aplicará en la próxima corrida.", "success")
        except ValidationError as e:
            _flash_validation_error(e)
        return redirect(url_for("config_basic"))

    settings = get_settings()
    profile = get_profile()
    search = settings["search"]
    stack = profile.get("stack") or {}

    return render_template(
        "config_basic.html",
        active_nav="config",
        search=search,
        min_score_to_save=settings["filters"]["min_score_to_save"],
        score_hot=settings["scoring"]["score_hot"],
        notifications=settings["notifications"],
        keywords="\n".join(search["keywords"]),
        locations="\n".join(search["locations"]),
        bonus_skills="\n".join(search["bonus_skills"]),
        profile=profile,
        languages="\n".join(profile.get("languages") or []),
        stack_primary="\n".join(stack.get("primary") or []),
        stack_secondary="\n".join(stack.get("secondary") or []),
    )


# --- Configuración: Avanzado ---

@app.route("/config/advanced")
def config_advanced():
    settings = get_settings()
    secrets = get_secrets()
    masked_token = ""
    if secrets["telegram_bot_token"]:
        t = secrets["telegram_bot_token"]
        masked_token = t[:4] + "*" * max(0, len(t) - 8) + t[-4:] if len(t) > 8 else "*" * len(t)

    return render_template(
        "config_advanced.html",
        active_nav="advanced",
        search=settings["search"],
        filters=settings["filters"],
        scoring=settings["scoring"],
        stack_patterns=settings["stack_patterns"],
        notifications=settings["notifications"],
        runtime=settings["runtime"],
        dashboard_cfg=settings["dashboard"],
        exclude_title_words="\n".join(settings["filters"]["exclude_title_words"]),
        allowed_location_patterns="\n".join(settings["filters"]["allowed_location_patterns"]),
        impossible_years_patterns="\n".join(settings["filters"]["impossible_years_patterns"]),
        retry_delays=",".join(str(x) for x in settings["runtime"]["retry_delays"]),
        masked_token=masked_token,
        chat_id=secrets["telegram_chat_id"],
    )


@app.route("/config/advanced/search", methods=["POST"])
def config_advanced_search():
    try:
        save_section_partial("search", {
            "results_wanted": request.form.get("results_wanted", type=int),
            "hours_old_daily": request.form.get("hours_old_daily", type=int),
            "hours_old_initial": request.form.get("hours_old_initial", type=int),
        })
        flash("Parámetros de búsqueda guardados.", "success")
    except ValidationError as e:
        _flash_validation_error(e)
    return redirect(url_for("config_advanced"))


@app.route("/config/advanced/filters", methods=["POST"])
def config_advanced_filters():
    try:
        save_section_partial("filters", {
            "exclude_title_words": _lines(request.form.get("exclude_title_words", "")),
            "allowed_location_patterns": _lines(request.form.get("allowed_location_patterns", "")),
            "impossible_years_patterns": _lines(request.form.get("impossible_years_patterns", "")),
            "max_age_days": request.form.get("max_age_days", type=int),
        })
        flash("Filtros guardados.", "success")
    except ValidationError as e:
        _flash_validation_error(e)
    return redirect(url_for("config_advanced"))


def _parse_rule_table(prefix: str) -> list[dict]:
    labels = request.form.getlist(f"{prefix}_label[]")
    patterns = request.form.getlist(f"{prefix}_pattern[]")
    all_ofs = request.form.getlist(f"{prefix}_all_of[]")
    points_raw = request.form.getlist(f"{prefix}_points[]")
    fields = request.form.getlist(f"{prefix}_field[]")
    enableds = request.form.getlist(f"{prefix}_enabled[]")

    rules = []
    for i in range(len(patterns)):
        try:
            points = int(points_raw[i])
        except (ValueError, IndexError):
            points = points_raw[i] if i < len(points_raw) else 0
        entry = {
            "label": labels[i].strip() if i < len(labels) else "",
            "pattern": patterns[i].strip(),
            "points": points,
            "field": fields[i] if i < len(fields) else "description",
            "enabled": (enableds[i] if i < len(enableds) else "true") == "true",
        }
        all_of = all_ofs[i].strip() if i < len(all_ofs) else ""
        if all_of:
            entry["all_of"] = [all_of]
        if entry["pattern"]:
            rules.append(entry)
    return rules


@app.route("/config/advanced/scoring", methods=["POST"])
def config_advanced_scoring():
    try:
        save_section_partial("scoring", {
            "rules": _parse_rule_table("rule"),
            "penalties": _parse_rule_table("penalty"),
            "bonus_skill_points": request.form.get("bonus_skill_points", type=int),
            "bonus_skill_cap": request.form.get("bonus_skill_cap", type=int),
            "remote_bonus": request.form.get("remote_bonus", type=int),
        })
        flash("Reglas de scoring guardadas.", "success")
    except ValidationError as e:
        _flash_validation_error(e)
    return redirect(url_for("config_advanced"))


@app.route("/config/advanced/stack", methods=["POST"])
def config_advanced_stack():
    names = request.form.getlist("stack_name[]")
    patterns = request.form.getlist("stack_pattern[]")
    stack_patterns = {n.strip(): p.strip() for n, p in zip(names, patterns) if n.strip() and p.strip()}
    try:
        save_section("stack_patterns", stack_patterns)
        flash("Detección de stack guardada.", "success")
    except ValidationError as e:
        _flash_validation_error(e)
    return redirect(url_for("config_advanced"))


@app.route("/config/advanced/runtime", methods=["POST"])
def config_advanced_runtime():
    try:
        retry_delays = [int(x.strip()) for x in request.form.get("retry_delays", "").split(",") if x.strip()]
    except ValueError:
        flash("retry_delays debe ser una lista de enteros separados por coma.", "danger")
        return redirect(url_for("config_advanced"))

    save_section_partial("runtime", {
        "request_delay_min": request.form.get("request_delay_min", type=int),
        "request_delay_max": request.form.get("request_delay_max", type=int),
        "retry_delays": retry_delays,
        "country_indeed": request.form.get("country_indeed", "usa").strip() or "usa",
    })
    flash("Parámetros de ejecución guardados.", "success")
    return redirect(url_for("config_advanced"))


@app.route("/config/advanced/notifications", methods=["POST"])
def config_advanced_notifications():
    save_section_partial("notifications", {
        "digest_top_n": request.form.get("digest_top_n", type=int),
    })
    flash("Notificaciones guardadas.", "success")
    return redirect(url_for("config_advanced"))


@app.route("/config/advanced/secrets", methods=["POST"])
def config_advanced_secrets():
    token = request.form.get("telegram_bot_token", "").strip()
    chat_id = request.form.get("telegram_chat_id", "").strip()
    kwargs = {}
    if token and not token.startswith("*"):
        kwargs["telegram_bot_token"] = token
    if chat_id:
        kwargs["telegram_chat_id"] = chat_id
    if kwargs:
        save_secrets(**kwargs)
        flash("Credenciales de Telegram guardadas.", "success")
    return redirect(url_for("config_advanced"))


@app.route("/config/advanced/dashboard", methods=["POST"])
def config_advanced_dashboard():
    try:
        save_section_partial("dashboard", {
            "per_page": request.form.get("per_page", type=int),
            "catch_up_on_start": "catch_up_on_start" in request.form,
        })
        flash("Preferencias del dashboard guardadas.", "success")
    except ValidationError as e:
        _flash_validation_error(e)
    return redirect(url_for("config_advanced"))


@app.route("/config/reset/<section>", methods=["POST"])
def config_reset(section):
    """Full-section reset. Only safe for sections owned entirely by one page
    (stack_patterns, runtime, dashboard) — sections shared between Básico
    and Avanzado use /config/reset-keys instead."""
    try:
        reset_section(section)
        flash(f"Sección '{section}' restaurada a sus valores por defecto.", "success")
    except KeyError:
        flash("Sección desconocida.", "danger")
    next_page = "config_advanced" if request.form.get("from") == "advanced" else "config_basic"
    return redirect(url_for(next_page))


@app.route("/config/reset-keys/<section>", methods=["POST"])
def config_reset_keys(section):
    keys = [k.strip() for k in request.form.get("keys", "").split(",") if k.strip()]
    try:
        reset_section_keys(section, keys)
        flash("Campos restaurados a sus valores por defecto.", "success")
    except KeyError:
        flash("Sección desconocida.", "danger")
    next_page = "config_advanced" if request.form.get("from") == "advanced" else "config_basic"
    return redirect(url_for(next_page))


@app.route("/config/regex-test", methods=["POST"])
def regex_test():
    data = request.get_json(silent=True) or {}
    pattern = data.get("pattern", "")
    sample = data.get("sample", "")
    err = validate_regex(pattern)
    if err:
        return jsonify({"ok": False, "error": err})
    match = bool(re.search(pattern, sample, re.IGNORECASE))
    return jsonify({"ok": True, "match": match})


@app.route("/notifications/test", methods=["POST"])
def notifications_test():
    from notifications.telegram import send_message
    ok = send_message("Job Hunter — mensaje de prueba desde el dashboard.")
    return jsonify({"ok": ok})


# --- Horarios ---

@app.route("/schedules")
def schedules():
    from automation.scheduler import get_next_run_times

    next_runs = get_next_run_times()
    sched_list = get_settings()["schedules"]
    return render_template(
        "schedules.html",
        active_nav="schedules",
        schedules=sched_list,
        next_runs=next_runs,
        task_installed=_task_installed(),
    )


@app.route("/schedules/create", methods=["POST"])
def schedules_create():
    from automation.scheduler import sync_schedules

    sched = {
        "id": new_schedule_id(),
        "name": request.form.get("name", "").strip(),
        "mode": request.form.get("mode", "daily"),
        "days_of_week": request.form.getlist("days_of_week"),
        "time": request.form.get("time", ""),
        "enabled": True,
        "notify": "notify" in request.form,
    }
    try:
        add_schedule(sched)
        sync_schedules()
        flash(f"Horario '{sched['name']}' creado.", "success")
    except ValidationError as e:
        _flash_validation_error(e)
    return redirect(url_for("schedules"))


@app.route("/schedules/<schedule_id>/toggle", methods=["POST"])
def schedules_toggle(schedule_id):
    from automation.scheduler import sync_schedules

    current = next((s for s in get_settings()["schedules"] if s["id"] == schedule_id), None)
    if current:
        update_schedule(schedule_id, {"enabled": not current.get("enabled", True)})
        sync_schedules()
    return redirect(url_for("schedules"))


@app.route("/schedules/<schedule_id>/delete", methods=["POST"])
def schedules_delete(schedule_id):
    from automation.scheduler import sync_schedules

    delete_schedule(schedule_id)
    sync_schedules()
    flash("Horario eliminado.", "success")
    return redirect(url_for("schedules"))


def _task_installed() -> bool:
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/tn", _TASK_NAME],
            capture_output=True, text=True, timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _run_task_script(action: str) -> str:
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", _INSTALL_SCRIPT, "-Action", action],
            capture_output=True, text=True, timeout=30,
        )
        return (proc.stdout or proc.stderr or "Sin salida.").strip()
    except Exception as e:
        return f"Error: {e}"


@app.route("/task/install", methods=["POST"])
def task_install():
    result = _run_task_script("Install")
    flash(result, "success" if "instalada" in result.lower() else "danger")
    return redirect(url_for("schedules"))


@app.route("/task/uninstall", methods=["POST"])
def task_uninstall():
    result = _run_task_script("Uninstall")
    flash(result, "success")
    return redirect(url_for("schedules"))


# --- Historial y corridas manuales ---

@app.route("/runs")
def runs():
    rm = RunManager.instance()
    return render_template(
        "runs.html",
        active_nav="runs",
        runs=get_search_runs(),
        run_status=rm.status(),
        search=get_settings()["search"],
    )


@app.route("/runs/start", methods=["POST"])
def runs_start():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "daily")
    overrides = {}
    if data.get("sites"):
        overrides["sites"] = data["sites"]
    if data.get("keywords"):
        overrides["keywords"] = data["keywords"]
    if data.get("locations"):
        overrides["locations"] = data["locations"]
    if data.get("results_wanted"):
        overrides["results_wanted"] = int(data["results_wanted"])
    if data.get("hours_old"):
        overrides["hours_old"] = int(data["hours_old"])
    overrides["no_notify"] = bool(data.get("no_notify"))

    try:
        run_id = RunManager.instance().start(mode=mode, trigger="manual", overrides=overrides)
        return jsonify({"ok": True, "run_id": run_id})
    except (RuntimeError, ValueError) as e:
        return jsonify({"ok": False, "error": str(e)}), 409


@app.route("/runs/cancel", methods=["POST"])
def runs_cancel():
    ok = RunManager.instance().cancel()
    return jsonify({"ok": ok})


@app.route("/runs/status")
def runs_status():
    rm = RunManager.instance()
    status = rm.status()
    if status["run_id"]:
        status["db"] = get_search_run(status["run_id"])
    return jsonify(status)


@app.route("/runs/log")
def runs_log():
    offset = request.args.get("offset", 0, type=int)
    return jsonify(RunManager.instance().tail(offset))


# --- Ayuda: configurar con una IA (prompt + importar YAML) ---

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "ayuda_prompt.md")


def _render_ayuda(yaml_text: str = "", plan=None, errors=None):
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        prompt = f.read()
    return render_template("ayuda.html", active_nav="ayuda", prompt=prompt,
                           yaml_text=yaml_text, plan=plan, errors=errors)


@app.route("/ayuda")
def ayuda():
    return _render_ayuda()


@app.route("/ayuda/revisar", methods=["POST"])
def ayuda_revisar():
    from config.importer import ImportConfigError, parse_import

    text = request.form.get("yaml_text", "")
    try:
        return _render_ayuda(text, plan=parse_import(text))
    except ImportConfigError as e:
        return _render_ayuda(text, errors=e.errors)


@app.route("/ayuda/aplicar", methods=["POST"])
def ayuda_aplicar():
    from automation.scheduler import sync_schedules
    from config.importer import ImportConfigError, apply_import, parse_import

    text = request.form.get("yaml_text", "")
    try:
        plan = parse_import(text)
    except ImportConfigError as e:
        return _render_ayuda(text, errors=e.errors)
    apply_import(plan)
    save_section_partial("dashboard", {"onboarding_done": True})
    if "schedules" in plan.sections:
        sync_schedules()
    flash("Configuración importada. Revísala aquí y lanza tu primera búsqueda desde Historial y búsquedas.", "success")
    return redirect(url_for("config_basic"))


# --- Bienvenida (primer arranque) ---

@app.context_processor
def _inject_onboarding():
    # Solo en la portada, y solo mientras no haya perfil ni se haya cerrado.
    if request.endpoint != "index":
        return {}
    show = not get_settings()["dashboard"].get("onboarding_done") and not get_profile()
    return {"show_onboarding": show}


@app.route("/onboarding/done", methods=["POST"])
def onboarding_done():
    save_section_partial("dashboard", {"onboarding_done": True})
    return ("", 204)


def _port_in_use(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _open_browser_when_ready(url: str, host: str, port: int) -> None:
    import threading
    import time
    import webbrowser

    def _wait_and_open():
        for _ in range(60):
            if _port_in_use(host, port):
                webbrowser.open(url)
                return
            time.sleep(0.5)

    threading.Thread(target=_wait_and_open, daemon=True).start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Job Hunter dashboard")
    parser.add_argument("--open-browser", action="store_true",
                        help="Abre el navegador al arrancar (lo usa el acceso directo JobHunter.bat)")
    args = parser.parse_args()

    host, port = "127.0.0.1", int(os.getenv("JOBHUNTER_PORT", "5000"))
    url = f"http://{host}:{port}"

    # Doble clic al acceso directo con el dashboard ya abierto (o lanzado al
    # iniciar Windows): no levantar un segundo servidor, solo mostrarlo.
    if _port_in_use(host, port):
        print(f"Job Hunter ya estaba abierto en {url}")
        if args.open_browser:
            import webbrowser
            webbrowser.open(url)
        sys.exit(0)

    init_db()
    from storage.repository import close_orphaned_runs
    close_orphaned_runs()
    from automation.scheduler import init_scheduler
    init_scheduler()
    if args.open_browser:
        _open_browser_when_ready(url, host, port)
    print(f"Dashboard en {url}")
    app.run(host=host, port=port, debug=False)
