import json
import subprocess

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('k6_store', Path(__file__).resolve().parents[1] / 'tools' / 'k6_store.py')
k6_store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k6_store)


def make_repo(path):
    path.mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    (path / 'manifest.json').write_text(json.dumps({
        'format': 1, 'build_id': 'abc', 'library': [], 'sha256': {},
    }))
    (path / 'README.md').write_text('# Example\n\nA module.\n')
    return path


def test_discovers_local_bundle_and_repository_without_config(tmp_path, monkeypatch):
    monkeypatch.setattr(k6_store, 'ROOT', tmp_path)
    repo = make_repo(tmp_path / 'local-modules' / 'example')
    bundle = tmp_path / 'local-modules' / 'standalone'
    bundle.mkdir()
    (bundle / 'manifest.json').write_text((repo / 'manifest.json').read_text())
    (bundle / 'README.md').write_text('# Standalone\n\nA local bundle.\n')
    config = tmp_path / 'config.json'
    store = k6_store.ModuleStore(config=config, cache=tmp_path / 'cache')
    entries = store.catalog()
    assert [entry['path'] for entry in entries] == [repo, bundle]
    assert all(entry['bundle'] is not None for entry in entries)
    assert store.by_id(entries[0]['id'])['path'] == repo
    assert store.by_id(entries[1]['id'])['path'] == bundle
    assert not config.exists()


def test_skips_directories_without_valid_bundles(tmp_path, monkeypatch):
    monkeypatch.setattr(k6_store, 'ROOT', tmp_path)
    root = tmp_path / 'local-modules'
    good = make_repo(root / 'good')
    (root / 'plain').mkdir()
    invalid = make_repo(root / 'invalid')
    (invalid / 'manifest.json').write_text('[]')
    assert [e['source'] for e in k6_store.ModuleStore(config=tmp_path / 'config').sources()] == [str(good)]


def test_add_accepts_local_bundle_without_git(tmp_path):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'manifest.json').write_text(json.dumps({
        'format': 1, 'build_id': 'abc', 'library': [], 'sha256': {},
    }))
    (bundle / 'README.md').write_text('# Example bundle\n\nA local module.\n')
    store = k6_store.ModuleStore(config=tmp_path / 'config.json', cache=tmp_path / 'cache')
    entry = store.add(str(bundle))
    assert entry['source'] == str(bundle)
    assert store.by_id(entry['id'])['bundle'] is not None


def test_session_radio_settings_are_reused_by_catalog_install(tmp_path, monkeypatch):
    calls = []

    class Store:
        def by_id(self, repo_id):
            assert repo_id == 'demo'
            return {'id': 'demo', 'title': 'Demo', 'bundle': {'path': tmp_path},
                    'screenshots': [], 'readme': '', 'readme_file': None,
                    'source': 'local', 'source_link': None, 'commit': 'local'}

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'loaded', '')

    monkeypatch.setattr(k6_store.subprocess, 'run', run)
    client = k6_store.create_app(Store()).test_client()
    response = client.post('/settings', data={
        'port': '/dev/ttyUSB7', 'key_file': '/tmp/radio-module.key',
    })
    assert response.status_code == 302
    page = client.get('/repo/demo')
    assert b'/dev/ttyUSB7' in page.data
    assert b'/tmp/radio-module.key' in page.data
    response = client.post('/repo/demo/install', data={'verify': 'yes'})
    assert response.status_code == 200
    command = calls[-1]
    assert command[command.index('--port') + 1] == '/dev/ttyUSB7'
    assert command[command.index('--key-file') + 1] == '/tmp/radio-module.key'
    assert command[-3:] == ['load', str(tmp_path), '--verify']


def test_radio_status_reuses_session_settings(tmp_path, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'K6 CABLE on\n', '')

    monkeypatch.setattr(k6_store.subprocess, 'run', run)
    client = k6_store.create_app(k6_store.ModuleStore(config=tmp_path / 'config')).test_client()
    client.post('/settings', data={'port': '/dev/ttyUSB9', 'key_file': ''})
    response = client.post('/radio')
    assert response.status_code == 200
    status_call = next(command for command in calls if command[-1:] == ['status'])
    assert status_call[-3:] == ['--port', '/dev/ttyUSB9', 'status']


def test_radio_remove_forms_build_safe_module_only_commands(tmp_path, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'module removal complete', '')

    monkeypatch.setattr(k6_store.subprocess, 'run', run)
    client = k6_store.create_app(k6_store.ModuleStore(config=tmp_path / 'config')).test_client()
    client.post('/settings', data={'port': '/dev/ttyUSB9', 'key_file': ''})
    single = client.post('/radio/remove', data={'action': 'single', 'slot': '4'})
    assert single.status_code == 200
    assert calls[-1][-3:] == ['remove-slots', '4', '--yes']
    selected = client.post('/radio/remove', data={'action': 'selected', 'slot': ['4', '17']})
    assert selected.status_code == 200
    assert calls[-1][-3:] == ['remove-slots', '4,17', '--yes']
    all_modules = client.post('/radio/remove', data={'action': 'all'})
    assert all_modules.status_code == 200
    assert calls[-1][-2:] == ['--all-modules', '--yes']
    assert client.post('/radio/remove', data={'action': 'selected'}).status_code == 400
    assert client.post('/radio/remove', data={'action': 'selected', 'slot': ['4', '4']}).status_code == 400


