use core::ffi::c_char;

#[repr(C)]
/// A struct
pub struct Error {
    _opaque: [u8; 0],
}

extern "C" {
    /// A function
    pub fn virtmcu_error_setg(errp: *mut *mut Error, fmt: *const c_char);
}

#[macro_export]
/// A macro
macro_rules! error_setg {
    ($errp:expr, $fmt:expr) => {
        unsafe {
            $crate::error::virtmcu_error_setg(
                $errp as *mut *mut $crate::error::Error,
                core::ffi::CStr::from_bytes_with_nul_unchecked(concat!($fmt, "\0").as_bytes())
                    .as_ptr(),
            );
        }
    };
}
