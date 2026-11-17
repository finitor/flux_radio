"""Reproducible whole-firmware host checks. Never contacts the physical radio."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from .__main__ import K6Board, overlay_module_bundle
from .lcd import write_svg

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbols(elf):
    rows = subprocess.check_output(['llvm-nm', '-S', '-C', str(elf)], text=True)
    result = {}
    for line in rows.splitlines():
        fields = line.split(None, 3)
        if len(fields) == 4:
            try:
                result[fields[3]] = (int(fields[0], 16), int(fields[1], 16))
            except ValueError:
                pass
    return result


def recorded_symbols(path, image):
    data = json.loads(path.read_text())
    image_sha = digest(image)
    if data.get('image_sha256') != image_sha:
        raise ValueError(f"symbol map is for image {data.get('image_sha256')}, not {image_sha}")
    return {name: tuple(value) for name, value in data['symbols'].items()}


def find_symbol(table, name):
    matches = [v for k, v in table.items() if k == name or k.startswith(name + ' (')]
    if len(matches) != 1:
        raise ValueError(f'expected one ELF symbol for {name}, got {len(matches)}')
    return matches[0]


def verify_image(image, elf):
    with tempfile.TemporaryDirectory() as tmp:
        binary = Path(tmp) / 'image.bin'
        subprocess.run(['llvm-objcopy', '-O', 'binary', str(elf), str(binary)], check=True)
        if binary.read_bytes() != image.read_bytes():
            raise ValueError('ELF does not match the supplied firmware image')


def build_probe(out):
    from modem import k6mod
    source = ROOT / 'c/k6/mod/hostprobe.c'
    code, _ = k6mod.build(str(source))
    out.mkdir()
    (out / 'hostprobe.bin').write_bytes(code)
    manifest = {'format': 1, 'build': 'host contract probe', 'build_id': '0000000000000000',
                'library': [{'slot': 29, 'kind': 'module', 'file': 'hostprobe.bin',
                             'name': 'HOST PROBE', 'level': 6}],
                'sha256': {'hostprobe.bin': hashlib.sha256(code).hexdigest()}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return out


def build_afsk_probe(out):
    """Build a simulator-only module that uses the bounded AFSK TX API."""
    from modem import k6mod
    source = ROOT / 'c/k6/mod/afskprobe.c'
    code, _ = k6mod.build(str(source))
    out.mkdir()
    (out / 'afskprobe.bin').write_bytes(code)
    manifest = {'format': 1, 'build': 'SIMULATION ONLY guarded AFSK TX probe',
                'build_id': '0000000000000000',
                'library': [{'slot': 29, 'kind': 'module', 'file': 'afskprobe.bin',
                             'name': 'AFSK PROBE', 'level': 13}],
                'sha256': {'afskprobe.bin': hashlib.sha256(code).hexdigest()}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return out


def build_kiss_probe(out):
    """Build a simulator-only serial RX/TX and binary-mode KISS API probe."""
    from modem import k6mod
    source = ROOT / 'c/k6/mod/kissprobe.c'
    code, _ = k6mod.build(str(source))
    out.mkdir()
    (out / 'kissprobe.bin').write_bytes(code)
    manifest = {'format': 1, 'build': 'SIMULATION ONLY KISS UART probe',
                'build_id': '0000000000000000',
                'library': [{'slot': 29, 'kind': 'module', 'file': 'kissprobe.bin',
                             'name': 'KISS PROBE', 'level': 14}],
                'sha256': {'kissprobe.bin': hashlib.sha256(code).hexdigest()}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return out


def build_explore_candidate_fixture(out):
    """Build a simulation-only Explore module with one deterministic candidate."""
    from modem import k6mod

    source_root = ROOT / 'c/k6'
    with tempfile.TemporaryDirectory(prefix='k6-explore-fixture-') as tmp:
        copied_root = Path(tmp) / 'c/k6'
        shutil.copytree(source_root, copied_root)
        source = copied_root / 'mod/explore_scan.c'
        text = source.read_text()
        marker = 'int k6_main(const k6_api_t *api) {'
        if text.count(marker) != 1:
            raise ValueError('Explore source has no unique k6_main fixture insertion point')
        source.write_text(text.replace(marker,
                                       '#define K6_EXPLORE_SIM_FIXTURE\n' + marker))
        code, _ = k6mod.build(str(source))

    out.mkdir()
    (out / 'module.bin').write_bytes(code)
    manifest = {'format': 1, 'build': 'SIMULATION ONLY Explore candidate fixture',
                'build_id': '0000000000000000',
                'library': [{'id': 'org.blowfang.k6.explore_scan', 'kind': 'module',
                             'file': 'module.bin', 'name': 'EXPLORE', 'level': 6, 'slot': 29}],
                'sha256': {'module.bin': hashlib.sha256(code).hexdigest()}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return out


def key_sequence(case=None, explore_fixture=False):
    if case in ('afskprobe', 'kissprobe'):
        # These API probes are dispatched through the firmware's real module loader below.
        # UI key timing is intentionally omitted: the emulator does not model interrupts.
        return ()
    # Aura's launcher route: UP from SETTINGS selects BLOWFANG, MENU enters it,
    # then the first module is selected after the SPI library scan.
    presses = [(1000, 'UP'), (1600, 'MENU'), (3500, 'DOWN'), (4100, 'MENU')]
    if case == 'probe':
        presses.extend(((7000, 'MENU'),))
    elif case == 'explore':
        if explore_fixture:
            presses.extend(((5350, 'MENU'), (5500, '*'), (5850, '*'),
                            (6200, 'BAND'), (6550, 'SIDE1'), (6900, 'BAND'),
                            (7450, 'BAND'), (8500, 'EXIT')))
        else:
            presses.extend(((5350, 'MENU'), (5650, 'BAND'), (5850, 'SIDE1'),
                            (6350, 'BAND'), (7050, 'BAND'), (8100, 'EXIT')))
    else:
        presses.append((10000, 'EXIT'))
    presses.sort()
    return tuple(event for ms, key in presses for event in
                 ((ms, key, True), (ms + 120, key, False)))


def run_case(args, case, bundle, slot, table):
    out = args.out / case
    out.mkdir()
    fixture = (case == 'explore' and
               'SIMULATION ONLY' in json.loads((bundle / 'manifest.json').read_text()).get('build', ''))
    events = key_sequence(case, explore_fixture=fixture)
    board = K6Board(args.image, spi_image=args.spi_flash, key_events=events)
    # Isolate only the virtual module library; retain the supplied settings/font seed.
    board.flash_data[0x110000:0x190000] = b'\xff' * 0x80000
    installed = overlay_module_bundle(board.flash_data, bundle, args.key_file, {slot},
                                       serial_start=0x6b600000)
    heap, _ = find_symbol(table, '__sheap')
    mod_stack, mod_bytes = find_symbol(table, 'aura::MODULE_PAGE_BUFFER_STORAGE')
    arena, arena_bytes = find_symbol(table, 'aura::hal::arena::ARENA')
    watched = {}
    app_addr, _ = find_symbol(table, 'aura::APP_SLOT')
    board.watch_write(app_addr, 64)
    watched['APP_SLOT.prefix'] = f'0x{app_addr:08x}'
    cb_addr, _ = find_symbol(table, 'aura::app::pager::CB_NOR')
    board.watch_write(cb_addr, 4)
    watched['CB_NOR'] = f'0x{cb_addr:08x}'
    for name in ('aura::ui::MOD_DISPLAY', 'aura::app::pager::MOD_LCD'):
        address, size = find_symbol(table, name)
        board.watch_write(address, size or 4)
        watched[name] = f'0x{address:08x}'
    menu_addr, menu_size = find_symbol(table, 'aura::app::pager::MENU')
    board.watch_write(menu_addr, min(menu_size, 4))
    watched['aura::app::pager::MENU.header'] = f'0x{menu_addr:08x}'
    pending_addr, pending_size = find_symbol(table, 'aura::app::pager::PENDING_MENU_OPEN')
    kiss_mode_addr = (find_symbol(table, 'aura::hal::uart::BINARY_MODE')[0]
                      if case == 'kissprobe' else None)
    board.watch_write(pending_addr, pending_size or 1)
    watched['aura::app::pager::PENDING_MENU_OPEN'] = f'0x{pending_addr:08x}'
    samples = []
    progress = None
    minimum_sp = 0xFFFFFFFF
    needed_runs = 2 if case == 'probe' else 1
    explore_lcd_before = None
    with (out / 'uart.log').open('w') as log, contextlib.redirect_stdout(log):
        if case in ('explore', 'afskprobe', 'kissprobe'):
            # The app-menu keypad route is timing-sensitive in this emulator. Open the real
            # firmware module list and queue the selected SPI slot after boot, so these cases
            # exercise the actual module loader/runtime and module API without UI timing noise.
            pending_open, _ = find_symbol(table, 'aura::app::pager::PENDING_MENU_OPEN')
            pending_slot, _ = find_symbol(table, 'aura::app::pager::PENDING_LIB_SLOT')
            board.run(70_000_000, args.quantum)
            explore_lcd_before = len(board.lcd_trace)
            board.uc.mem_write(pending_open, b'\x01')
            board.run(2_000_000, args.quantum)
            board.uc.mem_write(pending_slot, bytes((slot,)))
        while board.instructions < args.instructions and not board.fault:
            board.run(min(200000, args.instructions - board.instructions), args.quantum)
            if (case == 'kissprobe' and not getattr(board, 'kiss_input_injected', False)
                    and board.uc.mem_read(kiss_mode_addr, 1) == b'\x01'):
                board.inject_uart_rx(b'\xdb')
                board.kiss_input_injected = True
            minimum_sp = min(minimum_sp, int(board.cpu_registers()['sp'], 16))
            uart = bytes(board.uart_tx)
            starts = uart.count(b'K6 MOD stage dispatch begin')
            returns = uart.count(b'K6 MOD ret=')
            state = (starts, returns)
            app_prefix = bytes(board.uc.mem_read(app_addr, 8)).hex()
            kiss_active = (board.uc.mem_read(kiss_mode_addr, 1) == b'\x01') if case == 'kissprobe' else False
            marker = (state, app_prefix, board.key_events_applied, kiss_active)
            if marker != progress:
                samples.append({'instructions': board.instructions, 'starts': starts,
                                'returns': returns, 'lcd_events': len(board.lcd_trace),
                                'key_events_applied': board.key_events_applied,
                                'virtual_ms_estimate': round(board.cycles / 96_000, 3),
                                'app_prefix': app_prefix, 'kiss_mode_active': kiss_active,
                                'minimum_sp': f'0x{minimum_sp:08x}',
                                'registers': board.cpu_registers()})
                progress = marker
            if returns >= needed_runs:
                break
    board.write_report(out / 'report.json', args.image, 'host-contract',
                       [{'slot': s, 'name': n, 'image_bytes': z} for s, n, z in installed])
    if board.fault:
        app_addr, app_size = find_symbol(table, 'aura::APP_SLOT')
        cb_ptr = int.from_bytes(board.uc.mem_read(cb_addr, 4), 'little')
        (out / 'fault-memory.txt').write_text(
            f'APP_SLOT=0x{app_addr:08x} size={app_size}\n'
            f'APP first 64 bytes: {bytes(board.uc.mem_read(app_addr, 64)).hex(" ")}\n'
            f'CB_NOR global=0x{cb_addr:08x} value=0x{cb_ptr:08x}\n'
            f'CB_NOR object first 16 bytes: '
            f'{bytes(board.uc.mem_read(cb_ptr, 16)).hex(" ") if 0x20000000 <= cb_ptr < 0x20006000 else "outside SRAM"}\n')
        app_writes = [w for w in board.memory_writes if app_addr <= int(w['address'], 16) < app_addr + 64]
        (out / 'app-prefix-writes.json').write_text(json.dumps(app_writes, indent=2) + '\n')
        cb_writes = [w for w in board.memory_writes if int(w['address'], 16) == cb_addr]
        (out / 'cb-nor-writes.json').write_text(json.dumps(cb_writes, indent=2) + '\n')
    control_writes = [w for w in board.memory_writes
                      if menu_addr <= int(w['address'], 16) < menu_addr + 4
                      or int(w['address'], 16) == pending_addr]
    (out / 'menu-control-writes.json').write_text(json.dumps(control_writes, indent=2) + '\n')
    (out / 'lcd.jsonl').write_text(''.join(json.dumps({'t': t, 'dc': dc, 'cs': cs, 'byte': b}) + '\n'
                                         for t, dc, cs, b in board.lcd_trace))
    write_svg(out / 'lcd.jsonl', out / 'screen.svg')
    def valid_stack_pointer(write):
        sp = int(write['sp'], 16)
        return (heap <= sp <= 0x20006000 or
                mod_stack <= sp <= mod_stack + mod_bytes or
                arena <= sp <= arena + arena_bytes)
    collisions = [w for w in board.memory_writes if not valid_stack_pointer(w)]
    uart = bytes(board.uart_tx)
    first_entry = next((s for s in samples if s['starts'] > 0), None)
    first_return = next((s for s in samples if s['returns'] > 0), None)
    lcd_progress = bool(first_entry and first_return and
                        first_return['lcd_events'] > first_entry['lcd_events'])
    checks = {'no_cpu_fault': board.fault is None, 'no_unreserved_stack_at_watched_writes': not collisions,
              'module_entry_count': uart.count(b'K6 MOD stage dispatch begin') >= needed_runs,
              'module_return_count': uart.count(b'K6 MOD ret=') >= needed_runs}
    if case == 'explore':
        checks['module_entry_count'] = (b'K6 LIB run slot=29' in uart and
                                        b'K6 MOD say EXPLORE scan/list started; RX only' in uart)
        checks['lcd_callback_completed'] = (explore_lcd_before is not None and
                                            len(board.lcd_trace) > explore_lcd_before)
    elif case not in ('afskprobe', 'kissprobe'):
        checks['lcd_hook_registered'] = b'K6 LCD hook registered' in uart
        checks['lcd_callback_completed'] = lcd_progress
    if case == 'cardlink':
        checks['module_screen_flushed'] = lcd_progress
    if case == 'probe':
        checks['probe_return_42_twice'] = uart.count(b'K6 MOD ret=42 ') >= 2
    if case in ('afskprobe', 'kissprobe'):
        checks['module_entry_count'] = b'K6 LIB run slot=29' in uart
    if case == 'afskprobe':
        checks['guarded_tx_started'] = b'K6 MOD tx on hz=144390000' in uart
        checks['host_afsk_call_returned'] = b'K6 MOD ret=0 ' in uart
        checks['guarded_tx_stopped'] = b'K6 MOD tx off' in uart
    if case == 'kissprobe':
        # The binary-mode API intentionally hides the loader's normal K6 text diagnostics.
        # Receiving a byte and returning its escaped frame proves the module entered.
        checks['module_entry_count'] = (b'K6 MOD say KISS probe received' in uart
                                        and b'K6 MOD ret=0 ' in uart)
        checks['kiss_rx_byte'] = b'K6 MOD say KISS probe received' in uart
        checks['kiss_binary_frame'] = b'\xc0\x00\xdb\xc0' in uart
        checks['normal_diagnostics_restored'] = b'K6 MOD ret=0 ' in uart
    if case == 'explore':
        checks['candidate_list_toggle'] = b'K6 MOD say EXPLORE candidate list' in uart
        if fixture:
            checks['band_switch'] = b'K6 MOD say EXPLORE band 2M' in uart
            checks['candidate_ignore'] = b'K6 MOD say EXPLORE ignored' in uart
            checks['candidate_unignore'] = b'K6 MOD say EXPLORE unignored' in uart
            checks['try_park'] = b'K6 MOD say EXPLORE Try; key to resume scan' in uart
            checks['try_resume'] = b'K6 MOD say EXPLORE scan resumed' in uart
        else:
            checks['band_switch'] = all(text in uart for text in (
                b'K6 MOD say EXPLORE band ALL', b'K6 MOD say EXPLORE band 2M',
                b'K6 MOD say EXPLORE band 70CM', b'K6 MOD say EXPLORE band 1.25M'))
            checks['try_no_candidate_guard'] = b'K6 MOD say EXPLORE select a candidate first' in uart
    addresses = list(dict.fromkeys(w['pc'] for w in collisions))[:16]
    mappings = (subprocess.check_output(['llvm-addr2line', '-a', '-f', '-C', '-e', str(args.elf),
                                         *addresses], text=True)
                if addresses and args.elf else '')
    (out / 'collision-sources.txt').write_text(mappings)
    result = {'case': case, 'passed': all(checks.values()), 'checks': checks,
              'watched': watched, 'static_end': f'0x{heap:08x}',
              'temporary_boot_stack': {'start': f'0x{arena:08x}', 'end': f'0x{arena + arena_bytes:08x}'},
              'stack_collision_writes': collisions, 'progress': samples,
              'kiss_input_injected': getattr(board, 'kiss_input_injected', False),
              'image_sha256': digest(args.image),
              'elf_sha256': digest(args.elf) if args.elf else None,
              'symbol_map_sha256': digest(args.symbols_json) if args.symbols_json else None,
              'module_sha256': {p.name: digest(p) for p in bundle.glob('*.bin')},
              'spi_seed_sha256': digest(args.spi_flash), 'key_events': events,
              'quantum': args.quantum, 'instruction_budget': args.instructions,
              'limitations': ['No delivered hardware interrupts or real RF/audio.',
                              'SPI readiness is idealized.',
                              'Write watches cover selected control globals, not every stack write.']}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"{case}: {'PASS' if result['passed'] else 'FAIL'}; "
          f"fault={board.fault and board.fault['kind']}; collision writes={len(collisions)}")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'spi-flash', 'key-file', 'bundle', 'out'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--elf', type=Path)
    ap.add_argument('--symbols-json', type=Path,
                    help='recorded SRAM symbols, accepted only for its exact image SHA256')
    ap.add_argument('--fskb-bundle', type=Path,
                    help='optional FSKB capability bundle used by the fskbcap case')
    ap.add_argument('--cardlink-bundle', type=Path,
                    help='optional CARD LINK bundle used by the cardlink UI/return smoke case')
    ap.add_argument('--explore-bundle', type=Path,
                    help='optional EXPLORE scan bundle used by the explore case')
    ap.add_argument('--explore-candidate-fixture', action='store_true',
                    help='build a simulation-only module with a deterministic candidate')
    ap.add_argument('--cases', default='probe,vfo,surf')
    # The scripted cases navigate after 4.1 s and stop at 10 s; with the default
    # 1.5-cycle estimate, 180 M instructions only runs about 2.8 s and never enters
    # an interactive module. Keep enough budget to reach the final release event.
    ap.add_argument('--instructions', type=int, default=800000000)
    ap.add_argument('--quantum', type=int, default=256)
    args = ap.parse_args()
    cases = args.cases.split(',')
    if any(c not in ('probe', 'afskprobe', 'kissprobe', 'vfo', 'surf', 'fskbcap', 'explore', 'cardlink') for c in cases) or len(set(cases)) != len(cases):
        ap.error('cases must be distinct values from probe,afskprobe,kissprobe,vfo,surf,fskbcap,explore,cardlink')
    if 'fskbcap' in cases and args.fskb_bundle is None:
        ap.error('the fskbcap case requires --fskb-bundle')
    if args.explore_candidate_fixture and 'explore' not in cases:
        ap.error('--explore-candidate-fixture requires the explore case')
    if 'explore' in cases and args.explore_bundle is None and not args.explore_candidate_fixture:
        ap.error('the explore case requires --explore-bundle or --explore-candidate-fixture')
    if 'cardlink' in cases and args.cardlink_bundle is None:
        ap.error('the cardlink case requires --cardlink-bundle')
    if args.instructions <= 0 or args.quantum <= 0:
        ap.error('instruction budget and quantum must be positive')
    if args.symbols_json:
        table = recorded_symbols(args.symbols_json, args.image)
    else:
        if not args.elf:
            ap.error('--elf is required unless --symbols-json is supplied')
        verify_image(args.image, args.elf)
        table = symbols(args.elf)
    args.out.mkdir(parents=True, exist_ok=False)
    probe = build_probe(args.out / 'probe-bundle') if 'probe' in cases else None
    afskprobe = build_afsk_probe(args.out / 'afskprobe-bundle') if 'afskprobe' in cases else None
    kissprobe = build_kiss_probe(args.out / 'kissprobe-bundle') if 'kissprobe' in cases else None
    explore_fixture = (build_explore_candidate_fixture(args.out / 'explore-fixture')
                       if args.explore_candidate_fixture else None)
    results = [run_case(args, case,
                        probe if case == 'probe' else
                        afskprobe if case == 'afskprobe' else
                        kissprobe if case == 'kissprobe' else
                        args.fskb_bundle if case == 'fskbcap' else
                        explore_fixture if case == 'explore' and explore_fixture else
                        args.explore_bundle if case == 'explore' else
                        args.cardlink_bundle if case == 'cardlink' else args.bundle,
                        {'probe': 29, 'afskprobe': 29, 'kissprobe': 29, 'vfo': 30, 'surf': 0,
                         'fskbcap': 31, 'explore': 29, 'cardlink': 8}[case], table)
               for case in cases]
    (args.out / 'summary.json').write_text(json.dumps(
        {'passed': all(r['passed'] for r in results),
         'cases': [{'case': r['case'], 'passed': r['passed'], 'checks': r['checks']} for r in results]},
        indent=2) + '\n')
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
