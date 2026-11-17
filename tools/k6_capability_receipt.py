"""Reproducible host-side build receipt; NOT radio attestation or a signature."""
import hashlib
import json
from pathlib import Path
from k6_build_identity import image_build_id

FORMAT = 1


def create(image, plan, gates):
    image = Path(image)
    data = image.read_bytes()
    try:
        build_id = image_build_id(data)
    except ValueError:
        build_id = None
    return {'format': FORMAT, 'target': plan['target'], 'firmware_sha256': hashlib.sha256(data).hexdigest(), 'build_id': build_id,
            'firmware_bytes': image.stat().st_size, 'packs': plan['packs'],
            **({'theme': plan['theme']} if plan.get('theme', 'flux') != 'flux' else {}),
            'capabilities': plan['capabilities'], 'cargo_features': plan['cargo_features'],
            'service_gates': dict(sorted(gates.items())), 'source': 'host-build-receipt',
            'radio_attested': False}


def verify(receipt, image, plan, gates):
    if not isinstance(receipt, dict) or receipt != create(image, plan, gates):
        raise ValueError('firmware build receipt does not match image and selected capability plan')
    return True


def write(path, image, plan, gates):
    receipt = create(image, plan, gates)
    Path(path).write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt
