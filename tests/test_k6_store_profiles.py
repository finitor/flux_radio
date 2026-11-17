import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import k6_store


def test_profile_planner_is_read_only(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError('planner must not launch subprocesses or touch radio')
    monkeypatch.setattr(k6_store.subprocess, 'run', forbid)
    client = k6_store.create_app().test_client()
    page = client.get('/profiles')
    assert page.status_code == 200
    assert b'Build your radio' in page.data
    assert b'SOTTO' in page.data
    response = client.post('/profiles', data={'pack': ['scan', 'aprs']})
    assert response.status_code == 200
    assert b'K6_FSK_RX_SERVICE' in response.data
    assert b'K6_SCAN_SERVICE' in response.data
    assert b'explore_scan' in response.data
    assert client.post('/profiles', data={'pack': 'sotto'}).status_code == 400
    assert client.post('/profiles', data={'pack': 'nonexistent'}).status_code == 400
