#!/usr/bin/env python3
"""Add a subtle focus marker to the active Aura VFO on the Blowfang host build."""
from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from k6_feature_packs import validate_theme

theme = os.environ.get("K6_THEME", "flux")
validate_theme(theme)

root = Path(__file__).parent / "build/aura-fd6818b-port/src"
standby = root / "ui/standby.rs"
text = standby.read_text()

marker = '''    if is_master {
        let marker = super::icons::vfo_default();
        Image::new(&marker, Point::new(2, top)).draw(lcd).ok();
    } else if is_watching && app.audio_open() {
        let marker = super::icons::vfo_not_default();
        Image::new(&marker, Point::new(2, top)).draw(lcd).ok();
    }
'''
hidden_marker = '''    #[cfg(not(feature = "blowfang-host"))]
    if is_master {
        let marker = super::icons::vfo_default();
        Image::new(&marker, Point::new(2, top)).draw(lcd).ok();
    } else if is_watching && app.audio_open() {
        let marker = super::icons::vfo_not_default();
        Image::new(&marker, Point::new(2, top)).draw(lcd).ok();
    }
'''
if hidden_marker not in text:
    if text.count(marker) != 1:
        raise SystemExit("standby.rs: cannot find unique VFO arrow marker block")
    text = text.replace(marker, hidden_marker, 1)

call = '''    #[cfg(feature = "blowfang-host")]
    draw_active_vfo_focus(lcd, app, top0, top1);
'''
if call not in text:
    anchor = '''    draw_vfo_band(lcd, app, 0, top0);
    draw_vfo_band(lcd, app, 1, top1);
'''
    if text.count(anchor) != 1:
        raise SystemExit("standby.rs: cannot find unique two-VFO drawing sequence")
    text = text.replace(anchor, anchor + call, 1)

helper = '''#[cfg(feature = "blowfang-host")]
fn draw_active_vfo_focus<D>(lcd: &mut D, app: &app::App, top0: i32, top1: i32)
where
    D: DrawTarget<Color = BinaryColor>,
{
    let top = if app.master_index() == 0 { top0 } else { top1 };
    Rectangle::new(Point::new(0, top), Size::new(128, 1))
        .into_styled(PrimitiveStyle::with_fill(BinaryColor::On))
        .draw(lcd)
        .ok();
    // x=1 stays clear between the outline at x=0 and the row content at x=2.
    Rectangle::new(Point::new(0, top + 1), Size::new(1, (BAND_HEIGHT - 2) as u32))
        .into_styled(PrimitiveStyle::with_fill(BinaryColor::On))
        .draw(lcd)
        .ok();
}

'''
if theme == "minimal":
    start = helper.index("    Rectangle::new(Point::new(0, top),")
    end = helper.index("    // x=1", start)
    helper = helper[:start] + helper[end:]
elif theme == "classic":
    start = helper.index("    Rectangle::new(Point::new(0, top),")
    helper = helper[:start] + """    let marker = super::icons::vfo_default();
    Image::new(&marker, Point::new(2, top)).draw(lcd).ok();
}

"""

elif theme.startswith("custom-"):
    flags, bitmap = theme.split("-")[1:3]
    start = helper.index("    Rectangle::new(Point::new(0, top),")
    rail = helper.index("    // x=1", start)
    end = helper.index("\n}", rail)
    body = (helper[start:rail] if flags[0] == "1" else "")
    if flags[1] == "1":
        body += helper[rail:end] + "\n"
    if int(bitmap, 16):
        rows = ", ".join("0x" + bitmap[i:i+2] for i in range(0, 16, 2))
        icon = f"    const MARKER: [u8; 8] = [{rows}];\n"
        icon += "    let marker = embedded_graphics::image::ImageRaw::<BinaryColor>::new(&MARKER, 7);\n"
        icon += "    Image::new(&marker, Point::new(2, top)).draw(lcd).ok();\n"
        body = icon + body
    helper = helper[:start] + body + "}\n\n"

marker = "fn draw_tx_prohibited_overlay<D>"
import re

existing_helper = re.search(
    r'#\[cfg\(feature = "blowfang-host"\)\]\nfn draw_active_vfo_focus<D>[\s\S]*?(?=fn draw_tx_prohibited_overlay<D>)',
    text,
)
if existing_helper:
    text = text[:existing_helper.start()] + helper + text[existing_helper.end():]
else:
    if text.count(marker) != 1:
        raise SystemExit("standby.rs: cannot find focus-helper insertion point")
    text = text.replace(marker, helper + marker, 1)

standby.write_text(text)
print("Applied active-VFO focus marker")
