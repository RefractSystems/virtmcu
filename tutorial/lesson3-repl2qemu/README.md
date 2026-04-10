# Lesson 3: Parsing Renode `.repl` Platforms to QEMU Device Trees

Welcome to Lesson 3! In this tutorial, you will learn how qenode bridges the gap between Renode's human-readable platform descriptions (`.repl` files) and QEMU's internal Object Model.

## The Problem
In Lesson 1, we manually wrote a Device Tree Source (`.dts`) file to instantiate our machine. While Device Trees are powerful and standard in the Linux kernel world, they are incredibly verbose and focus heavily on physical bus addressing rather than high-level system architecture.

Renode uses a much cleaner, indentation-based format called REPL (REnode PLatform).
```repl
memory: Memory.MappedMemory @ sysbus 0x40000000
    size: 0x08000000

uart0: UART.PL011 @ sysbus 0x09000000
    -> gic@1
```

## The Solution: `repl2qemu`
To get the best of both worlds—Renode's clean syntax and QEMU's execution speed—we developed the `repl2qemu` offline translation tool.

It performs a three-step pipeline:
1. **Parser (`parser.py`)**: Uses a regex-based state machine to extract devices, memory addresses, properties, and interrupt mappings from the `.repl` file, ignoring complex inline initializations.
2. **Emitter (`fdt_emitter.py`)**: Translates the parsed AST into a valid QEMU Device Tree (`.dts`), mapping Renode class names (e.g., `UART.PL011`) directly to QEMU QOM type names (e.g., `pl011`). It injects required QEMU-specific scaffolding like `qemu:system-memory`.
3. **Compiler**: Invokes the standard `dtc` (Device Tree Compiler) to produce the binary `.dtb` blob that `arm-generic-fdt` expects.

## Part 1: Try the Translator

In the `test/phase3/` directory, there is a `test_board.repl` file that describes our standard Cortex-A15 board with 128MB of RAM and a PL011 UART.

Run the translation tool from the repository root:
```bash
source .venv/bin/activate
python3 tools/repl2qemu/__main__.py test/phase3/test_board.repl --out-dtb test_board.dtb --print-cmd
```

You will see output indicating that the devices were parsed, the DTS was generated, and compiled. It also prints the equivalent QEMU command line!

## Part 2: Boot the Generated Machine

Now, boot the translated machine using the `hello.elf` kernel we compiled in Lesson 1:

```bash
./scripts/run.sh --dtb test_board.dtb --kernel test/phase1/hello.elf -nographic
```

You should see `HI` printed to the console!

## Summary
You have successfully taken a Renode `.repl` file, translated it into a native QEMU Device Tree, and booted a bare-metal kernel on the resulting dynamic machine. This process forms the foundation of qenode's hardware definition pipeline.