import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import pytest
import k6_store
from k6_build_jobs import BuildJobs


class FakeProcess:
    def __init__(self):
        self.code = None
    def poll(self):
        return self.code


def test_jobs_serialize_and_report(tmp_path):
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return FakeProcess()
    jobs = BuildJobs(tmp_path, runner=runner)
    job_id = jobs.start(['scan', 'aprs'])
    assert jobs.get(job_id)['state'] == 'running'
    assert calls[0][2:5] == ['build', 'base', 'scan']
    with pytest.raises(ValueError, match='already running'):
        jobs.start(['base'])
    jobs._jobs[job_id]['process'].code = 1
    assert jobs.get(job_id)['state'] == 'failed'
    assert jobs.start(['base']) != job_id
    with pytest.raises(KeyError):
        jobs.get('not-a-real-job')


def test_catalog_build_routes_do_not_touch_radio(tmp_path):
    app = k6_store.create_app()
    jobs = BuildJobs(tmp_path, runner=lambda *args, **kwargs: FakeProcess())
    app.config['build_jobs'] = jobs
    client = app.test_client()
    assert client.post('/profiles/build', data={'pack': ['scan', 'aprs']}).status_code == 302
    job_id = next(iter(jobs._jobs))
    response = client.get(f'/profiles/build/{job_id}')
    assert response.status_code == 200
    assert b'RUNNING' in response.data
    assert client.post('/profiles/build', data={'pack': 'unknown'}).status_code == 400
    assert client.get('/profiles/build/nonexistent').status_code == 404
