"""
Quick smoke test for python-jobspy.
Run from job_hunter/ directory:
  python experiments/test_jobspy.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from jobspy import scrape_jobs
import pandas as pd

print("Running minimal JobSpy test: Python Developer on LinkedIn (10 results)...")

try:
    df = scrape_jobs(
        site_name=["linkedin"],
        search_term="Python Developer",
        location="Remote",
        results_wanted=10,
        hours_old=168,
        is_remote=True,
    )

    if df is None or df.empty:
        print("No results returned.")
    else:
        print(f"\nShape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print(f"\nFirst 3 jobs:")
        for _, row in df.head(3).iterrows():
            print(f"  [{row.get('site','')}] {row.get('title','')} @ {row.get('company','')} | {row.get('location','')}")

except Exception as e:
    print(f"ERROR: {e}")
    raise
