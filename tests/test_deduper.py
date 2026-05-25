import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
from core.deduper import dedupe, make_url_hash, make_content_hash


def test_url_hash_normalizes():
    h1 = make_url_hash("https://example.com/job/123?ref=linkedin")
    h2 = make_url_hash("https://example.com/job/123")
    assert h1 == h2


def test_content_hash_normalizes():
    h1 = make_content_hash("  Python Developer  ", "Acme Corp")
    h2 = make_content_hash("python developer", "acme corp")
    assert h1 == h2


def test_dedupe_removes_url_duplicates():
    df = pd.DataFrame([
        {"title": "Dev A", "company": "ACME", "job_url": "https://x.com/1"},
        {"title": "Dev B", "company": "ACME", "job_url": "https://x.com/1"},  # same URL
    ])
    result = dedupe(df)
    assert len(result) == 1


def test_dedupe_removes_content_duplicates():
    df = pd.DataFrame([
        {"title": "Python Dev", "company": "ACME", "job_url": "https://x.com/1"},
        {"title": "Python Dev", "company": "ACME", "job_url": "https://y.com/2"},  # same title+company
    ])
    result = dedupe(df)
    assert len(result) == 1


def test_dedupe_keeps_different_jobs():
    df = pd.DataFrame([
        {"title": "Python Dev", "company": "ACME", "job_url": "https://x.com/1"},
        {"title": "Django Dev", "company": "Betterfly", "job_url": "https://y.com/2"},
    ])
    result = dedupe(df)
    assert len(result) == 2
