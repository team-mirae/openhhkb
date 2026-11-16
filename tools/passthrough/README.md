# tools/passthrough/

Logging HID passthrough: an official tool running in the VM talks to the **real** keyboard on the host, with every
report logged and writes blocked by default. Use it to capture the genuine protocol (config reads a fake device
can't answer) without risking the real keyboard.

```
VM: official tool ──► virtual device (vhhkb) ──SSH──► passthrough.py (host) ──► hidbridge ──► REAL keyboard
```

```
python3 tools/passthrough/passthrough.py <device>      # e.g. realforce-x1p-jp-tkl
```

## Safety / guard

Reads pass through to the real keyboard (all a tool needs to connect). **Writes are blocked** — the relay logs them
and returns a synthetic ack instead of sending them to the device:

| Env | Effect |
|---|---|
| (default) | config writes (`0xC2`/`0xC8`) and firmware-flash (`0xE0`–`0xE3`) are **blocked** |
| `PASSTHROUGH_ALLOW_WRITES=1` | also forward config writes to the real keyboard |
| `PASSTHROUGH_ALLOW_FIRMWARE=1` | also forward firmware-flash commands — **DANGER: real flash** |
| `FAKE_OLD_VERSION=1` | rewrite the `0x02` get-info reply to report an older firmware (re-enables a tool's update menu) |

Flashing the real keyboard over an unproven relay is exactly the brick risk this project avoids; leave the guard on
unless you have decided otherwise.

## Parts

| File | Role |
|---|---|
| `hidbridge.c` | host-side hidapi bridge: opens the real keyboard's vendor interface and relays reports over a stdin/stdout line protocol (`W <hex>` / `R <hex>`). Build: `clang -O1 -o hidbridge hidbridge.c <hidapi>/mac/hid.c -I<hidapi>/hidapi -framework IOKit -framework CoreFoundation -framework AppKit`. |
| `passthrough.py` | relays reports between the VM's virtual device and `hidbridge`, logs to `analysis/<device>/captures/<ts>-passthrough.jsonl`, and enforces the guard. |

The compiled `hidbridge` binary and `*-passthrough.jsonl` captures (which contain the user's real keyboard config)
are git-ignored.

## Notes

- Build `hidbridge` against the hidapi sources (we used the submodule from `happy-hacking-gnu`).
- `hidbridge`'s line protocol must not print the device's wide product name (`%ls`) — it emits a control byte that
  corrupts the stdout stream. (Fixed; noted here because it looked like a device-open failure.)
- Repeatedly opening/closing a real keyboard's vendor interface makes macOS's `hid_open` flaky until a replug.
- Reuses `../responder/profiles/<device>.json` for the virtual-device identity.
