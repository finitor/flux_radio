"""Hardware-comparable IF packing timings from the actual module on Cortex-M0."""
import sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))


def test_ifbench_m0_timing_and_checksums():
    pytest.importorskip('unicorn')
    from modem import k6mod
    import k6_live_emu
    code, entry = k6mod.build(str(ROOT / 'c/k6/mod/ifbench.c'))
    assert len(code) < 1024
    emu = k6_live_emu.Emu(code, entry, np.zeros(1, np.uint8), 0, 85800,
                         cpi=1.5, max_s=2, scratch=4096)
    result = emu.run()
    assert result is not None
    values = {}
    for line in emu.said:
        parts = line.split()
        assert parts[0] == 'ifbench'
        if parts[1] == 'v1':
            continue
        values[parts[1]] = (int(parts[2]), int(parts[3]))
    assert values['arithmetic'][1] == 28672
    assert values['read'][1] == 32768
    assert values['pack'][1] == 32768
    assert values['checksum'][1] == 189440
    assert 0 < values['pack'][0] < 1000
