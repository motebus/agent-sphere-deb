#!/usr/bin/env python3
"""Build and audit the documentation-only Agent Sphere metapackage."""
import argparse
import gzip
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
NAMES = {"sphered", "moted", "mote-proxy", "mote-transportd", "medge", "mlink"}
DOC = "usr/share/doc/agent-sphere/"
PAYLOAD = {DOC + "README.md", DOC + "copyright"}


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
    if meta["Package"] != "agent-sphere" or meta["Architecture"] != "all":
        raise ValueError("wrong package identity")
    if set(meta) != {"Package", "Version", "Architecture", "Section", "Priority",
                    "Maintainer", "Homepage", "Depends", "Description"}:
        raise ValueError("unexpected control fields")
    deps = meta["Depends"].split(",")
    matches = [re.fullmatch(r"([a-z][a-z0-9-]*) \(>= ([0-9][0-9A-Za-z.+:~\-]*)\)", d.strip()) for d in deps]
    if len(deps) != 6 or not all(matches) or {m[1] for m in matches} != NAMES:
        raise ValueError("dependency boundary violation")
    baseline = json.loads((ROOT / "component-baseline.json").read_text())
    if {p["name"]: p["version"] for p in baseline["packages"]} != {m[1]: m[2] for m in matches}:
        raise ValueError("dependency floors differ from component baseline")


def archive(path, flag):
    data = subprocess.check_output(["dpkg-deb", flag, str(path)])
    return tarfile.open(fileobj=io.BytesIO(data))


def verify(path):
    with archive(path, "--ctrl-tarfile") as arc:
        files = [m for m in arc if not m.isdir()]
        if len(files) != 1 or files[0].name.removeprefix("./") != "control" or not files[0].isfile():
            raise ValueError("control archive must contain only control; hooks are forbidden")
        check_control(fields(arc.extractfile(files[0]).read().decode()))
    with archive(path, "--fsys-tarfile") as arc:
        files = set()
        allowed_dirs = {"", "usr", "usr/share", "usr/share/doc", "usr/share/doc/agent-sphere"}
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
                source = ROOT / ("README.md" if name.endswith("README.md") else "packaging/copyright")
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
        shutil.copyfile(ROOT / "README.md", docs / "README.md")
        shutil.copyfile(ROOT / "packaging/copyright", docs / "copyright")
        for p in [stage, *stage.rglob("*")]:
            p.chmod(0o755 if p.is_dir() else 0o644)
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
    path = out / ("agent-sphere_" + control()["Version"] + "_all.deb")
    verify(path)
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    data = {"schema": "agent-sphere-release/v1", "package": "agent-sphere",
            "version": control()["Version"], "architecture": "all",
            "status": "composition-prerelease", "sphere_ready_verified": False,
            "source": "https://github.com/motebus/agent-sphere-deb", "source_commit": commit,
            "source_ref": "refs/heads/main", "asset": path.name, "sha256": digest(path),
            "build_run": os.environ.get("GITHUB_SERVER_URL", "https://github.com") + "/" +
            os.environ.get("GITHUB_REPOSITORY", "motebus/agent-sphere-deb") + "/actions/runs/" +
            os.environ.get("GITHUB_RUN_ID", "local"),
            "component_baseline": json.loads((ROOT / "component-baseline.json").read_text())}
    record = out / "release-manifest.json"
    record.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    (out / "SHA256SUMS").write_text("".join(digest(p) + "  " + p.name + "\n" for p in [path, record]))


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
