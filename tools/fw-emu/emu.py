#!/usr/bin/env python3
"""Emulate the HHKB Hybrid main MCU (STM32F0 / Cortex-M0) and run its firmware under Unicorn.

Full boot-to-working-keyboard is NOT possible (no USB-FS peripheral, no Topre analog sensing models). This
runs the CPU with stubbed peripheral MMIO so we can trace the firmware's code and analyse specific routines
(e.g. the keymap -> HID report path). The .hfb is a multi-part container; the Cortex-M0 app is its first chunk,
loaded at 0x08010000.

    tools/fw-emu/emu.py firmware/HHKB820_FW_JP_A249.hfb [--trace N] [--pc 0xADDR] [--maxinsn N]

Memory map: FLASH 0x08000000 (app at 0x08010000), RAM 0x20000000 (32 KB), peripherals 0x40000000/0x48000000,
PPB 0xE0000000. Peripheral reads return 0xFFFFFFFF (so active-high "ready" flags pass); writes are logged.
"""
import argparse
import struct
from unicorn import *
from unicorn.arm_const import *
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

FLASH_BASE, FLASH_SIZE = 0x08000000, 0x00080000  # 512 KB window (covers app + trailing blobs)
RAM_BASE, RAM_SIZE = 0x20000000, 0x00008000      # 32 KB
PERI1_BASE, PERI1_SIZE = 0x40000000, 0x00100000
PERI2_BASE, PERI2_SIZE = 0x48000000, 0x00002000
PPB_BASE, PPB_SIZE = 0xE0000000, 0x00100000
LOAD_ADDR = 0x08010000

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("firmware")
    ap.add_argument("--trace", type=int, default=40, help="disassemble the first N instructions")
    ap.add_argument("--pc", type=lambda x: int(x, 0), default=None, help="start PC (default: reset vector)")
    ap.add_argument("--maxinsn", type=int, default=200000)
    args = ap.parse_args()

    img = open(args.firmware, "rb").read()
    if img[:2] != b"\x24\x41" and img[4:8] == b"":
        pass
    img = img[4:]  # strip the 2-byte CRC + 2-byte .hfb header -> raw ARM image

    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.mem_map(FLASH_BASE, FLASH_SIZE)
    uc.mem_map(RAM_BASE, RAM_SIZE)
    uc.mem_map(PERI1_BASE, PERI1_SIZE)
    uc.mem_map(PERI2_BASE, PERI2_SIZE)
    uc.mem_map(PPB_BASE, PPB_SIZE)
    uc.mem_write(LOAD_ADDR, img)

    sp = struct.unpack("<I", img[0:4])[0]
    reset = struct.unpack("<I", img[4:8])[0]
    pc = args.pc if args.pc is not None else reset

    state = {"n": 0, "last_pc": None, "same": 0, "stop": None}
    peri_writes = []

    def hook_code(uc, address, size, user):
        state["n"] += 1
        if address == state["last_pc"]:
            state["same"] += 1
            if state["same"] > 5000:
                state["stop"] = f"tight loop at {address:#010x}"
                uc.emu_stop()
        else:
            state["same"] = 0
        state["last_pc"] = address
        if state["n"] <= args.trace:
            code = uc.mem_read(address, size)
            for insn in md.disasm(bytes(code), address):
                print(f"  {insn.address:#010x}: {insn.mnemonic:<8}{insn.op_str}")

    def hook_read(uc, access, address, size, value, user):
        return  # value already defaulted; we override via UC_HOOK_MEM_READ below

    def hook_peri_read(uc, access, address, size, value, user):
        uc.mem_write(address, b"\xff" * size)  # active-high ready bits
        return True

    def hook_peri_write(uc, access, address, size, value, user):
        peri_writes.append((address, value))
        return True

    unmapped = []

    def hook_unmapped(uc, access, address, size, value, user):
        page = address & ~0xFFF
        try:
            uc.mem_map(page, 0x1000)
            unmapped.append((address, access))
        except UcError:
            pass
        return True  # retry the access now that the page exists

    uc.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED | UC_HOOK_MEM_FETCH_UNMAPPED,
                hook_unmapped)
    uc.hook_add(UC_HOOK_CODE, hook_code)
    for base, sz in ((PERI1_BASE, PERI1_SIZE), (PERI2_BASE, PERI2_SIZE)):
        uc.hook_add(UC_HOOK_MEM_READ, hook_peri_read, begin=base, end=base + sz)
        uc.hook_add(UC_HOOK_MEM_WRITE, hook_peri_write, begin=base, end=base + sz)

    uc.reg_write(UC_ARM_REG_SP, sp)
    print(f"SP={sp:#010x} reset={reset:#010x} start_pc={pc:#010x}")
    print("--- trace ---")
    try:
        uc.emu_start(pc | 1, 0, count=args.maxinsn)
        state["stop"] = state["stop"] or "count/limit reached"
    except UcError as e:
        state["stop"] = f"fault: {e} at pc={uc.reg_read(UC_ARM_REG_PC):#010x}"

    print(f"--- stopped: {state['stop']}  (instructions executed: {state['n']}) ---")
    print(f"peripheral writes: {len(peri_writes)} (first few):")
    for a, v in peri_writes[:12]:
        print(f"    [{a:#010x}] <- {v:#010x}")
    if unmapped:
        regions = sorted({a & ~0xFFF for a, _ in unmapped})
        print(f"auto-mapped {len(regions)} unmapped page(s): " + ", ".join(f"{r:#010x}" for r in regions))


if __name__ == "__main__":
    main()
