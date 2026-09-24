import importlib.util
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssh_readiness', ROOT / 'scripts/ssh-readiness.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)


def state(enabled='enabled', active='active', load='loaded'):
    return {'LoadState': load, 'ActiveState': active, 'SubState': 'running' if active == 'active' else 'dead', 'UnitFileState': enabled}


class SshReadinessTests(unittest.TestCase):
    def exercise(self, service=None, listener=None, package=True, config=True, banner=True, failure=None, host_key_error=None, host_proof=True):
        states = {'ssh.service': service or state(), 'ssh.socket': listener or state('disabled', 'inactive')}
        calls = []
        def run(args, timeout=30):
            calls.append(args)
            result = subprocess.CompletedProcess(args, 0, '', '')
            if args[0].endswith('dpkg-query'):
                result.stdout = 'install ok installed' if package else 'install ok unpacked'
            elif args == ['/usr/sbin/sshd', '-t']:
                result.returncode = 0 if config else 1
                result.stderr = 'SECRET OWNER CONFIG MUST NOT APPEAR'
            elif args[1] == 'enable':
                if failure == 'enable': result.returncode = 1
                else: states[args[2]]['UnitFileState'] = 'enabled'
            elif args[1] == 'start':
                if failure == 'start': result.returncode = 1
                else: states[args[2]]['ActiveState'] = 'active'
            return result
        with patch.object(ssh.os, 'geteuid', return_value=0), \
             patch.object(ssh, 'command', side_effect=run), \
             patch.object(ssh, 'unit', side_effect=lambda name: dict(states[name])), \
             patch.object(ssh, 'ensure_ed25519_host_key', side_effect=host_key_error) as host_key, \
             patch.object(ssh, 'trusted_runtime_directory') as directory, \
             patch.object(ssh, 'banner_ready', return_value=banner), \
             patch.object(ssh, 'pinned_host_key_ready', return_value=host_proof) as proof, \
             patch.object(ssh.time, 'sleep'):
            result = ssh.ensure_ssh_ready()
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertFalse(any(value in args for args in calls for value in ('unmask', 'stop', 'restart', 'reload', 'ssh-keygen')))
        self.assertEqual(result['mote_reachability'], 'not-tested')
        self.assertFalse(result['full_runtime_ready'])
        if not package:
            host_key.assert_not_called()
        if not banner or not package or not config or host_key_error:
            proof.assert_not_called()
        return result, calls, directory

    def test_running_service_is_preserved_and_socket_is_not_enabled(self):
        result, calls, _ = self.exercise()
        self.assertIsNone(result['error'])
        self.assertTrue(result['ssh_host_key_ready'])
        self.assertEqual(result['activation_unit'], 'ssh.service')
        self.assertFalse(any('systemctl' in args[0] for args in calls))

    def test_socket_activation_preserves_inactive_service_and_checks_banner(self):
        result, calls, _ = self.exercise(service=state('disabled', 'inactive'), listener=state())
        self.assertIsNone(result['error'])
        self.assertEqual(result['activation_unit'], 'ssh.socket')
        self.assertEqual(result['units']['ssh.service']['ActiveState'], 'inactive')
        self.assertFalse(any('systemctl' in args[0] for args in calls))

    def test_enabled_inactive_socket_does_not_compete_with_running_service(self):
        result, calls, _ = self.exercise(service=state('disabled', 'active'), listener=state('enabled', 'inactive'))
        self.assertIsNone(result['error'])
        self.assertEqual(result['activation_unit'], 'ssh.socket')
        self.assertTrue(result['boot_enabled'])
        self.assertFalse(any('systemctl' in args[0] for args in calls))

    def test_enabled_socket_starts_socket_not_service(self):
        result, calls, _ = self.exercise(service=state('disabled', 'inactive'), listener=state('enabled', 'inactive'))
        self.assertIsNone(result['error'])
        self.assertIn(['/usr/bin/systemctl', 'start', 'ssh.socket'], calls)
        self.assertNotIn(['/usr/bin/systemctl', 'start', 'ssh.service'], calls)

    def test_disabled_service_is_enabled_and_started_with_existing_configuration(self):
        result, calls, _ = self.exercise(service=state('disabled', 'inactive'))
        self.assertIsNone(result['error'])
        self.assertIn(['/usr/bin/systemctl', 'enable', 'ssh.service'], calls)
        self.assertIn(['/usr/bin/systemctl', 'start', 'ssh.service'], calls)

    def test_active_runtime_socket_gets_boot_enablement_without_restart(self):
        result, calls, _ = self.exercise(service=state('disabled', 'inactive'), listener=state('enabled-runtime'))
        self.assertIsNone(result['error'])
        self.assertIn(['/usr/bin/systemctl', 'enable', 'ssh.socket'], calls)
        self.assertFalse(any('start' in args for args in calls))

    def test_masked_service_is_reported_and_never_unmasked(self):
        result, calls, _ = self.exercise(service=state('masked', 'inactive', 'masked'), listener=state())
        self.assertEqual(result['error'], 'ssh-service-masked-or-unavailable')
        self.assertFalse(any('systemctl' in args[0] for args in calls))

    def test_masked_unused_socket_does_not_break_enabled_service(self):
        result, _, _ = self.exercise(listener=state('masked', 'inactive', 'masked'))
        self.assertIsNone(result['error'])
        self.assertEqual(result['activation_unit'], 'ssh.service')
        self.assertEqual(result['units']['ssh.socket']['UnitFileState'], 'masked')

    def test_missing_package_does_not_create_runtime_directory_or_start_service(self):
        result, calls, directory = self.exercise(package=False)
        self.assertEqual(result['error'], 'openssh-server-not-configured')
        directory.assert_not_called()
        self.assertEqual(len(calls), 1)

    def test_invalid_config_does_not_change_units_or_expose_diagnostics(self):
        result, calls, _ = self.exercise(config=False)
        self.assertEqual(result['error'], 'sshd-configuration-invalid')
        self.assertFalse(any('systemctl' in args[0] for args in calls))

    def test_incomplete_host_key_pair_prevents_ssh_activation(self):
        result, calls, directory = self.exercise(host_key_error=ssh.Refused('ssh-ed25519-host-key-pair-incomplete'))
        self.assertEqual(result['error'], 'ssh-ed25519-host-key-pair-incomplete')
        self.assertFalse(result['ssh_host_key_ready'])
        self.assertFalse(result['configuration_valid'])
        directory.assert_not_called()
        self.assertEqual(len(calls), 1)

    def test_active_service_without_ssh_banner_is_not_ready(self):
        result, _, _ = self.exercise(banner=False)
        self.assertEqual(result['error'], 'loopback-ssh-banner-unavailable')
        self.assertFalse(result['loopback_ssh_ready'])

    def test_banner_without_verified_host_signature_fails_readiness(self):
        result, calls, _ = self.exercise(host_proof=False)
        self.assertEqual(result['error'], 'loopback-ssh-host-key-unverified')
        self.assertTrue(result['loopback_ssh_ready'])
        self.assertFalse(result['ssh_host_key_ready'])
        self.assertFalse(any('systemctl' in args[0] for args in calls))

    def test_activation_failure_is_not_reported_as_success(self):
        for failure in ('enable', 'start'):
            with self.subTest(failure=failure):
                result, _, _ = self.exercise(service=state('disabled', 'inactive'), failure=failure)
                self.assertEqual(result['error'], 'ssh-' + failure + '-failed')

    def test_embedded_helpers_are_exact_source_and_alias_is_identical(self):
        subprocess.run(['python3', str(ROOT / 'scripts/embed-installer-support.py')], check=True)


