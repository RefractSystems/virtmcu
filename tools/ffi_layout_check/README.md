# FFI Layout Checker

This directory contains templates and a Makefile for debugging Foreign Function Interface (FFI) memory layout issues between C and Rust.

When interacting with C code from Rust (or vice versa), struct layouts must perfectly match, particularly when `#[repr(C)]` is used or when cross-compiling. If the size or alignment of a struct diverges between the two languages, it will lead to memory corruption, segmentation faults, or silent data manipulation.

## Files

*   `print_sizes.c`: A C template to compile and print the `sizeof` and `offsetof` of C structures.
*   `print_rust_sizes.rs`: A Rust template to compile and print the `std::mem::size_of` and `std::mem::align_of` of Rust structures.
*   `Makefile`: Utility to quickly compile and run these size checkers against the QEMU/VirtMCU source tree.

## Usage

1.  Edit `print_sizes.c` and `print_rust_sizes.rs` to include the specific structures you are investigating.
2.  Run `make` in this directory to build and execute both checkers.
3.  Compare the output to identify layout mismatches.

```bash
cd tools/ffi_layout_check
make
```
