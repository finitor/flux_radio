"""Persistent, named themes for the local Flux catalog."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from threading import Lock
import base64
import binascii

from k6_theme_package import pack, unpack


def default_library_path() -> Path:
    override = os.environ.get("FLUX_THEME_LIBRARY")
    if override:
        return Path(override).expanduser()
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data / "flux" / "themes.json"


class ThemeLibrary:
    def __init__(self, path: Path | None = None):
        self.path = path or default_library_path()
        self.lock = Lock()

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text())
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("themes"), dict):
            raise ValueError("invalid saved theme library")
        return data["themes"]

    def _write(self, themes: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".themes-", suffix=".tmp", delete=False) as out:
                temporary = Path(out.name)
                os.chmod(out.name, 0o600)
                json.dump({"version": 1, "themes": themes}, out, indent=2, ensure_ascii=False)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def list(self) -> list[dict[str, str]]:
        with self.lock:
            themes = self._read()
            return [dict(name=name, **({"token": themes[name]} if isinstance(themes[name], str) else themes[name]))
                    for name in sorted(themes, key=str.casefold)]

    def save(self, name: str, token: str, preview: str = "") -> dict[str, str]:
        name = name.strip()
        if not name or len(name) > 40 or any(ord(char) < 32 for char in name):
            raise ValueError("enter a theme name of 1–40 printable characters")
        token = unpack(pack(token))
        if preview:
            prefix = "data:image/png;base64,"
            if not preview.startswith(prefix) or len(preview) > 90000:
                raise ValueError("invalid theme preview")
            try:
                png = base64.b64decode(preview[len(prefix):], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("invalid theme preview") from exc
            if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("invalid theme preview")
        item = {"name": name, "token": token, "preview": preview}
        with self.lock:
            themes = self._read()
            if name not in themes and len(themes) >= 100:
                raise ValueError("theme library is full (100 themes)")
            themes[name] = {"token": token, "preview": preview}
            self._write(themes)
        return item

    def delete(self, name: str) -> bool:
        with self.lock:
            themes = self._read()
            if name not in themes:
                return False
            del themes[name]
            self._write(themes)
            return True
