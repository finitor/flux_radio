#!/usr/bin/env python3
"""Replace only the standby battery icon; five 17x8 row-packed states."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from k6_feature_packs import theme_battery
ORIGINAL = "    super::icons::draw_battery(lcd, 128 - RIGHT_MARGIN, 0, app.battery_bars() + 2);\n"
START = "    // FLUX battery begin\n"
END = "    // FLUX battery end\n"

def apply(text, data):
    if START in text or END in text:
        if text.count(START)!=1 or text.count(END)!=1 or ORIGINAL in text:
            raise ValueError("ambiguous battery patch")
        a,b=text.index(START),text.index(END)
        if b<=a: raise ValueError("invalid battery patch")
        text=text[:a]+ORIGINAL+text[b+len(END):]
    original=next((a for a in (ORIGINAL, ORIGINAL.replace(", 0, app",", row_y, app"), ORIGINAL.replace("128 - RIGHT_MARGIN, 0","c.map(|v|i32::from(v[4])+17).unwrap_or(128 - RIGHT_MARGIN), row_y")) if text.count(a)==1),None)
    if original is None: raise ValueError("missing battery anchor")
    if data is None: return text
    rows=",\n        ".join("["+",".join(f"0x{x:02x}" for x in data[i:i+24])+"]" for i in range(0,120,24))
    block=START+f"""    const BATTERY: [[u8; 24]; 5] = [
        {rows}
    ];
    let glyph = embedded_graphics::image::ImageRaw::<BinaryColor>::new(&BATTERY[app.battery_bars().min(4) as usize], 17);
    Image::new(&glyph, Point::new(128 - RIGHT_MARGIN - 17, 0)).draw(lcd).ok();
"""+END
    return text.replace(original,block,1)

if __name__=="__main__":
    p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent/"build/aura-fd6818b-port/src/ui/standby.rs"
    old=p.read_text()
    new=apply(old,theme_battery(os.environ.get("K6_THEME","flux")))
    if old!=new:p.write_text(new)
