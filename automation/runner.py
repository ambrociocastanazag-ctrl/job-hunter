"""RunManager: launches main.py as a subprocess and tracks its progress.

A full run is 100+ site × keyword × location combinations with a few seconds
of delay between each, so it can take tens of minutes. It runs as a
subprocess (not in-process) so it's cancelable and can never take down the
Flask process it's launched from.
"""
import json
import os
import signal
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime, timezone

from storage.models import SearchRun
from storage.repository import create_search_run, get_search_run, update_search_run
from utils.logger import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_MAIN_PY = os.path.join(_BASE_DIR, "main.py")
_LOG_DIR = os.path.join(_BASE_DIR, "logs", "runs")
_MAX_LOG_LINES = 2000


class RunManager:
    _instance: "RunManager | None" = None

    def __init__(self):
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._run_id: int | None = None
        self._log_lines: deque[str] = deque(maxlen=_MAX_LOG_LINES)
        self._log_path: str | None = None
        self._cancelling = False

    @classmethod
    def instance(cls) -> "RunManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def start(self, mode: str, trigger: str = "manual", overrides: dict | None = None) -> int:
        if mode not in ("daily", "initial"):
            raise ValueError("mode debe ser 'daily' o 'initial'")
        overrides = overrides or {}
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("Ya hay una corrida en curso.")

            os.makedirs(_LOG_DIR, exist_ok=True)
            run = SearchRun(
                started_at=datetime.now(timezone.utc),
                params_json={"mode": mode, "trigger": trigger, **overrides},
                mode=mode, trigger=trigger, status="running",
            )
            run_id = create_search_run(run)
            log_path = os.path.join(_LOG_DIR, f"run_{run_id}.log")
            update_search_run(run_id, log_path=log_path)

            cmd = [sys.executable, _MAIN_PY, "--mode", mode, "--run-id", str(run_id), "--trigger", trigger]
            if overrides.get("hours_old") is not None:
                cmd += ["--hours-old", str(overrides["hours_old"])]
            if overrides.get("results_wanted") is not None:
                cmd += ["--results-wanted", str(overrides["results_wanted"])]
            if overrides.get("sites") is not None:
                cmd += ["--sites-json", json.dumps(overrides["sites"])]
            if overrides.get("keywords") is not None:
                cmd += ["--keywords-json", json.dumps(overrides["keywords"])]
            if overrides.get("locations") is not None:
                cmd += ["--locations-json", json.dumps(overrides["locations"])]
            if overrides.get("no_notify"):
                cmd.append("--no-notify")

            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            process = subprocess.Popen(
                cmd, cwd=_BASE_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
                creationflags=creationflags,
            )

            self._process = process
            self._run_id = run_id
            self._log_path = log_path
            self._log_lines = deque(maxlen=_MAX_LOG_LINES)
            self._cancelling = False

            threading.Thread(target=self._pump_output, args=(process, run_id, log_path), daemon=True).start()
            logger.info(f"Run #{run_id} started (mode={mode}, trigger={trigger}, pid={process.pid})")
            return run_id

    def _pump_output(self, process: subprocess.Popen, run_id: int, log_path: str) -> None:
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                for line in process.stdout:
                    with self._lock:
                        self._log_lines.append(line.rstrip("\n"))
                    f.write(line)
                    f.flush()
        finally:
            process.wait()
            with self._lock:
                cancelling = self._cancelling
                if self._process is process:
                    self._process = None

            # main.py closes its own SearchRun row (status ok/failed) in a
            # finally block. If it's still "running" here, the subprocess
            # was killed (cancel) or crashed before reaching that point —
            # close the row ourselves so it never gets stuck.
            current = get_search_run(run_id)
            if current and current["status"] == "running":
                update_search_run(
                    run_id,
                    finished_at=datetime.now(timezone.utc),
                    status="cancelled" if cancelling else "failed",
                )
            logger.info(f"Run #{run_id} process exited (returncode={process.returncode})")

    def cancel(self) -> bool:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                return False
            self._cancelling = True
            process = self._process
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
        except Exception:
            pass

        def _force_kill():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

        threading.Thread(target=_force_kill, daemon=True).start()
        return True

    def status(self) -> dict:
        with self._lock:
            running = self._process is not None and self._process.poll() is None
            return {
                "running": running,
                "run_id": self._run_id,
                "cancelling": self._cancelling,
                "line_count": len(self._log_lines),
            }

    def tail(self, offset: int = 0) -> dict:
        with self._lock:
            lines = list(self._log_lines)
            running = self._process is not None and self._process.poll() is None
        new_lines = lines[offset:]
        return {"lines": new_lines, "next_offset": len(lines), "running": running}
