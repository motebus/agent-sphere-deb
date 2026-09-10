"""Real DPKG and Debian helper lifecycle in a private root.

Dependencies are explicit metadata-only fixtures. DPKG_ROOT prevents host
systemd calls; this checks enablement, masks, repeat/purge and ownership, not
boot or live service readiness. APT dependency resolution is checked separately.
"""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('target_package', ROOT/'scripts/package.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)

class TargetLifecycleTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'build').mkdir(exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=ROOT/'build');self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.root=self.base/'system';self.root.mkdir()
        self.unit=Path(package.TARGET).name
        self.name=package.control()['Package']
        self.deb=package.build(self.base/'dist')
        dependencies=[]
        for name,version in re.findall(r'([a-z][a-z0-9-]*) \(>= ([^()]+)\)',package.control()['Depends']):
            stage=self.base/name;control=stage/'DEBIAN';control.mkdir(parents=True)
            (control/'control').write_text(f'Package: {name}\nVersion: {version}\nArchitecture: all\nMaintainer: Fixture <fixture@example.invalid>\nDescription: Isolated dependency metadata fixture\n')
            document=stage/f'usr/share/doc/{name}/fixture';document.parent.mkdir(parents=True);document.write_text('No runtime dependency acceptance is claimed.\n')
            path=self.base/(name+'.deb');subprocess.run(['dpkg-deb','--build',str(stage),str(path)],check=True,capture_output=True)
            dependencies.append(str(path))
        self.dpkg('--install',*dependencies)
        self.state=self.root/'etc/systemd/system';self.state.mkdir(parents=True,exist_ok=True)
        self.enabled=self.state/'multi-user.target.wants'/self.unit
        self.owner=self.root/'etc/owner-preserved';self.owner.write_text('fixture identity bytes\n');self.owner.chmod(0o640)
        self.before=self.snapshot(self.owner)

    def snapshot(self,path):
        stat=path.stat()
        return (path.read_bytes(),stat.st_ino,stat.st_ctime_ns,stat.st_mtime_ns,stat.st_uid,stat.st_gid,stat.st_mode)

    def dpkg(self,*args):
        result=subprocess.run(['dpkg','--root='+str(self.root),'--force-not-root','--force-script-chrootless','--log='+str(self.base/'dpkg.log'),*map(str,args)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_install_repeat_disable_and_purge_native_target(self):
        self.dpkg('--install',self.deb)
        self.assertTrue(self.enabled.is_symlink())
        self.dpkg('--install',self.deb)
        self.assertTrue(self.enabled.is_symlink())
        self.enabled.unlink() # Explicit owner disable, retaining native helper receipt.
        self.dpkg('--install',self.deb)
        self.assertFalse(self.enabled.is_symlink())
        self.dpkg('--remove',self.name)
        self.dpkg('--purge',self.name)
        self.assertFalse((self.root/package.TARGET).exists())
        self.assertEqual(self.snapshot(self.owner),self.before)

    def test_explicit_administrator_mask_survives_reinstall_and_purge(self):
        mask=self.state/self.unit;mask.symlink_to('/dev/null')
        self.dpkg('--install',self.deb)
        self.assertEqual(os.readlink(mask),'/dev/null')
        self.dpkg('--install',self.deb)
        self.assertEqual(os.readlink(mask),'/dev/null')
        self.dpkg('--purge',self.name)
        self.assertEqual(os.readlink(mask),'/dev/null')
        self.assertEqual(self.snapshot(self.owner),self.before)

    def test_target_has_no_reverse_ui_or_cloud_dependency(self):
        text=(ROOT/package.SOURCES[package.TARGET]).read_text()
        for denied in ('sphere-manager','medge.service','iagent.service','ss-webos','network-online.target','UltraOne','PartOf=','Requires='):
            self.assertNotIn(denied,text)
        self.assertIn('WantedBy=multi-user.target',text)
        self.assertNotIn('Exec',text)
        self.assertNotIn('stop ',(ROOT/'packaging/postinst').read_text())
