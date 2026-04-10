#![no_std]

use core::panic::PanicInfo;

#[no_mangle]
pub extern "C" fn rust_dummy_read(addr: u64, _size: u32) -> u64 {
    // A simple test logic: read from 0 returns a magic number
    match addr {
        0 => 0xdeadbeef,
        _ => 0,
    }
}

#[no_mangle]
pub extern "C" fn rust_dummy_write(_addr: u64, _val: u64, _size: u32) {
    // Ignore writes in this dummy template
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}
