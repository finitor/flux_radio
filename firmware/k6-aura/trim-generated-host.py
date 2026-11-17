#!/usr/bin/env python3
"""Normalize repeated generated host guards without changing module safety checks."""
from pathlib import Path

root = Path(__file__).resolve().parent / 'build/aura-fd6818b-port/src/app/pager.rs'
s = root.read_text()
start = s.index('fn run_module(app: &mut App, syst: &mut SYST) {')
end = s.index('    let gpio = app.radio.fd6818.reg_read(syst, MOD_GPIO);', start)
head = s[start:end]
# Keep the first guard (before GPIO access). Subsequent identical guards in the
# generated module launcher are redundant and can accumulate on reruns.
guard_a = '''    #[cfg(not(feature = "blowfang-host"))]
    if room < 512 {
        rl!("K6 MOD refused: only {} B stack before dispatch", room);
        unsafe { ffi::km_reset() };
        return;
    }
'''
guard_b = '''    #[cfg(feature = "blowfang-host")]
    if module_stack_bytes() < 768 {
        rl!("K6 MOD refused: dedicated stack is only {} B", module_stack_bytes());
        unsafe { ffi::km_reset() };
        return;
    }
'''
# Do not remove a guard if its location is unknown: only remove exact duplicates
# in the run_module function before its first module execution call.
run_end = s.find('    let ret = unsafe { ffi::km_run_on_stack(', end)
if run_end < 0:
    raise SystemExit('unable to identify module run boundary; no changes')
region = s[start:run_end]
for guard in (guard_a, guard_b):
    n = region.count(guard)
    if n > 1:
        first = region.find(guard)
        region = region[:first+len(guard)] + region[first+len(guard):].replace(guard, '')
        print(f'normalized {n} copies of {guard.splitlines()[1].strip()}')
s = s[:start] + region + s[run_end:]
root.write_text(s)
