# Experimental resident SPI loader

The resident loader reuses `k6_lib.c`'s SPI image reader and `km_tag_check`.
Keyed builds authenticate the existing SipHash envelope. Cable-only builds
use the existing CRC32/complement integrity envelope; CRC is not authentication.
This is an experimental RX-only callback format, not a published module ABI
or advertised firmware capability.

Header flags are `LIB | CARDS | RESIDENT` (`0x25`). CARDS deliberately makes
older ordinary module loaders reject execution. Updated ordinary, action and
page loaders reject resident envelopes. `km_run` also rejects RESIDENT even
if a caller explicitly arms it. The header entry is zero and is never invoked.

The code begins with this 20-byte, little-endian descriptor:

| Offset | Field |
| --- | --- |
| 0 | `K6VM` |
| 4 | Descriptor version, 1 |
| 5 | Stable mode ID, 32–254 |
| 6 | State bytes, nonzero and divisible by four, u16 |
| 8 | Even callback offset within code, beyond the descriptor, u16 |
| 10 | RX-only marker, 1 |
| 11 | Reserved, zero |
| 12 | Eight printable ASCII label bytes, optionally NUL padded |

`kl_resident_info` reads metadata without executing or authenticating code.
`kl_find_resident` scans all slots and refuses duplicate IDs or SPI read errors.
Discovery is advisory: `kl_load_resident` rechecks the complete image/tag and
descriptor, verifies the requested identity, checks the caller's memory budget,
and zeroes state immediately after the four-byte-aligned image and tag.
The returned callback offset is relative to code at `arena + KM_HDR`.
The returned state offset is relative to the arena. The foreground launcher
is never armed by this loader. Removal uses the existing slot erase path.

The caller must stop an existing callback before overwriting its memory,
acquire exclusive arena ownership, exclude stack/guard space from `cap`, and
invalidate any cached foreground image. Loading is not an arena lease and does
not prove that other firmware subsystems cannot overwrite the loaded image.
The callback must return promptly; this loader cannot preempt a hung callback.

Validation: `python3 -m pytest -q tests/test_k6_resident_loader.py` compiles and
tests the real C library and shared tag-check implementation, including corrupt
tags, wrong keys, malformed descriptors, insufficient RAM, changed headers
between reads, duplicate providers, removal and foreground execution rejection.
