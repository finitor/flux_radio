import pytest
from sim.k6emu.scheduled_jobs import ScheduledJob

def poll(job, now, idle=True, arena=True):
    return job.poll(now, rf_idle=idle, arena_available=arena)

def test_disabled_and_periodic():
    j = ScheduledJob(100, 20)
    assert poll(j, 0) is None
    j.enable(0)
    assert poll(j, 99) is None
    assert poll(j, 100) == "dispatch"
    assert poll(j, 100) is None
    assert poll(j, 200) == "dispatch"

def test_defer_for_ptt_or_arena():
    j = ScheduledJob(100, 20)
    j.enable(0)
    assert poll(j, 100, idle=False) is None
    assert poll(j, 110, arena=False) is None
    assert poll(j, 120) == "dispatch"
    assert j.deadline == 200

def test_skip_without_catchup_and_cancel():
    j = ScheduledJob(100, 20)
    j.enable(0)
    assert poll(j, 350) == "skip"
    assert j.deadline == 400
    assert poll(j, 350) is None
    j.cancel()
    assert poll(j, 400) is None

def test_wraparound():
    j = ScheduledJob(100, 20)
    j.enable(0xffffffc0)
    assert poll(j, 0xffffffff) is None
    assert poll(j, 35) is None
    assert poll(j, 36) == "dispatch"
    assert j.deadline == 136

@pytest.mark.parametrize("interval,grace", [(0,0),(100,100),(2**31,0),(100,-1)])
def test_bad_parameters(interval, grace):
    with pytest.raises(ValueError):
        ScheduledJob(interval, grace)
