from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scanner_host_is_selectively_linked():
    script = (ROOT / 'tools/k6_build.sh').read_text()
    assert 'K6_SCAN_SERVICE:-1' in script
    assert '$OUT/scan_host_unavailable.o' in script
    assert '$OUT/xscan_modhost.o' in script
    assert 'K6_SCAN_SERVICE="${K6_SCAN_SERVICE:-1}"' in (ROOT / 'firmware/k6-aura/build-fd6818b.sh').read_text()


def test_unavailable_scanner_fails_closed():
    stub = (ROOT / 'c/k6/scan_host_unavailable.c').read_text()
    assert 'int kmx_xs_init(' in stub
    assert 'return -1;' in stub
    assert 'int kmx_xs_step(' in stub
