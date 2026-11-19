// K6T v6-v8 data-only reader. Relative offsets; no allocation or executable code.
// Shared between host tests and FD6818B; caller owns the slot and its read callback.
pub const MAX_BYTES: u16 = 8192;
const HEADER: u16 = 12;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Layer {
    pub kind: u8,
    pub offset: u16,
    pub len: u16,
}

const EMPTY: Layer = Layer { kind: 0, offset: 0, len: 0 };

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Theme {
    pub flags: u8,
    pub font: u8,
    pub inset: u8,
    pub meter: u8,
    pub splash: u8,
    pub logo_offset: u16,
    pub name_offset: u16,
    pub name_len: u8,
    pub marker: [u8; 8],
    pub meter_offset: u16,
    pub battery_offset: u16,
    pub layers: [Layer; 3],
    pub flat_offset: u16,
    pub separate_names: bool,
    pub font_offset:u16,
}

fn word(b: &[u8]) -> u16 { u16::from_le_bytes([b[0], b[1]]) }

#[inline(never)]
fn take(
    read: &mut dyn FnMut(u16, &mut [u8]) -> bool, at: &mut u16, end: u16, dst: &mut [u8],
) -> Option<()> {
    let next = at.checked_add(dst.len() as u16)?;
    if next > end || !read(*at, dst) { return None; }
    *at = next;
    Some(())
}

// Validate integrity and structure before exposing any offsets to consumers.
// The largest local buffer is 48 bytes; no borrowing of the shared module arena.
#[inline(never)]
pub fn open(read: &mut dyn FnMut(u16, &mut [u8]) -> bool) -> Option<Theme> {
    let mut header = [0u8; 12];
    if !read(0, &mut header) || (&header[..3] != b"K6T" || !matches!(header[3],6|7|8|9))
        || header[6] != 1 || header[7] != 0 { return None; }
    let end = HEADER.checked_add(word(&header[4..]))?;
    if end > MAX_BYTES || end < HEADER + 23 { return None; }
    let expected = u32::from_le_bytes([header[8],header[9],header[10],header[11]]);
    let mut buf = [0u8; 48];
    let mut crc = !0u32;
    let mut at = HEADER;
    while at < end {
        let n = usize::from((end-at).min(48));
        take(read,&mut at,end,&mut buf[..n])?;
        for &b in &buf[..n] {
            crc ^= u32::from(b);
            for _ in 0..8 { crc = (crc >> 1) ^ (0xedb88320 & 0u32.wrapping_sub(crc & 1)); }
        }
    }
    if !crc != expected { return None; }
    at = HEADER;
    let mut meta = [0u8;14];
    take(read,&mut at,end,&mut meta)?;
    if meta[0] > 3 || meta[1] > 1 || meta[2] > 3 || meta[3] > 3 ||
        meta[4] > (if header[3]>=7 {3} else {2}) || meta[5] > 1 || meta[6..].iter().any(|b| b & 1 != 0) { return None; }
    let mut t = Theme {
        flags: meta[0], font: meta[1], inset: meta[2], meter: meta[3], splash: meta[4], logo_offset: 0,
        name_offset: 0, name_len: 0,
        marker: [0;8], meter_offset: 0, battery_offset: 0, layers: [EMPTY;3], flat_offset: 0,font_offset:0,separate_names:header[3]==9,
    };
    t.marker.copy_from_slice(&meta[6..]);
    if t.meter == 3 {
        t.meter_offset = at;
        take(read,&mut at,end,&mut buf[..14])?;
        if buf[..14].iter().any(|b| b & 7 != 0)
            || !buf[..7].iter().any(|&b| b != 0)
            || !buf[7..14].iter().any(|&b| b != 0) { return None; }
    }
    if meta[5] == 1 {
        t.battery_offset = at;
        for _ in 0..5 {
            take(read,&mut at,end,&mut buf[..24])?;
            if !buf[..24].iter().any(|&b| b != 0)
                || buf[2..24].iter().step_by(3).any(|b| b & 127 != 0) { return None; }
        }
    }
    if t.splash == 3 {
        t.logo_offset = at;
        take(read,&mut at,end,&mut buf[..32])?;
        if !buf[..32].iter().any(|&b| b != 0) { return None; }
    }
    if header[3]>=8 {
        take(read,&mut at,end,&mut buf[..1])?;
        let n=buf[0];
        if n>14 || (n==0 && header[3]==8){return None;}
        t.name_offset=at;
        t.name_len=n;
        take(read,&mut at,end,&mut buf[..usize::from(n)])?;
        if buf[..usize::from(n)].iter().any(|b| !b.is_ascii_alphanumeric() && !matches!(*b,b' '|b'_'|b'-'))
            || (n!=0 && !buf[..usize::from(n)].iter().any(|b| !matches!(*b,b' '|b'_'|b'-'))) { return None; }
    }
    for i in 0..3 {
        take(read,&mut at,end,&mut buf[..3])?;
        let kind = buf[0];
        let len = word(&buf[1..]);
        if !match kind { 0 => len == 0, 1 => len > 0 && len <= 2048 && len % 3 == 0,
            2 => len == 2048, _ => false } { return None; }
        let layer = Layer { kind, offset: at, len };
        let mut ink = false;
        let mut last = 0u16;
        let stop = at.checked_add(len)?;
        if stop > end { return None; }
        while at < stop {
            let n = usize::from((stop-at).min(48));
            take(read,&mut at,stop,&mut buf[..n])?;
            if kind == 1 {
                for run in buf[..n].chunks_exact(3) {
                    let w = u16::from_be_bytes([run[0],run[1]]);
                    let pos = w & 0x7fff;
                    let count = u16::from(run[2]);
                    if pos < last || pos >= 8192 || count == 0 || count > 128 - pos % 128 { return None; }
                    last = pos + count;
                    ink |= w & 0x8000 == 0;
                }
            } else {
                for &b in &buf[..n] {
                    if b & (b >> 1) & 0x55 != 0 { return None; }
                    ink |= b & 0x55 != 0;
                }
            }
        }
        if i != 0 && ((kind != 0 && !ink) ||
            (t.flags == 0 && !t.marker.iter().any(|&b| b != 0) && !ink)) { return None; }
        t.layers[i] = layer;
    }
    if header[3]>=6 {
        take(read,&mut at,end,&mut buf[..1])?;
        if buf[0]>1{return None;}
        if buf[0]==1 {
            t.font_offset=at;
            for _ in 0..11 {take(read,&mut at,end,&mut buf[..12])?;if !buf[..12].iter().any(|&b|b!=0){return None;}}
        }
        t.flat_offset=at;
        let mut seen=[0u32;2];
        let count=if t.separate_names {34} else {32};
        for _ in 0..count {
            take(read,&mut at,end,&mut buf[..5])?;
            let (width,height)=widget_size(buf[0],buf[3])?;
            if buf[3]==2 && t.font_offset==0{return None;}
            if buf[0]>=count {return None;}
            let bank=usize::from(buf[0]>>5);let bit=1u32<<(buf[0]&31);
            if seen[bank] & bit !=0 || buf[4]>1 ||
                u16::from(buf[1])+width>128 || u16::from(buf[2])+height>64 {return None;}
            seen[bank]|=bit;
        }
    }
    if at != end { return None; }
    Some(t)
}

