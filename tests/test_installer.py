import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "agent-sphere-apps.sh"
BASH = shutil.which("bash")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "apt-calls.jsonl"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        APT_TEST_LOG=str(self.log), TMPDIR=str(self.root))
        for key in ('APT_TEST_FAIL', 'APT_TEST_UID', 'APT_TEST_PLAN', 'APT_TEST_ACTIONS', 'APT_TEST_OBSIDIAN', 'APT_TEST_CHATD', 'APT_TEST_CHATD_FILE'):
            self.env.pop(key, None)
        self.write_fake("id", """
import os, sys
assert sys.argv[1:] == ['-u']
print(os.environ.get('APT_TEST_UID', '0'))
""")
        self.write_fake("curl", """
import os, pathlib, sys
args=sys.argv[1:]
pathlib.Path(os.environ['APT_TEST_LOG'] + '.download').touch()
pathlib.Path(args[args.index('--output')+1]).write_bytes(b'fixture-official-deb')
""")
        self.write_fake("sha256sum", """
import os, sys
sys.stdin.read()
sys.exit(1 if os.environ.get('APT_TEST_OBSIDIAN') == 'bad-digest' else 0)
""")
        self.write_fake("dpkg-deb", """
import os, sys
values={'Package':'obsidian','Version':'1.13.7','Architecture':'amd64'}
print('unexpected' if os.environ.get('APT_TEST_OBSIDIAN') == 'bad-control' else values[sys.argv[-1]])
""")
        self.write_fake("dpkg-query", """
import os, sys
value=os.environ.get('APT_TEST_CHATD', '')
if value == 'query-error':sys.exit(2)
if not value:sys.exit(1)
if value == 'installed':value='installed\\n2.0.0-4\\n /etc/mote/mote-chatd/mote-chatd-mchat.env ' + 'a'*32 + ' obsolete'
print(value)
""")
        self.write_fake("stat", """
import os
print(os.environ.get('APT_TEST_CHATD_FILE', 'regular file'))
""")
        self.write_fake("apt-get", """
import json, os, subprocess, sys
args = sys.argv[1:]
with open(os.environ['APT_TEST_LOG'], 'a') as out:
    out.write(json.dumps(args) + '\\n')
stage = 'update' if args == ['update'] else 'simulate' if '--simulate' in args else 'install'
if os.environ.get('APT_TEST_FAIL') == stage:
    sys.exit(42)
if stage == 'simulate':
    print(os.environ.get('APT_TEST_PLAN', 'Inst agent-sphere (0.1.0-2 stable)\\nInst agent-apps (0.1.0-1 stable)'))
if stage == 'install':
    hook = next(a.split('=', 1)[1] for a in args if a.startswith('DPkg::Pre-Install-Pkgs::='))
    assert 'DPkg::Tools::Options::' + hook + '::Version=3' in args
    assert 'DPkg::Tools::Options::' + hook + '::InfoFD=0' in args
    protocol = 'VERSION 3\\nAPT::Architecture=amd64\\n\\n' + os.environ.get('APT_TEST_ACTIONS', '')
    result = subprocess.run([hook], input=protocol, text=True,
                            env=dict(os.environ, APT_HOOK_INFO_FD='0'))
    sys.exit(result.returncode)
""")

    def write_fake(self, name, body):
        target = self.bin / name
        target.write_text(f"#!{sys.executable}\n{body}")
        target.chmod(0o755)

    def run_installer(self, *args):
        return subprocess.run([BASH, str(INSTALLER), *args], env=self.env,
                              capture_output=True, text=True, check=False)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_default_keeps_apt_confirmation_and_installs_both(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0], ['update'])
        self.assertEqual(self.calls()[1][:4], ['--simulate','install','agent-sphere=0.1.0-6','agent-apps=0.1.0-2'])
        self.assertTrue(self.calls()[1][-1].endswith('/obsidian_1.13.7_amd64.deb'))
        self.assertEqual(self.calls()[-1][-4:], ['install', *self.calls()[1][2:]])
        self.assertNotIn('--yes', self.calls()[-1])
        self.assertIn('health are separate checks', result.stdout)
        self.assertFalse(list(self.root.glob('agent-sphere-apps.*')))

    def test_yes_requires_explicit_flag(self):
        result = self.run_installer('--yes')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--yes', self.calls()[-1])
        self.assertNotIn('--yes', self.calls()[1])

    def test_failed_preflight_never_starts_package_installation(self):
        self.env['APT_TEST_FAIL'] = 'simulate'
        result = self.run_installer('--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 2)
        self.assertIn('Package installation was not started', result.stderr)

    def test_failed_update_stops_before_preflight(self):
        self.env['APT_TEST_FAIL'] = 'update'
        self.assertNotEqual(self.run_installer().returncode, 0)
        self.assertEqual(self.calls(), [['update']])

    def test_install_failure_is_returned_without_fallback(self):
        self.env['APT_TEST_FAIL'] = 'install'
        self.assertEqual(self.run_installer().returncode, 42)
        self.assertEqual(len(self.calls()), 3)

    def test_non_root_is_rejected_without_apt(self):
        self.env['APT_TEST_UID'] = '1000'
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('root', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_unknown_arguments_are_rejected_without_apt(self):
        for arg in ('--allow-remove', '--allow-unauthenticated', '-y', 'agent-sphere'):
            with self.subTest(arg=arg):
                self.assertEqual(self.run_installer(arg).returncode, 2)
                self.assertEqual(self.calls(), [])

    def test_help_does_not_require_root_or_call_apt(self):
        self.env['APT_TEST_UID'] = '1000'
        result = self.run_installer('--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn('agent-sphere and agent-apps', result.stdout)
        self.assertEqual(self.calls(), [])

    def test_missing_apt_is_rejected(self):
        (self.bin / 'apt-get').unlink()
        self.env['PATH'] = str(self.bin)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('apt-get is required', result.stderr)

    def test_unrelated_preflight_removal_or_purge_is_refused(self):
        for plan in ('Remv openssh-server [1.0]', 'Purg mote-chatd [2.0.0-4]', 'Remv mote-chatd [2.0.0-4]'):
            with self.subTest(plan=plan):
                self.env['APT_TEST_PLAN'] = plan
                before = len(self.calls())
                self.assertNotEqual(self.run_installer('--yes').returncode, 0)
                self.assertEqual(len(self.calls()) - before, 2)

    def test_each_reviewed_rename_passes_both_checks(self):
        for old,new,oldversion,newversion in [('mote-sync','mote-vault-sync','1.1.0-2','1.1.0-3'),
                ('mote-syncd','mote-vault-syncd','1.1.0-2','1.1.0-3'),
                ('cx-node','cx-agent','0.3.4-1~local20260909','0.3.4-2'),
                ('model-node','model-llm','0.1.0-2','0.1.0-3')]:
            with self.subTest(old=old):
                self.env['APT_TEST_PLAN'] = f'Remv {old} [{oldversion}]\nInst {new} ({newversion} stable)'
                self.env['APT_TEST_ACTIONS'] = (f'{old} {oldversion} amd64 none > - - none **REMOVE**\n'
                    f'{new} - - none < {newversion} amd64 none /cache/{new}.deb\n')
                result=self.run_installer('--yes')
                self.assertEqual(result.returncode, 0,result.stderr)

    def test_legacy_chatd_record_is_upgraded_without_removal(self):
        self.env['APT_TEST_CHATD']='installed'
        result=self.run_installer('--yes')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('mote-chatd=2.0.0-6',self.calls()[1])
        self.assertIn('mote-chatd=2.0.0-6',self.calls()[-1])

    def test_unsupported_legacy_records_stop_before_download_or_apt(self):
        locked=' /etc/mote/mote-chatd/mote-chatd-mchat.env ' + 'a'*32 + ' obsolete'
        for record in ('query-error', 'installed\\n2.0.0-4', 'config-files\\n2.0.0-4',
                       'half-configured\\n2.0.0-4\\n'+locked,
                       'unpacked\\n2.0.0-6\\n'+locked,
                       'installed\\n2.0.0-7\\n'+locked,
                       'installed\\n2.0.0-4\\n'+locked+'\\n'+locked,
                       'installed\\n2.0.0-4\\n'+locked+' unexpected'):
            with self.subTest(record=record):
                self.env['APT_TEST_CHATD']=record.replace('\\n', '\n')
                result=self.run_installer('--yes')
                self.assertNotEqual(result.returncode,0,result.stderr)
                self.assertEqual(self.calls(),[])
                self.assertFalse(Path(str(self.log)+'.download').exists())

    def test_missing_or_symlinked_protected_file_stops_before_download(self):
        self.env['APT_TEST_CHATD']='installed'
        for kind in ('', 'symbolic link', 'directory'):
            with self.subTest(kind=kind):
                self.env['APT_TEST_CHATD_FILE']=kind
                self.assertNotEqual(self.run_installer('--yes').returncode,0)
                self.assertEqual(self.calls(),[])
                self.assertFalse(Path(str(self.log)+'.download').exists())

    def test_invalid_official_artifact_stops_before_apt(self):
        for reason in ('bad-digest','bad-control'):
            with self.subTest(reason=reason):
                self.env['APT_TEST_OBSIDIAN']=reason
                result=self.run_installer('--yes')
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(self.calls(),[])

    def test_obsolete_replacement_and_retired_reinstallation_are_refused(self):
        for action in ['cx-agent - - none < 0.3.4-1 amd64 none /cache/cx-agent.deb\n',
                       'mcp-run - - none < 2.0.0-1 amd64 none /cache/mcp-run.deb\n',
                       'model-node - - none < 0.1.0-2 amd64 none /cache/model-node.deb\n']:
            with self.subTest(action=action):
                self.env['APT_TEST_ACTIONS']=action
                self.assertNotEqual(self.run_installer('--yes').returncode,0)


    def test_changed_final_transaction_is_refused(self):
        # A successful simulation must not permit a different final removal.
        self.env['APT_TEST_ACTIONS'] = 'openssh-server 1.0 amd64 none > - - none **REMOVE**\n'
        result = self.run_installer('--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('removal of openssh-server', result.stderr)
        self.assertNotIn('packages installed', result.stdout)

    def test_guard_refuses_missing_replacement_downgrade_and_malformed_actions(self):
        actions = [
            'mote-chatd 2.0.0-4 amd64 none > - - none **REMOVE**\n',
            'medge 3.0.0-1 amd64 none > 2.0.0-2 amd64 none /cache/medge.deb\n',
            'bad action\n',
            'agos - - none < 2.0.0-1 amd64 none **UNKNOWN**\n',
        ]
        for action in actions:
            with self.subTest(action=action):
                self.env['APT_TEST_ACTIONS'] = action
                result = self.run_installer('--yes')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('transaction refused', result.stderr)

if __name__ == '__main__':
    unittest.main()
