#!/usr/bin/env python3
"""Append the guarded FD6818B fixed-frame FSK TX API to the Aura patch checkout."""
from pathlib import Path

root = Path(__file__).resolve().parent / "build" / "aura-fd6818b-port"
pager_path = root / "src/app/pager.rs"
driver_path = root / "src/drivers/fd6818b.rs"
pager = pager_path.read_text()
driver = driver_path.read_text()

if "fsk_tx_send: mod_fsk_tx_send" not in pager:
    pairs = [
        (
            "        pub fsk_rx_stop: unsafe extern \"C\" fn(),\n",
            "        pub fsk_rx_stop: unsafe extern \"C\" fn(),\n"
            "        // level 11: guarded FD6818B fixed 16-byte FSK TX frame.\n"
            "        pub fsk_tx_send: unsafe extern \"C\" fn(*const u16) -> i32,\n",
        ),
        (
            "    level: if cfg!(feature = \"fd6818b\") { 10 } else { 9 },\n",
            "    level: if cfg!(feature = \"fd6818b\") { 11 } else { 9 },\n",
        ),
        (
            "    fsk_rx_stop: mod_fsk_rx_stop,\n",
            "    fsk_rx_stop: mod_fsk_rx_stop,\n"
            "    fsk_tx_send: mod_fsk_tx_send,\n",
        ),
        (
            "unsafe extern \"C\" fn mod_delay_us(mut us: u32) {",
            "/// Level 11's fixed-frame FSK transmit call. RF key-up remains owned by the\n"
            "/// guarded level-3 transmitter; this entry point cannot key the radio itself.\n"
            "unsafe extern \"C\" fn mod_fsk_tx_send(words: *const u16) -> i32 {\n"
            "    if words.is_null() {\n"
            "        return -1;\n"
            "    }\n"
            "    mod_tx_guard();\n"
            "    let c = unsafe { &*addr_of!(MOD_CTX) };\n"
            "    if c.app.is_null() || !c.tx {\n"
            "        return -1;\n"
            "    }\n"
            "    #[cfg(feature = \"fd6818b\")]\n"
            "    {\n"
            "        let (app, syst) = unsafe { mod_ctx() };\n"
            "        let mut frame = [0u16; 8];\n"
            "        for (index, word) in frame.iter_mut().enumerate() {\n"
            "            *word = unsafe { words.add(index).read() };\n"
            "        }\n"
            "        let complete = app.radio.fd6818.fsk_transmit(syst, &frame);\n"
            "        mod_tx_guard();\n"
            "        return if complete { 0 } else { -1 };\n"
            "    }\n"
            "    #[cfg(not(feature = \"fd6818b\"))]\n"
            "    -1\n"
            "}\n\n"
            "unsafe extern \"C\" fn mod_delay_us(mut us: u32) {",
        ),
    ]
    for old, new in pairs:
        count = pager.count(old)
        if count != 1:
            raise SystemExit(f"pager anchor expected once, found {count}: {old[:70]!r}")
        pager = pager.replace(old, new, 1)
    pager_path.write_text(pager)

pager = pager_path.read_text()
if "card_store: mod_card_store" not in pager:
    pairs = [
        (
            "        pub fsk_tx_send: unsafe extern \"C\" fn(*const u16) -> i32,\n",
            "        pub fsk_tx_send: unsafe extern \"C\" fn(*const u16) -> i32,\n"
            "        // level 12: append a verified, data-only PXK6 record to SPI.\n"
            "        pub card_store: unsafe extern \"C\" fn(*const u8, u32) -> i32,\n",
        ),
        (
            "    level: if cfg!(feature = \"fd6818b\") { 11 } else { 9 },\n",
            "    level: if cfg!(all(feature = \"fd6818b\", feature = \"spilib\")) { 12 } else if cfg!(feature = \"fd6818b\") { 11 } else { 9 },\n",
        ),
        (
            "    fsk_tx_send: mod_fsk_tx_send,\n",
            "    fsk_tx_send: mod_fsk_tx_send,\n"
            "    card_store: mod_card_store,\n",
        ),
        (
            "unsafe extern \"C\" fn mod_delay_us(mut us: u32) {",
            "/// Module card-store append. CPS applies the bounded flash callbacks and disables erases.\n"
            "#[cfg(feature = \"spilib\")]\n"
            "unsafe extern \"C\" fn mod_card_store(record: *const u8, n: u32) -> i32 {\n"
            "    mod_tx_guard();\n"
            "    let c = unsafe { &*addr_of!(MOD_CTX) };\n"
            "    if c.app.is_null() || c.tx { return -1; }\n"
            "    let mut scratch = [0u8; 64];\n"
            "    let nor = { let (app, _) = unsafe { mod_ctx() }; &mut app.storage.norflash as *mut _ };\n"
            "    unsafe { crate::cps::module_card_store_put(nor, record, n as usize, scratch.as_mut_ptr(), scratch.len()) }\n"
            "}\n"
            "#[cfg(not(feature = \"spilib\"))]\n"
            "unsafe extern \"C\" fn mod_card_store(_record: *const u8, _n: u32) -> i32 { -1 }\n\n"
            "unsafe extern \"C\" fn mod_delay_us(mut us: u32) {",
        ),
    ]
    for old, new in pairs:
        count = pager.count(old)
        if count != 1:
            raise SystemExit(f"card-store anchor expected once, found {count}: {old[:70]!r}")
        pager = pager.replace(old, new, 1)
    pager_path.write_text(pager)

# Keep an existing generated checkout in sync if the append API's caller buffer contract changes.
pager = pager_path.read_text()
pager = pager.replace(
    'pub card_store: unsafe extern "C" fn(*const u8, u32, *mut u8, u32) -> i32,',
    'pub card_store: unsafe extern "C" fn(*const u8, u32) -> i32,')
old_read = '''#[cfg(feature = "lean")]
unsafe extern "C" fn mod_fl_read(_addr: u32, _buf: *mut u8, _n: u32) -> i32 {
    -1
}'''
new_read = '''#[cfg(all(feature = "lean", feature = "blowfang-host"))]
unsafe extern "C" fn mod_fl_read(addr: u32, buf: *mut u8, n: u32) -> i32 {
    mod_tx_guard();
    let live = unsafe { !(*addr_of!(MOD_CTX)).app.is_null() };
    if buf.is_null() || !live || addr < 0x190000 || addr >= 0x200000 || n > 0x200000 - addr {
        return -1;
    }
    let (app, _) = unsafe { mod_ctx() };
    if app.storage.norflash.read_bytes_checked(
        addr, unsafe { core::slice::from_raw_parts_mut(buf, n as usize) }) { 0 } else { -1 }
}'''
if new_read not in pager:
    if pager.count(old_read) != 1:
        raise SystemExit(f"expected one lean flash-read stub, found {pager.count(old_read)}")
    pager = pager.replace(old_read, new_read + '''
#[cfg(all(feature = "lean", not(feature = "blowfang-host")))]
unsafe extern "C" fn mod_fl_read(_addr: u32, _buf: *mut u8, _n: u32) -> i32 {
    -1
}''', 1)
fn_start = pager.find('#[cfg(feature = "spilib")]\nunsafe extern "C" fn mod_card_store(')
fn_end = pager.find('\nunsafe extern "C" fn mod_delay_us', fn_start)
if fn_start >= 0 and fn_end >= 0:
    new_fn = '''#[cfg(feature = "spilib")]
unsafe extern "C" fn mod_card_store(record: *const u8, n: u32) -> i32 {
    mod_tx_guard();
    let c = unsafe { &*addr_of!(MOD_CTX) };
    if c.app.is_null() || c.tx { return -1; }
    let mut scratch = [0u8; 64];
    let nor = { let (app, _) = unsafe { mod_ctx() }; &mut app.storage.norflash as *mut _ };
    unsafe { crate::cps::module_card_store_put(nor, record, n as usize, scratch.as_mut_ptr(), scratch.len()) }
}
#[cfg(not(feature = "spilib"))]
unsafe extern "C" fn mod_card_store(_record: *const u8, _n: u32) -> i32 { -1 }
'''
    pager = pager[:fn_start] + new_fn + pager[fn_end:]
pager_path.write_text(pager)

if "pub fn fsk_transmit(&mut self, syst: &mut SYST, data: &[u16; FSK_FRAME_LEN]) -> bool" not in driver:
    old = """    pub fn fsk_transmit(&mut self, syst: &mut SYST, data: &[u16; FSK_FRAME_LEN]) {
        self.write_reg(syst, REG_WORK_MODE, WORK_MODE_FSK_TX_IRQ);"""
    new = """    pub fn fsk_transmit(&mut self, syst: &mut SYST, data: &[u16; FSK_FRAME_LEN]) -> bool {
        self.write_reg(syst, REG_WORK_MODE, WORK_MODE_FSK_TX_IRQ);"""
    if driver.count(old) != 1:
        raise SystemExit("FD6818B fsk_transmit signature anchor was not unique")
    driver = driver.replace(old, new, 1)
    old = """        self.write_reg(syst, REG_FSK_CONTROL, FSK_CONTROL_BASE | FSK_CONTROL_TX_EN);
        for _ in 0..200 {
            delay::ms(syst, 5);
            if self.read_reg(syst, REG_STATUS) & 0x0001 != 0 {
                break;
            }
        }
        self.write_reg(syst, REG_INT_CLEAR, 0x0000);
        self.write_reg(syst, REG_WORK_MODE, 0x0000);
        self.write_reg(syst, REG_FSK_CONTROL, FSK_CONTROL_BASE);
    }"""
    new = """        self.write_reg(syst, REG_FSK_CONTROL, FSK_CONTROL_BASE | FSK_CONTROL_TX_EN);
        let mut complete = false;
        for _ in 0..200 {
            delay::ms(syst, 5);
            if self.read_reg(syst, REG_STATUS) & 0x0001 != 0 {
                complete = true;
                break;
            }
        }
        self.write_reg(syst, REG_INT_CLEAR, 0x0000);
        self.write_reg(syst, REG_WORK_MODE, 0x0000);
        self.write_reg(syst, REG_FSK_CONTROL, FSK_CONTROL_BASE);
        complete
    }"""
    start = driver.index("pub fn fsk_transmit(&mut self, syst: &mut SYST, data: &[u16; FSK_FRAME_LEN]) -> bool")
    end = driver.index("\n    /// True once a full raw FSK frame is ready to read.", start)
    tx_fn = driver[start:end]
    if tx_fn.count(old) != 1:
        raise SystemExit("FD6818B fsk_transmit completion anchor was not unique in its function")
    driver = driver[:start] + tx_fn.replace(old, new, 1) + driver[end:]
    driver_path.write_text(driver)

driver = driver_path.read_text()
marker = """        self.write_reg(syst, REG_WORK_MODE, WORK_MODE_FSK_TX_IRQ);
        self.write_reg(syst, REG_FSK_PREAMBLE, 0x00C1);
        self.write_reg(syst, REG_TONE_GAIN, 0x00E0);
        self.write_reg(syst, REG_FSK_BAUD, FSK_BAUD_1200);
        self.write_reg(syst, REG_FSK_5C, FSK_5C_VALUE);
        self.write_reg(syst, REG_FSK_5D, FSK_5D_VALUE);"""
if marker not in driver:
    old = """        self.write_reg(syst, REG_WORK_MODE, WORK_MODE_FSK_TX_IRQ);
        self.write_reg(
            syst,
            REG_FSK_CONTROL,
            FSK_CONTROL_BASE | FSK_CONTROL_TX_FIFO_CLEAR,
        );"""
    start = driver.index("pub fn fsk_transmit(&mut self, syst: &mut SYST, data: &[u16; FSK_FRAME_LEN]) -> bool")
    prefix, tx = driver[:start], driver[start:]
    if old not in tx:
        raise SystemExit("FD6818B FSK TX setup anchor was not found")
    new = """        self.write_reg(syst, REG_WORK_MODE, WORK_MODE_FSK_TX_IRQ);
        self.write_reg(syst, REG_FSK_PREAMBLE, 0x00C1);
        self.write_reg(syst, REG_TONE_GAIN, 0x00E0);
        self.write_reg(syst, REG_FSK_BAUD, FSK_BAUD_1200);
        self.write_reg(syst, REG_FSK_5C, FSK_5C_VALUE);
        self.write_reg(syst, REG_FSK_5D, FSK_5D_VALUE);
        self.write_reg(
            syst,
            REG_FSK_CONTROL,
            FSK_CONTROL_BASE | FSK_CONTROL_TX_FIFO_CLEAR,
        );"""
    driver = prefix + tx.replace(old, new, 1)
    driver_path.write_text(driver)

cps_path = root / "src/cps/mod.rs"
cps = cps_path.read_text()
if "pub(crate) unsafe fn module_card_store_put" not in cps:
    anchor = "static CARD_FLASH: CardFlash = CardFlash { read: card_flash_read, program: card_flash_program, erase: card_flash_erase };\n"
    addition = anchor + """#[cfg(feature = "spilib")]
pub(crate) unsafe fn module_card_store_put(
    nor: *mut crate::drivers::norflash::NorFlash<'static>, record: *const u8,
    record_bytes: usize, scratch: *mut u8, scratch_bytes: usize,
) -> i32 {
    if nor.is_null() { return -1; }
    unsafe { CARD_NOR = nor; CARD_WRITES_ALLOWED = true; }
    let result = unsafe { pxk6_store_put(&CARD_FLASH, record, record_bytes, scratch, scratch_bytes) };
    unsafe { CARD_WRITES_ALLOWED = false; }
    result
}
"""
    if cps.count(anchor) != 1:
        raise SystemExit("CPS card flash anchor expected once")
    cps_path.write_text(cps.replace(anchor, addition, 1))
