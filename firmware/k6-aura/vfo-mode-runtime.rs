// Experimental native lifecycle probe. Not a published module ABI or modem.
// Experimental lease: lower arena only, leaving 4096 bytes for native alternate stacks.
// SPI probe remains experimental and opt-in until the complete lease audit passes.
const STACK_RESERVE: usize = 4096;
const GUARD: u32 = 0x56464f47;
#[repr(C)]
struct Dispatcher { callback: usize, state: *mut u32 }
#[repr(C)]
#[derive(Default)]
pub struct ResidentInfo {
    pub state_bytes: u16, pub callback: u16, pub state_offset: u16,
    pub id: u8, pub label: [u8; 8],
}
extern "C" {
    fn vm_probe(state: *mut u32, event: u32, value: u32) -> i32;
    fn vm_dispatch(d: *mut Dispatcher, cb: usize, state: *mut u32) -> i32;
    fn vm_event(d: *mut Dispatcher, event: u32, value: u32) -> i32;
}
pub struct Runtime {
    dispatcher: Dispatcher,
    failed: bool,
    freq: u32,
    side: usize,
    #[cfg(k6_vfo_spi_probe)]
    ticks: u32,
}
impl Runtime {
    pub const fn new() -> Self {
        Self { dispatcher: Dispatcher { callback: 0, state: core::ptr::null_mut() },
               failed: false, freq: 0, side: 0,
               #[cfg(k6_vfo_spi_probe)] ticks: 0 }
    }
    pub fn stop(&mut self) {
        if self.dispatcher.callback != 0 {
            // Cable/foreground handoff can call stop before the next tick.
            // Do not jump into arena code if its stack boundary was damaged.
            if unsafe { core::ptr::read_volatile(Self::guard()) } != GUARD {
                self.dispatcher.callback = 0;
                self.dispatcher.state = core::ptr::null_mut();
                self.failed = true;
                return;
            }
            unsafe { vm_dispatch(&mut self.dispatcher, 0, core::ptr::null_mut()); }
            #[cfg(k6_vfo_spi_probe)]
            crate::rl!("K6 RESIDENT stopped ticks={}", self.ticks);
        }
    }
    fn guard() -> *mut u32 {
        unsafe { crate::hal::arena::base().add(crate::hal::arena::ARENA_BYTES - STACK_RESERVE - 4).cast() }
    }
    // Metadata ticks, NOT audio samples. Probe is built in and never controls RF.
    pub fn tick(&mut self, app: &crate::app::App) {
        if self.dispatcher.callback != 0 && unsafe { core::ptr::read_volatile(Self::guard()) } != GUARD {
            // Do not call a provider after the shared-arena guard is damaged.
            self.dispatcher.callback = 0;
            self.dispatcher.state = core::ptr::null_mut();
            self.failed = true;
        }
        if self.failed || app.resident_arena_busy() {
            self.stop();
            return;
        }
        if app.mode() != crate::app::Mode::Standby || app.is_transmitting()
            || app.cw_key_down() || app.power_save_is_asleep() {
            self.stop();
            return;
        }
        let freq = app.watching_freq_hz();
        let side = app.watching_index();
        #[cfg(k6_vfo_spi_probe)]
        let slot = app.resident_probe_slot();
        #[cfg(k6_vfo_spi_probe)]
        if slot < 0 {
            self.stop();
            return;
        }
        if self.dispatcher.callback == 0 {
            app.resident_invalidate_cached_module();
            unsafe {
                core::ptr::write_volatile(Self::guard(), GUARD);
                #[cfg(not(k6_vfo_spi_probe))]
                {
                let state = crate::hal::arena::base().cast::<u32>();
                if vm_dispatch(&mut self.dispatcher, vm_probe as *const () as usize, state) != 0 {
                    self.failed = true;
                    return;
                }
                }
                #[cfg(k6_vfo_spi_probe)]
                {
                    let mut info = ResidentInfo::default();
                    let cap = crate::hal::arena::ARENA_BYTES - STACK_RESERVE - 4;
                    if app.resident_probe_load(slot, cap, &mut info) <= 0 {
                        self.failed = true;
                        return;
                    }
                    let base = crate::hal::arena::base();
                    let callback = base.add(16 + info.callback as usize) as usize | 1;
                    let state = base.add(info.state_offset as usize).cast::<u32>();
                    core::arch::asm!("dsb", "isb", options(nostack, preserves_flags));
                    if vm_dispatch(&mut self.dispatcher, callback, state) != 0 {
                        self.failed = true;
                        return;
                    }
                    self.ticks = 0;
                    crate::rl!("K6 RESIDENT started slot={}", slot);
                }
            }
        } else {
            if self.freq != freq || self.side != side {
                if unsafe { vm_event(&mut self.dispatcher, 3, 0) } != 0 {
                    self.failed = true;
                    return;
                }
            }
        }
        self.freq = freq;
        self.side = side;
        if unsafe { vm_event(&mut self.dispatcher, 2, freq) } != 0 { self.failed = true; }
        #[cfg(k6_vfo_spi_probe)]
        if !self.failed { self.ticks = self.ticks.wrapping_add(1); }
    }
}
