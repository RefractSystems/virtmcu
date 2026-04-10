# Lesson 8: Interactive UART and Multi-Node Deterministic Serial

In this lesson, we explore how to interact directly with a running `virtmcu` instance using serial (UART) communication, and how to extend that capability across multiple nodes deterministically.

## 1. The Interactive Echo Firmware

Up until now, our test firmware (like `hello.elf`) has simply printed a message and halted. In a real development scenario, you often need interactive access to the firmware (e.g., a CLI shell, debugging menu, or sensor polling).

We have developed a basic "Interactive UART Echo" firmware in `test/phase8/echo.S`. 

### Key Concepts:
1. **Hardware Initialization:** Before a bare-metal program can print, it must enable the UART peripheral by writing to its Control Register (e.g., setting the `UARTEN`, `TXE`, and `RXE` bits on the ARM PL011).
2. **Polling Loop:** The firmware continuously polls the UART Flag Register (`UART0_FR`) checking the Receive FIFO Empty (`RXFE`) bit. When data arrives, it reads the Data Register (`UART0_DR`) and writes it back to echo the character to the user.

### Running it Manually

You can boot this firmware and interact with it directly in your terminal using standard QEMU arguments.

```bash
# Compile the firmware
make -C test/phase8

# Run virtmcu with stdio mapped to the primary serial port
./scripts/run.sh --dtb test/phase1/minimal.dtb --kernel test/phase8/echo.elf -nographic
```

Once booted, you will see:
```
Interactive UART Echo Ready.
Type something: 
```
Any keys you press will be echoed back immediately by the emulated Cortex-A15 processor.

*(Press `Ctrl-A` then `x` to exit QEMU).*

## 2. Automated Testing of Interactive Firmware

To prevent regressions, interactive firmware must be tested using an automated harness. The virtmcu project provides a Python QMP (QEMU Machine Protocol) Bridge and Robot Framework keywords to achieve this.

### The `Write To UART` Keyword

In Phase 8, we extended the test harness with a `Write To UART` keyword. This allows the test script to simulate a user typing into the console.

Here is an example test from `tests/test_interactive_echo.robot`:

```robotframework
*** Test Cases ***
Interactive Echo Should Work
    # 1. Wait for welcome message
    Wait For Line On UART    Interactive UART Echo Ready.
    Wait For Line On UART    Type something:
    
    # 2. Simulate user typing
    Write To UART    Hello virtmcu\r
    
    # 3. Verify the firmware echoed it back
    Wait For Line On UART    Hello virtmcu
```

Notice how we boot QEMU with the `-S` (suspend) flag in the test setup:
```robotframework
Launch Qemu    ${DTB_PATH}    ${FIRMWARE}    extra_args=-S
```
This is critical. If we do not suspend the CPU on boot, the firmware will execute instantly, printing the welcome message to the socket *before* our test harness has connected to read it. By pausing QEMU, connecting our listeners, and *then* issuing `Start Emulation` (via QMP `cont`), we guarantee no data is lost.

## 3. Multi-Node Deterministic UART (Upcoming)

While interactive local debugging is useful, true system validation often requires multiple microcontrollers communicating with each other over serial connections (e.g., an MCU commanding a GPS module or a motor driver over UART).

In the next phase, we will implement `zenoh-chardev.c`. This native QEMU plugin will allow us to map the UART byte stream to Zenoh topics (e.g., `virtmcu/uart/node1/tx`), enabling cycle-accurate, deterministic serial communication between multiple emulated nodes across the network, just as we did with Ethernet in Phase 6.
