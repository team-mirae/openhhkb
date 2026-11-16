//! HHKB Hybrid vendor HID protocol (interface 2, usage page 0xFF00, 64-byte reports).
//!
//! Request:  `AA AA <cmd> <param> <len> <payload...>`
//! Reply:    `55 55 <cmd> <status> <chunk> <len> <payload...>`
//!
//! HID framing: a write is a 0x00 report-ID byte + the 64-byte body (65 bytes total); a read
//! returns the 64-byte body. See `tools/passthrough/hidbridge.c` and `analysis/hhkb-hybrid-jis/`.

use anyhow::{bail, Result};
use hidapi::HidDevice;

const REQ: [u8; 2] = [0xAA, 0xAA];
const REPLY: [u8; 2] = [0x55, 0x55];
const READ_TIMEOUT_MS: i32 = 3000;

// Command IDs.
const CMD_NOTIFY_APP: u8 = 0x01;
const CMD_GET_INFO: u8 = 0x02;
const CMD_CONFIRM_KEYMAP: u8 = 0x04;
const CMD_GET_DIPSW: u8 = 0x05;
const CMD_GET_MODE: u8 = 0x06;
const CMD_RESET_DIPSW: u8 = 0x07;
const CMD_RESET_SLEEP: u8 = 0x08;
const CMD_GET_SLEEP: u8 = 0x09;
const CMD_SET_KEYMAP: u8 = 0x86;
const CMD_GET_KEYMAP: u8 = 0x87;
const CMD_FIRMUP_MODE: u8 = 0xE0;
const CMD_FIRMUP_START: u8 = 0xE1;
const CMD_FIRMUP_SEND: u8 = 0xE2;
const CMD_FIRMUP_END: u8 = 0xE3;

pub struct Proto<'a> {
    dev: &'a HidDevice,
}

#[derive(Debug, Default)]
pub struct Info {
    pub type_number: String,
    pub revision: String,
    pub serial: String,
    pub app_version: String,
    pub boot_version: String,
    pub running_firmware: u8,
    pub raw_hex: String,
}

impl Info {
    fn parse(d: &[u8]) -> Info {
        fn s(b: &[u8]) -> String {
            String::from_utf8_lossy(b)
                .trim_end_matches(['\0', ' '])
                .trim()
                .to_string()
        }
        let g = |a: usize, b: usize| -> String {
            if d.len() >= b {
                s(&d[a..b])
            } else {
                String::new()
            }
        };
        // Version fields are binary (e.g. 0a 02 04 09), not ASCII: render as trimmed hex.
        let v = |a: usize, b: usize| -> String {
            if d.len() < b {
                return String::new();
            }
            let bytes = &d[a..b];
            let end = bytes.iter().rposition(|&x| x != 0).map_or(0, |p| p + 1);
            bytes[..end].iter().map(|x| format!("{x:02x}")).collect()
        };
        // Field layout per happy-hacking-gnu's hhkb_info struct.
        Info {
            type_number: g(0, 20),
            revision: g(20, 24),
            serial: g(24, 40),
            app_version: v(40, 48),
            boot_version: v(48, 56),
            running_firmware: if d.len() > 56 { d[56] } else { 0 },
            raw_hex: d.iter().map(|b| format!("{b:02x}")).collect(),
        }
    }
}

impl<'a> Proto<'a> {
    pub fn new(dev: &'a HidDevice) -> Self {
        Proto { dev }
    }

    fn body(cmd: u8, param: u8, data: &[u8]) -> Vec<u8> {
        let mut v = vec![REQ[0], REQ[1], cmd, param, data.len() as u8];
        v.extend_from_slice(data);
        v
    }

    fn write_body(&self, body: &[u8]) -> Result<()> {
        if body.len() > 64 {
            bail!("request body too long ({} bytes)", body.len());
        }
        let mut buf = [0u8; 65]; // buf[0] = report ID 0
        buf[1..1 + body.len()].copy_from_slice(body);
        let n = self.dev.write(&buf)?;
        if n == 0 {
            bail!("HID write returned 0 bytes");
        }
        Ok(())
    }

