#!/usr/bin/env python3
"""Initialize the C module loader explicitly at firmware startup."""
from pathlib import Path

main = Path(__file__).parent / 'build/aura-fd6818b-port/src/main.rs'
text = main.read_text()
entry = '#[entry]\nfn main() -> ! {\n'
if text.count(entry) != 1:
    raise SystemExit('could not uniquely locate Aura firmware entry point')
decl = '#[cfg(feature = "spilib")]\nextern "C" { fn km_init(); }\n\n'
if 'fn km_init();' not in text:
    text = text.replace(entry, decl + entry, 1)
call = '    #[cfg(feature = "spilib")]\n    unsafe { km_init(); }\n'
if call not in text:
    text = text.replace(entry, entry + call, 1)
main.write_text(text)
print('Initialized C module-loader state at firmware startup')
