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


def test_live_preview_theme_and_validation(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError('preview must not start a build')
    monkeypatch.setattr(k6_store.subprocess, 'run', forbid)
    client = k6_store.create_app().test_client()
    response = client.post('/profiles/preview', data={'theme': 'classic', 'pack': ['aprs', 'scan']})
    assert response.status_code == 200
    result = response.get_json()
    assert result['plan']['theme'] == 'classic'
    assert set(result['plan']['packs']) == {'base', 'aprs', 'scan'}
    assert 'aprsdfsk' in result['plan']['modules']
    assert client.post('/profiles/preview', data={'theme': '../bad'}).status_code == 400
    assert client.post('/profiles/build', data={'theme': '../bad'}).status_code == 400
    assert client.post('/profiles/preview', data={'pack': 'sotto'}).status_code == 400
    page = client.post('/profiles', data={'theme': 'minimal', 'pack': 'scan'})
    assert b'--theme minimal' in page.data
    assert b'value="minimal" checked' in page.data


def test_custom_theme_is_buildable_and_rejects_invalid_markers():
    client = k6_store.create_app().test_client()
    token = 'custom-01-c0f0fcfefcf0c000'
    response = client.post('/profiles/preview', data={'theme': token, 'pack': 'scan'})
    assert response.status_code == 200
    assert response.get_json()['plan']['theme'] == token
    page = client.post('/profiles', data={'theme': token})
    assert b'Theme editor' in page.data
    assert token.encode() in page.data
    assert b'theme-editor.js' in page.data
    for invalid in ('custom-00-0000000000000000', 'custom-11-0100000000000000',
                    'custom-11-ffffffffffffffff', 'custom-22-c0f0fcfefcf0c000', 'custom-11-xyz'):
        assert client.post('/profiles/preview', data={'theme': invalid}).status_code == 400
        assert client.post('/profiles/build', data={'theme': invalid}).status_code == 400


def test_factory_themes_are_editable_presets():
    from k6_feature_packs import THEME_EDITOR_PRESETS
    client = k6_store.create_app().test_client()
    for key, token in THEME_EDITOR_PRESETS.items():
        page = client.post('/profiles', data={'theme': key})
        assert page.status_code == 200
        assert f'value="{token}" data-theme-id="{key}"'.encode() in page.data
        assert f'data-editor-custom value="{token}"'.encode() in page.data
        assert client.post('/profiles/preview', data={'theme': token}).status_code == 200
    assert 'Flux — factory default'.encode() in client.get('/profiles').data
