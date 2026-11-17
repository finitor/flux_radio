#!/usr/bin/env python3
"""Browse Git-hosted Blowfang modules and load compatible bundles over the cable."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).with_name("k6_store_templates")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(<?([^\s)>]+)>?(?:\s+[^)]*)?\)")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)


def default_config() -> Path:
    override = os.environ.get("BLOWFANG_STORE_CONFIG")
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "blowfang" / "module-store.json"


def default_cache() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "blowfang" / "module-store" / "repos"


def slug_for(source: str) -> str:
    parsed = urlparse(source)
    raw = Path(parsed.path).name if parsed.scheme else Path(source).name
    raw = re.sub(r"\.git$", "", raw, flags=re.I)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-_").lower() or "module"
    digest = hashlib.sha256(source.encode()).hexdigest()[:8]
    return f"{slug[:36]}-{digest}"


def repo_url(source: str, commit: str) -> str | None:
    if source.startswith(("https://", "http://")):
        base = source.rstrip("/")
        if base.endswith(".git"):
            base = base[:-4]
        return f"{base}/tree/{commit}"
    return None


def readme_path(path: Path) -> Path | None:
    for name in ("README.md", "Readme.md", "readme.md", "README.rst", "README.txt"):
        candidate = path / name
        if candidate.is_file():
            return candidate
    return None


def readme_info(path: Path) -> dict:
    file = readme_path(path)
    if not file:
        return {"title": path.name, "summary": "No README found.", "readme": "", "screenshots": []}
    text = file.read_text(errors="replace")
    title = next((m.group(1).strip() for line in text.splitlines()
                  if (m := re.match(r"^#\s+(.+?)\s*#*\s*$", line))), path.name)
    paragraphs = re.split(r"\n\s*\n", text)
    summary = ""
    for paragraph in paragraphs:
        candidate = paragraph.strip()
        if not candidate or candidate.startswith(("#", "![", "<", "[![", "```")):
            continue
        candidate = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", candidate)
        candidate = re.sub(r"[*_`>#]", "", candidate)
        candidate = " ".join(candidate.split())
        if candidate:
            summary = candidate[:340]
            break
    images = []
    for alt, src in IMAGE_RE.findall(text):
        images.append({"alt": alt or title, "src": src})
    for src in HTML_IMAGE_RE.findall(text):
        if not any(image["src"] == src for image in images):
            images.append({"alt": title, "src": src})
    return {"title": title, "summary": summary or "No short description in README.",
            "readme": text, "readme_file": file.name, "screenshots": images[:8]}


def find_bundle(path: Path) -> Path | None:
    candidates = [path / "manifest.json", path / "dist" / "manifest.json"]
    candidates.extend(sorted(path.glob("*/manifest.json")))
    for manifest_path in candidates:
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if (isinstance(manifest, dict) and manifest.get("format") == 1 and isinstance(manifest.get("build_id"), str)
                and isinstance(manifest.get("library"), list)
                and isinstance(manifest.get("sha256"), dict)):
            return manifest_path.parent
    return None


def bundle_info(path: Path | None) -> dict | None:
    if path is None:
        return None
    try:
        manifest = json.loads((path / "manifest.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    modules = [{"name": item.get("name", item.get("file", "Module")),
                "slot": item.get("slot"), "kind": item.get("kind", "module"),
                "level": item.get("level")} for item in manifest.get("library", [])]
    build_id = manifest.get("build_id", "")
    return {"path": path, "build": manifest.get("build", ""),
            "build_id": build_id if build_id and set(build_id) != {"0"} else None,
            "modules": modules}


class ModuleStore:
    def __init__(self, config: Path | None = None, cache: Path | None = None):
        self.config = (config or default_config()).expanduser()
        self.cache = (cache or default_cache()).expanduser()

    def configured_sources(self) -> list[dict]:
        try:
            data = json.loads(self.config.read_text())
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read catalog {self.config}: {exc}") from exc
        entries = data.get("sources", [])
        if not isinstance(entries, list):
            raise ValueError(f"{self.config}: 'sources' must be a list")
        return entries

    def sources(self) -> list[dict]:
        entries = self.configured_sources()
        configured_paths = {str(Path(e['source']).expanduser().resolve())
                            for e in entries if Path(e.get('source', '')).expanduser().is_dir()}
        directory = ROOT / 'local-modules'
        if not directory.is_dir():
            return entries
        for path in sorted(directory.iterdir()):
            if not path.is_dir():
                continue
            source = str(path.resolve())
            # Local module bundles are useful artifacts in their own right; they don't need
            # a synthetic .git directory just to appear in the catalog. Git repos continue
            # to work as before, provided they contain an installable bundle.
            if source in configured_paths or find_bundle(path) is None:
                continue
            entries.append({'id': slug_for(source + '#'), 'source': source})
            configured_paths.add(source)
        return entries

    def save(self, entries: list[dict]) -> None:
        self.config.parent.mkdir(parents=True, exist_ok=True)
        temp = self.config.with_suffix(self.config.suffix + ".tmp")
        temp.write_text(json.dumps({"format": 1, "sources": entries}, indent=2) + "\n")
        temp.replace(self.config)

    def add(self, source: str, ref: str | None = None) -> dict:
        source = source.strip()
        local = Path(source).expanduser()
        if local.exists():
            source = str(local.resolve())
            if not local.is_dir():
                raise ValueError("a local source must be a module bundle or Git repository directory")
            if find_bundle(local) is None:
                try:
                    subprocess.run(["git", "-C", source, "rev-parse", "--is-inside-work-tree"],
                                   check=True, capture_output=True, text=True, timeout=10)
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
                    raise ValueError("a local source must contain an installable bundle or be a Git checkout") from exc
        elif not source.startswith(("https://", "ssh://", "git@")):
            raise ValueError("source must be an HTTPS/SSH Git URL or an existing directory")
        entries = self.configured_sources()
        if any(e.get("source") == source and e.get("ref", "") == (ref or "") for e in self.sources()):
            raise ValueError("that source and ref are already in the catalog")
        entry = {"id": slug_for(source + "#" + (ref or "")), "source": source}
        if ref:
            entry["ref"] = ref
        entries.append(entry)
        self.sync(entry, refresh=True)
        self.save(entries)
        return entry

    def remove(self, repo_id: str) -> bool:
        entries = self.configured_sources()
        kept = [e for e in entries if e.get("id") != repo_id]
        if len(kept) == len(entries):
            return False
        self.save(kept)
        return True

    def location(self, entry: dict) -> Path:
        local = Path(entry["source"]).expanduser()
        if local.is_dir():
            return local.resolve()
        return self.cache / entry["id"]

    def sync(self, entry: dict, refresh: bool = False) -> Path:
        local = Path(entry["source"]).expanduser()
        if local.is_dir():
            return local.resolve()
        target = self.cache / entry["id"]
        if target.is_dir() and not refresh:
            return target
        self.cache.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        cmd = ["git", "clone", "--depth", "1"]
        if entry.get("ref"):
            cmd += ["--branch", entry["ref"]]
        cmd += [entry["source"], str(target)]
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "git clone failed")
        return target

    def repo(self, entry: dict, refresh: bool = False) -> dict:
        path = self.sync(entry, refresh=refresh)
        info = readme_info(path)
        try:
            commit = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                             text=True, stderr=subprocess.DEVNULL).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            commit = "local"
        bundle_path = find_bundle(path)
        return {**entry, **info, "path": path, "commit": commit,
                "source_link": repo_url(entry["source"], commit),
                "bundle": bundle_info(bundle_path)}

    def catalog(self) -> list[dict]:
        repos = []
        for entry in self.sources():
            try:
                repos.append(self.repo(entry))
            except (OSError, RuntimeError, ValueError) as exc:
                repos.append({**entry, "title": entry.get("id", "Repository"),
                              "summary": f"Catalog refresh failed: {exc}",
                              "screenshots": [], "readme": "", "error": str(exc),
                              "bundle": None, "path": self.location(entry)})
        return repos

    def by_id(self, repo_id: str, refresh: bool = False) -> dict:
        entry = next((e for e in self.sources() if e.get("id") == repo_id), None)
        if entry is None:
            raise KeyError(repo_id)
        return self.repo(entry, refresh=refresh)


def create_app(store: ModuleStore | None = None):
    try:
        from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
    except ImportError as exc:
        raise RuntimeError("Flask is required for the web UI; install tools/k6_store_requirements.txt") from exc

    app = Flask(__name__, template_folder=str(TEMPLATES), static_folder=str(TEMPLATES / "static"))
    app.secret_key = os.environ.get("BLOWFANG_STORE_SECRET") or secrets.token_bytes(32)
    catalog = store or ModuleStore()
    app.config["module_store"] = catalog

    def radio_settings() -> dict:
        return {"port": session.get("radio_port", ""),
                "key_file": session.get("radio_key_file", "")}

    def cable_command(*args: str) -> list[str]:
        settings = radio_settings()
        if not settings["port"]:
            raise ValueError("Set the USB serial port in Device settings first.")
        command = [sys.executable, str(ROOT / "tools" / "k6_install.py"), "--port", settings["port"]]
        if settings["key_file"]:
            command += ["--key-file", settings["key_file"]]
        return command + list(args)

    @app.context_processor
    def inject_radio_settings():
        return {"radio_settings": radio_settings()}

    @app.get("/settings")
    def settings_page():
        return render_template("settings.html", settings=radio_settings())

    @app.post("/settings")
    def save_settings():
        port = request.form.get("port", "").strip()
        key_file = request.form.get("key_file", "").strip()
        if not port:
            flash("Enter the serial device path, such as /dev/ttyUSB0.", "error")
            return render_template("settings.html", settings={"port": port, "key_file": key_file}), 400
        session["radio_port"] = port
        session["radio_key_file"] = key_file
        flash("Radio connection saved for this browser session.", "success")
        return redirect(url_for("settings_page"))

    @app.get("/")
    def index():
        try:
            repos = catalog.catalog()
        except ValueError as exc:
            repos = []
            flash(str(exc), "error")
        return render_template("index.html", repos=repos)

    @app.get("/profiles")
    def profiles():
        from k6_feature_packs import DEFAULT, resolve
        from k6_pack_policy import POLICY, validate, gate_environment
        spec = json.loads(DEFAULT.read_text())
        policy = json.loads(POLICY.read_text())
        validate(spec, policy)
        choices = {name: item for name, item in spec['packs'].items() if name != 'base'}
        return render_template("profiles.html", choices=choices, result=None, selected=['base'])

    @app.post("/profiles")
    def plan_profile():
        from k6_feature_packs import DEFAULT, resolve
        from k6_pack_policy import POLICY, validate, gate_environment
        spec = json.loads(DEFAULT.read_text())
        policy = json.loads(POLICY.read_text())
        choices = {name: item for name, item in spec['packs'].items() if name != 'base'}
        selected = request.form.getlist('pack')
        if any(name not in choices for name in selected):
            abort(400)
        try:
            validate(spec, policy)
            plan = resolve(spec, selected or ['base'])
            result = {'ok': True, 'plan': plan, 'gates': gate_environment(plan, policy)}
        except (ValueError, KeyError) as exc:
            result = {'ok': False, 'error': str(exc)}
        return render_template('profiles.html', choices=choices, result=result,
                               selected=selected), (200 if result['ok'] else 400)

    @app.get("/radio")
    def radio():
        return render_template("radio.html", inventory=None, action_result=None)

    @app.post("/radio")
    def inspect_radio():
        try:
            command = cable_command("status")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("settings_page"))
        settings = radio_settings()
        port, key_file = settings["port"], settings["key_file"]
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + "\nRadio status timed out after 60 seconds."
            return render_template("radio.html", inventory={"ok": False, "output": output,
                                     "slots": [], "protocol": 0}, port=port, key_file=key_file,
                                   action_result=None), 504
        output = result.stdout + ("\n" + result.stderr if result.stderr else "")
        protocol_match = re.search(r"cable session (\d+)", result.stdout)
        protocol = int(protocol_match.group(1)) if protocol_match else 0
        slots = []
        pattern = re.compile(r"^slot\s+(\d+)\s+(page|cards|module)\s+(.+?)\s+(\d+)\s+B code, serial (\d+)$")
        for line in result.stdout.splitlines():
            match = pattern.search(line.strip())
            if not match:
                continue
            slot, kind, name, size, serial = match.groups()
            slots.append({"slot": int(slot), "kind": kind, "name": name.strip(),
                          "size": int(size), "serial": int(serial)})
        repos = catalog.catalog() if result.returncode == 0 else []
        for slot in slots:
            slot["source"] = None
            if slot["kind"] != "module":
                continue
            for repo in repos:
                if not repo.get("bundle"):
                    continue
                if any(m["name"].casefold() == slot["name"].casefold()
                       for m in repo["bundle"]["modules"]):
                    slot["source"] = {"id": repo["id"], "title": repo["title"]}
                    break
        return render_template("radio.html", inventory={"ok": result.returncode == 0,
                               "output": output, "slots": slots, "protocol": protocol}, port=port,
                               key_file=key_file, action_result=None)

    @app.post("/radio/remove")
    def erase_radio_slot():
        try:
            slot = int(request.form.get("slot", ""))
        except ValueError:
            abort(400)
        confirmation = request.form.get("confirmation", "").strip()
        if confirmation != f"ERASE {slot}":
            return render_template("radio.html", inventory=None,
                                   action_result={"ok": False,
                                                  "output": f"Erase cancelled. Type ERASE {slot} exactly to confirm."}), 400
        try:
            command = cable_command("remove-slot", str(slot), "--yes")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("settings_page"))
        settings = radio_settings()
        port, key_file = settings["port"], settings["key_file"]
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=180)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + "\nSlot erase timed out. Reconnect and inspect the radio before retrying."
            return render_template("radio.html", inventory=None, port=port, key_file=key_file,
                                   action_result={"ok": False, "output": output}), 504
        output = result.stdout + ("\n" + result.stderr if result.stderr else "")
        return render_template("radio.html", inventory=None, port=port, key_file=key_file,
                               action_result={"ok": result.returncode == 0, "output": output}), (
                                   200 if result.returncode == 0 else 500)

    @app.post("/sources")
    def add_source():
        source = request.form.get("source", "").strip()
        ref = request.form.get("ref", "").strip() or None
        try:
            entry = catalog.add(source, ref)
            flash(f"Added {entry['id']}.", "success")
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            flash(str(exc), "error")
        return redirect(url_for("index"))

    @app.post("/refresh")
    def refresh_all():
        for entry in catalog.sources():
            try:
                catalog.repo(entry, refresh=True)
            except (OSError, RuntimeError, ValueError) as exc:
                flash(f"{entry.get('id')}: {exc}", "error")
        flash("Catalog refresh finished.", "success")
        return redirect(url_for("index"))

    @app.get("/repo/<repo_id>")
    def detail(repo_id):
        try:
            repo = catalog.by_id(repo_id)
        except KeyError:
            abort(404)
        return render_template("detail.html", repo=repo, result=None)

    @app.post("/repo/<repo_id>/install")
    def install(repo_id):
        try:
            repo = catalog.by_id(repo_id)
        except KeyError:
            abort(404)
        if not repo.get("bundle"):
            flash("This repository has no installable format-1 module bundle.", "error")
            return redirect(url_for("detail", repo_id=repo_id))
        try:
            command = cable_command("load", str(repo["bundle"]["path"]))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("settings_page"))
        port = radio_settings()["port"]
        if request.form.get("verify") == "yes":
            command.append("--verify")
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=240)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + "\nInstaller timed out after 240 seconds."
            return render_template("detail.html", repo=repo,
                                   result={"ok": False, "output": output,
                                           "returncode": "timeout"}), 504
        output = result.stdout + ("\n" + result.stderr if result.stderr else "")
        return render_template("detail.html", repo=repo,
                               result={"ok": result.returncode == 0, "output": output,
                                       "returncode": result.returncode}), (500 if result.returncode else 200)

    @app.get("/repo/<repo_id>/file/<path:filename>")
    def repo_file(repo_id, filename):
        try:
            repo = catalog.by_id(repo_id)
        except KeyError:
            abort(404)
        root = Path(repo["path"]).resolve()
        target = (root / filename).resolve()
        allowed = set()
        for image in repo['screenshots']:
            src = image['src']
            parsed = urlparse(src)
            if not parsed.scheme and not parsed.netloc and not src.startswith('/'):
                allowed.add((root / Path(repo.get('readme_file', '')).parent / src).resolve())
        if (root not in target.parents or not target.is_file() or target not in allowed
                or any(part.startswith('.') for part in Path(filename).parts)
                or any(part.startswith('.') for part in target.relative_to(root).parts)
                or target.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}):
            abort(404)
        return send_from_directory(root, filename)

    @app.context_processor
    def helpers():
        def screenshot_url(repo, src):
            parsed = urlparse(src)
            if parsed.scheme == "https":
                return src
            if parsed.scheme or src.startswith("/"):
                return ""
            clean = (Path(repo["readme_file"]).parent / src).as_posix()
            return url_for("repo_file", repo_id=repo["id"], filename=clean)
        return {"screenshot_url": screenshot_url}

    return app


def print_repo(repo: dict) -> None:
    print(f"{repo['id']}  {repo['title']}")
    print(f"  {repo['summary']}")
    print(f"  source: {repo['source']}  commit: {repo['commit'][:12]}")
    if repo.get("bundle"):
        for module in repo["bundle"]["modules"]:
            print(f"  {module['kind']} slot {module['slot']}: {module['name']} (API {module['level']})")
    elif not repo.get("error"):
        print("  no installable bundle found")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=default_config())
    parser.add_argument("--cache", type=Path, default=default_cache())
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add a Git URL or local repo")
    add.add_argument("source")
    add.add_argument("--ref", help="branch or tag to follow")
    remove = sub.add_parser("remove", help="remove a repository from the catalog")
    remove.add_argument("repo_id")
    listing = sub.add_parser("list", help="list catalog repos and installable modules")
    listing.add_argument("--refresh", action="store_true")
    show = sub.add_parser("show", help="show one repository's README metadata and screenshots")
    show.add_argument("repo_id")
    show.add_argument("--refresh", action="store_true")
    refresh = sub.add_parser("refresh", help="fetch the latest commits")
    refresh.add_argument("repo_id", nargs="?")
    serve = sub.add_parser("serve", help="start the local Flask catalog")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=5055)
    serve.add_argument("--debug", action="store_true")
    install = sub.add_parser("install", help="install a repository's format-1 bundle")
    install.add_argument("repo_id")
    install.add_argument("--port", required=True)
    install.add_argument("--key-file")
    install.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    store = ModuleStore(args.config, args.cache)
    try:
        if args.command == "add":
            entry = store.add(args.source, args.ref)
            print(f"Added {entry['id']}: {entry['source']}")
        elif args.command == "remove":
            if not store.remove(args.repo_id):
                parser.error(f"no repository with id {args.repo_id!r}")
            print(f"Removed {args.repo_id} from the catalog (cached checkout retained).")
        elif args.command == "list":
            for entry in store.sources():
                repo = store.repo(entry, refresh=args.refresh)
                print_repo(repo)
        elif args.command == "show":
            repo = store.by_id(args.repo_id, refresh=args.refresh)
            print_repo(repo)
            print("\nREADME preview:\n")
            print("\n".join(repo["readme"].splitlines()[:80]))
            if repo["screenshots"]:
                print("\nScreenshots:")
                for image in repo["screenshots"]:
                    print(f"  {image['alt']}: {image['src']}")
        elif args.command == "refresh":
            entries = store.sources()
            chosen = [e for e in entries if args.repo_id is None or e["id"] == args.repo_id]
            if not chosen:
                parser.error(f"no repository with id {args.repo_id!r}")
            for entry in chosen:
                print_repo(store.repo(entry, refresh=True))
        elif args.command == "serve":
            app = create_app(store)
            app.run(host=args.host, port=args.port, debug=args.debug)
        elif args.command == "install":
            repo = store.by_id(args.repo_id)
            if not repo.get("bundle"):
                raise ValueError("repository has no installable format-1 module bundle")
            command = [sys.executable, str(ROOT / "tools" / "k6_install.py"),
                       "--port", args.port]
            if args.key_file:
                command += ["--key-file", args.key_file]
            command += ["load", str(repo["bundle"]["path"])]
            if args.verify:
                command.append("--verify")
            return subprocess.run(command).returncode
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"k6-store: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
