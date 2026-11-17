#[cfg(any(all(not(feature = "lean"), shared_lcd), all(feature = "blowfang-host", not(banded))))]
fn draw_explore_page(buf: &mut [u8; 128], page: u8, f: &app::pager::ModExploreFrame) {
    let y0 = page as i32 * 8;
    let rect = |buf: &mut [u8; 128], x: i32, y: i32, w: i32, h: i32, on: bool| {
        let (a, b) = ((y - y0).max(0), (y + h - y0).min(8));
        let (x0, x1) = (x.max(0), (x + w).min(128));
        if a >= b || x0 >= x1 { return; }
        let mask = ((0xFFu16 << a) & (0xFFu16 >> (8 - b))) as u8;
        for p in &mut buf[x0 as usize..x1 as usize] {
            *p = if on { *p | mask } else { *p & !mask };
        }
    };
    let small = |buf: &mut [u8; 128], x: i32, top: i32, text: &[u8], on: bool| {
        super::glyph::text_small_page(buf, y0, x, top, text, on);
    };
    let header = |buf: &mut [u8; 128], x: i32, top: i32, text: &[u8]| {
        super::glyph::title_page(buf, y0, x, top, text, false);
    };
    let mut b = TextBuf::<24>::new();

    // Original Explore's half-lidded eyes and inverted title strip.
    rect(buf, 0, 0, 128, 11, true);
    let white: [u8; 6] = [0x7f, 0x7f, 0x7f, 0x7f, 0x3e, 0x1c];
    for e in [1, 9] {
        for (r, &m) in white.iter().enumerate() {
            for c in 0..7 {
                if m & (0x40 >> c) != 0 { rect(buf, e + c, 3 + r as i32, 1, 1, false); }
            }
        }
        let pupil = if f.gaze & 1 != 0 { 4 } else { 2 };
        rect(buf, e + pupil, 3, 3, 3, true);
    }
    if f.view == 2 {
        out!(b, "TRY {}.{:03}", f.scan_hz / 1_000_000, (f.scan_hz / 1000) % 1000);
    } else {
        let band: &[u8] = match f.band { 1 => b"2M", 2 => b"70CM", 3 => b"1.25M", _ => b"ALL" };
        header(buf, 20, 0, band);
        out!(b, "{} found", f.found);
    }
    header(buf, if f.view == 2 { 20 } else { 56 }, 0, b.as_str().as_bytes());

    // Seven six-pixel rows: grade, frequency, offset, signal bar, score trace and call.
    for i in 0..f.count.min(7) as usize {
        let r = &f.rows[i];
        let y = 11 + i as i32 * 6;
        let selected = i == f.selected as usize;
        if selected { rect(buf, 0, y, 128, 6, true); }
        let ink = !selected;
        let grade = if r.flags & 1 != 0 { b'x' } else { r.grade };
        let mut row = TextBuf::<24>::new();
        out!(row, "{}{} {}.{:03} ", if selected { '>' } else { ' ' }, grade as char,
             r.hz / 1_000_000, (r.hz / 1000) % 1000);
        if r.flags & 8 != 0 || r.off_hz == 0 { out!(row, "S"); }
        else { out!(row, "{}{}.{}", if r.off_hz < 0 { '-' } else { '+' },
                    r.off_hz.unsigned_abs() / 1_000_000,
                    (r.off_hz.unsigned_abs() / 100_000) % 10); }
        small(buf, 1, y, row.as_str().as_bytes(), ink);

        let level = ((r.hi as i32 + 120) / 5).clamp(0, 21);
        rect(buf, 75, y + 1, 20, 1, ink);
        rect(buf, 75, y + 1, level.min(20), 2, ink);
        let score = (r.score as i32 * 18 / 10).clamp(0, 18);
        for x in (0..score).step_by(2) { rect(buf, 75 + x, y + 4, 1, 1, ink); }
        if r.flags & 0x10 == 0 && r.call[0] != 0 {
            let n = r.call.iter().position(|&c| c == 0).unwrap_or(r.call.len());
            small(buf, 99, y, &r.call[..n.min(7)], ink);
        } else if r.flags & 0x20 != 0 {
            small(buf, 99, y, b"SAVED", ink);
        }
    }
    if f.count == 0 {
        small(buf, 1, 24, b"LISTENING FOR STATIONS", true);
    }

    // The original's detail/status footer is kept separate from the candidate rows.
    let mut foot = TextBuf::<32>::new();
    if f.view == 2 {
        out!(foot, "{} dBm  CW ID / CTCSS", f.level);
    } else if f.count > 0 {
        let r = &f.rows[f.selected.min(f.count - 1) as usize];
        if r.tone != 0 { out!(foot, "{} dBm  tone {}", r.hi, r.tone); }
        else { out!(foot, "{} dBm score {} {}x", r.hi, r.score, r.overs); }
    } else {
        out!(foot, "SCAN {}.{:03} MHz  # band", f.scan_hz / 1_000_000, (f.scan_hz / 1000) % 1000);
    }
    small(buf, 1, 58, foot.as_str().as_bytes(), true);
}