def test_radio_inventory_shows_simple_and_bulk_module_actions(tmp_path, monkeypatch):
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0,
            'Flux cable session 2\nslot 4 module Example 42 B code, serial 123\n', '')

    monkeypatch.setattr(k6_store.subprocess, 'run', run)
    client = k6_store.create_app(k6_store.ModuleStore(config=tmp_path / 'config')).test_client()
    client.post('/settings', data={'port': '/dev/ttyUSB9', 'key_file': ''})
    page = client.post('/radio').data
    assert b'Remove selected' in page
    assert b'Remove all modules' in page
    assert b'name="slot" value="4"' in page
    assert b'Type ERASE' not in page
    assert b'radio.js' in page


def test_manual_source_deduplicated_and_not_written_as_default(tmp_path, monkeypatch):
    monkeypatch.setattr(k6_store, 'ROOT', tmp_path)
    repo = make_repo(tmp_path / 'local-modules' / 'example')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'sources': [{'id': 'manual', 'source': str(repo)}]}))
    store = k6_store.ModuleStore(config=config)
    assert [e['id'] for e in store.sources()] == ['manual']
    assert store.remove('manual')
    assert json.loads(config.read_text())['sources'] == []
    assert len(store.sources()) == 1


def test_repo_file_does_not_expose_git_or_unreferenced_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(k6_store, 'ROOT', tmp_path)
    repo = make_repo(tmp_path / 'local-modules' / 'example')
    (repo / 'secret.txt').write_text('secret')
    (repo / 'picture.png').write_bytes(b'picture')
    (repo / 'README.md').write_text('# Example\n\n![image](picture.png)\n')
    store = k6_store.ModuleStore(config=tmp_path / 'config')
    repo_id = store.sources()[0]['id']
    client = k6_store.create_app(store).test_client()
    assert client.get(f'/repo/{repo_id}/file/picture.png').status_code == 200
    assert client.get(f'/repo/{repo_id}/file/.git/config').status_code == 404
    assert client.get(f'/repo/{repo_id}/file/secret.txt').status_code == 404


def test_shipped_defaults_merge_and_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(k6_store, 'ROOT', tmp_path)
    defaults = tmp_path / 'config' / 'flux-catalog.json'
    defaults.parent.mkdir()
    url = 'https://github.com/example/hello'
    item = {'source': url, 'ref': 'v1'}
    defaults.write_text(json.dumps({'format': 1, 'sources': [item, item]}))
    config = tmp_path / 'user.json'
    store = k6_store.ModuleStore(config=config, cache=tmp_path / 'cache')
    entry, = store.sources()
    assert entry['ref'] == 'v1'
    assert not config.exists()
    assert store.remove(entry['id'])
    assert not store.sources()
    assert not store.remove(entry['id'])
    monkeypatch.setattr(store, 'sync', lambda *a, **kw: tmp_path)
    assert store.add(url, 'v1') == entry
    assert store.sources() == [entry]
    assert store.remove(entry['id'])
    assert not store.sources()


def test_shipped_default_does_not_duplicate_manual(tmp_path, monkeypatch):
    monkeypatch.setattr(k6_store, 'ROOT', tmp_path)
    defaults = tmp_path / 'config' / 'flux-catalog.json'
    defaults.parent.mkdir()
    item = {'source': 'https://github.com/example/hello'}
    defaults.write_text(json.dumps({'format': 1, 'sources': [item]}))
    store = k6_store.ModuleStore(config=tmp_path / 'user.json')
    manual = dict(item, id=k6_store.slug_for(item['source'] + '#'))
    store.save([manual])
    assert store.sources() == [manual]
    assert store.remove(manual['id'])
    assert not store.sources()


def test_archived_local_bundle_hidden_but_explicitly_addable(tmp_path,monkeypatch):
    monkeypatch.setattr(k6_store,'ROOT',tmp_path)
    hidden=make_repo(tmp_path/'local-modules'/'old')
    current=make_repo(tmp_path/'local-modules'/'current')
    policy=tmp_path/'config'/'flux-catalog.json'
    policy.parent.mkdir()
    policy.write_text(json.dumps({'format':1,'sources':[],'archived_local':['old'],
                                  'local_metadata':{'current':{'title':'Current app'}}}))
    store=k6_store.ModuleStore(config=tmp_path/'user.json')
    assert [e['source'] for e in store.sources()]==[str(current)]
    assert store.catalog()[0]['title']=='Current app'
    store.add(str(hidden))
    assert {e['source'] for e in store.sources()}=={str(hidden),str(current)}
