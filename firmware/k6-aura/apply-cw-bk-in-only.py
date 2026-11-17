#!/usr/bin/env python3
"""Make Aura CW/CWF transmit gating depend on BK-IN only."""
from pathlib import Path

tx = Path(__file__).parent / "build/aura-fd6818b-port/src/app/tx.rs"
text = tx.read_text()
old = '''            let want_tx = app.settings.bk_in != 0
                && !app.settings.tx_forbid
                && !(app.settings.busy_lock && app.radio.rssi_open());
'''
new = '''            let want_tx = app.settings.bk_in != 0;
'''
if old in text:
    tx.write_text(text.replace(old, new, 1))
elif new not in text:
    raise SystemExit("tx.rs: cannot locate CW/CWF BK-IN transmit gate")

skip = '''            let want_tx = app.settings.bk_in != 0;
            if want_tx {
'''
skip_diag = '''            let want_tx = app.settings.bk_in != 0;
            if !want_tx {
                rl!("K6 CW TX skipped BK-IN=OFF");
            }
            if want_tx {
'''
if skip in text:
    text = text.replace(skip, skip_diag, 1)
elif skip_diag not in text:
    raise SystemExit("tx.rs: cannot locate CW/CWF TX decision for diagnostics")

entered = '''                app.cw_tx_active = app.radio.enter_tx_keyed(syst);
                if app.cw_tx_active {
'''
entered_diag = '''                app.cw_tx_active = app.radio.enter_tx_keyed(syst);
                if !app.cw_tx_active {
                    rl!("K6 CW TX refused freq={} Hz", tx_freq_hz);
                }
                if app.cw_tx_active {
'''
if entered in text:
    text = text.replace(entered, entered_diag, 1)
elif entered_diag not in text:
    raise SystemExit("tx.rs: cannot locate CW/CWF TX result for diagnostics")

sync = '''                app.radio.set_power(power);
                reload_pa_calibration(app, tx_freq_hz, power);
'''
sync_fixed = '''                app.radio.set_power(power);
                app.radio.set_modulation(s.cfg.modulation);
                reload_pa_calibration(app, tx_freq_hz, power);
'''
if sync in text:
    text = text.replace(sync, sync_fixed, 1)
elif sync_fixed not in text:
    raise SystemExit("tx.rs: cannot locate CW/CWF radio configuration")

tx.write_text(text)

radio = Path(__file__).parent / "build/aura-fd6818b-port/src/device/radio.rs"
text = radio.read_text()
old = '''        if !self.tx_allowed.allows(self.cfg.tx_freq_hz)
            || !matches!(self.cfg.modulation, Modulation::Cw | Modulation::Cwf)
        {
            return false;
        }
'''.replace("+", "")
new = '''        if !self.tx_allowed.allows(self.cfg.tx_freq_hz) {
            rl!("K6 CW TX denied band-lock freq={} Hz", self.cfg.tx_freq_hz);
            return false;
        }
        if !matches!(self.cfg.modulation, Modulation::Cw | Modulation::Cwf) {
            rl!("K6 CW TX denied modulation");
            return false;
        }
'''.replace("+", "")
if old in text:
    radio.write_text(text.replace(old, new, 1))
elif new not in text:
    raise SystemExit("radio.rs: cannot locate CW/CWF TX entry guard")
print("Applied CW/CWF BK-IN-only transmit gate")
