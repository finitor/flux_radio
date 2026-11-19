from sim.k6emu.vfo_modes import Runtime, Mode

APRS = Mode(40, 'APRS', 4096, 512)
PROBE = Mode(41, 'PROBE', 256, 32)

def test_lifecycle_and_dual_watch():
    r = Runtime()
    r.discover([APRS, PROBE])
    r.select(0, 40)
    r.select(1, 41)
    r.tick([1,0])
    r.watch(1)
    r.tick([0])
    r.watch(0)
    assert r.events == [('activate',0,40),('rx',0,(1,0)),
        ('deactivate',0,40),('activate',1,41),('rx',1,(0,)),
        ('deactivate',1,41),('activate',0,40)]
    assert r.frequency == [146520000,440850000]

def test_arena_handoff_and_retune():
    r = Runtime()
    r.discover([APRS])
    r.select(0,40)
    r.retune(0,144390000)
    r.arena_busy(True)
    r.tick([1])
    assert r.resident is None
    assert not r.ptt_allowed(0)
    r.arena_busy(False)
    assert r.events == [('activate',0,40),('reset_rx',0,40),
                        ('deactivate',0,40),('activate',0,40)]
    assert r.frequency[0] == 144390000

def test_discovery_duplicate_removal_and_budget():
    r = Runtime()
    r.discover([APRS, PROBE, Mode(42,'BIG',11776,1),Mode(43,'BAD',1,1,2)])
    assert set(r.providers) == {40,41}
    r.select(0,40)
    assert not r.ptt_allowed(0)
    r.discover([APRS, APRS, PROBE])
    assert r.resident is None and r.selected == [None,None]
    assert ('missing',0,40) in r.events
    assert r.ptt_allowed(0)

def test_mode_receives_existing_aprs_fixture_only_on_watched_side():
    from sim.k6emu.aprs_signal import ui_frame, afsk
    frame = ui_frame('N0CALL','APRS',b'>mode test')
    audio = afsk(frame)
    r = Runtime()
    r.discover([APRS])
    r.select(0,40)
    r.tick(audio[:64])
    r.watch(1)
    r.tick(audio[64:128])
    assert [e for e in r.events if e[0]=='rx'] == [('rx',0,tuple(audio[:64]))]
