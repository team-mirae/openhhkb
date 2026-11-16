"""Reply rules for a virtual HHKB Professional Hybrid (JIS), as seen by the HHKB Keymap Tool 2.0.1.

Framing (from analysis/keymap-tools): request  AA AA <cmd> <chunk> <len> <payload...>   (64 B)
                                       reply    55 55 <cmd> <status> <chunk> <len> <payload...>   (64 B)
Everything below is a guess to be refined against the tool's behaviour. Edit freely: the responder reloads
this file on every change.
"""

VENDOR_IF = 2
SIZE = 64


def pad(b):
    return bytes(b) + bytes(SIZE - len(b))


def reply(cmd, payload=b"", chunk=0x00, status=0x00):
    return pad([0x55, 0x55, cmd, status, chunk, len(payload)] + list(payload))


def ascii_field(s, n):
    return s.encode("ascii")[:n].ljust(n, b"\x00")


def keyboard_info():
    # Offsets are from the reply start, as parsed by HHKBDriver.command02GetKeyboardInformation():
    #   6..26 type number (string), 26..30 revision (string), 30..46 serial (string),
    #   46..50 app firmware version, 54..58 boot firmware version (UInt8ToVersion), 62 running firmware state.
    b = bytearray(SIZE)
    b[0:6] = bytes([0x55, 0x55, 0x02, 0x00, 0x00, 0x38])
    b[6:26] = ascii_field("PD-KB820BS", 20)
    b[26:30] = ascii_field("A", 4)
    b[30:46] = ascii_field("VHHKB0000000001", 16)
    b[46:50] = bytes([1, 0, 0, 0])
    b[54:58] = bytes([1, 0, 0, 0])
    b[62] = 0x00
    return bytes(b)


def handle(iface, data, state):
    if iface != VENDOR_IF or len(data) < 5 or data[0:2] != b"\xaa\xaa":
        return []
    cmd, chunk, n = data[2], data[3], data[4]
    payload = data[5:5 + n]
    state.setdefault("seen", []).append(cmd)

    if cmd == 0x01:  # NotifyApplicationState
        return [(iface, reply(0x01))]
    if cmd == 0x02:  # GetKeyboardInformation
        return [(iface, keyboard_info())]
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
        # Probe: position i holds code (i + 1) so the tool's labels reveal the encoding.
        km = state.setdefault("keymap", {}).get(bytes(payload), bytes(range(1, 129)))
        return [(iface, reply(0x87, km[0:58], chunk=0x41)),
                (iface, reply(0x87, km[58:116], chunk=0x82)),
                (iface, reply(0x87, km[116:128], chunk=0xC3))]
    if cmd == 0x86:  # SetKeymap chunk: store, ack each chunk
        state.setdefault("keymap_write", []).append(bytes(data))
        return [(iface, reply(0x86))]
    if cmd in (0xE0, 0xE1, 0xE2, 0xE3):  # firmware update: ack only, never "flash" anything
        print(f"!!! firmware command {cmd:#04x} chunk={chunk:#04x} len={n}")
        return [(iface, reply(cmd))]
    print(f"??? unknown command {cmd:#04x}")
    return []
