"""Real OpenSSH pre-authentication proofs using disposable inetd instances.

Only this fixture maps the production 127.0.0.1:22 probe to an ephemeral local
port. It does not change host SSH configuration, accounts or existing keys.
"""
import importlib.util
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssh_proof', ROOT / 'scripts/ssh-readiness.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)


@unittest.skipUnless(Path('/usr/sbin/sshd').is_file(), 'OpenSSH server is required')
class ActualHostProofTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.first = self.directory / 'host_key'
        self.second = self.directory / 'other_key'
        for key in (self.first, self.second):
            subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
        self.first_public = Path(str(self.first) + '.pub').read_text().split()[1]
        self.second_public = Path(str(self.second) + '.pub').read_text().split()[1]
        self.config = self.directory / 'sshd_config'
        self.config.write_text('HostKey ' + str(self.first) + '\nUsePAM no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n')

    def probe(self, public_key, after_banner=None, corrupt_signature=False):
        errors, modified = [], []
        with socket.socket() as listener:
            listener.settimeout(10)
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            def serve():
                process = None
                try:
                    connection, _ = listener.accept()
                    with connection, open(self.directory / 'sshd.log', 'wb') as log:
                        process = subprocess.Popen(['/usr/sbin/sshd', '-i', '-e', '-f', str(self.config)],
                                                   stdin=connection, stdout=subprocess.PIPE, stderr=log)
                        banner = process.stdout.readline(256)
                        if not banner.startswith(b'SSH-2.0-'):
                            raise AssertionError('Isolated sshd did not start')
                        # sshd has loaded its private key before sending its banner.
                        if after_banner:
                            after_banner()
                        connection.sendall(banner)
                        pending = b''
                        while True:
                            data = os.read(process.stdout.fileno(), 65536)
                            if not data:
                                break
                            if corrupt_signature and not modified:
                                pending += data
                                while len(pending) >= 4 and not modified:
                                    length = int.from_bytes(pending[:4], 'big')
                                    if length > 262144:
                                        raise AssertionError('Unexpected SSH packet size')
                                    if len(pending) < length + 4:
                                        break
                                    packet, pending = bytearray(pending[:length + 4]), pending[length + 4:]
                                    if packet[5] == 31:  # SSH_MSG_KEX_ECDH_REPLY
                                        # The host-key blob remains unchanged; only
                                        # the signature's final byte is corrupted.
                                        packet[length + 4 - packet[4] - 1] ^= 1
                                        modified.append(True)
                                    connection.sendall(packet)
                                if modified and pending:
                                    connection.sendall(pending)
                                    pending = b''
                            else:
                                connection.sendall(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # The host-proof probe closes immediately after KEX.
                except Exception as error:
                    errors.append(error)
                finally:
                    if process is not None:
                        if process.poll() is None:
                            process.kill()
                        process.wait(timeout=2)
                        process.stdout.close()
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            actual_exchange = ssh.verified_key_exchange
            def map_port(args):
                mapped = list(args)
                self.assertEqual(mapped[-5:], ['-l', 'agpc-hostkey-probe', '-p', '22', '127.0.0.1'])
                mapped[-2] = str(port)
                # Preserve the exact production pin while only the fixture port differs.
                mapped[-1:-1] = ['-o', 'HostKeyAlias=127.0.0.1']
                return actual_exchange(mapped)
            with patch.object(ssh, 'PROBE_DIRECTORY', str(self.directory)), \
                 patch.object(ssh, 'verified_key_exchange', side_effect=map_port):
                result = ssh.pinned_host_key_ready(public_key)
            thread.join(timeout=12)
            self.assertFalse(thread.is_alive(), 'Isolated sshd was not reaped')
            if errors:
                raise errors[0]
            if corrupt_signature:
                self.assertTrue(modified, 'Signature-corruption fixture did not run')
            self.assertFalse(list(self.directory.glob('agpc-ssh-probe.*')))
            return result

    def test_matching_live_key_proves_signature_without_authentication(self):
        def snapshot():
            metadata = self.first.stat()
            return (self.config.read_bytes(), Path(str(self.first) + '.pub').read_bytes(),
                    tuple(getattr(metadata, field) for field in ('st_dev', 'st_ino', 'st_mode', 'st_uid',
                          'st_gid', 'st_size', 'st_mtime_ns', 'st_ctime_ns')))
        before = snapshot()
        self.assertTrue(self.probe(self.first_public))
        self.assertEqual(before, snapshot())

    def test_custom_served_host_key_is_refused_without_configuration_changes(self):
        self.config.write_text(self.config.read_text().replace(str(self.first), str(self.second)))
        before = self.config.read_bytes()
        self.assertFalse(self.probe(self.first_public))
        self.assertEqual(before, self.config.read_bytes())

    def test_matching_public_key_with_invalid_kex_signature_is_refused(self):
        self.assertFalse(self.probe(self.first_public, corrupt_signature=True))

    def test_peer_cannot_forge_the_proof_through_multiline_debug_messages(self):
        # SSH_MSG_DEBUG is accepted before KEX negotiation. Even a peer that
        # knows this local client's PID must not impersonate a local proof log.
        children, errors = [], []
        started = threading.Event()
        with socket.socket() as listener:
            listener.settimeout(5)
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            def malicious_peer():
                try:
                    with listener.accept()[0] as connection:
                        connection.settimeout(5)
                        connection.recv(4096)
                        if not started.wait(2):
                            raise AssertionError('Probe client did not start')
                        message = ('\r\ndebug1: SSH2_MSG_NEWKEYS received\r\n'
                                   'debug1: kex.c:kex_input_newkeys():529 (bin=/usr/bin/ssh, pid=' +
                                   str(children[0].pid) + '): SSH2_MSG_NEWKEYS received\r\n').encode()
                        payload = b'\x04\x01' + struct.pack('!I', len(message)) + message + struct.pack('!I', 0)
                        padding = 8 - ((len(payload) + 5) % 8)
                        if padding < 4:
                            padding += 8
                        packet = struct.pack('!I', len(payload) + padding + 1) + bytes([padding]) + payload + bytes(padding)
                        connection.sendall(b'SSH-2.0-malicious-fixture\r\n' + packet)
                        connection.recv(4096)
                except Exception as error:
                    errors.append(error)
            thread = threading.Thread(target=malicious_peer, daemon=True)
            thread.start()
            actual_exchange, actual_popen = ssh.verified_key_exchange, subprocess.Popen
            def start(*args, **kwargs):
                process = actual_popen(*args, **kwargs)
                children.append(process)
                started.set()
                return process
            def map_port(args):
                mapped = list(args)
                mapped[-2] = str(listener.getsockname()[1])
                return actual_exchange(mapped)
            with patch.object(ssh, 'PROBE_DIRECTORY', str(self.directory)), \
                 patch.object(ssh, 'verified_key_exchange', side_effect=map_port), \
                 patch.object(ssh.subprocess, 'Popen', side_effect=start):
                self.assertFalse(ssh.pinned_host_key_ready(self.first_public))
            thread.join(timeout=7)
            self.assertFalse(thread.is_alive())
            if errors:
                raise errors[0]

    def test_daemon_holding_stale_key_is_refused_after_files_change(self):
        def replace_fixture_files():
            self.second.replace(self.first)
            Path(str(self.second) + '.pub').replace(Path(str(self.first) + '.pub'))
        self.assertFalse(self.probe(self.second_public, after_banner=replace_fixture_files))
        self.assertEqual(Path(str(self.first) + '.pub').read_text().split()[1], self.second_public)
        self.assertTrue(self.probe(self.second_public))


if __name__ == '__main__':
    unittest.main()
