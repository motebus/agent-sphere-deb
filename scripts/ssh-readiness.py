#!/usr/bin/python3
"""Validate and activate Ubuntu SSH without modifying its owner configuration."""
import json
import os
import socket
import stat
import subprocess
import sys
import time


class Refused(Exception):
    pass


def command(args, timeout=30):
    return subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=timeout, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})


def unit(name):
    result = command(["/usr/bin/systemctl", "show", name,
                      "--property=LoadState,ActiveState,SubState,UnitFileState"])
    if result.returncode:
        raise Refused("systemd-unit-inspection-failed")
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    expected = {"LoadState", "ActiveState", "SubState", "UnitFileState"}
    if set(fields) != expected or any(not value.replace("-", "").isalnum() for value in fields.values() if value):
        raise Refused("systemd-unit-state-invalid")
    return fields


def trusted_runtime_directory():
    # sshd -t needs its privilege-separation directory on fresh Ubuntu installs.
    # Create only this missing directory; never follow a link or repair ownership.
    root = os.lstat("/run")
    if not stat.S_ISDIR(root.st_mode) or root.st_uid != 0 or root.st_mode & 0o022:
        raise Refused("ssh-runtime-parent-untrusted")
    try:
        previous = os.umask(0o022)
        try:
            os.mkdir("/run/sshd", 0o755)
        finally:
            os.umask(previous)
    except FileExistsError:
        pass
    metadata = os.lstat("/run/sshd")
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
        raise Refused("ssh-runtime-directory-untrusted")


def banner_ready():
    # This is the existing MoteD host handoff target, not a MoteC reachability test.
    try:
        with socket.create_connection(("127.0.0.1", 22), timeout=2) as stream:
            deadline = time.monotonic() + 2
            data = bytearray()
            while len(data) < 255:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                stream.settimeout(remaining)
                part = stream.recv(1)
                if not part:
                    break
                data.extend(part)
                if part == b"\n":
                    return bytes(data).startswith((b"SSH-2.0-", b"SSH-1.99-"))
    except (OSError, TimeoutError):
        pass
    return False


def ensure_ssh_ready():
    result = {"schema": "agpc.ssh-readiness/v1", "package_installed": False,
              "configuration_valid": False, "activation_unit": None,
              "boot_enabled": False, "loopback_ssh_ready": False,
              "mote_reachability": "not-tested", "full_runtime_ready": False,
              "units": {}, "error": None}
    try:
        if os.geteuid() != 0:
            raise Refused("root-required")
        package = command(["/usr/bin/dpkg-query", "-W", "-f=${Status}", "openssh-server"])
        if package.returncode or package.stdout != "install ok installed":
            raise Refused("openssh-server-not-configured")
        result["package_installed"] = True
        trusted_runtime_directory()
        if command(["/usr/sbin/sshd", "-t"]).returncode:
            raise Refused("sshd-configuration-invalid")
        result["configuration_valid"] = True
        service, listener = unit("ssh.service"), unit("ssh.socket")
        result["units"] = {"ssh.service": service, "ssh.socket": listener}
        if service["LoadState"] != "loaded" or service["UnitFileState"] in {"masked", "masked-runtime"}:
            raise Refused("ssh-service-masked-or-unavailable")
        active = {"active", "activating", "reloading"}
        enabled = {"enabled", "enabled-runtime"}
        socket_selected = listener["LoadState"] == "loaded" and listener["UnitFileState"] not in {"masked", "masked-runtime"} and (
            listener["UnitFileState"] in enabled or listener["ActiveState"] in active)
        selected = "ssh.socket" if socket_selected else "ssh.service"
        result["activation_unit"] = selected
        state = listener if socket_selected else service
        # Preserve the existing socket/service choice. No restart, stop, unmask,
        # key generation, authentication edits, listen changes or firewall edits.
        if state["UnitFileState"] != "enabled":
            if command(["/usr/bin/systemctl", "enable", selected]).returncode:
                raise Refused("ssh-enable-failed")
        # An enabled socket may currently be stopped while its already-running
        # service owns port 22. Preserve that live listener instead of starting
        # a second socket on the occupied address; socket boot intent remains.
        if state["ActiveState"] not in active and not (socket_selected and service["ActiveState"] in active):
            if command(["/usr/bin/systemctl", "start", selected]).returncode:
                raise Refused("ssh-start-failed")
        for _ in range(10):
            if banner_ready():
                result["loopback_ssh_ready"] = True
                break
            time.sleep(0.5)
        result["units"] = {name: unit(name) for name in ("ssh.service", "ssh.socket")}
        final = result["units"][selected]
        result["boot_enabled"] = final["UnitFileState"] == "enabled"
        current_listener_active = final["ActiveState"] == "active" or (
            socket_selected and result["units"]["ssh.service"]["ActiveState"] == "active")
        if not result["boot_enabled"] or not current_listener_active:
            raise Refused("ssh-activation-not-ready")
        if not result["loopback_ssh_ready"]:
            raise Refused("loopback-ssh-banner-unavailable")
    except Refused as error:
        result["error"] = str(error)
    except (OSError, ValueError, subprocess.SubprocessError):
        # Never include command output or owner configuration in the report.
        result["error"] = "ssh-verification-unavailable"
    return result


if __name__ == "__main__":
    if sys.argv[1:] != ["--ensure"]:
        sys.exit("Usage: ssh-readiness.py --ensure")
    report = ensure_ssh_ready()
    print(json.dumps(report, sort_keys=True))
    sys.exit(0 if report["error"] is None else 1)
