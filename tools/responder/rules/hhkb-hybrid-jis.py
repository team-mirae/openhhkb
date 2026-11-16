"""Reply rules for a virtual HHKB Professional Hybrid (JIS), as seen by the HHKB Keymap Tool 2.0.1.

Framing (from analysis/keymap-tools): request  AA AA <cmd> <chunk> <len> <payload...>   (64 B)
                                       reply    55 55 <cmd> <status> <chunk> <len> <payload...>   (64 B)
Everything below is a guess to be refined against the tool's behaviour. Edit freely: the responder reloads
this file on every change.
"""

import json
import pathlib

VENDOR_IF = 2
SIZE = 64


def pad(b):
    return bytes(b) + bytes(SIZE - len(b))


def reply(cmd, payload=b"", chunk=0x00, status=0x00):
    return pad([0x55, 0x55, cmd, status, chunk, len(payload)] + list(payload))


def ascii_field(s, n):
    return s.encode("ascii")[:n].ljust(n, b"\x00")


def keyboard_info(state):
    # Offsets are from the reply start, as parsed by HHKBDriver.command02GetKeyboardInformation():
    #   6..26 type number (string), 26..30 revision (string), 30..46 serial (string),
    #   46..50 app firmware version, 54..58 boot firmware version (UInt8ToVersion), 62 running firmware state.
    b = bytearray(SIZE)
    b[0:6] = bytes([0x55, 0x55, 0x02, 0x00, 0x00, 0x38])
    b[6:26] = ascii_field("PD-KB820BS", 20)
    b[26:30] = ascii_field("A", 4)
    b[30:46] = ascii_field("VHHKB0000000001", 16)
    # Version bytes print as "%X%x.%x%x": 0A 02 04 08 -> "A2.48". Latest for PD-KB820BS on PFU's update
    # server (HHKBVersion.json, 2026-11-16) is A2.49, so the tool should offer an update.
    b[46:50] = state.get("app_version", bytes([0x0A, 0x02, 0x04, 0x08]))
    b[54:58] = bytes([0x0A, 0x01, 0x00, 0x00])
    b[62] = 0x00
    return bytes(b)


FACTORY = pathlib.Path(__file__).resolve().parents[3] / "analysis/hhkb-hybrid-jis/factory-keymap.json"


def factory_keymap(mode_fn):
    """Factory default captured from the tool's factory reset; mode 0 only (fn byte 0 = Standard, 1 = Fn)."""
    if mode_fn[:1] == b"\x10":  # shortcut (modifier) map, read only for newer firmware (A2.48): none set
        return bytes(128)
    f = json.loads(FACTORY.read_text())
    return bytes.fromhex(f["fn"] if mode_fn[1:2] == b"\x01" else f["standard"])


def handle(iface, data, state):
    if iface != VENDOR_IF or len(data) < 5 or data[0:2] != b"\xaa\xaa":
        return []
    cmd, chunk, n = data[2], data[3], data[4]
    payload = data[5:5 + n]
    state.setdefault("seen", []).append(cmd)

    if cmd == 0x01:  # NotifyApplicationState
        return [(iface, reply(0x01))]
    if cmd == 0x02:  # GetKeyboardInformation
        return [(iface, keyboard_info(state))]
    if cmd == 0x04:  # ConfirmKeymap
        return [(iface, reply(0x04))]
    if cmd == 0x05:  # GetDipswInformation: 12 bytes
        return [(iface, reply(0x05, state.get("dipsw", bytes(12))))]
    if cmd == 0x06:  # GetKeyboardMode: 1 byte
        return [(iface, reply(0x06, bytes([state.get("mode", 0)])))]
    if cmd == 0x07:  # ResetDIPSW(keyboardMode)
        state["mode"] = payload[0] if payload else 0
        return [(iface, reply(0x07))]
    if cmd == 0x08:  # ResetSleepSetting
        state["sleep"] = payload[:1]
        return [(iface, reply(0x08))]
    if cmd == 0x09:  # GetSleepSetting: 1 byte
        return [(iface, reply(0x09, state.get("sleep", b"\x00")))]
    if cmd == 0x87:  # GetKeymap(mode, fn): 128 bytes in chunks of 58, 58, 12
        km = state.setdefault("keymap", {}).get(bytes(payload)) or factory_keymap(payload)
        return [(iface, reply(0x87, km[0:58], chunk=0x41)),
                (iface, reply(0x87, km[58:116], chunk=0x82)),
                (iface, reply(0x87, km[116:128], chunk=0xC3))]
    if cmd == 0x86:  # SetKeymap: chunk 0x41 = mode, fn + positions 0..56; 0x82 = 57..115; 0xC3 = 116..127
        if chunk == 0x41:
            state["write_key"] = bytes(payload[:2])
            state["write_buf"] = bytearray(payload[2:])
        else:
            state.setdefault("write_buf", bytearray()).extend(payload)
        if chunk == 0xC3 and len(state["write_buf"]) == 128:
            state.setdefault("keymap", {})[state["write_key"]] = bytes(state["write_buf"])
            print(f"=== stored keymap mode/fn {state['write_key'].hex()}")
        return [(iface, reply(0x86))]
    if cmd in (0xE0, 0xE1, 0xE2, 0xE3):  # firmware update: ack and record, never "flash" anything
        print(f"!!! firmware command {cmd:#04x} chunk={chunk:#04x} len={n} head={bytes(payload[:8]).hex()}")
        fw = state.setdefault("fw", bytearray())
        if cmd == 0xE1:
            state["fw_start"] = bytes(payload)
            fw.clear()
        elif cmd == 0xE2:
            fw.extend(data[7:5 + n])  # skip "aa aa e2 00 <len>" and the 2-byte block number
            # The tool expects "55 55 e2 00 00 02" + 2 bytes; it accepted any value there. Echo the block number.
            return [(iface, reply(0xE2, bytes(data[5:7])))]
        elif cmd == 0xE3:
            # Upload framing (captured 2026-11-16): E2 = "aa aa e2 00 <len> <block LE16> <len-2 data bytes>",
            # the concatenated data is the .hfb file minus its first 2 bytes (those go in E1 after the size).
            # The image ends with "<model id> 0a <version 4 B>", e.g. "AHJX01\n" 0a 02 04 09 = A2.49.
            out = FACTORY.parent / "captures" / f"firmware-upload-{len(fw)}B.bin"  # git-ignored (vendor binary)
            out.write_bytes(bytes(fw))
            tail = bytes(fw).rstrip(b"\x00").rstrip(b"\xff")
            if len(tail) >= 4:
                state["app_version"] = tail[-4:]  # pretend the flash succeeded: report the new version
            print(f"=== wrote {out.name}; now reporting version {state.get('app_version', b'').hex()}")
        return [(iface, reply(cmd))]
    print(f"??? unknown command {cmd:#04x}")
    return []