    fn read_reply(&self) -> Result<[u8; 64]> {
        let mut buf = [0u8; 64];
        let n = self.dev.read_timeout(&mut buf, READ_TIMEOUT_MS)?;
        if n == 0 {
            bail!("timed out waiting for a reply");
        }
        if buf[0..2] != REPLY {
            bail!("unexpected reply header {:02x} {:02x}", buf[0], buf[1]);
        }
        Ok(buf)
    }

    fn request(&self, cmd: u8, param: u8, data: &[u8]) -> Result<[u8; 64]> {
        self.write_body(&Self::body(cmd, param, data))?;
        self.read_reply()
    }

    fn request_n(&self, cmd: u8, param: u8, data: &[u8], n: usize) -> Result<Vec<[u8; 64]>> {
        self.write_body(&Self::body(cmd, param, data))?;
        (0..n).map(|_| self.read_reply()).collect()
    }

    fn query_byte(&self, cmd: u8) -> Result<u8> {
        Ok(self.request(cmd, 0x00, &[])?[6])
    }

    pub fn keyboard_mode(&self) -> Result<u8> {
        self.query_byte(CMD_GET_MODE)
    }
    pub fn sleep_setting(&self) -> Result<u8> {
        self.query_byte(CMD_GET_SLEEP)
    }

    pub fn get_info(&self) -> Result<Info> {
        let r = self.request(CMD_GET_INFO, 0x00, &[])?;
        let len = (r[5] as usize).min(58);
        Ok(Info::parse(&r[6..6 + len]))
    }

    /// 6 DIP-switch booleans (best-effort decode of the 0x05 reply).
    pub fn dip_switches(&self) -> Result<Vec<bool>> {
        let r = self.request(CMD_GET_DIPSW, 0x00, &[])?;
        let len = r[5] as usize;
        let data = &r[6..6 + len.min(58)];
        // Observed form is one byte per switch; fall back to a bitmask of the first byte.
        let dips = if data.len() >= 6 {
            data[..6].iter().map(|&b| b != 0).collect()
        } else if !data.is_empty() {
            (0..6).map(|i| data[0] & (1 << i) != 0).collect()
        } else {
            vec![false; 6]
        };
        Ok(dips)
    }

    pub fn get_keymap(&self, mode: u8, fn_layer: u8) -> Result<Vec<u8>> {
        let parts = self.request_n(CMD_GET_KEYMAP, 0x00, &[mode, fn_layer], 3)?;
        let mut km = Vec::with_capacity(128);
        for p in parts {
            let l = p[5] as usize;
            km.extend_from_slice(&p[6..6 + l]);
        }
        if km.len() != 128 {
            bail!("got {} keymap bytes, expected 128", km.len());
        }
        Ok(km)
    }

    fn set_keymap(&self, mode: u8, fn_layer: u8, km: &[u8]) -> Result<()> {
        if km.len() != 128 {
            bail!("keymap must be 128 bytes");
        }
        let mut c1 = vec![mode, fn_layer];
        c1.extend_from_slice(&km[0..57]);
        self.request(CMD_SET_KEYMAP, 0x41, &c1)?;
        self.request(CMD_SET_KEYMAP, 0x82, &km[57..116])?;
        self.request(CMD_SET_KEYMAP, 0xC3, &km[116..128])?;
        Ok(())
    }

    /// Read the active profile's (mode, Normal, Fn) layers.
    pub fn read_active(&self) -> Result<(u8, Vec<u8>, Vec<u8>)> {
        let mode = self.keyboard_mode()?;
        let normal = self.get_keymap(mode, 0)?;
        let fnl = self.get_keymap(mode, 1)?;
        Ok((mode, normal, fnl))
    }

