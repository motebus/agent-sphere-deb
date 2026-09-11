import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import fcntl
import pty
import select
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "agpc.sh"
BASH = shutil.which("bash")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Separate shell orchestration from the real bootstrap's root/OS checks.
        # The production fragment has its own namespace tests; no runtime test
        # switch is introduced into the public installer.
        self.installer = self.root / "agpc.sh"
        text = INSTALLER.read_text()
        text = text.replace("agentsphere_platform_check || fail 'Platform preflight failed. No package or source change was started.'", ": # platform checked by isolated bootstrap tests")
        text = text.replace("agentsphere_apt_bootstrap || fail 'Signed APT bootstrap failed. Package installation was not started.'", ": # bootstrap checked by isolated bootstrap tests")
        # Exercise original migration guards and confirmation here. The durable
        # worker and SSH checks have separate process/namespace tests.
        start = text.index('# BEGIN DETACHED INSTALL SUPPORT\n')
        end = text.index('# END DETACHED INSTALL SUPPORT\n', start) + len('# END DETACHED INSTALL SUPPORT\n')
        text = text[:start] + '''agentsphere_job_platform_check() { :; }
agentsphere_run_detached() {
    apt-get -o "DPkg::Pre-Install-Pkgs::=$guard" \\
      -o "DPkg::Tools::Options::$guard::Version=3" \\
      -o "DPkg::Tools::Options::$guard::InfoFD=0" \\
      -o 'Dpkg::Options::=--force-confold' --yes install "${packages[@]}" </dev/null
}
''' + text[end:]
        text = text.replace('job_stage=$(mktemp -d /var/lib/agpc-install.XXXXXXXX)',
                            'job_stage=$(mktemp -d "$TMPDIR/agpc-install.XXXXXXXX")')
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # Trap an accidental fixed-path or PATH-based UI launch inside the fixture.
        for name in ("agpc-manager", "sphere-manager"):
            text = text.replace("/usr/bin/" + name, str(self.bin / name))
        self.installer.write_text(text)
        self.log = self.root / "apt-calls.jsonl"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        APT_TEST_LOG=str(self.log), TMPDIR=str(self.root))
        for key in ('APT_TEST_FAIL', 'APT_TEST_UID', 'APT_TEST_PLAN', 'APT_TEST_ACTIONS', 'APT_TEST_OBSIDIAN', 'APT_TEST_CHATD', 'APT_TEST_CHATD_FILE', 'APT_TEST_FINAL_CHATD', 'APT_TEST_HOOK', 'APT_TEST_PROMPT', 'APT_TEST_CHATD_ACCESS', 'APT_TEST_MANAGER', 'APT_TEST_FINAL_MANAGER', 'APT_TEST_MANAGER_BAD_DIGEST'):
            self.env.pop(key, None)
        for name in ("agpc-manager", "sphere-manager"):
            self.write_fake(name, """
import os, pathlib, sys
pathlib.Path(os.environ['APT_TEST_LOG'] + '.manager').touch()
sys.exit(37)
""")
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
if len(sys.argv) == 2:
    hashes={'prerm':'a583a5e196cab7845800d8bade6cca1b1e86db9d077e2749d24ce7ad3b224085',
            'postrm':'cad515185035337dd03da926ff380a1cf5a47fd074b6ff7f8525f7d7d1384196'}
    if '/cx-node.' in sys.argv[1]:hashes={'prerm':'5a07af360b9e229fad483ba3ada220d81636f0a145ad38550542f9324432dfc3','postrm':'fc2ae1c462331eeb4c7a93eee8b27012120ca620baf6d91dd4b2e714b39c2f99'}
    print(('0'*64 if os.environ.get('APT_TEST_HOOK') else hashes[sys.argv[1].rsplit('.',1)[-1]])+'  '+sys.argv[1])
else:
    check=sys.stdin.read()
    bad_manager=os.environ.get('APT_TEST_MANAGER_BAD_DIGEST') and '/manager.deb' in check
    sys.exit(1 if os.environ.get('APT_TEST_OBSIDIAN') == 'bad-digest' or bad_manager else 0)
""")
        self.write_fake("dpkg-deb", """
import os, sys
values={'Package':'obsidian','Version':'1.13.7','Architecture':'amd64'}
print('unexpected' if os.environ.get('APT_TEST_OBSIDIAN') == 'bad-control' else values[sys.argv[-1]])
""")
        self.write_fake("dpkg-query", """
