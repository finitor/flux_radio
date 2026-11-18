// Read-only bench renderer. The native UI draws live data over the SPI art.
// Cache validated metadata; production install/selection must invalidate it.
use super::{theme_reader, standby};
use crate::app::App;
use embedded_graphics::{pixelcolor::BinaryColor, prelude::*, image::{Image,ImageRaw}, Pixel};
const BENCH_SLOT: u32 = TEST_SLOT;
fn slot(selection:u8)->u32 {
    match selection{0=>BENCH_SLOT,2..=33=>u32::from(selection-2),_=>255}
}
static mut CACHE_SLOT:u32=255;
static mut RECORDS:[u8;160]=[0;160];
static mut FONT:[u8;132]=[0;132];
static mut CACHED: Option<theme_reader::Theme> = None;
static mut CHECKED: bool = false;

fn read(app: &mut App, slot:u32, off: u16, dst: &mut [u8]) -> bool {
    app.designer_read(0x110000 + slot * 0x4000 + u32::from(off), dst)
}

fn reset() { unsafe { CACHED = None; CHECKED = false; } }

#[inline(never)]
pub fn draw<D: DrawTarget<Color = BinaryColor>>(lcd: &mut D, app: &mut App) -> bool {
    let slot=slot(app.settings().theme_selection);
    if slot >= 32 || app.is_transmitting() || app.tx_prohibited() ||
        app.no_channels_notice() || app.ani_caller_id().is_some() { return false; }
    let theme = unsafe {
        if !CHECKED || CACHE_SLOT!=slot {
            CACHE_SLOT=slot;
            CACHED = theme_reader::open(&mut |off,dst| read(app,slot,off,dst));
            if let Some(t)=CACHED {
                // Load the immutable descriptor table and optional font once.
                for (i,chunk) in (&mut *core::ptr::addr_of_mut!(RECORDS)).chunks_mut(40).enumerate(){
                    if !read(app,slot,t.flat_offset+i as u16*40,chunk){CACHED=None;break;}
                }
                if t.font_offset!=0 && CACHED.is_some(){
                    for (i,chunk) in (&mut *core::ptr::addr_of_mut!(FONT)).chunks_mut(44).enumerate(){
                        if !read(app,slot,t.font_offset+i as u16*44,chunk){CACHED=None;break;}
                    }
                }
            }
            CHECKED = true;
        }
        CACHED
    };
    let Some(theme) = theme else { return false; };
    if app.freq_input_len()!=0 || app.channel_input_len()!=0 || app.dtmf_dial_active()

        || (0..2).any(|i| app.side_is_channel_mode(i) && !app.side_name_str(i).is_empty()) {
        return false;
    }
    let active = app.master_index() + 1;
    let bars = app.battery_bars().min(4);
    let mut glyph = [0u8;24];
    if theme.battery_offset != 0 &&
        !read(app,slot,theme.battery_offset + u16::from(bars)*24,&mut glyph) {
        reset(); return false;
    }
    let mut meter = [0u8;14];
    if theme.meter_offset != 0 && !read(app,slot,theme.meter_offset,&mut meter) {
        reset(); return false;
    }
    lcd.draw_iter((0..8192u16).map(|pos|Pixel(Point::new(i32::from(pos%128),i32::from(pos/128)),BinaryColor::Off))).ok();
    // Compose background and active cursor before drawing native text.
    // Dynamic status and the meter are opaque reserved strips.
    for layer in [theme.layers[0], theme.layers[active]] {
        if !theme_reader::spans(&mut |off,dst| read(app,slot,off,dst), layer, |pos,n,ink| {
            let y = i32::from(pos / 128);
            let color = if ink { BinaryColor::On } else { BinaryColor::Off };
            let x=i32::from(pos%128);
            lcd.draw_iter((0..i32::from(n)).map(|dx|Pixel(Point::new(x+dx,y),color))).ok();
        }) { reset(); return false; }
    }
    let modes=[standby::mode_fields(app,0),standby::mode_fields(app,1)];
    let records=unsafe{&*core::ptr::addr_of!(RECORDS)};
    let font=unsafe{&*core::ptr::addr_of!(FONT)};
    for chunk in records.chunks_exact(5) {
        let w:&[u8;5]=chunk.try_into().unwrap();
        standby::draw_flat_widget(lcd,app,w,&theme,&glyph,&meter,font,&modes);
    }
    true
}

// Only the logo in the built-in splash is replaced; user boot bitmap wins.
pub(crate) fn boot_logo<D: DrawTarget<Color=BinaryColor>>(lcd: &mut D, storage: &mut crate::device::storage::Storage,selection:u8) {
    let slot=slot(selection);
    if slot >= 32 {return;}
    let base = 0x110000 + slot*0x4000;
    let theme=theme_reader::open(&mut |off,dst| storage.norflash.read_bytes_checked(base+u32::from(off),dst));
    unsafe { CACHED=theme; CHECKED=false; CACHE_SLOT=slot; }
    let Some(t)=theme else {return;};
    let rows: [u16;16]=match t.splash {
        1=>[0,0x0180,0x03c0,0x07e0,0x0ff0,0x1ff8,0x3ffc,0x7ffe,0x7ffe,0x3ffc,0x1ff8,0x0ff0,0x07e0,0x03c0,0x0180,0],
        2=>[0x0180,0x05a0,0x0990,0x1188,0x2184,0x0180,0x03c0,0x03c0,0x07e0,0x07e0,0x0ff0,0x0ff0,0x1ff8,0x3ffc,0x7ffe,0],
        _=>return,
    };
    let mut pixels=[0u8;32];
    for (i,row) in rows.iter().enumerate() {
        pixels[i*2..i*2+2].copy_from_slice(&row.to_be_bytes());
    }
    let image=ImageRaw::<BinaryColor>::new(&pixels,16);
    Image::new(&image,Point::new(20,8)).draw(lcd).ok();
}
