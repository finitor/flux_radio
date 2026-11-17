import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_pack_matrix import profiles, report

SPEC = json.loads((Path(__file__).resolve().parents[1] / 'config/k6-feature-packs.json').read_text())


def test_matrix_enumerates_combinations():
    names = [name for name, _ in profiles(SPEC, ['scan', 'aprs'])]
    assert names == [('base',), ('base', 'scan'), ('base', 'aprs'), ('base', 'scan', 'aprs')]


def test_required_combo_must_fit():
    rows = [(('base',), 90000), (('base', 'scan'), 110000),
            (('base', 'aprs'), 111000), (('base', 'scan', 'aprs'), 122881)]
    r = report(rows)
    assert not r['all_fit'] and not r['required_combo_fits']
    rows[-1] = (('base', 'scan', 'aprs'), 122880)
    assert report(rows)['required_combo_fits']
    assert not report(rows[:-1])['required_combo_tested']
