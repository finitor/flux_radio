#!/usr/bin/env python3
"""Gate the Sotto voice pager poll path behind K6_SOTTO_SERVICE without changing ABI.

Base (K6_SOTTO_SERVICE=0, rustc --cfg k6_no_sotto from build-fd6818b.sh) keeps the
early return after the module queue, so the voice receive/playback body below it
is unreachable and the linker never pulls sp_packet, sp_play_pwm, sotto_dec_create
or the fixed-point decoder from libsotto_k6.a. Sotto builds (cfg absent) run the
queue then fall through into the real pager path, linking the genuine decoder.
"""
import os
from pathlib import Path

p = Path(__file__).parent / 'build/aura-fd6818b-port/src/app/pager.rs'
s = p.read_text()
app = p.parent / 'mod.rs'
app_s = app.read_text()
mode = os.environ.get('K6_SOTTO_SERVICE', '0')
if mode not in ('0', '1'):
    raise SystemExit('K6_SOTTO_SERVICE must be 0 or 1')

old_status = '''fn refresh_status(app: &mut App) {
    unsafe { ffi::sp_status(&mut app.pager.status) };
}'''
# In Base the decoder is never linked, so the status block stays at its zero
# initial state: every live reader of app.pager.status sits in the voice-only
# path (poll_stream, receive_packet, play, stream_*, report_*), which Base
# never reaches. Skip the FFI poll there so sp_status links only into Sotto.
new_status = '''fn refresh_status(app: &mut App) {
    #[cfg(not(k6_no_sotto))]
    unsafe { ffi::sp_status(&mut app.pager.status) };
}'''

old = '''pub(super) fn poll(app: &mut App, syst: &mut SYST) {
    #[cfg(feature = "fd6818b")]
    {
        #[cfg(feature = "spilib")]
        poll_library_queue(app, syst);
        return;
    }'''
# Superseded milestone-2 draft: referenced cfg k6_sotto, which build-fd6818b.sh
# never sets (it passes --cfg k6_no_sotto for Base and nothing for Sotto), so the
# Sotto branch was dead and both images behaved like Base. Migrate it in place.
broken = '''pub(super) fn poll(app: &mut App, syst: &mut SYST) {
    #[cfg(all(feature = "fd6818b", not(k6_sotto)))]
    {
        #[cfg(feature = "spilib")]
        poll_library_queue(app, syst);
        return;
    }
    #[cfg(all(feature = "fd6818b", k6_sotto))]
    {
        #[cfg(feature = "spilib")]
        poll_library_queue(app, syst);
    }'''
new = '''pub(super) fn poll(app: &mut App, syst: &mut SYST) {
    #[cfg(all(feature = "fd6818b", k6_no_sotto))]
    {
        #[cfg(feature = "spilib")]
        poll_library_queue(app, syst);
        return;
    }
    #[cfg(all(feature = "fd6818b", not(k6_no_sotto)))]
    {
        #[cfg(feature = "spilib")]
        poll_library_queue(app, syst);
    }'''
if new_status in s:
    pass
elif old_status in s:
    assert s.count(old_status) == 1, 'pager status poll anchor is not unique'
    s = s.replace(old_status, new_status, 1)
    p.write_text(s)
else:
    raise SystemExit('pager status poll anchor changed; refusing to patch')
if new in s:
    pass
elif broken in s:
    assert s.count(broken) == 1, 'superseded sotto gate is not unique'
    s = s.replace(broken, new, 1)
    p.write_text(s)
elif old in s:
    assert s.count(old) == 1, 'voice pager poll anchor is not unique'
    s = s.replace(old, new, 1)
    p.write_text(s)
else:
    raise SystemExit('voice pager poll anchor changed; refusing to patch')

# In the Flux host build, app::poll_pager currently bypasses pager::poll and
# calls only the module queue. Route Sotto builds through pager::poll so they
# retain the module queue and then run the legacy voice pager. Base continues
# to call only the queue, which leaves all voice-only sections unreachable.
old_dispatch = '''    pub fn poll_pager(&mut self, syst: &mut SYST) {
        #[cfg(feature = "blowfang-host")]
        pager::poll_library_queue(self, syst);
        #[cfg(not(feature = "blowfang-host"))]
        pager::poll(self, syst);
    }'''
new_dispatch = '''    pub fn poll_pager(&mut self, syst: &mut SYST) {
        #[cfg(all(feature = "blowfang-host", k6_no_sotto))]
        pager::poll_library_queue(self, syst);
        #[cfg(any(not(feature = "blowfang-host"), not(k6_no_sotto)))]
        pager::poll(self, syst);
    }'''
if new_dispatch not in app_s:
    assert app_s.count(old_dispatch) == 1, 'pager main-loop dispatch anchor is not unique'
    app.write_text(app_s.replace(old_dispatch, new_dispatch, 1))
print('Applied Sotto voice pager service gate; cfg selected by K6_SOTTO_SERVICE=' + mode)
