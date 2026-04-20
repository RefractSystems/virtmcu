use core::ffi::c_void;

/// A constant
pub const QEMU_CLOCK_VIRTUAL: i32 = 1;

#[repr(C)]
/// A struct
pub struct QemuTimer {
    _opaque: [u8; 0],
}

/// A type alias
pub type QemuTimerCb = extern "C" fn(opaque: *mut c_void);

extern "C" {
    /// A function
    pub fn qemu_clock_get_ns(clock_type: i32) -> i64;
    /// A function
    pub fn virtmcu_timer_new_ns(
        clock_type: i32,
        cb: QemuTimerCb,
        opaque: *mut c_void,
    ) -> *mut QemuTimer;
    /// A function
    pub fn virtmcu_timer_mod(timer: *mut QemuTimer, expire_time: i64);
    /// A function
    pub fn virtmcu_timer_del(timer: *mut QemuTimer);
    /// A function
    pub fn virtmcu_timer_free(timer: *mut QemuTimer);

    /// A function
    pub fn qemu_clock_run_all_timers();
}
