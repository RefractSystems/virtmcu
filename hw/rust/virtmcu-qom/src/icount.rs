extern "C" {
    /// A function
    pub fn virtmcu_icount_enabled() -> bool;
    /// A function
    pub fn virtmcu_icount_advance(delta: i64);
}

/// A function
pub fn icount_enabled() -> bool {
    unsafe { virtmcu_icount_enabled() }
}

/// A function
pub fn icount_advance(delta: i64) {
    unsafe { virtmcu_icount_advance(delta) }
}
