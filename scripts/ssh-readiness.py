#!/usr/bin/python3
"""Validate and activate Ubuntu SSH without modifying its owner configuration."""
import base64
import binascii
import json
import os
import re
import selectors
import socket
import stat
import subprocess
import sys
import tempfile
import time


class Refused(Exception):
    pass


SSH_DIRECTORY = "/etc/ssh"
PROBE_DIRECTORY = "/run"
ED25519_PUBLIC_PREFIX = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"


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


def host_key_metadata(path, private=False):
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return None
    forbidden = 0o077 if private else 0o022
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or
            metadata.st_mode & forbidden or metadata.st_nlink != 1):
        raise Refused("ssh-host-key-file-untrusted")
    return metadata


def ensure_ed25519_host_key():
    # Only OpenSSH creates private key material. This helper inspects private
    # file metadata, never opens its contents, and reads only the public file.
    for path in (os.path.dirname(SSH_DIRECTORY), SSH_DIRECTORY):
        metadata = os.lstat(path)
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise Refused("ssh-host-key-directory-untrusted")
    private = os.path.join(SSH_DIRECTORY, "ssh_host_ed25519_key")
    public = private + ".pub"
    private_metadata = host_key_metadata(private, private=True)
    public_metadata = host_key_metadata(public)
    if private_metadata is None and public_metadata is None:
        # -A creates missing standard host keys and does not rotate existing
        # keys. Refuse a partial pair rather than replacing an owner's identity.
        if command(["/usr/bin/ssh-keygen", "-A"]).returncode:
            raise Refused("ssh-host-key-generation-failed")
        private_metadata = host_key_metadata(private, private=True)
        public_metadata = host_key_metadata(public)
    if private_metadata is None or public_metadata is None:
        raise Refused("ssh-ed25519-host-key-pair-incomplete")
    descriptor = os.open(public, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_mode, opened.st_uid, opened.st_nlink) != (
                public_metadata.st_dev, public_metadata.st_ino, public_metadata.st_mode,
                public_metadata.st_uid, public_metadata.st_nlink):
            raise Refused("ssh-host-key-file-changed")
        data = stream.read(4097)
    try:
        lines = data.decode("ascii").strip().splitlines()
        fields = lines[0].split() if len(lines) == 1 else []
        if len(data) > 4096 or len(fields) < 2 or fields[0] != "ssh-ed25519":
            raise ValueError()
        wire = base64.b64decode(fields[1], validate=True)
        if len(wire) != len(ED25519_PUBLIC_PREFIX) + 32 or not wire.startswith(ED25519_PUBLIC_PREFIX):
            raise ValueError()
        if base64.b64encode(wire).decode("ascii") != fields[1]:
            raise ValueError()
    except (UnicodeError, ValueError, binascii.Error):
        raise Refused("ssh-ed25519-host-public-key-invalid") from None
    return fields[1]


def verified_key_exchange(args):
    # Ordinary stderr can contain peer-supplied multiline diagnostics. The
    # caller suppresses them and forces only this local OpenSSH source/function
    # record, emitted after signature verification. Bind it to this process.
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, start_new_session=True,
                               env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
    try:
        marker = re.compile(rb"debug1: kex\.c:kex_input_newkeys\(\):[0-9]+ \((?:bin=(?:/usr/bin/)?ssh, )?pid=" +
                            str(process.pid).encode("ascii") + rb"\): SSH2_MSG_NEWKEYS received")
        deadline, received, pending = time.monotonic() + 5, 0, b""
        with selectors.DefaultSelector() as selector:
            selector.register(process.stderr, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    return False
                data = os.read(process.stderr.fileno(), 4096)
                if not data:
                    return False
                received += len(data)
                if received > 65536:
                    return False
                pending += data
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    if marker.fullmatch(line.rstrip(b"\r")):
                        return True
    finally:
        try:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)
        finally:
            process.stderr.close()


def pinned_host_key_ready(public_key):
    # The pinned value comes only from the validated local public key file.
    # This is a host-proof probe: no user credentials, session or command.
    with tempfile.TemporaryDirectory(prefix="agpc-ssh-probe.", dir=PROBE_DIRECTORY) as directory:
        known_hosts = os.path.join(directory, "known_hosts")
        descriptor = os.open(known_hosts, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write("127.0.0.1 ssh-ed25519 " + public_key + "\n")
        options = (
            "StrictHostKeyChecking=yes", "UserKnownHostsFile=" + known_hosts,
            "GlobalKnownHostsFile=/dev/null", "HostKeyAlgorithms=ssh-ed25519",
            "UpdateHostKeys=no", "VerifyHostKeyDNS=no", "CanonicalizeHostname=no",
            "BatchMode=yes", "IdentityFile=none", "IdentityAgent=none", "IdentitiesOnly=yes",
            "PubkeyAuthentication=no", "PasswordAuthentication=no", "KbdInteractiveAuthentication=no",
            "GSSAPIAuthentication=no", "HostbasedAuthentication=no", "PreferredAuthentications=none",
            "NumberOfPasswordPrompts=0", "ConnectionAttempts=1", "ConnectTimeout=2",
            "ClearAllForwardings=yes", "ForwardAgent=no", "ForwardX11=no", "PermitLocalCommand=no",
            "ControlMaster=no", "ControlPath=none", "ControlPersist=no", "ProxyCommand=none", "ProxyJump=none",
            "LogVerbose=kex.c:kex_input_newkeys():*",
        )
        # -q overrides -vv's ordinary output; LogVerbose forces only the local
        # proof record. Peers cannot inject a fake marker through debug/errors.
        args = ["/usr/bin/ssh", "-F", "/dev/null", "-vv", "-q", "-N", "-T"]
        for option in options:
            args.extend(["-o", option])
        args.extend(["-l", "agpc-hostkey-probe", "-p", "22", "127.0.0.1"])
        return verified_key_exchange(args)


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
              "ssh_host_key_ready": False,
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
        public_key = ensure_ed25519_host_key()
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
        # authentication edits, listen changes or firewall edits.
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
        if not pinned_host_key_ready(public_key):
            raise Refused("loopback-ssh-host-key-unverified")
        result["ssh_host_key_ready"] = True
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