import os, sys
if sys.argv[-1] in ('mote-bridge-mcp','sphere-manager'):sys.exit(1)
if sys.argv[-1] in ('cx-node','cx-agent','codex-mesh'):sys.exit(1)
value=os.environ.get('APT_TEST_CHATD', '')
if 'Architecture' in sys.argv[2]:
    print('amd64\\n'+('deinstall ok config-files' if value.startswith('config-files') else 'install ok installed'))
    sys.exit(0)
if value == 'query-error':sys.exit(2)
if not value:sys.exit(1)
if value == 'installed':value='installed\\n2.0.0-4\\n /etc/mote/mote-chatd/mote-chatd-mchat.env ' + 'a'*32 + ' obsolete'
print(value)
""")
        self.write_fake("stat", """
import os,sys
print(os.environ.get('APT_TEST_CHATD_ACCESS','0:640') if sys.argv[2] == '%u:%a' else '0:0:755:regular file' if sys.argv[-1].startswith('/var/lib/dpkg/info/') else os.environ.get('APT_TEST_CHATD_FILE', 'regular file'))
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
    final_env=dict(os.environ, APT_HOOK_INFO_FD='0')
    if 'APT_TEST_FINAL_CHATD' in os.environ:final_env['APT_TEST_CHATD']=os.environ['APT_TEST_FINAL_CHATD']
    if 'APT_TEST_FINAL_MCP' in os.environ:final_env['APT_TEST_MCP']=os.environ['APT_TEST_FINAL_MCP']
    if 'APT_TEST_FINAL_CX' in os.environ:final_env['APT_TEST_CX']=os.environ['APT_TEST_FINAL_CX']
    if 'APT_TEST_FINAL_MANAGER' in os.environ:final_env['APT_TEST_MANAGER']=os.environ['APT_TEST_FINAL_MANAGER']
    result = subprocess.run([hook], input=protocol, text=True, env=final_env)
    if result.returncode == 0 and os.environ.get('APT_TEST_PROMPT'):
        assert '--yes' in args and not os.isatty(0), 'the approved worker must not depend on an SSH terminal'
    sys.exit(result.returncode)
""")

    def write_fake(self, name, body):
        target = self.bin / name
        target.write_text(f"#!{sys.executable}\n{body}")
        target.chmod(0o755)

    def run_installer(self, *args):
        return subprocess.run([BASH, str(self.installer), *args], env=self.env,
                              capture_output=True, text=True, check=False)

    def run_piped_installer(self, answer):
        master, slave = pty.openpty()
        def terminal():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        env=dict(self.env, APT_TEST_PROMPT='1')
        child=subprocess.Popen([BASH], stdin=subprocess.PIPE, stdout=slave, stderr=slave,
                               env=env, preexec_fn=terminal, pass_fds=(slave,))
        os.close(slave)
        child.stdin.write(self.installer.read_bytes());child.stdin.close()
        output=b'';sent=False;deadline=time.monotonic()+20
        try:
            while time.monotonic()<deadline:
                if select.select([master],[],[],0.1)[0]:
                    try:chunk=os.read(master,65536)
                    except OSError:break
                    if not chunk:break
                    output+=chunk
                    if b'Proceed with the displayed package plan and SSH readiness check?' in output and not sent:
                        os.write(master,(answer+'\n').encode());sent=True
                if child.poll() is not None:break
            self.assertTrue(sent,output.decode())
            child.wait(timeout=3)
            return subprocess.CompletedProcess([BASH],child.returncode,output.decode(),'')
        finally:
            if child.poll() is None:child.kill();child.wait()
            os.close(master)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def fake_mcp_classifier(self, state='installed:reviewed'):
        # This isolates the shell transaction protocol; the real Python
        # classifier is tested independently in test_mcp_preflight.py.
        self.env['APT_TEST_MCP']=state
        self.write_fake('python3', """
import os,sys
body=sys.stdin.read()
assert 'def classify():' in body
state=(os.environ.get('APT_TEST_MANAGER','absent') if 'MANAGER_PACKAGE =' in body else
       os.environ.get('APT_TEST_CX','absent') if 'MESH_FILES =' in body else os.environ.get('APT_TEST_MCP','absent'))
