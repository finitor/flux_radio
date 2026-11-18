#!/usr/bin/env python3
"""Optional standby graphics layers; no extra framebuffer or heap."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from k6_feature_packs import theme_layers, encode_layer

START = "// FLUX theme layers begin\n"
END = "// FLUX theme layers end\n"
ANCHOR = "pub fn draw_standby<D>"
STATUS = "    draw_status_bar(lcd, app);\n"
FOCUS = '    #[cfg(feature = "blowfang-host")]\n    draw_active_vfo_focus(lcd, app, top0, top1);\n'
BG = "    if !app.is_transmitting() { draw_flux_layer(lcd, THEME_BG); }\n"
BEFORE = "    // FLUX theme status moved below cursor.\n"
AFTER = "    // FLUX theme cursor end.\n"

def apply(text,layers):
    # Remove an existing generated patch first, restoring original anchors.
    if START in text or END in text:
        if text.count(START)!=1 or text.count(END)!=1:
            raise ValueError("ambiguous layer helper")
        a,b=text.index(START),text.index(END)
        if b<=a:
            raise ValueError("invalid layer helper")
        text=text[:a]+text[b+len(END):]
        if text.count(BG+BEFORE)!=1 or text.count(AFTER)!=1:
            raise ValueError("missing layer draw sequence")
        text=text.replace(BG+BEFORE,STATUS,1)
        a=text.index("    // FLUX theme cursor begin.\n")
        b=text.index(AFTER,a)+len(AFTER)
        text=text[:a]+FOCUS+text[b:]
    if not layers or not any(map(any,layers)):
        return text
    if any(text.count(x)!=1 for x in (ANCHOR,STATUS,FOCUS)):
        raise ValueError("unexpected standby draw anchors")
    helper=START
    for name,pixels in zip(("BG","A","B"),layers):
        part=encode_layer(pixels)
        data=bytes.fromhex(part[1:]) if part!="0" else b""
        literal=",".join(f"0x{x:02x}" for x in data)
        helper+=f"const THEME_{name}: (bool, &[u8]) = ({str(part.startswith('p')).lower()}, &[{literal}]);\n"
    helper+="""
fn draw_flux_layer<D: DrawTarget<Color = BinaryColor>>(lcd: &mut D, layer: (bool, &[u8])) {
    let (packed, data) = layer;
    if packed {
        for (i, byte) in data.iter().enumerate() {
            for j in 0..4 {
                let state = (byte >> (6 - 2*j)) & 3;
                if state == 0 { continue; }
                let pos = i*4+j;
                let color = if state == 1 { BinaryColor::On } else { BinaryColor::Off };
                lcd.draw_iter(core::iter::once(Pixel(Point::new((pos%128) as i32,(pos/128) as i32),color))).ok();
            }
        }
    } else {
        for run in data.chunks_exact(3) {
            let word = u16::from_be_bytes([run[0],run[1]]);
            let pos = word & 0x7fff;
            let color = if word & 0x8000 == 0 { BinaryColor::On } else { BinaryColor::Off };
            Rectangle::new(Point::new((pos%128) as i32,(pos/128) as i32),Size::new(run[2] as u32,1))
                .into_styled(PrimitiveStyle::with_fill(color)).draw(lcd).ok();
        }
    }
}
"""+END
    cursor="""    // FLUX theme cursor begin.
    let cursor = if app.master_index()==0 { THEME_A } else { THEME_B };
    if app.is_transmitting() || cursor.1.is_empty() {
"""+FOCUS+"""    } else {
        draw_flux_layer(lcd, cursor);
    }
"""+STATUS+AFTER
    return text.replace(ANCHOR,helper+ANCHOR,1).replace(STATUS,BG+BEFORE,1).replace(FOCUS,cursor,1)

if __name__=="__main__":
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent/"build/aura-fd6818b-port/src/ui/standby.rs"
    before=path.read_text()
    after=apply(before,theme_layers(os.environ.get("K6_THEME","flux")))
    if before!=after:
        path.write_text(after)