// Stream the already validated layer as horizontal spans. Recheck bounds in case
// SPI changes after validation. The caller must discard a partial frame on failure.
pub fn spans<R, F>(read: &mut R, layer: Layer, mut draw: F) -> bool
where R: FnMut(u16, &mut [u8]) -> bool, F: FnMut(u16, u8, bool) {
    let mut at = layer.offset;
    let Some(end) = at.checked_add(layer.len) else { return false; };
    if end > MAX_BYTES || !match layer.kind {
        0 => layer.len == 0, 1 => layer.len > 0 && layer.len <= 2048 && layer.len % 3 == 0,
        2 => layer.len == 2048, _ => false,
    } { return false; }
    let mut buf = [0u8;48];
    let mut last = 0;
    let mut pos = 0u16;
    let mut run=0u8;
    let mut color=0u8;
    let mut start=0u16;
    while at < end {
        let n = usize::from((end-at).min(48));
        if take(read,&mut at,end,&mut buf[..n]).is_none() { return false; }
        if layer.kind == 1 {
            for r in buf[..n].chunks_exact(3) {
                let w = u16::from_be_bytes([r[0],r[1]]);
                let p = w & 0x7fff;
                if p < last || p >= 8192 || r[2] == 0 ||
                    u16::from(r[2]) > 128 - p % 128 { return false; }
                last = p + u16::from(r[2]);
                draw(p,r[2],w & 0x8000 == 0);
            }
        } else {
            for &b in &buf[..n] {
                for shift in [6,4,2,0] {
                    let next=(b>>shift)&3;
                    if next==3{return false;}
                    if run!=0 && (next!=color || pos%128==0){
                        draw(start,run,color==1);run=0;
                    }
                    if next!=0 {
                        if run==0 {start=pos;color=next;}
                        run+=1;
                    }
                    pos += 1;
                }
            }
        }
    }
    if run!=0 {draw(start,run,color==1);}
    true
}


// This is geometry validation, not layout: the Catalog supplies final positions.
#[inline(never)]
pub fn widget_size(source:u8,font:u8)->Option<(u16,u16)> {
    if font>0 {return if matches!(source,8|13){match font{1=>Some((54,10)),2=>Some((72,12)),_=>None}}else{None};}
    Some(match source {
        0|7|12=>(30,8),1|6|11|29|30|31=>(10,8),2=>(17,8),3=>(60,8),4=>(65,8),
        5|10=>(7,8),8|13=>(82,17),9|14=>(12,6),15|22|18|25=>(16,6),16|23=>(24,6),17|24|19|26=>(4,6),20|27=>(20,6),21|28=>(32,6),32|33=>(60,8),_=>return None,
    })
}
