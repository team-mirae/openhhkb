//! openhhkb — open remapper / updater for HHKB and Realforce (Topre) keyboards.
//!
//! Stateless: every command carries its own `--device` and options. Only the HHKB Hybrid is fully
//! supported for configuration/firmware; other recognised models are detect-only (`list`).

mod cli;
mod device;
mod firmware;
mod keymap;
mod proto;

use anyhow::{Context, Result};
use clap::Parser;
use hidapi::HidApi;

use cli::{Cli, Command, Format, Layer};
use device::{discover, open, require_full_support, resolve};
use keymap::Profile;
use proto::Proto;

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e:#}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let api = HidApi::new().context("initialising HID API")?;
    match Cli::parse().command {
        Command::List => cmd_list(&api),
        Command::FirmwareInfo { device } => cmd_firmware_info(&api, &device),
        Command::Remap {
            device,
            layer,
            position,
            code,
            confirm,
        } => cmd_remap(&api, &device, layer, position, code, confirm),
        Command::Load {
            device,
            input,
            format,
            confirm,
        } => cmd_load(&api, &device, &input, format, confirm),
        Command::Export {
            device,
            output,
            format,
        } => cmd_export(&api, &device, &output, format),
        Command::FirmwareRecovery { device, confirm } => {
            cmd_firmware_recovery(&api, &device, confirm)
        }
        Command::FirmwareFlash {
            device,
            input,
            confirm,
        } => cmd_firmware_flash(&api, &device, &input, confirm),
    }
}

fn cmd_list(api: &HidApi) -> Result<()> {
    let found = discover(api);
    if found.is_empty() {
        println!("No recognised keyboards connected.");
        return Ok(());
    }
    println!("{:<3}  {:<9}  {:<34}  {:<10}  support", "idx", "vid:pid", "model", "serial");
    for f in &found {
        println!(
            "{:<3}  {:<9}  {:<34}  {:<10}  {}",
            f.index,
            f.id(),
            f.model.label(),
            if f.serial.is_empty() { "-" } else { &f.serial },
            if f.model.full_support() { "full" } else { "detect-only" },
        );
    }
    Ok(())
}

fn cmd_firmware_info(api: &HidApi, device: &str) -> Result<()> {
    let found = discover(api);
    let f = resolve(&found, device)?;
    println!(
        "device : {} [{}]  product={:?}  serial={}",
        f.model.label(),
        f.id(),
        f.product,
        if f.serial.is_empty() { "-" } else { &f.serial }
    );

    if !f.model.full_support() {
        println!("(detect-only model: no protocol-level info in this version)");
        return Ok(());
    }
    let dev = open(api, f)?;
    let proto = Proto::new(&dev);
    let info = proto.get_info()?;
    println!("type number     : {}", info.type_number);
    println!("revision        : {}", info.revision);
    println!("serial          : {}", info.serial);
    println!("app firmware    : {}", info.app_version);
    println!("boot firmware   : {}", info.boot_version);
    println!(
        "running bank    : {}",
        if info.running_firmware == 0 { "app (primary)" } else { "boot (backup)" }
    );
    println!("keyboard mode   : {:#04x}", proto.keyboard_mode()?);
    println!("raw info        : {}", info.raw_hex);
    Ok(())
}

fn cmd_remap(
    api: &HidApi,
    device: &str,
    layer: Layer,
    position: u8,
    code: u8,
    confirm: bool,
) -> Result<()> {
    let found = discover(api);
    let f = resolve(&found, device)?;
    require_full_support(f)?;
    let fn_layer = matches!(layer, Layer::Fn);

    if !confirm {
        println!(
            "DRY RUN — would set {} layer position {} to {:#04x} on {}.\nRe-run with --confirm to write.",
            if fn_layer { "Fn" } else { "Normal" },
            position,
            code,
            f.id()
        );
        return Ok(());
    }

    let dev = open(api, f)?;
    let proto = Proto::new(&dev);
    let (mode, old) = proto.remap(fn_layer, position as usize, code)?;
    println!(
        "ok: {} layer position {} {:#04x} -> {:#04x} (profile mode {:#04x})",
        if fn_layer { "Fn" } else { "Normal" },
        position,
        old,
        code,
        mode
    );
    Ok(())
}

