//! Device discovery, model identification, and selection.
//!
//! A physical keyboard shows up as several HID interfaces. We group them by (vid, pid, serial) and
//! remember the path of the *vendor* interface (the one carrying the configuration protocol).

use anyhow::{anyhow, bail, Result};
use hidapi::{HidApi, HidDevice};
use std::ffi::CString;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Model {
    Hybrid,
    Studio,
    RealforceX1P,
    RealforceCompact,
    Unknown,
}

impl Model {
    pub fn from_ids(vid: u16, pid: u16) -> Model {
        match (vid, pid) {
            (0x04fe, 0x0022) => Model::Hybrid,
            (0x04fe, 0x0015) => Model::Studio,
            (0x0853, 0x0322) => Model::RealforceX1P,
            (0x0853, 0x0200) => Model::RealforceCompact,
            _ => Model::Unknown,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            Model::Hybrid => "HHKB Professional Hybrid (Type-S)",
            Model::Studio => "HHKB Studio",
            Model::RealforceX1P => "Realforce X1P",
            Model::RealforceCompact => "Realforce Compact",
            Model::Unknown => "Unknown",
        }
    }

    /// Whether this version speaks the configuration/firmware protocol for this model.
    /// Only the Hybrid is fully supported; others are detect-only.
    pub fn full_support(&self) -> bool {
        matches!(self, Model::Hybrid)
    }
}

pub struct Found {
    pub index: usize,
    pub vid: u16,
    pub pid: u16,
    pub model: Model,
    pub serial: String,
    pub product: String,
    pub vendor_path: Option<CString>,
}

impl Found {
    pub fn id(&self) -> String {
        format!("{:04x}:{:04x}", self.vid, self.pid)
    }
}

/// Enumerate connected keyboards we recognise (by VID/PID).
pub fn discover(api: &HidApi) -> Vec<Found> {
    let mut found: Vec<Found> = Vec::new();

    for info in api.device_list() {
        let (vid, pid) = (info.vendor_id(), info.product_id());
        let model = Model::from_ids(vid, pid);
        if model == Model::Unknown {
            continue;
        }
        let serial = info.serial_number().unwrap_or("").to_string();

        let idx = match found
            .iter()
            .position(|f| f.vid == vid && f.pid == pid && f.serial == serial)
        {
            Some(i) => i,
            None => {
                found.push(Found {
                    index: 0,
                    vid,
                    pid,
                    model,
                    serial: serial.clone(),
                    product: info.product_string().unwrap_or("").to_string(),
                    vendor_path: None,
                });
                found.len() - 1
            }
        };

        // Identify the vendor/config interface for this model.
        let is_vendor = match model {
            // HHKB Hybrid / Realforce: vendor HID on interface 2, usage page 0xFF00.
            Model::Hybrid | Model::RealforceX1P | Model::RealforceCompact => {
                info.interface_number() == 2 || info.usage_page() == 0xFF00
            }
            // HHKB Studio: QMK RAW_HID on interface 1, usage page 0xFF60.
            Model::Studio => info.interface_number() == 1 || info.usage_page() == 0xFF60,
            Model::Unknown => false,
        };
        if is_vendor && found[idx].vendor_path.is_none() {
            found[idx].vendor_path = Some(info.path().to_owned());
        }
    }

    for (i, f) in found.iter_mut().enumerate() {
        f.index = i;
    }
    found
}

pub enum Selector {
    Index(usize),
    VidPid(u16, u16),
    Serial(String),
}

pub fn parse_selector(s: &str) -> Result<Selector> {
    if let Some(rest) = s.strip_prefix("serial:") {
        return Ok(Selector::Serial(rest.to_string()));
    }
    if let Some((a, b)) = s.split_once(':') {
        let hv = u16::from_str_radix(a.trim_start_matches("0x"), 16);
        let hp = u16::from_str_radix(b.trim_start_matches("0x"), 16);
        if let (Ok(v), Ok(p)) = (hv, hp) {
            return Ok(Selector::VidPid(v, p));
        }
    }
    if let Ok(i) = s.parse::<usize>() {
        return Ok(Selector::Index(i));
    }
    bail!("could not parse --device {s:?}; use an index, vid:pid (e.g. 04fe:0022), or serial:<s>")
}

pub fn select<'a>(found: &'a [Found], sel: &Selector) -> Result<&'a Found> {
    let matches: Vec<&Found> = found
        .iter()
        .filter(|f| match sel {
            Selector::Index(i) => f.index == *i,
            Selector::VidPid(v, p) => f.vid == *v && f.pid == *p,
            Selector::Serial(s) => &f.serial == s,
        })
        .collect();
    match matches.len() {
        0 => bail!("no connected device matches that selector (run `openhhkb list`)"),
        1 => Ok(matches[0]),
        n => bail!("selector matches {n} devices; narrow it with an index or serial from `openhhkb list`"),
    }
}

/// Resolve `--device`, erroring clearly if the model isn't fully supported for protocol access.
pub fn resolve<'a>(found: &'a [Found], device: &str) -> Result<&'a Found> {
    let sel = parse_selector(device)?;
    let f = select(found, &sel)?;
    Ok(f)
}

pub fn require_full_support(f: &Found) -> Result<()> {
    if !f.model.full_support() {
        bail!(
            "{} ({}) is detect-only in this version; configuration/firmware commands support the HHKB Hybrid",
            f.model.label(),
            f.id()
        );
    }
    Ok(())
}

pub fn open(api: &HidApi, f: &Found) -> Result<HidDevice> {
    let path = f
        .vendor_path
        .as_ref()
        .ok_or_else(|| anyhow!("no vendor interface found for {} — is it the right device?", f.id()))?;
    api.open_path(path)
        .map_err(|e| anyhow!("could not open {} vendor interface: {e}", f.id()))
}
