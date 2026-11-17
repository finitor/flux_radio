"""Synthetic-fixture tests for firmware/k6-aura/apply-theme-meter.py.

No network, radio, build tree, or main checkout access. The fixture mimics
the standby RX S-meter anchor plus the neighbors that must stay untouched
(dBm + S-unit text, MIC bar).
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "firmware/k6-aura/apply-theme-meter.py"
APPLY = ROOT / "firmware/k6-aura/apply-theme-meter.py"


import importlib.util
spec = importlib.util.spec_from_file_location("theme_meter", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
B = {name: getattr(mod, name) for name in ("ORIG_BLOCK", "FLAT_BLOCK", "BAR_BLOCK")}


DBM_LINE = '    Text::new(dbm_text, Point::new(2, base_y), small).draw(lcd).ok();\n'
SUNIT_LINE = '    Text::new(s_unit, Point::new(40, base_y), small).draw(lcd).ok();\n'
MIC_LINE = '    // MIC bar (TX audio, untouched by RX meter themes).\n    mic_bar(lcd, mic_level);\n'


def make_fixture(path: Path) -> str:
    text = ("fn draw_standby_rx_meter<D>(lcd: &mut D, lit: u8, base_y: i32)\n"
            "where D: DrawTarget<Color = BinaryColor>,\n{\n"
            + DBM_LINE + SUNIT_LINE + B["ORIG_BLOCK"] + MIC_LINE + "}\n")
    path.write_text(text)
    return text


def run_theme(theme: str, target: Path):
    env = dict(__import__("os").environ, K6_THEME=theme)
    return subprocess.run([sys.executable, str(SCRIPT), str(target)],
                          capture_output=True, text=True, env=env)


BASE = "custom-11-0000000000000000"
T0, T1, T2 = f"{BASE}-0000", f"{BASE}-0010", f"{BASE}-0020"


def test_meter0_keeps_original_staircase(tmp_path):
    f = tmp_path / "standby.rs"
    before = make_fixture(f)
    proc = run_theme(T0, f)
    assert proc.returncode == 0, proc.stderr
    after = f.read_text()
    assert after == before  # idempotent, byte-exact
    assert B["ORIG_BLOCK"] in after
    assert DBM_LINE in after and SUNIT_LINE in after and MIC_LINE in after


def test_meter1_flat_13_segments(tmp_path):
    f = tmp_path / "standby.rs"
    make_fixture(f)
    assert run_theme(T1, f).returncode == 0
    after = f.read_text()
    assert B["FLAT_BLOCK"] in after and B["ORIG_BLOCK"] not in after
    assert "bar_x + i as i32 * BAR_SEG_PITCH" in after
    assert "level.min(S_METER_SEGS)" in after
    assert DBM_LINE in after and SUNIT_LINE in after and MIC_LINE in after
    # idempotent second run
    assert run_theme(T1, f).returncode == 0
    assert f.read_text() == after


def test_meter2_continuous_bar_preserves_over_s9(tmp_path):
    f = tmp_path / "standby.rs"
    make_fixture(f)
    assert run_theme(T2, f).returncode == 0
    after = f.read_text()
    assert B["BAR_BLOCK"] in after and B["ORIG_BLOCK"] not in after
    assert "Point::new(bar_x, base_y - BAR_MAX_H + 1)" in after
    assert "PrimitiveStyle::with_stroke" in after
    assert DBM_LINE in after and SUNIT_LINE in after and MIC_LINE in after


def test_reset_to_default_restores_original(tmp_path):
    f = tmp_path / "standby.rs"
    original = make_fixture(f)
    assert run_theme(T1, f).returncode == 0
    assert f.read_text() != original
    assert run_theme("flux", f).returncode == 0
    assert f.read_text() == original


def test_fail_closed_without_anchor(tmp_path):
    f = tmp_path / "standby.rs"
    text = "fn draw_standby_rx_meter<D>(lcd: &mut D) {}\n" + DBM_LINE + MIC_LINE
    f.write_text(text)
    proc = run_theme(T1, f)
    assert proc.returncode != 0
    assert f.read_text() == text  # untouched


def test_invalid_theme_rejected(tmp_path):
    f = tmp_path / "standby.rs"
    make_fixture(f)
    proc = run_theme("custom-11-0000000000000000-0030", f)
    assert proc.returncode != 0
