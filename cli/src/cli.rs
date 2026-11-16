//! Command-line surface. Stateless: every command carries its own `--device` and options; there
//! is no config file or remembered selection.

use clap::{Parser, Subcommand, ValueEnum};
use std::path::PathBuf;

#[derive(Parser)]
#[command(
    name = "openhhkb",
    version,
    about = "Open remapper / updater for HHKB and Realforce (Topre) keyboards",
    long_about = "Stateless CLI: pass --device (and all options) on every command. \
Run `openhhkb list` to see connected keyboards and their selectors."
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    /// List connected supported keyboards and their selectors.
    List,

    /// Show firmware / keyboard information for one device.
    FirmwareInfo {
        #[arg(long, value_name = "SELECTOR", help = DEVICE_HELP)]
        device: String,
    },

    /// Remap a single key on the active profile (--confirm only for media/action keys).
    Remap {
        #[arg(long, value_name = "SELECTOR", help = DEVICE_HELP)]
        device: String,
        /// Which layer to change.
        #[arg(long, value_enum)]
        layer: Layer,
        /// Key position, 0-127 (P = 44; index 0 = bottom-right, 69 = top-left Esc).
        #[arg(long)]
        position: u8,
        /// New keymap byte, decimal or 0x-hex (e.g. 0x0b = H, 0x78 = Stop).
        #[arg(long, value_parser = parse_u8)]
        code: u8,
        /// Required only for media/action keys (plain keyboard keys write without it).
        #[arg(long)]
        confirm: bool,
    },

    /// Load a keymap file onto the keyboard (writes; needs --confirm).
    Load {
        #[arg(long, value_name = "SELECTOR", help = DEVICE_HELP)]
        device: String,
        /// Input file: openhhkb-json or an official-tool .hks profile.
        #[arg(long, value_name = "FILE")]
        input: PathBuf,
        /// Input format (default: auto-detect from content).
        #[arg(long, value_enum, default_value_t = Format::Auto)]
        format: Format,
        /// Required to actually write to the keyboard.
        #[arg(long)]
        confirm: bool,
    },

    /// Export the keyboard's current keymap to a file.
    Export {
        #[arg(long, value_name = "SELECTOR", help = DEVICE_HELP)]
        device: String,
        /// Output file path.
        #[arg(long, value_name = "FILE")]
        output: PathBuf,
        /// Output format.
        #[arg(long, value_enum, default_value_t = Format::OpenhhkbJson)]
        format: Format,
    },

    /// Load a recovery image. NOT IMPLEMENTED YET.
    FirmwareRecovery {
        #[arg(long, value_name = "SELECTOR", help = DEVICE_HELP)]
        device: String,
        #[arg(long)]
        confirm: bool,
    },

    /// Flash a firmware .hfb file (writes firmware; needs --confirm).
    FirmwareFlash {
        #[arg(long, value_name = "SELECTOR", help = DEVICE_HELP)]
        device: String,
        /// Firmware image (.hfb).
        #[arg(long, value_name = "FILE")]
        input: PathBuf,
        /// Required to flash. Also required to proceed when the checksum does not match.
        #[arg(long)]
        confirm: bool,
    },
}

const DEVICE_HELP: &str =
    "Device selector: an index, a vid:pid (e.g. 04fe:0022), or serial:<serial>. See `openhhkb list`.";

#[derive(Clone, Copy, ValueEnum)]
pub enum Layer {
    /// Standard layer.
    Normal,
    /// Fn layer.
    Fn,
}

#[derive(Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum Format {
    /// Detect from file content (load only).
    Auto,
    /// openhhkb's native JSON.
    OpenhhkbJson,
    /// Official HHKB Keymap Tool `.hks` profile.
    Hks,
}

/// Parse a u8 given as decimal or `0x`-prefixed hex.
fn parse_u8(s: &str) -> Result<u8, String> {
    let r = if let Some(h) = s.strip_prefix("0x").or_else(|| s.strip_prefix("0X")) {
        u8::from_str_radix(h, 16)
    } else {
        s.parse::<u8>()
    };
    r.map_err(|_| format!("'{s}' is not a byte value (0-255, decimal or 0x-hex)"))
}
