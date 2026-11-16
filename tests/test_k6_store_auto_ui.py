"""Display automatic module slot selection in the app catalog."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import k6_store


def test_detail_describes_automatic_slot():
    repo = {"id": "demo", "title": "Demo", "summary": "", "source": "local", "commit": "local",
            "bundle": {"build": "Demo", "build_id": None, "modules": [{"name": "Demo", "kind": "module",
                        "slot": None, "level": 6}]}, "screenshots": [], "readme": ""}
    app = k6_store.create_app()
    with app.test_request_context():
        from flask import render_template
        page = render_template("detail.html", repo=repo, result=None)
    assert "automatic slot" in page.lower()
    assert "slot None" not in page
