"""Reply rules for a virtual REALFORCE X1P JP TKL (REALFORCE CONNECT, WebHID).

Finding (from CONNECT's app bundle): it uses the SAME vendor protocol and the SAME firmware-update flow
as the HHKB Hybrid.
  request  AA AA <cmd> <param> <len> <data...>
  reply    55 55 <cmd> <status=0> <x> <len> <data...>   (app reads cmd@2, status@3, len@5, data@6..)
  getDeviceInfo = cmd 0x02: modelNumber = printable ASCII of data; fwVersion = hex of data[8:] joined by "."
  romRead/ramRead = 0xC1/0xC3 (+0xC0/0xC7); firmware update = 0xE0/0xE1/0xE2/0xE3 (same as HHKB, same CRC-16).

This reports an OLD firmware (01.00) and answers the config reads generically, enough to probe how far CONNECT
gets toward the firmware-update screen. Responder hot-reloads this file.
"""

VENDOR_IF = 2
SIZE = 64


def reply(cmd, data=b"", status=0x00):
    return bytes([0x55, 0x55, cmd, status, 0x00, len(data)]) + bytes(data) + bytes(SIZE - 6 - len(data))


def device_info():
    # data[0:8] model ASCII (R30H..), data[8:] version bytes -> "01.00" (old, and not starting with 'B')
    model = b"R30H\x00\x00\x00\x00"
    version = bytes([0x01, 0x00])
    return model + version


def handle(iface, data, state):
    if iface != VENDOR_IF or len(data) < 3 or data[0:2] != b"\xaa\xaa":
        return []
    cmd = data[2]
    n = data[4] if len(data) > 4 else 0
    param = data[5] if len(data) > 5 else 0
    seq = state.setdefault("cmds", [])
    if not seq or seq[-1] != (cmd, param):
        seq.append((cmd, param))
        print(f"??? CONNECT cmd {cmd:#04x} param {param:#04x} len {n}")

    if cmd == 0x01:  # appLaunchNotification
        return [(iface, reply(cmd))]
    if cmd == 0x02:  # getDeviceInfo
        return [(iface, reply(cmd, device_info()))]
    if cmd in (0xC1, 0xC7):  # romRead(addr): address-specific config bytes (decoded from CONNECT's connect flow)
        buf = bytearray(20)
        if param == 0:
            buf[0:4] = b"R30H"       # device name (bytes 0..6, up to first NUL)
            buf[6] = 0x01            # low nibble = profile/layer count
            buf[7] = 0x00            # bit7 clear -> not a "setting limit device"
        elif param == 191:
            buf[2] = 0x12            # bytes 2:3 = running-FW CRC; must be non-zero
            buf[3] = 0x34
            buf[7] = 0x01            # version/config byte the UI reads
        # all other addresses: zeros (blank keymap/macros) -> UI shows defaults
        return [(iface, reply(cmd, bytes(buf)))]
    if cmd in (0xC3, 0xC0):  # ramRead / request: zeros
        return [(iface, reply(cmd, bytes(16)))]
    if cmd in (0xC2, 0xC8):  # romWrite / romWrite2: ack
        return [(iface, reply(cmd))]
    if cmd == 0xE0:  # enter firmware update mode
        print("!!! CONNECT entered firmware update mode")
        return [(iface, reply(cmd))]
    if cmd == 0xE1:  # firmup start: payload = size LE32 + CRC LE32 (CONNECT-computed)
        state["fw"] = bytearray()
        print(f"!!! FIRMUP_START size+crc = {bytes(data[5:13]).hex(' ')}")
        return [(iface, reply(cmd))]
    if cmd == 0xE2:  # firmup block: data = block LE16 + 57 bytes; reply must echo block number
        blk = data[5] | (data[6] << 8)
        state.setdefault("fw", bytearray()).extend(data[7:5 + n])
        return [(iface, reply(cmd, bytes([data[5], data[6]])))]
    if cmd == 0xE3:  # firmup end
        print(f"!!! FIRMUP_END, received {len(state.get('fw', b''))} bytes")
        return [(iface, reply(cmd))]
    print(f"??? unknown CONNECT cmd {cmd:#04x}")
    return [(iface, reply(cmd))]
