# openhhkb

## Ground rule
Read-only until the protocol is understood. Never send reports, feature requests or control transfers to a
keyboard without the user's explicit OK.

## macOS: Karabiner-Elements
Karabiner-Elements can open a keyboard exclusively (seize it). That locks out other programs, including the
official keymap tools and our own tooling, and changes what scans show about who has the device open.

Before doing anything with a keyboard on macOS (scans, listening, captures, running a keymap tool):

1. **Check** whether Karabiner is running and holding the device:
   - `pgrep -fl Karabiner-Core-Service`
   - `ioreg -w0 -l -r -n '<Product>@<locationID>' | grep -A6 Karabiner`: a client with `"ClientOpened"=Yes`
     means Karabiner has it open. Other clients showing `"ClientSeized"=Yes` means they are locked out.
   - `~/.config/karabiner/karabiner.json`: the selected profile's `devices` entry for the VID/PID, `"ignore": true/false`.
2. **Disable temporarily** for that device: set `"ignore": true` on its `devices` entry in the selected profile
   (Karabiner reloads the file on save; keep a backup first), or ask the user to toggle it in
   Karabiner-Elements → Devices. Re-check with `ioreg` that the Karabiner client shows `"ClientOpened"=No`.
3. **Restore** the previous setting when finished, unless it was already ignored before you started.
   Tell the user what you changed and that it was restored.

Note that a device may have several entries (keyboard / pointing device). Only touch the ones for the device in use.
