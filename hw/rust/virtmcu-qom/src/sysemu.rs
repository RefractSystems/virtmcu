//! Safe wrappers for QEMU system emulation state.

extern "C" {
    /// A function
    pub fn virtmcu_runstate_is_running() -> bool;
}

/// A function
pub fn runstate_is_running() -> bool {
    unsafe { virtmcu_runstate_is_running() }
}
