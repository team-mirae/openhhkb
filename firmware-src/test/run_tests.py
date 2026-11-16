#!/usr/bin/env python3
"""Host tests for the openhhkb protocol core, driving build/hhkb_cli.

1. structural replay: feed every captured tool->device report to the core and check the reply
   header matches what the real tool accepted (same cmd/status/chunk/len bytes).
2. keymap round-trip: SetKeymap then GetKeymap returns what was written.
3. default marker: GetKeymap(standard) shows A S D F -> H H K B, Z / \\ preserved.
4. firmware receiver: feed the real vendor .hfb as E1/E2/E3 and check the receiver reassembles
   it byte-exact (the "accept the vendor binary" requirement). Skipped if the file is absent.
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / "firmware-src/build/hhkb_cli"
CAP = ROOT / "analysis/hhkb-hybrid-jis/captures/20261116-223229.jsonl"
VENDOR = ROOT / "firmware/HHKB820_FW_JP_A249.hfb"
RLEN = 64
fails = []


class Core:
    def __init__(self):
        self.p = subprocess.Popen([str(CLI)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def cmd(self, s):
        self.p.stdin.write(s + "\n"); self.p.stdin.flush()
        return self.p.stdout.readline().strip()

    def handle(self, req_hex):
        n = int(self.cmd(req_hex))
        return [self.p.stdout.readline().strip() for _ in range(n)]

    def dumpfw(self):
        self.p.stdin.write("DUMPFW\n"); self.p.stdin.flush()
        return bytes.fromhex(self.p.stdout.readline().strip())

    def reset(self):
        self.cmd("RESET")


def check(cond, msg):
    if not cond:
        fails.append(msg)
    print(("  ok  " if cond else " FAIL ") + msg)


def test_replay(core):
    print("[1] structural replay of captured traffic")
    recs = [json.loads(l) for l in CAP.open()]
    outs = [r for r in recs if r.get("dir") == "out" and r.get("if") == 2]
    # pair each request with the reply(ies) the responder served (consecutive 'in' lines)
    reqs = []
    i = 0
    while i < len(recs):
        r = recs[i]
        if r.get("dir") == "out" and r.get("if") == 2:
            j = i + 1
            served = []
            while j < len(recs) and recs[j].get("dir") == "in" and recs[j].get("if") == 2:
                served.append(bytes.fromhex(recs[j]["hex"])); j += 1
            reqs.append((bytes.fromhex(r["hex"][:14]) if r.get("redacted") else bytes.fromhex(r["hex"]), served))
            i = j
        else:
            i += 1
    core.reset()
    seen_cmds = set()
    mismatch = 0
    for req, served in reqs:
        if len(req) < 5:
            continue
        cmd = req[2]
        seen_cmds.add(cmd)
        # firmware block data bytes are redacted in the capture, so only check header for E2
        replies = core.handle(req.hex().ljust(RLEN * 2, "0"))
        if cmd == 0xE2:
            # header 55 55 e2 00 00 02 only
            check(replies and bytes.fromhex(replies[0])[:6] == bytes([0x55, 0x55, 0xE2, 0, 0, 2]),
                  "E2 reply header") if req is reqs[0][0] else None
            continue
        if not served:
            continue
        # compare reply count and the 6-byte header of each reply with what the tool accepted
        if len(replies) != len(served):
            mismatch += 1
            fails.append(f"cmd {cmd:#04x}: reply count {len(replies)} != served {len(served)}")
            continue
        for got_hex, want in zip(replies, served):
            got = bytes.fromhex(got_hex)
            if got[:6] != want[:6]:
                mismatch += 1
                fails.append(f"cmd {cmd:#04x}: header {got[:6].hex()} != {want[:6].hex()}")
    check(mismatch == 0, f"all reply headers match captured ({len(reqs)} requests, cmds "
          + " ".join(f"{c:#04x}" for c in sorted(seen_cmds)) + ")")


def test_roundtrip(core):
    print("[2] keymap write/read round-trip")
    core.reset()
    km = bytes((i * 7 + 3) & 0x7F for i in range(128))
    # SetKeymap standard (mode 0, fn 0): 3 chunks
    c1 = bytes([0xAA, 0xAA, 0x86, 0x41, 0x3B, 0x00, 0x00]) + km[0:57]
    c2 = bytes([0xAA, 0xAA, 0x86, 0x82, 0x3B]) + km[57:116]
    c3 = bytes([0xAA, 0xAA, 0x86, 0xC3, 0x0C]) + km[116:128]
    for c in (c1, c2, c3):
        core.handle(c.hex().ljust(RLEN * 2, "0"))
    rep = core.handle(bytes([0xAA, 0xAA, 0x87, 0x00, 0x02, 0x00, 0x00]).hex().ljust(RLEN * 2, "0"))
    got = b"".join(bytes.fromhex(r)[6:6 + l] for r, l in zip(rep, (58, 58, 12)))
    check(got == km, "GetKeymap returns what SetKeymap wrote")


def test_default(core):
    print("[3] default marker ASDF->HHKB, Z / \\ preserved")
    core.reset()
    rep = core.handle(bytes([0xAA, 0xAA, 0x87, 0x00, 0x02, 0x00, 0x00]).hex().ljust(RLEN * 2, "0"))
    km = b"".join(bytes.fromhex(r)[6:6 + l] for r, l in zip(rep, (58, 58, 12)))
    # A=pos39 S=38 D=37 F=36 -> H(0x0b) H(0x0b) K(0x0e) B(0x05); Z=26=0x1d /=17=0x38 \\=16=0x87
    check(km[39] == 0x0B and km[38] == 0x0B and km[37] == 0x0E and km[36] == 0x05, "A S D F -> H H K B")
    check(km[26] == 0x1D and km[17] == 0x38 and km[16] == 0x87, "Z / \\ preserved")


def test_firmware(core):
    print("[4] firmware update receiver reassembles the vendor .hfb")
    if not VENDOR.exists():
        print("  skip  vendor firmware not present (" + str(VENDOR.relative_to(ROOT)) + ")")
        return
    f = VENDOR.read_bytes()
    core.reset()
    core.handle(bytes([0xAA, 0xAA, 0xE0, 0, 0, 0]).hex().ljust(RLEN * 2, "0"))
    # E1: size LE32 + first 2 bytes of file
    e1 = bytes([0xAA, 0xAA, 0xE1, 0x00, 0x08]) + len(f).to_bytes(4, "little") + f[0:2]
    core.handle(e1.hex().ljust(RLEN * 2, "0"))
    # E2 blocks: 57 data bytes each, starting at file[2:]
    data = f[2:]
    block = 0
    off = 0
    while off < len(data):
        chunk = data[off:off + 57]
        body = block.to_bytes(2, "little") + chunk
        e2 = bytes([0xAA, 0xAA, 0xE2, 0x00, len(body)]) + body
        core.handle(e2.hex().ljust(RLEN * 2, "0"))
        off += 57
        block += 1
    core.handle(bytes([0xAA, 0xAA, 0xE3, 0, 0, 0]).hex().ljust(RLEN * 2, "0"))
    got = core.dumpfw()
    check(got == f, f"reassembled image == vendor file ({len(got)}/{len(f)} bytes, {block} blocks)")


def test_descriptors():
    print("[5] USB descriptor consistency")
    import re
    hdr = (ROOT / "firmware-src/src/usb_descriptors.h").read_text()
    arr = {}
    for m in re.finditer(r"usb_\w+|hid_report\d", hdr):
        pass
    for name in ("usb_device_desc", "usb_config_desc", "hid_report0", "hid_report1", "hid_report2"):
        m = re.search(name + r"\[\d+\] = \{([0-9,]+)\}", hdr)
        arr[name] = bytes(int(x) for x in m.group(1).split(","))
    dev, cfg = arr["usb_device_desc"], arr["usb_config_desc"]
    check(dev[8] | (dev[9] << 8) == 0x04FE and dev[10] | (dev[11] << 8) == 0x0022, "device VID:PID 04fe:0022")
    check((cfg[2] | (cfg[3] << 8)) == len(cfg), "config wTotalLength == actual length")
    # report descriptors match the captured .bin
    for i in (0, 1, 2):
        b = (ROOT / f"analysis/hhkb-hybrid-jis/report-descriptors/input{i}.bin").read_bytes()
        check(arr[f"hid_report{i}"] == b, f"hid_report{i} matches captured descriptor")
    # walk config: each HID descriptor's wDescriptorLength == its report length
    i = 9
    cur_iface = None
    ok = True
    while i < len(cfg):
        blen, btype = cfg[i], cfg[i + 1]
        if btype == 0x04:
            cur_iface = cfg[i + 2]
        elif btype == 0x21:
            wlen = cfg[i + 7] | (cfg[i + 8] << 8)
            if wlen != len(arr[f"hid_report{cur_iface}"]):
                ok = False
        i += blen
    check(ok, "HID wDescriptorLength matches each report descriptor")


def test_crc(core):
    print("[6] .hfb CRC-16 matches vendor images (C implementation)")
    fw = ROOT / "firmware"
    files = sorted(fw.glob("*.hfb"))
    if not files:
        print("  skip  no vendor .hfb present")
        return
    for f in files:
        d = f.read_bytes()
        stored = d[0] | (d[1] << 8)
        got = core.cmd(f"CRCFILE {f}")
        check(int(got, 16) == stored, f"{f.name}: C CRC {got} == stored {stored:04x}")


def main():
    if not CLI.exists():
        print("build hhkb_cli first (make -C firmware-src test)"); sys.exit(2)
    core = Core()
    test_replay(core)
    test_roundtrip(core)
    test_default(core)
    test_firmware(core)
    test_descriptors()
    test_crc(core)
    print()
    if fails:
        print(f"{len(fails)} FAILURE(S):")
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print("all tests passed")


if __name__ == "__main__":
    main()
