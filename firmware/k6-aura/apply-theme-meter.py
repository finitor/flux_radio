#!/usr/bin/env python3
"""Compile-time styling of only the standby RX S-meter (Aura host build).

Reads ``K6_THEME`` (default ``flux``) via :func:`theme_layout` and rewrites
exactly one anchored meter block in ``ui/standby.rs``:

* meter 0 -- original exact staircase (byte-exact restore);
* meter 1 -- flat 13 segments, same geometry, 9 solid + 4 outlined;
* meter 2 -- continuous solid bar from x=62, with the over-S9 span kept
  as a 1px outline so the S9+ distinction survives.

Original geometry (validated below): x0=62, pitch=5, width=4, height
capped at 7, 13 segments (9 solid S0-S9 + 4 outlined over-S9). dBm and
S-unit text plus the MIC bar are never touched: the patch only replaces
the one anchored RX-meter block and fails closed when the anchor is not
unique. Re-running with the same theme is a no-op; switching back to a
meter-0 theme restores the original block byte-exact.

Usage: ``K6_THEME=<theme> python3 apply-theme-meter.py [standby_rs]``.
The optional path override exists for the synthetic test fixture; the
build calls it with no arguments.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from k6_feature_packs import theme_layout, validate_theme

# Validated numeric choices for the RX S-meter. Fail closed if edited wrong.
X0, PITCH, WIDTH, HMAX = 62, 5, 4, 7
NSOLID, NOVER = 9, 4
NSEG = NSOLID + NOVER
OVER_X = X0 + NSOLID * PITCH          # 107: first over-S9 segment
OVER_W = NOVER * PITCH - (PITCH - WIDTH)  # 19: 4 segs incl. gaps
TOTAL_W = NSEG * PITCH - (PITCH - WIDTH)  # 64: 62..126


def _check_geometry() -> None:
    if not (WIDTH < PITCH and X0 + (NSEG - 1) * PITCH + WIDTH <= 128 and HMAX == 7
            and NSEG == 13 and NSOLID == 9 and NOVER == 4 and OVER_X == 107):
        raise SystemExit("apply-theme-meter: internal meter geometry is invalid")


ORIG_BLOCK = "    draw_classic_bar(lcd, bar_x, base_y, level, S_METER_SEGS);\n"

FLAT_BLOCK = """    // FLUX RX S-meter: flat segments.
    for i in 0..level.min(S_METER_SEGS) {
        let x = bar_x + i as i32 * BAR_SEG_PITCH;
        let style = if i < S_METER_SEGS - BAR_HOLLOW_COUNT {
            PrimitiveStyle::with_fill(BinaryColor::On)
        } else {
            PrimitiveStyle::with_stroke(BinaryColor::On, 1)
        };
        Rectangle::new(Point::new(x, base_y - BAR_MAX_H + 1),
                       Size::new(BAR_SEG_W as u32, BAR_MAX_H as u32))
            .into_styled(style).draw(lcd).ok();
    }
"""

BAR_BLOCK = """    // FLUX RX S-meter: continuous solid and outlined over-S9 spans.
    let solid = level.min(S_METER_SEGS - BAR_HOLLOW_COUNT) as i32;
    let over = level.saturating_sub(S_METER_SEGS - BAR_HOLLOW_COUNT)
        .min(BAR_HOLLOW_COUNT) as i32;
    if solid > 0 {
        Rectangle::new(Point::new(bar_x, base_y - BAR_MAX_H + 1),
                       Size::new((solid * BAR_SEG_PITCH - BAR_GAP) as u32, BAR_MAX_H as u32))
            .into_styled(PrimitiveStyle::with_fill(BinaryColor::On)).draw(lcd).ok();
    }
    if over > 0 {
        Rectangle::new(Point::new(bar_x + (S_METER_SEGS - BAR_HOLLOW_COUNT) as i32 * BAR_SEG_PITCH,
                                  base_y - BAR_MAX_H + 1),
                       Size::new((over * BAR_SEG_PITCH - BAR_GAP) as u32, BAR_MAX_H as u32))
            .into_styled(PrimitiveStyle::with_stroke(BinaryColor::On, 1)).draw(lcd).ok();
    }
"""

BLOCKS = {0: ORIG_BLOCK, 1: FLAT_BLOCK, 2: BAR_BLOCK}


def main() -> None:
    _check_geometry()
    theme = os.environ.get("K6_THEME", "flux")
    try:
        validate_theme(theme)
        meter = theme_layout(theme)[2]
    except ValueError as exc:
        raise SystemExit(f"apply-theme-meter: {exc}") from None
    if meter not in BLOCKS:
        raise SystemExit(f"apply-theme-meter: unsupported meter style {meter!r}")
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).parent / "build/aura-fd6818b-port/src/ui/standby.rs")
    try:
        text = target.read_text()
    except OSError as exc:
        raise SystemExit(f"apply-theme-meter: cannot read {target}: {exc}") from None
    want = BLOCKS[meter]
    if sum(text.count(b) for b in BLOCKS.values()) != 1:
        raise SystemExit("apply-theme-meter: expected exactly one known RX meter block")
    if want in text:
        print(f"RX S-meter already at style {meter} ({theme})")
        return
    others = [b for m, b in BLOCKS.items() if m != meter and b in text]
    if len(others) != 1 or sum(text.count(b) for b in BLOCKS.values()) != 1:
        raise SystemExit(
            "apply-theme-meter: cannot find unique RX S-meter anchor in "
            f"{target} (expected exactly one known meter block)")
    text = text.replace(others[0], want, 1)
    target.write_text(text)
    print(f"Applied standby RX S-meter style {meter} ({theme})")


if __name__ == "__main__":
    main()