fn cmd_load(api: &HidApi, device: &str, input: &std::path::Path, format: Format, confirm: bool) -> Result<()> {
    let found = discover(api);
    let f = resolve(&found, device)?;
    require_full_support(f)?;

    let profile = Profile::load(input, format)?;
    println!(
        "loaded {} (model {}, {} normal + {} fn bytes)",
        input.display(),
        if profile.model.is_empty() { "?" } else { &profile.model },
        profile.normal.len(),
        profile.fnl.len()
    );

    let dev = open(api, f)?;
    let proto = Proto::new(&dev);
    let info = proto.get_info()?;
    if !profile.model.is_empty()
        && !info.type_number.is_empty()
        && !model_compatible(&profile.model, &info.type_number)
    {
        anyhow::bail!(
            "file is for model {:?} but the connected keyboard is {:?} — refusing (use a matching file)",
            profile.model,
            info.type_number
        );
    }

    if !confirm {
        println!("DRY RUN — file validated and model matches. Re-run with --confirm to write.");
        return Ok(());
    }

    proto.write_active(&profile.normal, &profile.fnl)?;
    println!("ok: keymap written to {} and applied.", info.type_number);
    Ok(())
}

fn cmd_export(api: &HidApi, device: &str, output: &std::path::Path, format: Format) -> Result<()> {
    let found = discover(api);
    let f = resolve(&found, device)?;
    require_full_support(f)?;

    let dev = open(api, f)?;
    let proto = Proto::new(&dev);
    let info = proto.get_info()?;
    let (_mode, normal, fnl) = proto.read_active()?;
    let dip = proto.dip_switches().unwrap_or_else(|_| vec![false; 6]);
    let sleep = proto.sleep_setting().unwrap_or(0) as i64;

    let profile = Profile {
        model: info.type_number,
        dip,
        sleep,
        layout: 0,
        normal,
        fnl,
    };
    let out_format = if format == Format::Auto { Format::OpenhhkbJson } else { format };
    let text = profile.to_string(out_format)?;
    std::fs::write(output, text).with_context(|| format!("writing {}", output.display()))?;
    println!("exported {} keymap to {}", profile.model, output.display());
    Ok(())
}

fn cmd_firmware_recovery(api: &HidApi, device: &str, _confirm: bool) -> Result<()> {
    let found = discover(api);
    let f = resolve(&found, device)?;
    require_full_support(f)?;
    anyhow::bail!("firmware-recovery is not implemented yet");
}

fn cmd_firmware_flash(api: &HidApi, device: &str, input: &std::path::Path, confirm: bool) -> Result<()> {
    let found = discover(api);
    let f = resolve(&found, device)?;
    require_full_support(f)?;

    let bytes = std::fs::read(input).with_context(|| format!("reading {}", input.display()))?;
    let dev = open(api, f)?;
    let proto = Proto::new(&dev);
    let info = proto.get_info()?;

    let plan = firmware::plan_flash(&bytes, &info.type_number, confirm)?;
    println!(
        "firmware {}  model-id {}  version {}  size {} B  CRC {:#06x} ({})",
        input.display(),
        plan.hfb.model_id,
        plan.hfb.version,
        plan.hfb.size_body,
        plan.hfb.stored_crc,
        if plan.hfb.crc_ok() { "ok" } else { "MISMATCH" },
    );
    println!("device   {}  current app {}", info.type_number, info.app_version);

    if !plan.confirmed {
        println!("DRY RUN — image validated. Re-run with --confirm to flash.");
        return Ok(());
    }

    eprintln!(
        "WARNING: flashing firmware. This is irreversible and can brick the keyboard. \
The E0-E3 framing matches CONNECT/happy-hacking-gnu but openhhkb has not completed a verified hardware flash."
    );
    firmware::execute_flash(&proto, &bytes)?;
    println!("firmware sent. Re-enumerate the device and verify with `openhhkb firmware-info`.");
    Ok(())
}

/// Loose model compatibility: compare the file's model string against the device type number.
fn model_compatible(file_model: &str, device_type: &str) -> bool {
    let norm = |s: &str| s.to_uppercase().replace(['-', ' '], "");
    let (a, b) = (norm(file_model), norm(device_type));
    // Match on the shared prefix (e.g. PD-KB820BS vs PD-KB820B).
    a.starts_with(&b) || b.starts_with(&a)
}
