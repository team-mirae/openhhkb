"""Reply rules for a virtual REALFORCE X1P JP TKL, as seen by REALFORCE CONNECT (WebHID app in Chrome).

The CONNECT protocol is not yet reverse-engineered. This starts as a logger: it records every output
report on the vendor channel (interface 2, 0xFF00/0x01, 64 B) and sends no reply, so we can see what
CONNECT asks for and build real replies from the capture. Edit freely; the responder hot-reloads this file.
"""

VENDOR_IF = 2


def handle(iface, data, state):
    if iface != VENDOR_IF or not data:
        return []
    state.setdefault("seen", []).append(data[:8].hex())
    # Unknown protocol: log only, reply nothing yet. Fill in replies once we see CONNECT's requests.
    print(f"??? CONNECT -> if{iface}: {bytes(data[:16]).hex(' ')}")
    return []
