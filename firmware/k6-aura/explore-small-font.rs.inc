/// Compact Explore row text (the stock 4x6 face), clipped into one controller page.
pub fn text_small_page(buf: &mut [u8; 128], y0: i32, x: i32, top: i32, t: &[u8], on: bool) {
    let s = top - y0;
    if s <= -7 || s >= 8 { return; }
    let mut x = x;
    for &c in t {
        if x >= 128 { break; }
        let mut cols = [0u8; 5];
        let w = glyph(c, true, &mut cols);
        for (i, &m) in cols.iter().enumerate() {
            let xi = x + i as i32;
            if !(0..128).contains(&xi) { continue; }
            let m = if s >= 0 { (m as u16) << s } else { (m as u16) >> -s } as u8;
            let p = &mut buf[xi as usize];
            *p = if on { *p | m } else { *p & !m };
        }
        x += w;
    }
}

/// FONT_6X10's glyph for c: 6 columns of 10 rows, bit 0 the cell's top row (the baseline is row
/// 7). Bytes outside 0x20-0x7E show '?'
fn glyph_6x10(c: u8, cols: &mut [u16; 6]) {
    let i = if (0x20..0x7F).contains(&c) { c - 0x20 } else { b'?' - 0x20 };
    // 16 glyphs a row of its bitmap, each 6 x 10
    let (gx, gy) = ((i % 16) as i32 * 6, (i / 16) as i32 * 10);
    for (x, m) in cols.iter_mut().enumerate() {
        *m = 0;
        for y in 0..10 {
            if FONT_6X10.image.pixel(Point::new(gx + x as i32, gy + y)) == Some(BinaryColor::On) {
                *m |= 1 << y;
            }
        }
    }
}

/// A module screen's title in FONT_6X10, its cell's top row at `top` (baseline less 7), lit or
/// dark; 0x80 and up (the module's own glyphs) leave their 6-pixel cell empty
pub fn title<D>(lcd: &mut D, x: i32, top: i32, t: &[u8], on: bool)
where
    D: DrawTarget<Color = BinaryColor>,
{
    let ink = if on { BinaryColor::On } else { BinaryColor::Off };
    let mut x = x;
    for &c in t {
        if x >= 128 {
            break;
        }
        if c < 0x80 {
            let mut cols = [0u16; 6];
            glyph_6x10(c, &mut cols);
            let x0 = x;
            let px = cols.into_iter().enumerate().flat_map(move |(i, m)| {
                (0..10).filter(move |&r| m >> r & 1 != 0).map(move |r| Pixel(Point::new(x0 + i as i32, top + r), ink))
            });
            lcd.draw_iter(px).ok();
        }
        x += 6;
    }
}

/// title's line straight into one controller page (pixel rows y0 .. y0 + 7 in `buf`)
pub fn title_page(buf: &mut [u8; 128], y0: i32, x: i32, top: i32, t: &[u8], on: bool) {
    let s = top - y0;
    if s <= -10 || s >= 8 {
        return;
    }
    let mut x = x;
    for &c in t {
        if x >= 128 {
            break;
        }
        if c < 0x80 {
            let mut cols = [0u16; 6];
            glyph_6x10(c, &mut cols);
            for (i, &m) in cols.iter().enumerate() {
                let xi = x + i as i32;
                if !(0..128).contains(&xi) {
                    continue;
                }
                let m = if s >= 0 { (m as u32) << s } else { (m as u32) >> -s } as u8;
                let p = &mut buf[xi as usize];
                *p = if on { *p | m } else { *p & !m };
            }
        }
        x += 6;
    }
}

/// A list's scroll bar (Jeff 2026-11-14): 2 px wide at the right edge, rows y0 .. y0 + h, when
/// the list (n rows) is longer than the screen (vis rows from row top): the lit part is the rows
/// on screen, its length and place their share of the list and where they are in it. The two
/// columns are cleared first, so a selected row's inverted bar stops short of it (text ends by
/// x = 124 in EXPLORE, the editor and the module list).
pub fn scroll_bar<D>(lcd: &mut D, y0: i32, h: u32, top: u32, vis: u32, n: u32)
where
    D: DrawTarget<Color = BinaryColor>,
{
    use embedded_graphics::primitives::Rectangle;
    if n <= vis {
        return;
    }
    let th = (h * vis / n).max(3);
    let y = y0 + ((h - th) * top.min(n - vis) / (n - vis)) as i32;
    lcd.fill_solid(&Rectangle::new(Point::new(126, y0), Size::new(2, h)), BinaryColor::Off).ok();
    lcd.fill_solid(&Rectangle::new(Point::new(126, y), Size::new(2, th)), BinaryColor::On).ok();
}
