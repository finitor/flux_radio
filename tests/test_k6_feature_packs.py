import json
from pathlib import Path
import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from k6_feature_packs import resolve

SPEC = json.loads((Path(__file__).resolve().parents[1] / 'config/k6-feature-packs.json').read_text())

def test_scan_aprs_deduplicates_base():
    plan = resolve(SPEC, ['scan', 'aprs'])
    assert plan['packs'] == ['base', 'scan', 'aprs']
    assert plan['modules'] == ['vfo', 'cardlink', 'surf', 'explore_scan', 'aprsdfsk']
    assert len(plan['cargo_features']) == len(set(plan['cargo_features']))

def test_unknown_and_unavailable_rejected():
    with pytest.raises(ValueError, match='unknown'):
        resolve(SPEC, ['missing'])
    with pytest.raises(ValueError, match='planned'):
        resolve(SPEC, ['sotto'])

def test_cycles_rejected():
    spec = json.loads(json.dumps(SPEC))
    spec['packs']['base']['requires'] = ['scan']
    with pytest.raises(ValueError, match='cyclic'):
        resolve(spec, ['scan'])
