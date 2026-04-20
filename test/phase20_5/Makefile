# ==============================================================================
# Makefile (Phase 20.5)
# ==============================================================================

CC = arm-none-eabi-gcc
CFLAGS = -mcpu=cortex-a15 -nostdlib -g
LDFLAGS = -T linker.ld

all: spi_echo.elf

spi_echo.elf: spi_echo.S linker.ld
	$(CC) $(CFLAGS) $(LDFLAGS) spi_echo.S -o spi_echo.elf

clean:
	rm -f *.elf