class PinnedProbeTests(unittest.TestCase):
    def test_probe_is_pinned_private_credential_free_and_always_cleans_up(self):
        for outcome in (True, False, OSError('SECRET DIAGNOSTIC')):
            with self.subTest(outcome=type(outcome).__name__), tempfile.TemporaryDirectory() as temporary:
                observed = []
                def exchange(args):
                    self.assertEqual(args[:8], ['/usr/bin/ssh', '-F', '/dev/null', '-vv', '-q', '-N', '-T', '-o'])
                    self.assertEqual(args[-5:], ['-l', 'agpc-hostkey-probe', '-p', '22', '127.0.0.1'])
                    options = args[8:-5:2]
                    for value in ('StrictHostKeyChecking=yes', 'HostKeyAlgorithms=ssh-ed25519',
                                  'GlobalKnownHostsFile=/dev/null', 'IdentityFile=none', 'IdentityAgent=none',
                                  'IdentitiesOnly=yes', 'BatchMode=yes', 'PreferredAuthentications=none',
                                  'PubkeyAuthentication=no', 'PasswordAuthentication=no', 'KbdInteractiveAuthentication=no',
                                  'GSSAPIAuthentication=no', 'HostbasedAuthentication=no', 'ClearAllForwardings=yes',
                                  'ForwardAgent=no', 'ForwardX11=no', 'ControlPath=none', 'ProxyCommand=none',
                                  'LogVerbose=kex.c:kex_input_newkeys():*'):
                        self.assertIn(value, options)
                    filename = Path(next(value.split('=', 1)[1] for value in options if value.startswith('UserKnownHostsFile=')))
                    observed.append(filename)
                    self.assertEqual(filename.parent.stat().st_mode & 0o777, 0o700)
                    self.assertEqual(filename.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(filename.read_text(), '127.0.0.1 ssh-ed25519 PINNED_PUBLIC\n')
                    if isinstance(outcome, Exception):
                        raise outcome
                    return outcome
                with patch.object(ssh, 'PROBE_DIRECTORY', temporary), patch.object(ssh, 'verified_key_exchange', side_effect=exchange):
                    if isinstance(outcome, Exception):
                        with self.assertRaises(OSError):
                            ssh.pinned_host_key_ready('PINNED_PUBLIC')
                    else:
                        self.assertIs(ssh.pinned_host_key_ready('PINNED_PUBLIC'), outcome)
                self.assertEqual(len(observed), 1)
                self.assertFalse(observed[0].parent.exists())
                self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_only_complete_local_verified_exchange_marker_is_accepted(self):
        for diagnostic, expected in ((b'debug1: kex.c:kex_input_newkeys():536 (bin=ssh, pid=PID): SSH2_MSG_NEWKEYS received\r\n', True),
                                     (b'debug1: kex.c:kex_input_newkeys():536 (pid=PID): SSH2_MSG_NEWKEYS received\r\n', True),
                                     (b'debug1: kex.c:kex_input_newkeys():536 (bin=ssh, pid=0): SSH2_MSG_NEWKEYS received\r\n', False),
                                     (b'debug1: SSH2_MSG_NEWKEYS received\r\n', False),
                                     (b'debug1: Server host key: ssh-ed25519 SHA256:test\r\n', False),
                                     (b'debug1: Host is known and matches the ED25519 host key.\n', False),
                                     (b'debug1: SSH2_MSG_NEWKEYS received', False),
                                     (b'debug1: Remote: debug1: SSH2_MSG_NEWKEYS received\n', False),
                                     (b'debug1: Remote: evil\\ndebug1: SSH2_MSG_NEWKEYS received\n', False),
                                     (b'Permission denied (publickey).\n', False)):
            with self.subTest(diagnostic=diagnostic):
                args = [sys.executable, '-c', 'import os; os.write(2, ' + repr(diagnostic) + '.replace(b"PID",str(os.getpid()).encode()))']
                self.assertIs(ssh.verified_key_exchange(args), expected)

    def test_flood_and_stalled_probe_are_bounded_and_reaped(self):
        real_popen = subprocess.Popen
        for code in ('import os; os.write(2,b"x"*70000); import time; time.sleep(30)',
                     'import time; time.sleep(30)'):
            with self.subTest(code=code):
                children = []
                def start(*args, **kwargs):
                    child = real_popen(*args, **kwargs)
                    children.append(child)
                    self.assertEqual(kwargs['env']['LC_ALL'], 'C')
                    self.assertNotIn('SSH_AUTH_SOCK', kwargs['env'])
                    self.assertTrue(kwargs['start_new_session'])
                    return child
                started = ssh.time.monotonic()
                with patch.object(ssh.subprocess, 'Popen', side_effect=start):
                    self.assertFalse(ssh.verified_key_exchange([sys.executable, '-c', code]))
                self.assertLess(ssh.time.monotonic() - started, 7)
                self.assertEqual(len(children), 1)
                self.assertIsNotNone(children[0].poll())
                self.assertTrue(children[0].stderr.closed)


class HostKeyTests(unittest.TestCase):
    PUBLIC = b'ssh-ed25519 ' + base64.b64encode(ssh.ED25519_PUBLIC_PREFIX + bytes(range(32))) + b' fixture\n'

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.etc = Path(self.temporary.name) / 'etc'
        self.directory = self.etc / 'ssh'
        self.directory.mkdir(parents=True)
        self.etc.chmod(0o755)
        self.directory.chmod(0o755)
        self.private = self.directory / 'ssh_host_ed25519_key'
        self.public = self.directory / 'ssh_host_ed25519_key.pub'
        self.owners = {}
        self.opened = []
        # Real temporary files exercise links, file modes, bounded reads and
        # inode checks. Only root ownership is represented by a fixture.
        real_lstat, real_fstat, real_open = os.lstat, os.fstat, os.open
        def metadata(value, owner=0):
            values = {name: getattr(value, name) for name in dir(value) if name.startswith('st_')}
            values['st_uid'] = owner
            return SimpleNamespace(**values)
        def lstat(path, *args, **kwargs):
            return metadata(real_lstat(path, *args, **kwargs), self.owners.get(str(path), 0))
        def open_public(path, *args, **kwargs):
            if str(path) == str(self.private):
                raise AssertionError('Installer must never open the private key')
            self.opened.append(str(path))
            return real_open(path, *args, **kwargs)
        for patcher in (patch.object(ssh, 'SSH_DIRECTORY', str(self.directory)),
                        patch.object(ssh.os, 'lstat', side_effect=lstat),
                        patch.object(ssh.os, 'fstat', side_effect=lambda fd: metadata(real_fstat(fd))),
                        patch.object(ssh.os, 'open', side_effect=open_public)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_pair(self, public=None):
        self.private.write_bytes(b'SYNTHETIC PRIVATE FIXTURE - NEVER OPENED BY INSTALLER\n')
        self.private.chmod(0o600)
        self.public.write_bytes(self.PUBLIC if public is None else public)
        self.public.chmod(0o644)

    def snapshot(self):
        return {path.name: (path.read_bytes(), path.stat()) for path in self.directory.iterdir() if path.is_file()}

    def test_existing_pair_retains_bytes_metadata_and_never_opens_private_key(self):
        self.make_pair()
        before = self.snapshot()
        with patch.object(ssh, 'command') as command:
            ssh.ensure_ed25519_host_key()
        command.assert_not_called()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.opened, [str(self.public)])

    def test_missing_pair_is_generated_and_public_key_verified(self):
        def generate(args):
            self.assertEqual(args, ['/usr/bin/ssh-keygen', '-A'])
            self.make_pair()
            return subprocess.CompletedProcess(args, 0, '', '')
        with patch.object(ssh, 'command', side_effect=generate) as command:
            ssh.ensure_ed25519_host_key()
        command.assert_called_once()
        self.assertEqual(self.opened, [str(self.public)])

    def test_generation_failure_cannot_succeed_or_expose_command_output(self):
        with patch.object(ssh, 'command', return_value=subprocess.CompletedProcess([], 1, 'SECRET', 'SECRET')):
            with self.assertRaisesRegex(ssh.Refused, '^ssh-host-key-generation-failed$'):
                ssh.ensure_ed25519_host_key()
        self.assertEqual(self.opened, [])

    def test_successful_generator_must_actually_create_both_valid_files(self):
        with patch.object(ssh, 'command', return_value=subprocess.CompletedProcess([], 0, '', '')):
            with self.assertRaisesRegex(ssh.Refused, '^ssh-ed25519-host-key-pair-incomplete$'):
                ssh.ensure_ed25519_host_key()
        def invalid_generate(args):
            self.make_pair(b'not-a-public-key\n')
            return subprocess.CompletedProcess(args, 0, '', '')
        with patch.object(ssh, 'command', side_effect=invalid_generate):
            with self.assertRaisesRegex(ssh.Refused, '^ssh-ed25519-host-public-key-invalid$'):
                ssh.ensure_ed25519_host_key()

    def test_partial_pairs_are_retained_and_never_regenerated(self):
        for missing in (self.private, self.public):
            with self.subTest(missing=missing.name):
                self.make_pair()
                missing.unlink()
                before = self.snapshot()
                with patch.object(ssh, 'command') as command:
                    with self.assertRaisesRegex(ssh.Refused, '^ssh-ed25519-host-key-pair-incomplete$'):
                        ssh.ensure_ed25519_host_key()
                command.assert_not_called()
                self.assertEqual(before, self.snapshot())

    def test_invalid_public_keys_are_retained_and_never_regenerated(self):
        invalid = [b'', b'ssh-rsa AAAA\n', b'ssh-ed25519 invalid!\n',
                   b'ssh-ed25519 ' + base64.b64encode(ssh.ED25519_PUBLIC_PREFIX + bytes(31)),
                   b'ssh-ed25519 ' + base64.b64encode(b'not-an-ssh-key'),
                   self.PUBLIC + self.PUBLIC, self.PUBLIC + b'x' * 4096, b'\xff']
        for public in invalid:
            with self.subTest(public=public[:40]):
                self.make_pair(public)
                before = self.snapshot()
                with patch.object(ssh, 'command') as command:
                    with self.assertRaisesRegex(ssh.Refused, '^ssh-ed25519-host-public-key-invalid$'):
                        ssh.ensure_ed25519_host_key()
                command.assert_not_called()
                self.assertEqual(before, self.snapshot())

    def test_unsafe_existing_permissions_or_ownership_are_not_repaired(self):
        for path, mode, owner in ((self.private, 0o644, 0), (self.public, 0o666, 0),
                                  (self.private, 0o600, 1000), (self.public, 0o644, 1000),
                                  (self.directory, 0o777, 0), (self.etc, 0o755, 1000)):
            with self.subTest(path=path.name, mode=mode, owner=owner):
                self.make_pair()
                path.chmod(mode)
                self.owners[str(path)] = owner
                with patch.object(ssh, 'command') as command:
                    with self.assertRaisesRegex(ssh.Refused, '^ssh-host-key-(file|directory)-untrusted$'):
                        ssh.ensure_ed25519_host_key()
                command.assert_not_called()
                self.assertEqual(path.stat().st_mode & 0o777, mode)
                self.owners.clear()
                self.directory.chmod(0o755)
                self.etc.chmod(0o755)

    def test_symlink_and_hardlink_keys_are_refused_without_reading_targets(self):
        for path in (self.private, self.public):
            for link_type in ('symbolic', 'hard'):
                with self.subTest(path=path.name, link_type=link_type):
                    self.make_pair()
                    target = self.directory / 'outside-key'
                    path.rename(target)
                    if link_type == 'symbolic':
                        path.symlink_to(target)
                    else:
                        os.link(target, path)
                    with patch.object(ssh, 'command') as command:
                        with self.assertRaisesRegex(ssh.Refused, '^ssh-host-key-file-untrusted$'):
                            ssh.ensure_ed25519_host_key()
                    command.assert_not_called()
                    self.assertEqual(self.opened, [])
                    path.unlink()
                    target.unlink()


if __name__ == '__main__':
    unittest.main()
