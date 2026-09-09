"""Real DPKG ownership states in a private root; network and APT remain mocked."""
from pathlib import Path
import shutil
import subprocess
import unittest

import test_installer as fixtures

TARGET = '/etc/mote/mote-chatd/mote-chatd-mchat.env'


class LegacyDpkgPreflightTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.InstallerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root / 'private-dpkg-root'
        self.root.mkdir()
        self.target = self.root / TARGET.lstrip('/')
        self.query = shutil.which('dpkg-query')
        self.stat = shutil.which('stat')
        self.fixture.write_fake('dpkg-query', f'''
import subprocess,sys
sys.exit(subprocess.call([{self.query!r}, {'--admindir='+str(self.root/'var/lib/dpkg')!r}, *sys.argv[1:]]))
''')
        self.fixture.write_fake('stat', f'''
import subprocess,sys
# Map the unprivileged private-root fixture UID to virtual root.
if sys.argv[2] == '%u:%a':print('0:640');sys.exit(0)
assert sys.argv[-1] == {TARGET!r}
sys.exit(subprocess.call([{self.stat!r}, *sys.argv[1:-1], {str(self.target)!r}]))
''')

    def run_dpkg(self, *args):
        result = subprocess.run(['dpkg', '--root='+str(self.root), '--force-not-root',
                                 '--log='+str(self.fixture.root/'dpkg.log'), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def package(self, version, protected=False):
        tree = self.fixture.root / ('package-'+version)
        control = tree/'DEBIAN'
        control.mkdir(parents=True)
        (control/'control').write_text(
            f'Package: mote-chatd\nVersion: {version}\nArchitecture: all\n'
            'Maintainer: Fixture <fixture@example.invalid>\nDescription: Offline ownership fixture\n')
        paths = ['/etc/mote/mote-chatd/mote-chatd-deb.env'] + ([TARGET] if protected else [])
        (control/'conffiles').write_text('\n'.join(paths)+'\n')
        for name in paths:
            p=tree/name.lstrip('/');p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('# synthetic fixture only\n');p.chmod(0o640)
        deb=self.fixture.root/(version+'.deb')
        # Fixture archives use this test user's identity, allowing standard
        # dpkg --force-not-root to operate only inside its private root.
        subprocess.run(['dpkg-deb','--build',str(tree),str(deb)], check=True,
                       capture_output=True, text=True)
        return str(deb)

    def rejected_before_download(self):
        before=(self.root/'var/lib/dpkg/status').read_bytes()
        result=self.fixture.run_installer('--yes')
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.fixture.calls(),[])
        self.assertFalse(Path(str(self.fixture.log)+'.download').exists())
        self.assertEqual((self.root/'var/lib/dpkg/status').read_bytes(),before)

    def test_unreviewed_installed_fixture_without_identity_is_rejected(self):
        self.run_dpkg('--install',self.package('2.0.0-4'))
        self.rejected_before_download()

    def test_unreviewed_residual_fixture_without_identity_is_rejected(self):
        self.run_dpkg('--install',self.package('2.0.0-4'))
        self.run_dpkg('--remove','mote-chatd')
        self.rejected_before_download()

    def test_actual_unpacked_record_requires_repair(self):
        self.run_dpkg('--unpack',self.package('2.0.0-4',protected=True))
        self.rejected_before_download()

    def test_actual_obsolete_protected_record_selects_retention_without_touching_identity(self):
        self.run_dpkg('--install',self.package('1.1.0-1',protected=True))
        self.run_dpkg('--install',self.package('2.0.0-4'))
        records=subprocess.check_output([self.query,'--admindir='+str(self.root/'var/lib/dpkg'),
                                         '-W','-f=${Conffiles}','mote-chatd'],text=True)
        self.assertIn('obsolete',records)
        before=(self.target.read_bytes(),self.target.stat())
        result=self.fixture.run_installer('--yes')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('mote-chatd=2.0.0-6',self.fixture.calls()[-1])
        after=(self.target.read_bytes(),self.target.stat())
        self.assertEqual(before[0],after[0])
        for field in ('st_ino','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_gid'):
            self.assertEqual(getattr(before[1],field),getattr(after[1],field),field)

    def test_actual_missing_or_symlinked_protected_target_requires_repair(self):
        self.run_dpkg('--install',self.package('2.0.0-4',protected=True))
        self.target.unlink()
        self.rejected_before_download()
        self.target.symlink_to('mote-chatd-deb.env')
        self.rejected_before_download()
