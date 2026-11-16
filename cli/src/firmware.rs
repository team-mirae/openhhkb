//! `.hfb` firmware parsing/verification and the gated flash routine.
//!
//! `.hfb` = `[CRC-16 LE, 2 bytes] + body`, CRC-16 (reflected, poly 0x8408, init 0xFFFF) over the
//! body. The body ends with a model-ID footer `AH?X01\n` + version. The device and the official
//! tool both verify the CRC; the tool also refuses a wrong model-ID. See
//! `analysis/firmware/hfb-checksum.md` and `analysis/firmware/hybrid-keycodes.md`.

use anyhow::{bail, Result};

use crate::proto::Proto;

pub fn crc16(data: &[u8]) -> u16 {
    let mut crc: u16 = 0xFFFF;
    for &b in data {
        crc ^= b as u16;
        for _ in 0..8 {
            crc = if crc & 1 != 0 { (crc >> 1) ^ 0x8408 } else { crc >> 1 };
        }
    }
    crc
}

pub struct Hfb {
    pub size_body: u32,
    pub stored_crc: u16,
    pub computed_crc: u16,
    pub model_id: String, // e.g. "AHJX01"
    pub version: String,  // hex of the version bytes after the footer
}

impl Hfb {
    pub fn crc_ok(&self) -> bool {
        self.stored_crc == self.computed_crc
    }
}

pub fn parse_hfb(bytes: &[u8]) -> Result<Hfb> {
    if bytes.len() < 32 {
        bail!("file is too small to be a .hfb ({} bytes)", bytes.len());
    }
    let stored_crc = u16::from_le_bytes([bytes[0], bytes[1]]);
    let body = &bytes[2..];
    let computed_crc = crc16(body);
    let (model_id, version) = extract_footer(bytes);
    if model_id.is_empty() {
        bail!("no model-ID footer (AH?X01) found — this does not look like a HHKB .hfb");
    }
    Ok(Hfb {
        size_body: body.len() as u32,
        stored_crc,
        computed_crc,
        model_id,
        version,
    })
}

/// Find the `AH?X01` model-ID footer and the version bytes following it.
fn extract_footer(b: &[u8]) -> (String, String) {
    let n = b.len();
    if n < 6 {
        return (String::new(), String::new());
    }
    for i in (0..=n - 6).rev() {
        if &b[i..i + 2] == b"AH" && &b[i + 3..i + 6] == b"X01" {
            let model = String::from_utf8_lossy(&b[i..i + 6]).to_string();
            let mut j = i + 6;
            if j < n && b[j] == 0x0a {
                j += 1;
            }
            let version = b[j..(j + 4).min(n)]
                .iter()
                .take_while(|&&x| x != 0x00 && x != 0xFF)
                .map(|x| format!("{x:02X}"))
                .collect::<String>();
            return (model, version);
        }
    }
    (String::new(), String::new())
}

/// Expected `.hfb` model-ID for a device, from its GET_KEYBOARD_INFO type number.
/// Returns None when we don't have a verified mapping (then flashing requires explicit --confirm).
pub fn expected_model_id(type_number: &str) -> Option<&'static str> {
    let t = type_number.to_uppercase();
    if t.starts_with("PD-KB820") {
        Some("AHJX01") // HHKB Professional Hybrid, JIS — verified
    } else {
        None
    }
}

pub struct FlashPlan {
    pub hfb: Hfb,
    pub confirmed: bool,
}

/// Validate a firmware image against the connected device. Returns a plan; never writes.
pub fn plan_flash(bytes: &[u8], type_number: &str, confirm: bool) -> Result<FlashPlan> {
    let hfb = parse_hfb(bytes)?;

    match expected_model_id(type_number) {
        Some(expected) => {
            if hfb.model_id != expected {
                bail!(
                    "firmware is for model {} but the device ({}) expects {} — refusing",
                    hfb.model_id,
                    type_number,
                    expected
                );
            }
        }
        None => {
            if !confirm {
                bail!(
                    "no verified model mapping for device type {:?}; cannot confirm firmware {} is compatible. \
Re-run with --confirm only if you are certain.",
                    type_number,
                    hfb.model_id
                );
            }
        }
    }

    if !hfb.crc_ok() && !confirm {
        bail!(
            "checksum mismatch (stored {:#06x}, computed {:#06x}); re-run with --confirm to flash anyway",
            hfb.stored_crc,
            hfb.computed_crc
        );
    }

    Ok(FlashPlan {
        hfb,
        confirmed: confirm,
    })
}

/// Perform the E0-E3 firmware update. Caller must have confirmed and validated via `plan_flash`.
///
/// NOTE: this framing matches REALFORCE CONNECT and happy-hacking-gnu byte-for-byte, but openhhkb
/// has not itself completed a hardware flash. Flashing can brick the keyboard. CRC is recomputed
/// over the body (the device computes it too; the stored header CRC is not trusted).
pub fn execute_flash(proto: &Proto, bytes: &[u8]) -> Result<()> {
    let body = &bytes[2..];
    let crc = crc16(body) as u32;
    let size = body.len() as u32;

    proto.firmup_enter()?;
    proto.firmup_start(size, crc)?;
    for (i, chunk) in body.chunks(57).enumerate() {
        proto.firmup_send(i as u16, chunk)?;
    }
    proto.firmup_end()?;
    Ok(())
}
