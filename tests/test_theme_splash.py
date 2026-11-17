"""Focused tests for firmware/k6-aura/apply-theme-splash.py.

Covers: splash selection via theme_layout, factory-exact splash 0,
16x16 dimensions, distinct alternates, LOGO-only patching, repeated
builds, and restore-default. No generated build dirs, radio, or network.
"""
import importlib.util
import re
from pathlib import Path

import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from k6_feature_packs import theme_layout

SPLASH_MOD_PATH = REPO / "firmware/k6-aura/apply-theme-splash.py"
BRANDING_PATH = REPO / "firmware/k6-aura/apply-flux-branding.py"


def load_splash_module():
    spec = importlib.util.spec_from_file_location("apply_theme_splash", SPLASH_MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = load_splash_module()


def factory_rows_from_branding():
    text = BRANDING_PATH.read_text()
    m = re.search(
        r"const LOGO: \[u16; 16\] = \[(?P<body>[^\]]*?)\];",
        text,
        re.DOTALL,
    )
    assert m is not None, "branding script must contain the factory LOGO array"
    return [int(tok, 2) for tok in re.findall(r"0b([01]{16})", m.group("body"))]


def fixture_boot(factory_rows):
    logo = "\n".join(f"        0b{row:016b}," for row in factory_rows)
    return f"""/// Flux startup splash with a small one-bit logo and optional user boot text.
pub fn draw_flux_splash<D>(lcd: &mut D, settings: &Settings)
where D: DrawTarget<Color = BinaryColor>, {{
    use embedded_graphics::primitives::PrimitiveStyle;
    clear(lcd);
    // 16x16 monochrome Flux glyph (row-major bitmap), rendered directly to pixels.
    const LOGO: [u16; 16] = [
{logo}
    ];
    let logo_pixels = LOGO.iter().enumerate().flat_map(|(y, row)| {{
        (0..16usize).filter_map(move |x| {{
            if row & (1 << (15 - x)) != 0 {{
                Some(Pixel(Point::new(20 + x as i32, 8 + y as i32), BinaryColor::On))
            }} else {{ None }}
        }})
    }});
    lcd.draw_iter(logo_pixels).ok();
    Rectangle::new(Point::new(44, 5), Size::new(70, 23))
        .into_styled(PrimitiveStyle::with_stroke(BinaryColor::On, 1)).draw(lcd).ok();
    draw_centered_big(lcd, "FLUX", 22);
    draw_centered_small(lcd, "AG7SU  /  K6", 42);
    let a = ascii_line(&settings.boot_text_line1);
    let b = ascii_line(&settings.boot_text_line2);
    if !a.is_empty() && !b.is_empty() {{
        draw_centered_small(lcd, a, 52);
        draw_centered_small(lcd, b, 61);
    }} else if !a.is_empty() {{
        draw_centered_small(lcd, a, 57);
        draw_centered_small(lcd, FIRMWARE_VERSION, 63);
    }} else if !b.is_empty() {{
        draw_centered_small(lcd, b, 57);
        draw_centered_small(lcd, FIRMWARE_VERSION, 63);
    }} else {{
        draw_centered_small(lcd, FIRMWARE_VERSION, 58);
    }}
}}

pub fn draw_voltage<D>(lcd: &mut D, volts: f32) {{ let _ = (lcd, volts); }}
pub fn draw_message<D>(lcd: &mut D, settings: &Settings) {{ let _ = (lcd, settings); }}
"""


def extract_logo_rows(text):
    m = re.search(
        r"const LOGO: \[u16; 16\] = \[(?P<body>[^\]]*?)\];",
        text,
        re.DOTALL,
    )
    assert m is not None
    return [int(tok, 2) for tok in re.findall(r"0b([01]{16})", m.group("body"))]


def test_splash_defaults_to_factory():
    assert theme_layout("flux") == (0, 0, 0, 0)
    assert mod.splash_for_theme("flux") == 0


def test_splash_indices_for_custom_themes():
    base = "custom-11-0000000000000000"
    assert mod.splash_for_theme(base + "-0000") == 0
    assert mod.splash_for_theme(base + "-0001") == 1
    assert mod.splash_for_theme(base + "-0002") == 2


def test_splash_zero_matches_factory_branding():
    assert factory_rows_from_branding() == mod.FACTORY_LOGO
    assert len(mod.FACTORY_LOGO) == 16
    assert all(0 <= row <= 0xFFFF for row in mod.FACTORY_LOGO)


def test_alternate_logos_are_16x16_and_distinct():
    for rows in (mod.DIAMOND_LOGO, mod.ANTENNA_LOGO):
        assert len(rows) == 16
        assert all(0 <= row <= 0xFFFF for row in rows)
        assert any(row != 0 for row in rows)
    assert mod.DIAMOND_LOGO != mod.FACTORY_LOGO
    assert mod.ANTENNA_LOGO != mod.FACTORY_LOGO
    assert mod.DIAMOND_LOGO != mod.ANTENNA_LOGO


def test_apply_patches_only_logo_and_preserves_boot():
    before = fixture_boot(mod.FACTORY_LOGO)
    after = mod.apply_splash(before, 1)
    assert extract_logo_rows(after) == mod.DIAMOND_LOGO
    # Boot text, geometry, and other boot modes are untouched.
    for needle in (
        'draw_centered_big(lcd, "FLUX", 22)',
        'draw_centered_small(lcd, "AG7SU  /  K6", 42)',
        "FIRMWARE_VERSION",
        "boot_text_line1",
        "boot_text_line2",
        "Point::new(20 + x as i32, 8 + y as i32)",
        "Size::new(70, 23)",
        "pub fn draw_voltage",
        "pub fn draw_message",
    ):
        assert needle in after
    assert after.count("const LOGO: [u16; 16]") == 1
    # Only the LOGO block differs.
    strip = lambda s: re.sub(
        r"const LOGO: \[u16; 16\] = \[[^\]]*?\];", "LOGO", s, flags=re.DOTALL
    )
    assert strip(before) == strip(after)


def test_repeated_builds_are_idempotent():
    once = mod.apply_splash(fixture_boot(mod.FACTORY_LOGO), 2)
    twice = mod.apply_splash(once, 2)
    assert once == twice
    assert extract_logo_rows(twice) == mod.ANTENNA_LOGO


def test_restore_default_is_exact():
    original = fixture_boot(mod.FACTORY_LOGO)
    altered = mod.apply_splash(original, 1)
    assert altered != original
    restored = mod.apply_splash(altered, 0)
    assert restored == original
    assert extract_logo_rows(restored) == factory_rows_from_branding()
