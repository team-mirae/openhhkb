"""Reply rules for a virtual HHKB Studio (JIS), as seen by the HHKB Studio Keymap Tool 1.1.2.

The tool uses VIA command IDs on the raw HID interface (0xFF60/0x61, 32 B, interface 1). VIA firmware replies by
echoing the 32-byte request with the requested data filled in, so the default reply is an echo. Values are guesses
to be refined against the tool's behaviour. Edit freely: the responder reloads this file on every change.
"""

RAW_IF = 1
SIZE = 32


def echo(data, fill=None, at=3):
    b = bytearray(data[:SIZE].ljust(SIZE, b"\x00"))
    if fill:
        b[at:at + len(fill)] = fill
    return bytes(b)


def handle(iface, data, state):
    if iface != RAW_IF or not data:
        return []
    cmd = data[0]
    state.setdefault("seen", []).append(data[:4].hex())

    if cmd == 0x02:  # id_get_keyboard_value; data[1] = PFU value id (0x10 info, 0x11 settings)
        return [(iface, echo(data))]
    if cmd == 0x03:  # id_set_keyboard_value
        state.setdefault("set", []).append(bytes(data))
        return [(iface, echo(data))]
    if cmd == 0x12:  # id_dynamic_keymap_get_buffer: offset(BE16) size
        return [(iface, echo(data))]
    if cmd == 0x13:  # id_dynamic_keymap_set_buffer
        state.setdefault("keymap_write", []).append(bytes(data))
        return [(iface, echo(data))]
    if cmd == 0x0B:  # id_bootloader_jump: log loudly, do not change mode yet
        print("!!! bootloader jump requested")
        return [(iface, echo(data))]
    print(f"??? unknown command {cmd:#04x}")
    return [(iface, echo(data))]