if state=='unreviewed':sys.exit(1)
print(state)
""")

    def manager_migration(self):
        self.fake_mcp_classifier('absent')
        self.env['APT_TEST_MANAGER']='installed:sha256:fixture'
        artifact=self.root/'manager.deb';artifact.touch()
        self.env['APT_TEST_PLAN']='Remv sphere-manager [3.1.0-1]\nInst agpc-manager (3.1.0-2 stable)'
        self.env['APT_TEST_ACTIONS']=(f'agpc-manager - - none < 3.1.0-2 amd64 none {artifact}\n'
            'sphere-manager 3.1.0-1 amd64 none > - - none **REMOVE**\n')
        return artifact

    def test_container_runtime_addition_is_refused_before_final_transaction(self):
        for name in ('docker.io', 'docker-ce', 'podman', 'containerd.io', 'runc', 'moby-engine'):
            with self.subTest(name=name):
                if self.log.exists(): self.log.unlink()
                self.env['APT_TEST_PLAN']=f'Inst {name} (1.0 stable)'
                result=self.run_installer('--yes')
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Refusing container runtime package',result.stderr)
                self.assertEqual(len(self.calls()),2)

    def test_container_runtime_late_install_or_configure_is_refused_under_lock(self):
        for action in ('docker.io - - none < 1.0 amd64 none /cache/docker.deb',
                       'containerd 1.0 amd64 none = 1.0 amd64 none **CONFIGURE**'):
            with self.subTest(action=action):
                self.env['APT_TEST_ACTIONS']=action+'\n'
                result=self.run_installer('--yes')
                self.assertNotEqual(result.returncode,0)
                self.assertIn('outside native AGPC installation',result.stderr)

    def test_unrelated_fixture_data_and_container_commands_are_not_touched(self):
        owner_data=self.root/'existing-container-data';owner_data.write_bytes(b'owner data')
        before=owner_data.stat()
        for name in ('docker','podman'):
            self.write_fake(name, "import os, pathlib, sys; pathlib.Path(os.environ['APT_TEST_LOG']+'.container').touch(); sys.exit(89)")
        result=self.run_installer('--yes')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(Path(str(self.log)+'.container').exists())
        self.assertEqual(owner_data.read_bytes(),b'owner data')
        after=owner_data.stat()
        self.assertEqual((before.st_ino,before.st_mtime_ns,before.st_ctime_ns),
                         (after.st_ino,after.st_mtime_ns,after.st_ctime_ns))
        self.assertFalse(any('remove' in call or 'purge' in call for call in self.calls()))

    def test_clean_manager_rename_requires_exact_artifact_in_same_transaction(self):
        self.manager_migration()
        result=self.run_installer('--yes');self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('agpc-manager=3.1.0-2',self.calls()[-1])
        self.assertFalse(Path(str(self.log)+'.manager').exists())
        self.env['APT_TEST_MANAGER_BAD_DIGEST']='1'
        result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.assertIn('Manager artifact changed',result.stderr)

    def test_manager_unknown_state_stops_before_download_and_lock_drift_stops_dpkg(self):
        self.manager_migration();self.env['APT_TEST_MANAGER']='unreviewed'
        result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.assertIn('Manager preflight failed',result.stderr)
        self.assertEqual(self.calls(),[])
        self.assertFalse(Path(str(self.log)+'.download').exists())
        self.env['APT_TEST_MANAGER']='installed:sha256:fixture'
        self.env['APT_TEST_FINAL_MANAGER']='installed:sha256:changed'
        result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.assertIn('legacy Manager state changed',result.stderr)

    def test_manager_removal_without_new_payload_and_retired_install_are_refused(self):
        artifact=self.manager_migration()
        actions=[
            'sphere-manager 3.1.0-1 amd64 none > - - none **REMOVE**\n',
            f'agpc-manager - - none < 3.1.0-3 amd64 none {artifact}\n',
            f'sphere-manager - - none < 3.1.0-1 amd64 none {artifact}\n',
            f'agpc-manager - - none < 3.1.0-2 amd64 none {artifact}\nsphere-manager 3.1.0-2 amd64 none > - - none **REMOVE**\n',
        ]
        for action in actions:
            with self.subTest(action=action):
                self.env['APT_TEST_ACTIONS']=action
                result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertIn('transaction refused',result.stderr)
        self.env['APT_TEST_MANAGER']='absent'
        self.env['APT_TEST_ACTIONS']=''
        result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.assertIn('unreviewed Manager package removal',result.stderr)

    def test_reviewed_mcp_replacement_is_required_in_same_transaction(self):
        self.fake_mcp_classifier()
        artifact=self.root/'mote-mcpd.deb';artifact.touch()
        self.env['APT_TEST_PLAN']='Remv mote-bridge-mcp [3.0.0-2]\nInst mote-mcpd (3.0.0-3 stable)'
        self.env['APT_TEST_ACTIONS']=(f'mote-mcpd - - none < 3.0.0-3 amd64 none {artifact}\n'
            'mote-bridge-mcp 3.0.0-2 amd64 none > - - none **REMOVE**\n')
        result=self.run_installer('--yes');self.assertEqual(result.returncode,0,result.stderr)
        self.env['APT_TEST_ACTIONS']='mote-bridge-mcp 3.0.0-2 amd64 none > - - none **REMOVE**\n'
        result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.assertIn('lacks its reviewed replacement',result.stderr)

    def test_custom_mcp_preflight_stops_before_download(self):
        self.fake_mcp_classifier('unreviewed')
        result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.assertIn('MCP preflight failed',result.stderr)
        self.assertEqual(self.calls(),[])
        self.assertFalse(Path(str(self.log)+'.download').exists())

    def test_mcp_state_drift_is_checked_under_apt_lock(self):
        self.fake_mcp_classifier();self.env['APT_TEST_FINAL_MCP']='installed:changed'
        result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.assertIn('MCP state changed after preflight',result.stderr)

    def test_mcp_old_version_retired_install_and_residual_removal_are_refused(self):
        self.fake_mcp_classifier()
        for action in ('mote-bridge-mcp 3.0.0-1 amd64 none > - - none **REMOVE**\n',
                       'mote-bridge-mcp - - none < 3.0.0-2 amd64 none /cache/old.deb\n'):
            self.env['APT_TEST_ACTIONS']=action
            result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.fake_mcp_classifier('config-files')
        self.env['APT_TEST_ACTIONS']='mote-bridge-mcp 3.0.0-2 amd64 none > - - none **REMOVE**\n'
        result=self.run_installer('--yes');self.assertNotEqual(result.returncode,0)
        self.env['APT_TEST_ACTIONS']=''
        result=self.run_installer('--yes');self.assertEqual(result.returncode,0,result.stderr)

    def test_default_requires_confirmation_before_noninteractive_worker(self):
        result = self.run_piped_installer('y')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.calls()[0], ['update'])
        self.assertEqual(self.calls()[1][:6], ['--simulate','install','agent-sphere=0.2.0-5','agent-ultra=0.1.0-1','agpc-manager=3.1.0-2','agent-apps=0.2.0-1'])
        self.assertTrue(self.calls()[1][-1].endswith('/obsidian_1.13.7_amd64.deb'))
        self.assertEqual(self.calls()[-1][-6:], ['install', *self.calls()[1][2:]])
        self.assertIn('--yes', self.calls()[-1])
        self.assertIn('health are separate checks', result.stdout)
        self.assertFalse(list(self.root.glob('agent-sphere-apps.*')))

    def test_successful_interactive_install_exits_without_opening_manager(self):
        result = self.run_piped_installer('y')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('packages installed.', result.stdout)
        self.assertIn('Use agpc-manager', result.stdout)
        self.assertFalse(Path(str(self.log) + '.manager').exists(), result.stdout)
        self.assertNotIn('AGPC Manager exited', result.stdout)

    def test_piped_installer_respects_interactive_refusal(self):
        result=self.run_piped_installer('n')
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertNotIn('--yes',self.calls()[-1])
        self.assertEqual(len(self.calls()),2)

    def test_headless_stdin_requires_explicit_yes(self):
        # A fresh session cannot inherit a developer terminal accidentally.
        result=subprocess.run([BASH,str(self.installer)],env=self.env,stdin=subprocess.DEVNULL,
                              capture_output=True,text=True,start_new_session=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('confirmation needs a terminal',result.stderr)
        self.assertEqual(len(self.calls()),2)

    def ordinary_record(self, state='installed'):
        return state+'\n2.0.0-4\n /etc/mote/mote-chatd/mote-chatd-deb.env '+'a'*32

    def test_ordinary_release_uses_runtime_replacement_without_retention(self):
        self.env['APT_TEST_CHATD']=self.ordinary_record()
        artifact=self.root/'transport.deb';artifact.touch()
        self.env['APT_TEST_PLAN']='Remv mote-chatd [2.0.0-4]\nInst mote-transportd (2.0.0-6 stable)'
        self.env['APT_TEST_ACTIONS']=('mote-chatd 2.0.0-4 amd64 none > - - none **REMOVE**\n'
            f'mote-transportd - - none < 2.0.0-6 amd64 none {artifact}\n')
        result=self.run_installer('--yes')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('mote-chatd=2.0.0-6',self.calls()[-1])
        self.assertIn('mote-chatd-',self.calls()[-1])

    def test_exact_public_cx_baseline_is_checked_before_removal(self):
        self.fake_mcp_classifier('absent')
        self.env['APT_TEST_CX']='cx-node=0.3.3-6,cx-agent=-,codex-mesh=-;sha256:fixture'
        artifact=self.root/'cx-mesh.deb';artifact.touch()
        self.env['APT_TEST_PLAN']='Remv cx-node [0.3.3-6]\nInst cx-mesh (1.1.0-1 stable)'
        self.env['APT_TEST_ACTIONS']=(f'cx-mesh - - none < 1.1.0-1 amd64 none {artifact}\n'
            'cx-node 0.3.3-6 amd64 none > - - none **REMOVE**\n')
        result=self.run_installer('--yes')
        self.assertEqual(result.returncode,0,result.stderr)
        self.env['APT_TEST_FINAL_CX']='changed'
        result=self.run_installer('--yes')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('CX state changed after preflight',result.stderr)

    def test_ordinary_residual_state_does_not_install_retention(self):
        self.env['APT_TEST_CHATD']=self.ordinary_record('config-files')
        result=self.run_installer('--yes')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('mote-chatd=2.0.0-6',self.calls()[-1])
        self.assertIn('mote-chatd-',self.calls()[-1])

    def test_unknown_ordinary_hook_stops_before_download(self):
        self.env['APT_TEST_CHATD']=self.ordinary_record();self.env['APT_TEST_HOOK']='changed'
        result=self.run_installer('--yes')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('differs from the reviewed',result.stderr)
        self.assertEqual(self.calls(),[])
        self.assertFalse(Path(str(self.log)+'.download').exists())

    def test_unsafe_existing_topology_access_is_rejected_early(self):
        self.env['APT_TEST_CHATD']=self.ordinary_record()
        for access in ('1000:640','0:666','0:660'):
            self.env['APT_TEST_CHATD_ACCESS']=access
            result=self.run_installer('--yes')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('root-owned and not writable',result.stderr)
            self.assertEqual(self.calls(),[])
            self.assertFalse(Path(str(self.log)+'.download').exists())

    def test_ordinary_migration_rejects_other_transport_version(self):
        self.env['APT_TEST_CHATD']=self.ordinary_record()
        self.env['APT_TEST_ACTIONS']='mote-transportd - - none < 2.0.0-7 amd64 none /cache/transport.deb\n'
        result=self.run_installer('--yes')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('requires exact transport 2.0.0-6',result.stderr)

    def test_lock_time_ownership_drift_stops_before_dpkg(self):
        for initial,final in [(self.ordinary_record(),'installed'),('installed',self.ordinary_record()),('',self.ordinary_record())]:
            self.env['APT_TEST_CHATD']=initial;self.env['APT_TEST_FINAL_CHATD']=final
            result=self.run_installer('--yes')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('ownership changed after preflight',result.stderr)

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
        self.assertEqual(self.run_installer('--yes').returncode, 42)
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
        self.assertIn('agent-sphere, agent-ultra, agpc-manager and agent-apps', result.stdout)
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
                ('cx-node','cx-mesh','0.3.3-4','1.1.0-1'),
                ('cx-node','cx-mesh','0.3.4-1~local20260909','1.1.0-1'),
                ('model-node','model-llm','0.1.0-2','0.1.0-3')]:
            with self.subTest(old=old):
                self.fake_mcp_classifier('absent')
                self.env['APT_TEST_CX']=f'cx-node={oldversion},cx-agent=-,codex-mesh=-;sha256:fixture' if old=='cx-node' else 'absent'
                artifact=self.root/(new+'.deb');artifact.touch()
                self.env['APT_TEST_PLAN'] = f'Remv {old} [{oldversion}]\nInst {new} ({newversion} stable)'
                self.env['APT_TEST_ACTIONS'] = (f'{old} {oldversion} amd64 none > - - none **REMOVE**\n'
                    f'{new} - - none < {newversion} amd64 none {artifact}\n')
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
