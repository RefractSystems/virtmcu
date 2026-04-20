.section .text
.global _start
_start:
    ldr r0, =0x10000000
    ldr r1, =0xDEADBEEF
    str r1, [r0]
    ldr r0, =0x10000004
    ldr r1, =0xCAFEBABE
    str r1, [r0]

    /* ARM Semihosting Exit: SYS_EXIT (0x18) with ApplicationExit (0x20026) */
    mov r0, #0x18
    ldr r1, =0x20026
    svc #0x123456

loop:
    b loop
