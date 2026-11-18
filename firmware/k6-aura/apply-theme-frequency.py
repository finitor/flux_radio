#!/usr/bin/env python3
"""Patch only standby frequency display; restore exact factory on default."""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from k6_feature_packs import theme_layout

CALL = "draw_frequency(lcd, freq_hz, top + PROFONT_14_POINT.baseline as i32);"
CUSTOM = "draw_flux_theme_frequency(lcd, freq_hz, top + PROFONT_14_POINT.baseline as i32);"
START = "// FLUX theme frequency begin\n"
END = "// FLUX theme frequency end\n"
ANCHOR = '/// Mid-entry VFO frequency:'

def apply(text, font, inset):
    if font not in (0, 1) or inset not in range(4):
        raise ValueError("invalid frequency layout")
    if START in text or END in text:
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError("ambiguous theme frequency block")
        a, b = text.index(START), text.index(END)
        if b <= a or text.count(CUSTOM) != 1 or CALL in text:
            raise ValueError("invalid installed frequency block")
        text = text[:a] + text[b+len(END):]
        text = text.replace(CUSTOM, CALL)
    if text.count(CALL) != 1:
        raise ValueError("missing or ambiguous standby frequency call")
    if not font and not inset:
        return text
    if text.count(ANCHOR) != 1:
        raise ValueError("missing or ambiguous frequency insertion point")
    if font == 0:
        start = text.index("pub(crate) fn draw_frequency<D>")
        end = text.index(ANCHOR, start)
        helper = text[start:end].strip().replace("pub(crate) fn draw_frequency<D>", "fn draw_flux_theme_frequency<D>", 1)
        source = "128 - RIGHT_MARGIN - small_width - big_width"
        if helper.count(source) != 1:
            raise ValueError("unexpected original frequency geometry")
        helper = helper.replace(source, source + f" - {inset}")
    else:
        helper = f"""fn draw_flux_theme_frequency<D>(lcd: &mut D, freq_hz: u32, baseline_y: i32)
where D: DrawTarget<Color = BinaryColor>,
{{
    let mut value: TextBuf<12> = TextBuf::new();
    write!(value, "{{:3}}.{{:05}}", freq_hz / 1_000_000, (freq_hz % 1_000_000) / 10).ok();
    let width = value.as_str().len() as i32 * FONT_6X10.character_size.width as i32;
    Text::new(value.as_str(), Point::new(128 - RIGHT_MARGIN - width - {inset},
        baseline_y - PROFONT_14_POINT.baseline as i32 + FONT_6X10.baseline as i32),
        MonoTextStyle::new(&FONT_6X10, BinaryColor::On)).draw(lcd).ok();
}}"""
    return text.replace(CALL, CUSTOM, 1).replace(ANCHOR, START + helper + "\n" + END + ANCHOR, 1)

if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent / "build/aura-fd6818b-port/src/ui/standby.rs"
    font, inset, _, _ = theme_layout(os.environ.get("K6_THEME", "flux"))
    old = p.read_text()
    new = apply(old, font, inset)
    if old != new:
        p.write_text(new)
