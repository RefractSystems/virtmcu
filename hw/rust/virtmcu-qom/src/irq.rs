#[repr(C)]
/// A struct
pub struct IRQState {
    _opaque: [u8; 0],
}

#[allow(non_camel_case_types)]
/// A type alias
pub type qemu_irq = *mut IRQState;

#[derive(Copy, Clone)]
/// A struct
pub struct SafeIrq(pub qemu_irq);
unsafe impl Send for SafeIrq {}
unsafe impl Sync for SafeIrq {}

extern "C" {
    /// A function
    pub fn qemu_set_irq(irq: qemu_irq, level: i32);
    /// A static
    pub static mut virtmcu_irq_hook: Option<
        extern "C" fn(opaque: *mut core::ffi::c_void, n: core::ffi::c_int, level: core::ffi::c_int),
    >;
}
