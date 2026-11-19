// Experimental no-TX job; only runs when the normal radio and arena are idle.
#[cfg(k6_scheduled_probe)]
#[repr(C)]
struct Job { interval: u32, grace: u32, deadline: u32, enabled: u8 }
#[cfg(k6_scheduled_probe)]
extern "C" {
    fn sd_enable(j: *mut Job, now: u32, interval: u32, grace: u32) -> i32;
    fn sd_poll(j: *mut Job, now: u32, rf_idle: i32, arena_available: i32) -> i32;
}
#[cfg(k6_scheduled_probe)]
pub struct ScheduledProbe { job: Job, now: u32, runs: u32 }
#[cfg(k6_scheduled_probe)]
impl ScheduledProbe {
    pub const fn new() -> Self {
        Self { job: Job { interval:0, grace:0, deadline:0, enabled:0 }, now:0, runs:0 }
    }
    pub fn poll(&mut self, runtime: &mut Runtime, app: &crate::app::App, ticks: u16, audio_open: bool) {
        self.now = self.now.wrapping_add(ticks as u32 * 10);
        if self.job.enabled == 0 {
            unsafe { sd_enable(&mut self.job, self.now, 10000, 2000); }
            return;
        }
        let idle = app.scheduled_rf_idle() && !audio_open;
        // First milestone defers rather than evicting a running resident.
        let selected = app.resident_selected(0) || app.resident_selected(1);
        let available = !selected && !runtime.failed && runtime.dispatcher.callback == 0 && !app.resident_arena_busy();
        let decision = unsafe { sd_poll(&mut self.job, self.now, idle as i32, available as i32) };
        if decision == 1 {
            // Use the same lease and cooperative contract; no peripheral API.
            app.resident_invalidate_cached_module();
            unsafe {
                core::ptr::write_volatile(Runtime::guard(), GUARD);
                let state = crate::hal::arena::base().cast::<u32>();
                let mut d = Dispatcher { callback:0, state:core::ptr::null_mut() };
                let r = vm_dispatch(&mut d, vm_probe as *const () as usize, state);
                if r == 0 { vm_event(&mut d, 2, app.watching_freq_hz()); }
                vm_dispatch(&mut d, 0, core::ptr::null_mut());
            }
            self.runs = self.runs.wrapping_add(1);
            crate::rl!("K6 SCHEDULED run={}", self.runs);
        } else if decision == 2 { crate::rl!("K6 SCHEDULED skipped"); }
    }
}
