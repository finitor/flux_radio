#!/usr/bin/env python3
"""Compile-time alternate boot logo styles for the Flux splash.

Runs after ``apply-flux-branding.py`` and patches only the existing
``const LOGO: [u16; 16]`` array inside ``draw_flux_splash`` in the
generated ``ui/boot.rs``. All boot text, logo dimensions (16x16),
render position, and other boot modes are left untouched.

Theme selection comes from ``K6_THEME`` via
``tools/k6_feature_packs.py:theme_layout`` (font, inset, meter, splash):

* splash 0 -- exact factory 16x16 logo from ``apply-flux-branding.py``
* splash 1 -- vibrating string loop (legacy diamond slot)
* splash 2 -- antenna / tower
* splash 3 -- the custom 16x16 icon from a theme code

The script is idempotent: running it twice with the same theme yields
identical output, and splash 0 restores the factory bitmap byte-for-byte.
Wire it in the build after the branding pass (not done here).
"""
from pathlib import Path
import os
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from k6_feature_packs import theme_layout, theme_logo

ROOT = Path(__file__).resolve().parent / "build/aura-fd6818b-port/src"
BOOT_RS = ROOT / "ui/boot.rs"

# Exact factory 16x16 Flux glyph from apply-flux-branding.py boot().
FACTORY_LOGO = [
    0x0000, 0x07FE, 0x07FE, 0x0F7E,
    0x0EFC, 0x1DC0, 0x1DF8, 0x1830,
    0x3070, 0x38E0, 0x3900, 0x7200,
    0x7400, 0xE800, 0xF000, 0x0000,
]

# Splash 1: vibrating string loop, 16x16. Keep the legacy name and slot for compatibility.
DIAMOND_LOGO = [
    0x0000, 0x0780, 0x0840, 0x103C,
    0x1002, 0x33E2, 0x4202, 0x4204,
    0x4384, 0x4202, 0x2202, 0x1204,
    0x1004, 0x0878, 0x0C80, 0x0300,
]

# Splash 2: standalone antenna tower with aerial crossbars and open lattice legs.
ANTENNA_LOGO = [
    0x2928, 0x4FE4, 0x2928, 0x0100,
    0x0280, 0x0540, 0x0640, 0x0540,
    0x04C0, 0x0540, 0x0640, 0x0540,
    0x04C0, 0x0540, 0x0640, 0x0920,
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
    if splash not in LOGOS and splash != 3:
        raise SystemExit(f"theme splash: unknown splash index {splash} for theme {theme!r}")
    return splash


def format_logo(rows):
    """Render a 16-row LOGO array in the factory source formatting."""
    if len(rows) != 16:
        raise ValueError(f"LOGO must have 16 rows, got {len(rows)}")
    lines = "\n".join(f"        0b{row:016b}," for row in rows)
    return f"const LOGO: [u16; 16] = [\n{lines}\n    ];"


def apply_splash(text, splash, custom_logo=None):
    """Replace only the LOGO array inside draw_flux_splash; return new text."""
    if splash not in LOGOS and not (splash == 3 and custom_logo is not None and len(custom_logo) == 32):
        raise SystemExit(f"theme splash: unknown splash index {splash}")
    if "pub fn draw_flux_splash" not in text:
        raise SystemExit("theme splash: draw_flux_splash not found; run apply-flux-branding.py first")
    if text.count("const LOGO: [u16; 16]") != 1:
        raise SystemExit(
            "theme splash: expected one LOGO array anchor, "
            f"found {text.count('const LOGO: [u16; 16]')}"
        )
    rows = LOGOS[splash] if splash in LOGOS else [int.from_bytes(custom_logo[i:i+2], 'big') for i in range(0,32,2)]
    replacement = format_logo(rows)
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
    new = apply_splash(old, splash, theme_logo(theme) if splash == 3 else None)
    if old != new:
        BOOT_RS.write_text(new)
    print(f"Applied theme splash {splash} for theme {theme!r}")


if __name__ == "__main__":
    main()
