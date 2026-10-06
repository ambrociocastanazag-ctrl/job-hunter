import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from storage.models import Base, Job
from storage import repository
from storage.migrations import run_migrations
from dashboard.app import app

@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(repository, 'get_session', sessions)
    with sessions() as s:
        s.add_all([Job(title='Python developer', company='Test', url_hash='a', content_hash='a', score=80), Job(title='Designer', company='Test', url_hash='b', content_hash='b', score=50)])
        s.commit()
    with app.test_client() as c:
        yield c
    engine.dispose()

def test_favorite_persists_and_filters(client):
    for _ in range(2):
        assert client.post('/job/1/favorite', json={'favorite': True}).json == {'ok': True, 'favorite': True}
    assert bool(repository.get_pipeline_jobs().set_index('id').loc[1, 'is_favorite'])
    page = client.get('/?favorites=1').get_data(as_text=True)
    assert 'data-panel-job="1"' in page and 'data-panel-job="2"' not in page
    assert 'id="job-panel"' in page
    assert 'data-panel-job="1"' not in client.get('/?favorites=1&q=Designer').get_data(as_text=True)
    assert client.post('/job/1/favorite', json={'favorite': False}).status_code == 200
    assert 'data-panel-job="1"' not in client.get('/?favorites=1').get_data(as_text=True)

@pytest.mark.parametrize('payload', [{}, {'favorite': 'true'}, {'favorite': 1}, [], None])
def test_rejects_invalid_favorite(client, payload):
    assert client.post('/job/1/favorite', json=payload).status_code == 400

def test_missing_job(client):
    assert client.post('/job/999/favorite', json={'favorite': True}).status_code == 404

def test_migration_preserves_legacy_jobs():
    engine = create_engine('sqlite://')
    with engine.begin() as c:
        c.execute(text('CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT)'))
        c.execute(text("INSERT INTO jobs VALUES (1, 'Existing job')"))
        c.execute(text('CREATE TABLE search_runs (id INTEGER PRIMARY KEY)'))
    run_migrations(engine)
    run_migrations(engine)
    with engine.connect() as c:
        assert c.execute(text('SELECT title, is_favorite FROM jobs')).one() == ('Existing job', 0)
    engine.dispose()
