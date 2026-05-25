"""
Wrapper for scheduled runs. Can be called by Task Scheduler (Windows) or cron (Linux).
Usage: python automation/scheduler.py --mode daily
"""
import subprocess
import sys
import os

def run(mode: str = "daily"):
    script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    python = sys.executable
    subprocess.run([python, script, "--mode", mode], check=True)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default="daily")
    args = p.parse_args()
    run(args.mode)
