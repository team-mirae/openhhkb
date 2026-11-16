#!/usr/bin/env python3
"""Read or write the HHKB Hybrid keymap over the vendor HID protocol (interface 2).

Talks to the keyboard through `tools/passthrough/hidbridge` (a tiny hidapi line-protocol
bridge), so this script needs no native HID bindings itself.

    read  : dump the active profile's Standard + Fn layers (safe, read-only)
    set   : change one key, replicating the OFFICIAL tool's full apply sequence

WRITE SAFETY (repo ground rule): a `set` is a config write to a real keyboard. Only run it
with the user's explicit OK. It always prints a backup of the layer it is about to change.

Why the "full apply sequence" matters (learned 2026-11-17, see
analysis/firmware/hybrid-keycodes.md):
  * The keymap is stored PER keyboard-mode profile. The active profile is the mode byte from
    0x06 GetKeyboardMode (0x01 on the tested unit) -- NOT 0x00. Writing to 0x00 reads back
    fine but never changes live keys.
  * The official tool writes FOUR layers (keymap Std+Fn at `mode`, shortcut Std+Fn at
    `mode|0x10`), then 0x08 (sleep), 0x04 (ConfirmKeymap), 0x07 (ResetDIPSW, payload=mode).
    Skipping the shortcut layers or the 0x08/0x07 commit means the change is not applied.

Usage:
    hhkb_keymap.py <hidbridge> read
    hhkb_keymap.py <hidbridge> set <layer:std|fn> <pos:0-127> <value>   # value e.g. 0x78

Key positions: index 0 = bottom-right, 69 = top-left Esc, decreasing left-to-right per row.
P = 44. See analysis/hhkb-hybrid-jis/ for the full decode.
"""
import subprocess, sys

VID, PID, IFACE = "04fe", "0022", "2"   # HHKB Hybrid vendor interface


class Bridge:
    def __init__(self, path):
        self.p = subprocess.Popen([path, VID, PID, IFACE], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)
        line = self.p.stdout.readline().strip()
        if not line.startswith("READY"):
            raise SystemExit(f"hidbridge did not open the device: {line!r}")

    def xfer(self, req, nreplies=1):
        self.p.stdin.write("W " + bytes(req).hex().ljust(128, "0") + "\n")
        self.p.stdin.flush()
        out = []
        for _ in range(nreplies):
            while True:
                l = self.p.stdout.readline().strip()
                if l.startswith("R "):
                    out.append(bytes.fromhex(l[2:])); break
        return out

    def close(self):
        try:
            self.p.stdin.write("Q\n"); self.p.stdin.flush()
        except Exception:
            pass

    # --- protocol helpers -------------------------------------------------
    def reply_byte(self, cmd):
        """First payload byte of a simple query reply (e.g. 0x06 mode, 0x09 sleep)."""
        return self.xfer([0xAA, 0xAA, cmd, 0x00, 0x00])[0][6]

    def get_keymap(self, mode, fn):
        parts = self.xfer([0xAA, 0xAA, 0x87, 0x00, 0x02, mode, fn], nreplies=3)
        km = b""
        for p in parts:
            km += p[6:6 + p[5]]
        return bytearray(km)  # 128 bytes

    def set_keymap(self, mode, fn, km):
        assert len(km) == 128
        self.xfer([0xAA, 0xAA, 0x86, 0x41, 0x3B, mode, fn] + list(km[0:57]))
        self.xfer([0xAA, 0xAA, 0x86, 0x82, 0x3B] + list(km[57:116]))
        self.xfer([0xAA, 0xAA, 0x86, 0xC3, 0x0C] + list(km[116:128]))


def do_read(b):
    mode = b.reply_byte(0x06)
    print(f"active keyboard-mode profile = {mode:#04x}")
    for fn, name in ((0, "standard"), (1, "fn")):
        print(f"{name:8} = {b.get_keymap(mode, fn).hex()}")


def do_set(b, layer, pos, val):
    fn = {"std": 0, "fn": 1}[layer]
    mode = b.reply_byte(0x06)
    sleep = b.reply_byte(0x09)

    # Read all four layers of the active profile.
    s0 = b.get_keymap(mode, 0)
    s1 = b.get_keymap(mode, 1)
    t0 = b.get_keymap(mode | 0x10, 0)
    t1 = b.get_keymap(mode | 0x10, 1)
    target = s1 if fn else s0
    print(f"mode={mode:#04x}  backup {layer} = {bytes(target).hex()}")
    print(f"changing {layer}[{pos}] {target[pos]:#04x} -> {val:#04x}")
    target[pos] = val

    # Full apply sequence, exactly as the official tool drives it.
    b.xfer([0xAA, 0xAA, 0x01, 0x00, 0x01, 0x00])             # NotifyAppState(0)
    b.xfer([0xAA, 0xAA, 0x02, 0x00, 0x00])                   # GetKeyboardInfo
    b.xfer([0xAA, 0xAA, 0x05, 0x00, 0x00])                   # GetDipsw
    b.set_keymap(mode, 0, s0)
    b.set_keymap(mode, 1, s1)
    b.set_keymap(mode | 0x10, 0, t0)
    b.set_keymap(mode | 0x10, 1, t1)
    b.xfer([0xAA, 0xAA, 0x08, 0x00, 0x01, sleep])            # ResetSleepSetting (preserve)
    b.xfer([0xAA, 0xAA, 0x04, 0x00, 0x00])                   # ConfirmKeymap
    b.xfer([0xAA, 0xAA, 0x07, 0x00, 0x01, mode])             # ResetDIPSW (payload = mode)
    b.xfer([0xAA, 0xAA, 0x01, 0x00, 0x01, 0x01])             # NotifyAppState(1)

    back = b.get_keymap(mode, fn)[pos]
    ok = "OK" if back == val else "MISMATCH"
    print(f"readback {layer}[{pos}] = {back:#04x} ({ok})")


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    bridge, cmd = argv[1], argv[2]
    b = Bridge(bridge)
    try:
        if cmd == "read":
            do_read(b)
        elif cmd == "set":
            if len(argv) != 6:
                print("usage: set <std|fn> <pos> <value>"); return 2
            do_set(b, argv[3], int(argv[4]), int(argv[5], 0))
        else:
            print(f"unknown command {cmd!r}"); return 2
    finally:
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
