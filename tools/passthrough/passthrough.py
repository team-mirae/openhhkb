#!/usr/bin/env python3
"""Logging HID passthrough: a vendor tool in the VM talks to the REAL keyboard on the host.

    VM: REALFORCE CONNECT -> virtual device (vhhkb)  <--SSH-->  this script  <-->  hidbridge -> real keyboard

Every report is logged. Reads pass through to the real device so the tool connects for real; writes are
GUARDED: keymap writes and firmware-flash commands are blocked (logged + a synthetic ack returned) unless
explicitly enabled, so nothing is written to the real keyboard by accident.

    python3 tools/passthrough/passthrough.py realforce-x1p-jp-tkl
    PASSTHROUGH_ALLOW_WRITES=1    also forward config writes to the real device
    PASSTHROUGH_ALLOW_FIRMWARE=1  also forward firmware-flash commands (DANGER: real flash)

Needs the host-side bridge built at tools/passthrough/hidbridge (or $HIDBRIDGE).
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
VM = os.environ.get("VM", "admin@192.168.64.3")
PASSWORD = os.environ.get("VHHKB_PASSWORD", "admin")
VM_BIN = "~/vhhkb/vhhkb"
HIDBRIDGE = os.environ.get("HIDBRIDGE", str(ROOT / "tools/passthrough/hidbridge"))
ALLOW_WRITES = os.environ.get("PASSTHROUGH_ALLOW_WRITES") == "1"
ALLOW_FIRMWARE = os.environ.get("PASSTHROUGH_ALLOW_FIRMWARE") == "1"
FAKE_OLD_VERSION = os.environ.get("FAKE_OLD_VERSION") == "1"


def rewrite_reply(data):
    """Optionally report an older firmware so the tool offers an update.
    getDeviceInfo (cmd 0x02) reply: 55 55 02 00 00 0c <model...> <ver@[14:18]>. The real X1P reports
    A1.13; set the low version bytes to 0 -> A1.00 (100 < latest 113) to enable the update menu."""
    if FAKE_OLD_VERSION and len(data) >= 18 and data[2] == 0x02:
        d = bytearray(data)
        d[16] = 0x00
        d[17] = 0x00
        return bytes(d), True
    return data, False

# vendor command guard (REALFORCE/HHKB protocol): block writes by default
FIRMWARE_CMDS = {0xE0, 0xE1, 0xE2, 0xE3}
WRITE_CMDS = {0xC2, 0xC8}  # romWrite / romWrite2


def ssh_base():
    askpass = pathlib.Path(tempfile.gettempdir()) / "vhhkb-askpass.sh"
    askpass.write_text(f"#!/bin/sh\necho '{PASSWORD}'\n")
    askpass.chmod(0o700)
    env = dict(os.environ, SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE="force", DISPLAY="x")
    opts = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]
    return ["ssh", *opts, VM], env


def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "realforce-x1p-jp-tkl"
    profile = json.loads((ROOT / "tools/responder/profiles" / f"{device}.json").read_text())
    vid = int(profile["vid"], 16)
    pid = int(profile["pid"], 16)
    capdir = ROOT / "analysis" / device / "captures"
    capdir.mkdir(parents=True, exist_ok=True)
    logpath = capdir / f"{dt.datetime.now():%Y%m%d-%H%M%S}-passthrough.jsonl"
    log = logpath.open("a")
    t0 = time.monotonic()

    def record(direction, data, **extra):
        rec = {"t": round(time.monotonic() - t0, 4), "dir": direction, "hex": data.hex(), **extra}
        log.write(json.dumps(rec) + "\n")
        log.flush()
        print(f"{rec['t']:9.3f} {direction:9} {data[:16].hex(' ')}{'' if len(data) <= 16 else ' ...'}"
              + (f"  [{extra.get('note')}]" if extra.get("note") else ""), flush=True)

    # host bridge to the real keyboard (interface 2 = vendor channel)
    bridge = subprocess.Popen([HIDBRIDGE, f"{vid:04x}", f"{pid:04x}", "2"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    ready = bridge.stdout.readline().strip()
    if not ready.startswith("READY"):
        print(f"[bridge] did not open real device: {ready}", file=sys.stderr)
        sys.exit(1)
    print(f"[bridge] real device: {ready[6:]}", file=sys.stderr)
    print(f"[guard] writes={'ON' if ALLOW_WRITES else 'BLOCKED'} firmware={'ON' if ALLOW_FIRMWARE else 'BLOCKED'}",
          file=sys.stderr)

    # vhhkb in the VM presents the virtual device to CONNECT
    cmd, env = ssh_base()
    vm = subprocess.Popen(cmd + [VM_BIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env, bufsize=1)
    vm_lock = threading.Lock()

    def vm_send(line):
        with vm_lock:
            vm.stdin.write(line + "\n")
            vm.stdin.flush()

    for iface in profile["interfaces"]:
        desc = (ROOT / iface["descriptor"]).read_bytes()
        vm_send("\t".join(str(x) for x in ["DEV", iface["n"], profile["vid"], profile["pid"], profile["version"],
                                           profile["location"], profile["product"], profile["manufacturer"], desc.hex()]))
    vm_send("GO")
    print(f"[passthrough] {device}: logging to {logpath.relative_to(ROOT)}", file=sys.stderr)

    bridge_lock = threading.Lock()
    pending = []  # reply reports from the real device waiting to go back to the VM

    def bridge_reader():
        for line in bridge.stdout:
            line = line.strip()
            if line.startswith("R "):
                data = bytes.fromhex(line[2:])
                data, rewritten = rewrite_reply(data)
                record("real->in", data, note="version rewritten -> A1.00" if rewritten else None)
                vm_send(f"IN\t2\t{data.hex()}")
            elif line:
                print(f"[bridge] {line}", file=sys.stderr)

    threading.Thread(target=bridge_reader, daemon=True).start()

    try:
        for line in vm.stdout:
            f = line.rstrip("\n").split("\t")
            if f[0] == "OUT" and len(f) >= 5 and int(f[1]) == 2:
                data = bytes.fromhex(f[4])
                cmd_id = data[2] if len(data) > 2 else -1
                blocked = (cmd_id in FIRMWARE_CMDS and not ALLOW_FIRMWARE) or \
                          (cmd_id in WRITE_CMDS and not ALLOW_WRITES)
                if blocked:
                    kind = "firmware" if cmd_id in FIRMWARE_CMDS else "write"
                    record("out-BLOCKED", data, note=f"{kind} cmd {cmd_id:#04x} not sent to real device")
                    # synthetic ack so the tool does not hang
                    ack = bytes([0x55, 0x55, cmd_id, 0x00, 0x00, 0x00]) + bytes(58)
                    vm_send(f"IN\t2\t{ack.hex()}")
                else:
                    record("out->real", data)
                    with bridge_lock:
                        bridge.stdin.write("W " + data.hex() + "\n")
                        bridge.stdin.flush()
            elif f[0] in ("READY", "GET", "ERR"):
                print(f"[vhhkb] {' '.join(f)}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bridge.stdin.write("Q\n")
            bridge.stdin.flush()
        except Exception:
            pass
        vm.terminate()
        bridge.terminate()
        log.close()


if __name__ == "__main__":
    main()
