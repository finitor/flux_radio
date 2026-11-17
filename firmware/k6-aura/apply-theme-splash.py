#!/usr/bin/env python3
"""Compile-time alternate boot logo styles for the Flux splash.

Runs after ``apply-flux-branding.py`` and patches only the existing
``const LOGO: [u16; 16]`` array inside ``draw_flux_splash`` in the
generated ``ui/boot.rs``. All boot text, logo dimensions (16x16),
render position, and other boot modes are left untouched.

Theme selection comes from ``K6_THEME`` via
``tools/k6_feature_packs.py:theme_layout`` (font, inset, meter, splash):

* splash 0 -- exact factory 16x16 logo from ``apply-flux-branding.py``
* splash 1 -- filled diamond
* splash 2 -- antenna / tower

The script is idempotent: running it twice with the same theme yields
identical output, and splash 0 restores the factory bitmap byte-for-byte.
Wire it in the build after the branding pass (not done here).
"""
from pathlib import Path
import os
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from k6_feature_packs import theme_layout

ROOT = Path(__file__).resolve().parent / "build/aura-fd6818b-port/src"
BOOT_RS = ROOT / "ui/boot.rs"

# Exact factory 16x16 Flux glyph from apply-flux-branding.py boot().
FACTORY_LOGO = [
    0x0000, 0x00F0, 0x03F8, 0x0FF0,
    0x1F80, 0x3C00, 0x7800, 0xFFE0,
    0xFFF8, 0x007C, 0x001E, 0x000F,
    0x0007, 0x0003, 0x0000, 0x0000,
]

# Splash 1: filled diamond, 16x16, centered.
DIAMOND_LOGO = [
    0x0000, 0x0180, 0x03C0, 0x07E0,
    0x0FF0, 0x1FF8, 0x3FFC, 0x7FFE,
    0x7FFE, 0x3FFC, 0x1FF8, 0x0FF0,
    0x07E0, 0x03C0, 0x0180, 0x0000,
]

# Splash 2: antenna mast with side radiating arcs over a solid base.
ANTENNA_LOGO = [
    0x0180, 0x05A0, 0x0990, 0x1188,
    0x2184, 0x0180, 0x03C0, 0x03C0,
    0x07E0, 0x07E0, 0x0FF0, 0x0FF0,
    0x1FF8, 0x3FFC, 0x7FFE, 0x0000,
]

LOGOS = {
    0: FACTORY_LOGO,
    1: DIAMOND_LOGO,
    2: ANTENNA_LOGO,
}

LOGO_RE = re.compile(
    r"const LOGO: \[u16; 16\] = \[(?P<body>[^\]]*?)\];",
    re.DOTALL,
)


def splash_for_theme(theme):
    """Return the splash logo index for a K6 theme string."""
    layout = theme_layout(theme)
    splash = layout[3]
    if splash not in LOGOS:
        raise SystemExit(f"theme splash: unknown splash index {splash} for theme {theme!r}")
    return splash


def format_logo(rows):
    """Render a 16-row LOGO array in the factory source formatting."""
    if len(rows) != 16:
        raise ValueError(f"LOGO must have 16 rows, got {len(rows)}")
    lines = "\n".join(f"        0b{row:016b}," for row in rows)
    return f"const LOGO: [u16; 16] = [\n{lines}\n    ];"


def apply_splash(text, splash):
    """Replace only the LOGO array inside draw_flux_splash; return new text."""
    if splash not in LOGOS:
        raise SystemExit(f"theme splash: unknown splash index {splash}")
    if "pub fn draw_flux_splash" not in text:
        raise SystemExit("theme splash: draw_flux_splash not found; run apply-flux-branding.py first")
    if text.count("const LOGO: [u16; 16]") != 1:
        raise SystemExit(
            "theme splash: expected one LOGO array anchor, "
            f"found {text.count('const LOGO: [u16; 16]')}"
        )
    replacement = format_logo(LOGOS[splash])
    new = LOGO_RE.sub(replacement, text, count=1)
    if new == text:
        return text
    # Sanity: only the LOGO block may change.
    if new.count("const LOGO: [u16; 16]") != 1:
        raise SystemExit("theme splash: patch left an unexpected LOGO count")
    return new


def main():
    theme = os.environ.get("K6_THEME", "flux")
    splash = splash_for_theme(theme)
    if not BOOT_RS.is_file():
        raise SystemExit(f"theme splash: generated file not found: {BOOT_RS}")
    old = BOOT_RS.read_text()
    new = apply_splash(old, splash)
    if old != new:
        BOOT_RS.write_text(new)
    print(f"Applied theme splash {splash} for theme {theme!r}")


if __name__ == "__main__":
    main()