    /// Write both visible layers to the active profile, replicating the official tool's full apply
    /// sequence: write four layers (keymap + shortcut, each Normal+Fn), then ResetSleep / Confirm /
    /// ResetDIPSW. The shortcut layers (mode|0x10) are read and written back unchanged.
    pub fn write_active(&self, normal: &[u8], fnl: &[u8]) -> Result<()> {
        if normal.len() != 128 || fnl.len() != 128 {
            bail!("each layer must be 128 bytes");
        }
        let mode = self.keyboard_mode()?;
        let sleep = self.sleep_setting()?;
        let sc0 = self.get_keymap(mode | 0x10, 0)?;
        let sc1 = self.get_keymap(mode | 0x10, 1)?;

        self.request(CMD_NOTIFY_APP, 0x00, &[0x00])?; // NotifyAppState(0)
        self.request(CMD_GET_INFO, 0x00, &[])?;
        self.request(CMD_GET_DIPSW, 0x00, &[])?;
        self.set_keymap(mode, 0, normal)?;
        self.set_keymap(mode, 1, fnl)?;
        self.set_keymap(mode | 0x10, 0, &sc0)?;
        self.set_keymap(mode | 0x10, 1, &sc1)?;
        self.request(CMD_RESET_SLEEP, 0x00, &[sleep])?;
        self.request(CMD_CONFIRM_KEYMAP, 0x00, &[])?;
        self.request(CMD_RESET_DIPSW, 0x00, &[mode])?;
        self.request(CMD_NOTIFY_APP, 0x00, &[0x01])?; // NotifyAppState(1)
        Ok(())
    }

    /// Change one key on the active profile and apply.
    pub fn remap(&self, fn_layer: bool, pos: usize, code: u8) -> Result<(u8, u8)> {
        if pos >= 128 {
            bail!("position must be 0-127");
        }
        let (mode, mut normal, mut fnl) = self.read_active()?;
        let old = if fn_layer { fnl[pos] } else { normal[pos] };
        if fn_layer {
            fnl[pos] = code;
        } else {
            normal[pos] = code;
        }
        self.write_active(&normal, &fnl)?;
        // read back
        let back = self.get_keymap(mode, if fn_layer { 1 } else { 0 })?[pos];
        if back != code {
            bail!("read-back mismatch: wrote {code:#04x}, device has {back:#04x}");
        }
        Ok((mode, old))
    }

    // --- firmware update (E0-E3) --------------------------------------------
    // Framing is documented (matches REALFORCE CONNECT and happy-hacking-gnu byte-for-byte);
    // openhhkb has not itself performed a successful hardware flash. See firmware.rs.

    pub fn firmup_enter(&self) -> Result<()> {
        self.request(CMD_FIRMUP_MODE, 0x00, &[])?;
        Ok(())
    }

    /// E1: size (LE32) + CRC (LE32), both over the firmware body (file after the 2 CRC bytes).
    pub fn firmup_start(&self, size: u32, crc: u32) -> Result<()> {
        let mut p = Vec::with_capacity(8);
        p.extend_from_slice(&size.to_le_bytes());
        p.extend_from_slice(&crc.to_le_bytes());
        self.request(CMD_FIRMUP_START, 0x00, &p)?;
        Ok(())
    }

    /// E2: blockNo (LE16) + 57 payload bytes (zero-padded). Reply must echo blockNo.
    pub fn firmup_send(&self, block_no: u16, chunk: &[u8]) -> Result<()> {
        if chunk.len() > 57 {
            bail!("firmware block payload must be <= 57 bytes");
        }
        let mut p = Vec::with_capacity(59);
        p.extend_from_slice(&block_no.to_le_bytes());
        p.extend_from_slice(chunk);
        p.resize(59, 0);
        let reply = self.request(CMD_FIRMUP_SEND, 0x00, &p)?;
        let echoed = u16::from_le_bytes([reply[6], reply[7]]);
        if echoed != block_no {
            bail!("firmware block {block_no} not acknowledged (device echoed {echoed})");
        }
        Ok(())
    }

    pub fn firmup_end(&self) -> Result<()> {
        self.request(CMD_FIRMUP_END, 0x00, &[])?;
        Ok(())
    }
}
