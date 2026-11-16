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


def test_discovers_local_repositories_without_config(tmp_path, monkeypatch):
    monkeypatch.setattr(k6_store, 'ROOT', tmp_path)
    repo = make_repo(tmp_path / 'local-modules' / 'example')
    config = tmp_path / 'config.json'
    store = k6_store.ModuleStore(config=config, cache=tmp_path / 'cache')
    entries = store.catalog()
    assert len(entries) == 1
    assert entries[0]['path'] == repo
    assert entries[0]['bundle'] is not None
    assert store.by_id(entries[0]['id'])['path'] == repo
    assert not config.exists()


def test_skips_non_repositories_and_invalid_manifests(tmp_path, monkeypatch):
    monkeypatch.setattr(k6_store, 'ROOT', tmp_path)
    root = tmp_path / 'local-modules'
    good = make_repo(root / 'good')
    (root / 'plain').mkdir()
    (root / 'plain' / 'manifest.json').write_text((good / 'manifest.json').read_text())
    invalid = make_repo(root / 'invalid')
    (invalid / 'manifest.json').write_text('[]')
    assert [e['source'] for e in k6_store.ModuleStore(config=tmp_path / 'config').sources()] == [str(good)]


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
