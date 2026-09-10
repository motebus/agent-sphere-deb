import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssh_readiness', ROOT / 'scripts/ssh-readiness.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)


def state(enabled='enabled', active='active', load='loaded'):
    return {'LoadState': load, 'ActiveState': active, 'SubState': 'running' if active == 'active' else 'dead', 'UnitFileState': enabled}


class SshReadinessTests(unittest.TestCase):
    def exercise(self, service=None, listener=None, package=True, config=True, banner=True, failure=None):
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
             patch.object(ssh, 'trusted_runtime_directory') as directory, \
             patch.object(ssh, 'banner_ready', return_value=banner), \
             patch.object(ssh.time, 'sleep'):
            result = ssh.ensure_ssh_ready()
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertFalse(any(value in args for args in calls for value in ('unmask', 'stop', 'restart', 'reload', 'ssh-keygen')))
        self.assertEqual(result['mote_reachability'], 'not-tested')
        self.assertFalse(result['full_runtime_ready'])
        return result, calls, directory

    def test_running_service_is_preserved_and_socket_is_not_enabled(self):
        result, calls, _ = self.exercise()
        self.assertIsNone(result['error'])
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

    def test_active_service_without_ssh_banner_is_not_ready(self):
        result, _, _ = self.exercise(banner=False)
        self.assertEqual(result['error'], 'loopback-ssh-banner-unavailable')
        self.assertFalse(result['loopback_ssh_ready'])

    def test_activation_failure_is_not_reported_as_success(self):
        for failure in ('enable', 'start'):
            with self.subTest(failure=failure):
                result, _, _ = self.exercise(service=state('disabled', 'inactive'), failure=failure)
                self.assertEqual(result['error'], 'ssh-' + failure + '-failed')

    def test_embedded_helpers_are_exact_source_and_alias_is_identical(self):
        subprocess.run(['python3', str(ROOT / 'scripts/embed-installer-support.py')], check=True)


if __name__ == '__main__':
    unittest.main()
