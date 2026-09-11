#!/usr/bin/env python3
"""Build and audit the declarative systemd target Agent Sphere metapackage."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NAMES = {'mlink', 'mote-proxy', 'model-router', 'cx-mesh', 'mote-mcpd', 'model-llm', 'moted', 'mote-transportd', 'mote-secd', 'agos', 'sphered'}
DOC = "usr/share/doc/agent-sphere/"
TARGET = "usr/lib/systemd/system/agentsphere.target"
SOURCES = {DOC + "README.md": "README.md", DOC + "copyright": "packaging/copyright", TARGET: "packaging/agentsphere.target"}
PAYLOAD = set(SOURCES)
HOOKS = {"postinst", "prerm", "postrm"}


def fields(text):
    result = {}
    key = None
    for line in text.splitlines():
        if line.startswith(" ") and key:
            result[key] += "\n" + line
        elif line:
            key, value = line.split(":", 1)
            if key in result:
                raise ValueError("duplicate control field: " + key)
            result[key] = value.strip()
    return result


def control():
    return fields((ROOT / "packaging/control").read_text())


def check_control(meta):
    expected = control()
    if meta != expected:
        raise ValueError("package metadata differs from reviewed control")
    if meta["Package"] != "agent-sphere" or meta["Architecture"] != "all" or meta["Version"] != "0.2.0-9":
        raise ValueError("wrong package identity")
    if set(meta) != {"Package", "Version", "Architecture", "Section", "Priority",
                    "Maintainer", "Homepage", "Depends", "Description"}:
        raise ValueError("unexpected control fields")
    deps = meta["Depends"].split(",")
    matches = [re.fullmatch(r"([a-z][a-z0-9-]*) \(>= ([0-9][0-9A-Za-z.+:~\-]*)\)", d.strip()) for d in deps]
    if len(deps) != 12 or not all(matches) or {m[1] for m in matches} != NAMES | {"init-system-helpers"}:
        raise ValueError("dependency boundary violation")
    baseline = json.loads((ROOT / "component-baseline.json").read_text())
    if {**{p["name"]: p["version"] for p in baseline["packages"]}, **baseline["system_dependencies"]} != {m[1]: m[2] for m in matches}:
        raise ValueError("dependency floors differ from component baseline")


def archive(path, flag):
    data = subprocess.check_output(["dpkg-deb", flag, str(path)])
    return tarfile.open(fileobj=io.BytesIO(data))


def verify(path):
    with archive(path, "--ctrl-tarfile") as arc:
        seen = set()
        for member in arc:
            name = member.name.removeprefix("./").rstrip("/")
            if member.uid != 0 or member.gid != 0:
                raise ValueError("control member is not root-owned")
            if member.isdir():
                if name not in {"", "."} or member.mode != 0o755:
                    raise ValueError("unexpected control directory")
                continue
            if not member.isfile() or name not in HOOKS | {"control"} or name in seen:
                raise ValueError("unexpected control payload")
            if member.mode != (0o644 if name == "control" else 0o755):
                raise ValueError("wrong control permissions")
            contents = arc.extractfile(member).read()
            if name == "control":
                check_control(fields(contents.decode()))
            elif contents != (ROOT / "packaging" / name).read_bytes():
                raise ValueError("native target hook differs from reviewed source")
            seen.add(name)
        if seen != HOOKS | {"control"}:
            raise ValueError("incomplete native target lifecycle")
    with archive(path, "--fsys-tarfile") as arc:
        files = set()
        allowed_dirs = {"", "usr", "usr/share", "usr/share/doc", "usr/share/doc/agent-sphere", "usr/lib", "usr/lib/systemd", "usr/lib/systemd/system"}
        for member in arc:
            name = member.name.removeprefix("./").rstrip("/")
            if name == ".":
                name = ""
            if member.uid != 0 or member.gid != 0:
                raise ValueError("archive member is not root-owned")
            if member.isdir():
                if name not in allowed_dirs or member.mode != 0o755:
                    raise ValueError("unexpected directory or permission: " + name)
            else:
                if not member.isfile() or name not in PAYLOAD or member.mode != 0o644 or name in files:
                    raise ValueError("unexpected payload or permission: " + name)
                source = ROOT / SOURCES[name]
                if arc.extractfile(member).read() != source.read_bytes():
                    raise ValueError("documentation bytes differ: " + name)
                files.add(name)
        if files != PAYLOAD:
            raise ValueError("incomplete documentation payload")


def build(out):
    meta = control()
    check_control(meta)
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / "build").mkdir(exist_ok=True)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or subprocess.check_output(
        ["git", "-C", str(ROOT), "log", "-1", "--format=%ct"], text=True).strip())
    with tempfile.TemporaryDirectory(prefix="agent-sphere-", dir=ROOT / "build") as tmp:
        stage = Path(tmp) / "root"
        (stage / "DEBIAN").mkdir(parents=True)
        docs = stage / DOC
        docs.mkdir(parents=True)
        shutil.copyfile(ROOT / "packaging/control", stage / "DEBIAN/control")
        for target, source in SOURCES.items():
            destination = stage / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, destination)
        for hook in HOOKS:
            shutil.copyfile(ROOT / "packaging" / hook, stage / "DEBIAN" / hook)
        for p in [stage, *stage.rglob("*")]:
            p.chmod(0o755 if p.is_dir() or (p.parent.name == "DEBIAN" and p.name in HOOKS) else 0o644)
            os.utime(p, (epoch, epoch))
        result = out / ("agent-sphere_" + meta["Version"] + "_all.deb")
        subprocess.run(["dpkg-deb", "--build", "--root-owner-group", "-Zxz", "-z9",
                        str(stage), str(result)], check=True,
                       env={**os.environ, "SOURCE_DATE_EPOCH": str(epoch)})
    verify(result)
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(out):
    if "PENDING_REVIEWED_" in (ROOT / "agpc.sh").read_text():
        raise ValueError("release blocked: exact committed-main migration artifacts are required")
    path = out / ("agent-sphere_" + control()["Version"] + "_all.deb")
    verify(path)
    if (ROOT / "agpc.sh").read_bytes() != (ROOT / "agent-sphere-apps.sh").read_bytes():
        raise ValueError("compatibility installer differs from canonical agpc.sh")
    installer = out / "agpc.sh"
    shutil.copyfile(ROOT / installer.name, installer)
    installer.chmod(0o755)
    alias = out / "agent-sphere-apps.sh"
    shutil.copyfile(installer, alias)
    alias.chmod(0o755)
    if subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip():
        raise ValueError("manifest requires clean committed source")
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    data = {"schema": "agent-sphere-release/v2", "package": "agent-sphere",
            "version": control()["Version"], "architecture": "all",
            "status": "composition-prerelease", "sphere_ready_verified": False,
            "source": "https://github.com/motebus/agent-sphere-deb", "source_commit": commit,
            "source_ref": os.environ.get("GITHUB_REF", "local"), "asset": path.name, "sha256": digest(path),
            "assets": [{"name": p.name, "sha256": digest(p)} for p in [path, installer, alias]],
            "build_run": os.environ.get("GITHUB_SERVER_URL", "https://github.com") + "/" +
            os.environ.get("GITHUB_REPOSITORY", "motebus/agent-sphere-deb") + "/actions/runs/" +
            os.environ.get("GITHUB_RUN_ID", "local"),
            "component_baseline": json.loads((ROOT / "component-baseline.json").read_text())}
    record = out / "release-manifest.json"
    record.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    (out / "SHA256SUMS").write_text("".join(digest(p) + "  " + p.name + "\n" for p in [path, installer, alias, record]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "verify", "manifest"])
    parser.add_argument("path", nargs="?", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if args.action == "build":
        print(build(args.path.resolve()))
    elif args.action == "verify":
        verify(args.path.resolve())
        print("Package boundary audit passed")
    else:
        manifest(args.path.resolve())
