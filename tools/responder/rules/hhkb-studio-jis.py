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


# Probe: marker strings so the tool's log shows which reply feeds which field.
# Parser (static): 0x01/0x03/0x05 -> 27-byte string at offset 3; 0x0B -> 4-byte string at 3; 0x07 -> 2 x 2 bytes.
INFO = {
    0x01: b"M01abcdefghijklmnopqrstuvwx",
    0x03: b"M03abcdefghijklmnopqrstuvwx",
    0x05: b"PD-ID120B",  # -> TypeNumber (confirmed via tool log)
    0x0B: b"M0Bz",
    0x07: b"7a7b7c7d",  # -> Serial (confirmed via tool log)
}


def handle(iface, data, state):
    if iface != RAW_IF or not data:
        return []
    cmd = data[0]
    state.setdefault("seen", []).append(data[:4].hex())

    if cmd == 0x02:  # id_get_keyboard_value; data[1] = PFU value id (0x10 info, 0x11 settings)
        if data[1] == 0x10 and data[2] in INFO:
            return [(iface, echo(data, INFO[data[2]]))]
        return [(iface, echo(data))]
    if cmd == 0x03:  # id_set_keyboard_value
        state.setdefault("set", []).append(bytes(data))
        if data[1:3] == b"\x11\x01":  # SetProfile: tool checks the reply starts "02 11 01 00" (format1)
            first = bytearray(echo(data))
            first[0], first[3] = 0x02, 0x00
            return [(iface, bytes(first)), (iface, echo(data))]
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
