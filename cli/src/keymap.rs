//! Keymap profile model and the two file formats: openhhkb-json (native) and the official
//! HHKB Keymap Tool `.hks` file. See `analysis/keymap-tools/hks-format.md`.

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;

use crate::cli::Format;

/// Format-neutral keymap profile.
pub struct Profile {
    pub model: String,
    pub dip: Vec<bool>, // 6
    pub sleep: i64,
    pub layout: i64,
    pub normal: Vec<u8>, // 128
    pub fnl: Vec<u8>,    // 128
}

impl Profile {
    pub fn validate(&self) -> Result<()> {
        if self.normal.len() != 128 || self.fnl.len() != 128 {
            bail!("keymap layers must be 128 bytes each");
        }
        Ok(())
    }

    pub fn to_string(&self, format: Format) -> Result<String> {
        match format {
            Format::Hks => Ok(serde_json::to_string_pretty(&Hks::from(self))?),
            Format::OpenhhkbJson | Format::Auto => {
                Ok(serde_json::to_string_pretty(&OpenJson::from(self))?)
            }
        }
    }

    /// Parse a file, auto-detecting the format unless one is forced.
    pub fn load(path: &Path, format: Format) -> Result<Profile> {
        let text = std::fs::read_to_string(path)
            .with_context(|| format!("reading {}", path.display()))?;
        let detected = match format {
            Format::Auto => detect(&text)?,
            f => f,
        };
        match detected {
            Format::Hks => {
                let h: Hks = serde_json::from_str(&text).context("parsing .hks")?;
                Profile::try_from(h)
            }
            Format::OpenhhkbJson | Format::Auto => {
                let o: OpenJson = serde_json::from_str(&text).context("parsing openhhkb-json")?;
                Profile::try_from(o)
            }
        }
    }
}

fn detect(text: &str) -> Result<Format> {
    let v: serde_json::Value = serde_json::from_str(text).context("file is not valid JSON")?;
    if v.get("ToolVersion").is_some() || v.get("Keymap").and_then(|k| k.get("Normal")).is_some() {
        Ok(Format::Hks)
    } else if v.get("format").is_some() || v.get("keymap").is_some() {
        Ok(Format::OpenhhkbJson)
    } else {
        bail!("could not detect keymap format; pass --format openhhkb-json or --format hks")
    }
}

// ---- openhhkb-json -------------------------------------------------------

#[derive(Serialize, Deserialize)]
struct OpenJson {
    format: String,
    version: u32,
    model: String,
    dip_switch: Vec<bool>,
    sleep_setting: i64,
    keyboard_layout: i64,
    keymap: OpenLayers,
}

#[derive(Serialize, Deserialize)]
struct OpenLayers {
    normal: Vec<u8>,
    #[serde(rename = "fn")]
    fnl: Vec<u8>,
}

impl From<&Profile> for OpenJson {
    fn from(p: &Profile) -> Self {
        OpenJson {
            format: "openhhkb-json".into(),
            version: 1,
            model: p.model.clone(),
            dip_switch: p.dip.clone(),
            sleep_setting: p.sleep,
            keyboard_layout: p.layout,
            keymap: OpenLayers {
                normal: p.normal.clone(),
                fnl: p.fnl.clone(),
            },
        }
    }
}

impl TryFrom<OpenJson> for Profile {
    type Error = anyhow::Error;
    fn try_from(o: OpenJson) -> Result<Profile> {
        let p = Profile {
            model: o.model,
            dip: o.dip_switch,
            sleep: o.sleep_setting,
            layout: o.keyboard_layout,
            normal: o.keymap.normal,
            fnl: o.keymap.fnl,
        };
        p.validate()?;
        Ok(p)
    }
}

// ---- .hks (official tool) ------------------------------------------------

#[derive(Serialize, Deserialize)]
struct Hks {
    #[serde(rename = "ToolVersion")]
    tool_version: String,
    #[serde(rename = "DipSwitch")]
    dip_switch: Vec<bool>,
    #[serde(rename = "TypeNumber")]
    type_number: String,
    #[serde(rename = "SleepSetting")]
    sleep_setting: i64,
    #[serde(rename = "Keymap")]
    keymap: HksLayers,
    #[serde(rename = "KeyboardLayout")]
    keyboard_layout: i64,
    #[serde(rename = "SettingFileVersion")]
    setting_file_version: String,
}

// The tool's keymap arrays are mostly byte values, but some keys carry a >255 value where the
// high byte is tool-specific metadata (e.g. WithFn position 46 = 0x0A21 in a real export). The low
// byte is the actual protocol keymap byte (confirmed against a live device read). We parse them as
// wide integers and reduce to the protocol byte at the Profile boundary.
#[derive(Serialize, Deserialize)]
struct HksLayers {
    #[serde(rename = "Normal")]
    normal: Vec<i64>,
    #[serde(rename = "WithFn")]
    with_fn: Vec<i64>,
}

/// The official tool stores SleepSetting as a menu index; the protocol (0x09) uses minutes.
/// Observed mapping: 60 min -> index 6, consistent with a 10-minute-step menu (index = min / 10).
/// This is inferred from one data point; openhhkb-json keeps the raw minutes value.
fn sleep_minutes_to_index(min: i64) -> i64 {
    if min > 0 && min % 10 == 0 {
        min / 10
    } else {
        min
    }
}
fn sleep_index_to_minutes(idx: i64) -> i64 {
    if idx > 0 && idx <= 60 {
        idx * 10
    } else {
        idx
    }
}

impl From<&Profile> for Hks {
    fn from(p: &Profile) -> Self {
        // Pad/clone the DIP vector to the 6 the tool expects.
        let mut dip = p.dip.clone();
        dip.resize(6, false);
        Hks {
            tool_version: "2.0.1.0".into(),
            dip_switch: dip,
            type_number: p.model.clone(),
            sleep_setting: sleep_minutes_to_index(p.sleep),
            keymap: HksLayers {
                normal: p.normal.iter().map(|&b| b as i64).collect(),
                with_fn: p.fnl.iter().map(|&b| b as i64).collect(),
            },
            keyboard_layout: p.layout,
            setting_file_version: "1.0.0.0".into(),
        }
    }
}

impl TryFrom<Hks> for Profile {
    type Error = anyhow::Error;
    fn try_from(h: Hks) -> Result<Profile> {
        let to_bytes = |v: Vec<i64>| v.iter().map(|&x| (x & 0xFF) as u8).collect::<Vec<u8>>();
        let p = Profile {
            model: h.type_number,
            dip: h.dip_switch,
            sleep: sleep_index_to_minutes(h.sleep_setting),
            layout: h.keyboard_layout,
            normal: to_bytes(h.keymap.normal),
            fnl: to_bytes(h.keymap.with_fn),
        };
        p.validate()?;
        Ok(p)
    }
}
