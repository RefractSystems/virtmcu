// ==============================================================================
// print_sizes.c
//
// C template for printing the sizes and alignments of C structures.
// Used for debugging FFI layout mismatches with Rust.
// ==============================================================================

#include "qemu/osdep.h"
#include <stddef.h>
#include <stdio.h>

// Example: Include the header containing the structs you want to check
// #include "hw/remote-port/remote-port-proto.h"
// #include "net/can_emu.h"

int main() {
  printf("Add the structures you want to measure to "
         "tools/ffi_layout_check/print_sizes.c\n");

  /* Example usage:
  printf("CanBusClientState size: %zu, align: %zu\n", sizeof(CanBusClientState),
  _Alignof(CanBusClientState)); printf("CanBusClientInfo size: %zu, align:
  %zu\n", sizeof(CanBusClientInfo), _Alignof(CanBusClientInfo));
  printf("qemu_can_frame size: %zu, align: %zu\n", sizeof(qemu_can_frame),
  _Alignof(qemu_can_frame));
  */

  return 0;
}
