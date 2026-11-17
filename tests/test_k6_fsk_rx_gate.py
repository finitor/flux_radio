from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_fsk_rx_service_gated_by_pack():
    build = (ROOT / 'tools/k6_pack_build.py').read_text()
    assert "env['K6_FSK_RX_SERVICE'] = '1' if 'aprs' in plan['packs'] else '0'" in build
    script = (ROOT / 'firmware/k6-aura/build-fd6818b.sh').read_text()
    assert '--cfg k6_no_fsk_rx' in script
    assert '-C link-arg=-Tlink.x' in script
    patch = (ROOT / 'firmware/k6-aura/apply-pack-service-gates.py').read_text()
    assert 'fn mod_fsk_rx_start() -> i32 { -1 }' in patch
    assert 'fn mod_fsk_rx_read(_words: *mut u16) -> i32 { -1 }' in patch
