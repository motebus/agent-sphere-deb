"""Actual APT resolver checks; isolated synthetic metadata, no DPKG execution."""
import hashlib
import os
from pathlib import Path
import pwd
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def control_fields(text):
    return dict(line.split(': ',1) for line in text.splitlines() if line and not line.startswith(' '))


class DependencyUpgradeTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.repo=self.root/'repo';self.repo.mkdir()
        self.etc=self.root/'etc';self.etc.mkdir()
        for d in ('apt.conf.d','sources.list.d','preferences.d','trusted.gpg.d'):(self.etc/d).mkdir()
        (self.etc/'sources.list').write_text(f'deb [trusted=yes] file:{self.repo} ./\n')
        self.config=self.root/'apt.conf';self.config.write_text(f'Dir::Etc "{self.etc}";\n')
        self.status=self.root/'status'
        self.sphere=control_fields((ROOT/'packaging/control').read_text())
        self.assertEqual(self.sphere['Version'],'0.1.0-8')
        dependencies=re.findall(r'([a-z0-9-]+) \(>= ([^)]+)\)',self.sphere['Depends'])
        self.installed={name:version for name,version in dependencies}
        self.installed.update({'medge':'3.0.0-2','agent-sphere':'0.1.0-7','agent-apps':'0.1.0-2'})
        self.base=['apt-get','-o',f'Dir::Etc={self.etc}',
                   '-o',f'Dir::State={self.root}/state','-o',f'Dir::State::status={self.status}',
                   '-o',f'Dir::Cache={self.root}/cache','-o',f'Dir::Log={self.root}/log',
                   '-o','APT::Architecture=amd64','-o','Acquire::Languages=none',
                   '-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=',
                   '-o','APT::Sandbox::User='+pwd.getpwuid(os.getuid()).pw_name]
        for path in ('state/lists/partial','cache/archives/partial','log'):(self.root/path).mkdir(parents=True)
        self.write_status()

    def fields(self,name,version):
        result={'Package':name,'Version':version,'Architecture':'all',
                'Maintainer':'Fixture <fixture@example.invalid>','Description':'Offline APT metadata fixture'}
        if name=='agent-sphere':
            result['Depends']=self.sphere['Depends'] if version=='0.1.0-8' else self.sphere['Depends'].replace('medge (>= 3.0.0-3)','medge (>= 3.0.0-2)')
        return result

    def write_status(self):
        self.status.write_text('\n\n'.join('\n'.join(f'{k}: {v}' for k,v in
            dict(self.fields(n,v),Status='install ok installed').items()) for n,v in self.installed.items())+'\n')

    def command(self,*args,success=True):
        result=subprocess.run([*self.base,*args],capture_output=True,text=True,
                              env=dict(os.environ,LC_ALL='C',APT_CONFIG=str(self.config)))
        self.assertEqual(result.returncode==0,success,result.stdout+result.stderr)
        return result.stdout+result.stderr

    def publish_fixture(self,fixed=True):
        packages=list(self.installed.items())+[('agent-sphere','0.1.0-8')]+([('medge','3.0.0-3')] if fixed else [])
        index=[]
        for name,version in packages:
            fields=self.fields(name,version);tree=self.root/(name+'-'+version);(tree/'DEBIAN').mkdir(parents=True)
            (tree/'DEBIAN/control').write_text('\n'.join(f'{k}: {v}' for k,v in fields.items())+'\n')
            deb=self.repo/f'{name}_{version}_all.deb'
            subprocess.run(['dpkg-deb','--build',str(tree),str(deb)],check=True,capture_output=True)
            fields.update(Filename='./'+deb.name,Size=str(deb.stat().st_size),SHA256=hashlib.sha256(deb.read_bytes()).hexdigest())
            index.append('\n'.join(f'{k}: {v}' for k,v in fields.items()))
        (self.repo/'Packages').write_text('\n\n'.join(index)+'\n')
        self.command('update')

    def test_old_floor_keeps_satisfied_dependency_but_new_floor_upgrades_it(self):
        self.publish_fixture()
        before=self.status.read_bytes()
        old=self.command('--simulate','--no-remove','install','agent-sphere=0.1.0-7','agent-apps=0.1.0-2')
        self.assertFalse(any(line.startswith('Inst medge ') for line in old.splitlines()),old)
        self.assertIn('0 upgraded, 0 newly installed',old)
        new=self.command('--simulate','--no-remove','install','agent-sphere=0.1.0-8','agent-apps=0.1.0-2')
        changes=[line for line in new.splitlines() if line.startswith('Inst ')]
        self.assertEqual({line.split()[1] for line in changes},{'agent-sphere','medge'},new)
        self.assertTrue(any(line.startswith('Inst medge [3.0.0-2] (3.0.0-3 ') for line in changes),new)
        self.assertEqual(self.status.read_bytes(),before,'a simulation modified fixture DPKG metadata')

    def test_rerun_after_upgrade_is_stable(self):
        self.publish_fixture()
        self.installed.update({'agent-sphere':'0.1.0-8','medge':'3.0.0-3'});self.write_status()
        output=self.command('--simulate','--no-remove','install','agent-sphere=0.1.0-8','agent-apps=0.1.0-2')
        self.assertIn('0 upgraded, 0 newly installed',output)

    def test_missing_fixed_dependency_is_rejected(self):
        self.publish_fixture(fixed=False)
        before=self.status.read_bytes()
        self.command('--simulate','--no-remove','install','agent-sphere=0.1.0-8','agent-apps=0.1.0-2',success=False)
        self.assertEqual(self.status.read_bytes(),before)
