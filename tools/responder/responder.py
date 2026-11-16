#!/usr/bin/env python3
"""Host-side brain for vhhkb.

Starts vhhkb inside the throwaway VM over SSH, declares the virtual devices from a profile,
logs every report the official tool sends, and answers with replies from a rules module that is
hot-reloaded on every change. Never talks to real hardware.

    python3 tools/responder/responder.py hhkb-studio-jis
    python3 tools/responder/responder.py hhkb-hybrid-jis --vm admin@192.168.64.3

Profiles: tools/responder/profiles/<device>.json
Rules:    tools/responder/rules/<device>.py, providing  handle(iface, data, state) -> [(iface, bytes), ...]
Logs:     analysis/<device>/captures/<timestamp>.jsonl
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
VM_BIN = "~/vhhkb/vhhkb"


class Rules:
    def __init__(self, path):
        self.path = path
        self.mtime = None
        self.mod = None
        self.state = {}

    def get(self):
        m = self.path.stat().st_mtime
        if m != self.mtime:
            spec = importlib.util.spec_from_file_location(f"rules_{int(m)}", self.path)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                self.mod, self.mtime = mod, m
                print(f"[rules] loaded {self.path.name}", file=sys.stderr)
            except Exception as e:  # keep the old rules on a syntax error
                print(f"[rules] reload failed, keeping previous: {e}", file=sys.stderr)
                self.mtime = m
        return self.mod


def ssh_cmd(vm, password):
    askpass = pathlib.Path(tempfile.gettempdir()) / "vhhkb-askpass.sh"
    askpass.write_text(f"#!/bin/sh\necho '{password}'\n")
    askpass.chmod(0o700)
    env = dict(os.environ, SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE="force", DISPLAY="x")
    opts = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]
    return ["ssh", *opts, vm], env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("device", help="profile name, e.g. hhkb-studio-jis")
    ap.add_argument("--vm", default="admin@192.168.64.3")
    ap.add_argument("--password", default=os.environ.get("VHHKB_PASSWORD", "admin"))
    args = ap.parse_args()

    profile = json.loads((HERE / "profiles" / f"{args.device}.json").read_text())
    rules = Rules(HERE / "rules" / f"{args.device}.py")
    capdir = ROOT / "analysis" / args.device / "captures"
    capdir.mkdir(parents=True, exist_ok=True)
    logpath = capdir / f"{dt.datetime.now():%Y%m%d-%H%M%S}.jsonl"
    log = logpath.open("a")
    t0 = time.monotonic()

    def record(direction, iface, data, **extra):
        rec = {"t": round(time.monotonic() - t0, 4), "dir": direction, "if": iface, "hex": data.hex(), **extra}
        log.write(json.dumps(rec) + "\n")
        log.flush()
        print(f"{rec['t']:9.3f} {direction:3} if{iface} {data.hex(' ')}", flush=True)

    cmd, env = ssh_cmd(args.vm, args.password)
    proc = subprocess.Popen(cmd + [VM_BIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                            env=env, bufsize=1)
    send_lock = threading.Lock()

    def send(line):
        with send_lock:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()

    for iface in profile["interfaces"]:
        desc = (ROOT / iface["descriptor"]).read_bytes()
        fields = ["DEV", iface["n"], profile["vid"], profile["pid"], profile["version"], profile["location"],
                  profile["product"], profile["manufacturer"], desc.hex()]
        send("\t".join(str(x) for x in fields))
    send("GO")
    print(f"[responder] {args.device}: logging to {logpath.relative_to(ROOT)}", file=sys.stderr)

    try:
        for line in proc.stdout:
            f = line.rstrip("\n").split("\t")
            if f[0] == "OUT":
                iface, rtype, rid, data = int(f[1]), int(f[2]), int(f[3]), bytes.fromhex(f[4] if len(f) > 4 else "")
                mod = rules.get()
                logged = mod.redact(iface, data) if mod and hasattr(mod, "redact") else data
                record("out", iface, logged, type=rtype, id=rid, **({"redacted": True} if logged != data else {}))
                try:
                    replies = mod.handle(iface, data, rules.state) if mod else []
                except Exception as e:
                    print(f"[rules] handle() raised: {e!r}", file=sys.stderr)
                    replies = []
                for riface, rdata in replies or []:
                    record("in", riface, rdata)
                    send(f"IN\t{riface}\t{rdata.hex()}")
            elif f[0] in ("READY", "GET", "ERR"):
                print(f"[vhhkb] {' '.join(f)}", file=sys.stderr)
                log.write(json.dumps({"t": round(time.monotonic() - t0, 4), "event": " ".join(f)}) + "\n")
                log.flush()
            else:
                print(f"[vhhkb?] {line.rstrip()}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            send("QUIT")
        except Exception:
            pass
        proc.terminate()
        log.close()


if __name__ == "__main__":
    main()
