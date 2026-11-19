#!/usr/bin/env python3
"""Import Flux sprite-sheet arrays into firmware branding and Designer splash art."""
import ast
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ART_DIR = Path(os.environ.get("K6_FLUX_ART_DIR", HERE.parent.parent / "flux-art-kit/flux-arrays"))
BRANDING = Path(os.environ.get("K6_FLUX_BRANDING_SCRIPT", HERE / "apply-flux-branding.py"))
THEMES = Path(os.environ.get("K6_FLUX_THEME_SCRIPT", HERE / "apply-theme-splash.py"))
DESIGNER = Path(os.environ.get("K6_FLUX_DESIGNER_SOURCE", HERE / "designer-render.rs"))
GENERATED_DESIGNER = HERE / "build/aura-fd6818b-port/src/ui/designer.rs"
NAMES = ("FACTORY_LOGO", "DIAMOND_LOGO", "ANTENNA_LOGO")


def read_arrays(path):
    arrays = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in NAMES:
                    arrays[target.id] = ast.literal_eval(node.value)
    for name in NAMES:
        rows = arrays.get(name)
        if (not isinstance(rows, list) or len(rows) != 16
                or any(type(value) is not int or not 0 <= value <= 0xFFFF for value in rows)):
            raise SystemExit(f"Flux art: {name} must contain exactly 16 unsigned 16-bit rows in {path}")
    return arrays


def format_python(name, rows):
    return name + " = [\n" + "".join(
        "    " + ", ".join(f"0x{value:04X}" for value in rows[i:i + 4]) + ",\n"
        for i in range(0, 16, 4)
    ) + "]"


def replace_python_array(source, name, rows):
    pattern = re.compile(rf"(?m)^{name} = \[[^\]]*\]")
    source, count = pattern.subn(format_python(name, rows), source)
    if count != 1:
        raise SystemExit(f"Flux art: expected one {name} array, found {count}")
    return source


def replace_rust_logo(source, rows):
    pattern = re.compile(r"const LOGO: \[u16; 16\] = \[[^\]]*\];", re.DOTALL)
    body = "const LOGO: [u16; 16] = [\n" + "".join(
        f"        0b{value:016b},\n" for value in rows
    ) + "    ];"
    source, count = pattern.subn(body, source)
    if count != 1:
        raise SystemExit(f"Flux art: expected one LOGO array in branding script, found {count}")
    return source


def replace_designer_logo(source, index, rows):
    pattern = re.compile(rf"(?m)^(\s*{index}=>)\[[^\]]*\](,?)$")
    value = "[" + ",".join(f"0x{row:04x}" for row in rows) + "]"
    source, count = pattern.subn(lambda match: match.group(1) + value + match.group(2), source)
    if count != 1:
        raise SystemExit(f"Flux art: expected one Designer splash {index}, found {count}")
    return source


def main():
    arrays = read_arrays(ART_DIR / "logos.py")
    splash = (ART_DIR / "splash.bin").read_bytes()
    if len(splash) != 1024:
        raise SystemExit(f"Flux art: splash.bin must be exactly 1024 bytes, got {len(splash)}")

    old_branding = BRANDING.read_text()
    old_themes = THEMES.read_text()
    new_branding = replace_rust_logo(old_branding, arrays["FACTORY_LOGO"])
    new_themes = old_themes
    for name in NAMES:
        new_themes = replace_python_array(new_themes, name, arrays[name])
    designer_sources = {}
    for path in (DESIGNER, GENERATED_DESIGNER):
        if path.is_file():
            original = path.read_text()
            updated = replace_designer_logo(original, 1, arrays["DIAMOND_LOGO"])
            updated = replace_designer_logo(updated, 2, arrays["ANTENNA_LOGO"])
            designer_sources[path] = (original, updated)
    if new_branding != old_branding:
        BRANDING.write_text(new_branding)
    if new_themes != old_themes:
        THEMES.write_text(new_themes)
    for path, (original, updated) in designer_sources.items():
        if updated != original:
            path.write_text(updated)
    print(f"Imported Flux art from {ART_DIR}")


if __name__ == "__main__":
    main()
