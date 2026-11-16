"""Local module catalog generator: slot-independent, reproducible packages."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import k6_make_local_catalog as catalog


def test_generate_repository_is_installable_and_does_not_overwrite(tmp_path, monkeypatch):
    source = tmp_path / "demo.c"
    source.write_text('#define K6_MODULE_LEVEL 6\n')
    monkeypatch.setattr(catalog.k6mod, "build", lambda path: (b"\x70\x47", 0))
    out = tmp_path / "repos"
    result = catalog.make_repo("demo", source, out)
    manifest = json.loads((result / "manifest.json").read_text())
    assert manifest["library"][0]["id"] == "org.blowfang.k6.demo"
    assert "slot" not in manifest["library"][0]
    assert (result / ".git").is_dir()
    assert "not validated" in (result / "README.md").read_text().lower()
    with pytest.raises(FileExistsError):
        catalog.make_repo("demo", source, out)
