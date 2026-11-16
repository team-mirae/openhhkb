# openhhkb clean-room firmware.
#   make test   - build the host CLI and run the protocol test suite
#   make gen    - regenerate the default keymap header from the capture analysis
# The STM32F0 target (startup, linker, USB) is added once the host core is validated.

ROOT := $(abspath ..)
SRC := src
BUILD := build
HOSTCC ?= cc
HOSTCFLAGS := -std=c11 -Wall -Wextra -Werror -I$(SRC)

# STM32F0 target
CROSS := arm-none-eabi-
TCC := $(CROSS)gcc
TOBJCOPY := $(CROSS)objcopy
TSIZE := $(CROSS)size
MCUFLAGS := -mcpu=cortex-m0 -mthumb
TCFLAGS := $(MCUFLAGS) -std=c11 -Os -ffreestanding -fno-jump-tables -ffunction-sections -fdata-sections \
           -Wall -Wextra -I$(SRC) -Itarget
TLDFLAGS := $(MCUFLAGS) -T target/stm32f072.ld -nostdlib -Wl,--gc-sections -Wl,-Map,$(BUILD)/hhkb_fw.map
FW_SRC := $(SRC)/hhkb_proto.c target/main.c target/startup_stm32f0.c target/flash_stm32f0.c \
          target/usb_stm32f0.c target/board_stub.c

.PHONY: test gen clean fw qemu
gen:
	python3 gen/make_default_keymap.py
	python3 gen/make_descriptors.py

$(BUILD)/hhkb_cli: $(SRC)/hhkb_proto.c $(SRC)/hhkb_proto.h $(SRC)/default_keymap.h test/hhkb_cli.c | $(BUILD)
	$(HOSTCC) $(HOSTCFLAGS) $(SRC)/hhkb_proto.c test/hhkb_cli.c -o $@

$(BUILD):
	mkdir -p $(BUILD)

test: $(BUILD)/hhkb_cli
	python3 test/run_tests.py

fw: $(BUILD)/hhkb_fw.bin
$(BUILD)/hhkb_fw.bin: $(FW_SRC) target/stm32f072.ld $(SRC)/hhkb_proto.h target/hhkb_board.h src/default_keymap.h src/usb_descriptors.h | $(BUILD)
	$(TCC) $(TCFLAGS) $(TLDFLAGS) $(FW_SRC) -o $(BUILD)/hhkb_fw.elf
	$(TOBJCOPY) -O binary $(BUILD)/hhkb_fw.elf $@
	$(TSIZE) $(BUILD)/hhkb_fw.elf

QEMU_SRC := $(SRC)/hhkb_proto.c target/qemu/qemu_test.c
qemu: | $(BUILD)
	$(TCC) $(MCUFLAGS) -std=c11 -Os -ffreestanding -fno-jump-tables -nostdlib -I$(SRC) \
	  -T target/qemu/qemu.ld $(QEMU_SRC) -o $(BUILD)/qemu_test.elf
	qemu-system-arm -machine microbit -semihosting -nographic -kernel $(BUILD)/qemu_test.elf \
	  2>&1 | tee $(BUILD)/qemu.out; grep -q "RESULT: PASS" $(BUILD)/qemu.out

clean:
	rm -rf $(BUILD)
