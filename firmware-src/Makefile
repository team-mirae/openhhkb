# openhhkb clean-room firmware.
#   make test   - build the host CLI and run the protocol test suite
#   make gen    - regenerate the default keymap header from the capture analysis
# The STM32F0 target (startup, linker, USB) is added once the host core is validated.

ROOT := $(abspath ..)
SRC := src
BUILD := build
HOSTCC ?= cc
HOSTCFLAGS := -std=c11 -Wall -Wextra -Werror -I$(SRC)

.PHONY: test gen clean
gen:
	python3 gen/make_default_keymap.py

$(BUILD)/hhkb_cli: $(SRC)/hhkb_proto.c $(SRC)/hhkb_proto.h $(SRC)/default_keymap.h test/hhkb_cli.c | $(BUILD)
	$(HOSTCC) $(HOSTCFLAGS) $(SRC)/hhkb_proto.c test/hhkb_cli.c -o $@

$(BUILD):
	mkdir -p $(BUILD)

test: $(BUILD)/hhkb_cli
	python3 test/run_tests.py

clean:
	rm -rf $(BUILD)
