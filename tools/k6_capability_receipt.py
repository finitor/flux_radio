"""Reproducible host-side build receipt; NOT radio attestation or a signature."""
import hashlib
import json
from pathlib import Path

FORMAT = 1


def create(image, plan, gates):
    image = Path(image)
    return {'format': FORMAT, 'target': plan['target'], 'firmware_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
            'firmware_bytes': image.stat().st_size, 'packs': plan['packs'],
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
