"""Real isolated APT core-only resolution; synthetic metadata, no DPKG action."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASELINE=json.loads((ROOT/'component-baseline.json').read_text())
CORE={p['name']:p['version'] for p in BASELINE['packages']}
DEPS={**CORE,**BASELINE['system_dependencies']}


class CoreDependencyTests(unittest.TestCase):
    def plan(self,missing=None,legacy=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();etc=root/'etc';etc.mkdir()
            for d in ('apt.conf.d','sources.list.d','preferences.d','trusted.gpg.d'):(etc/d).mkdir()
            (etc/'sources.list').write_text(f'deb [trusted=yes] file:{repo} ./\n')
            config=root/'apt.conf';config.write_text(f'Dir::Etc "{etc}";\n');status=root/'status'
            def fields(name,version):
                data={'Package':name,'Version':version,'Architecture':'all','Maintainer':'Fixture <fixture@example.invalid>','Description':'Offline metadata fixture'}
                if name=='agent-sphere':data['Depends']=', '.join(f'{n} (>= {v})' for n,v in DEPS.items()) if version=='0.2.0-2' else 'medge (>= 3.0.0-3)'
                if name=='agpc-manager':data['Depends']='medge (>= 3.1.0-2)'
                return data
            existing=[('agent-sphere','0.1.0-8'),('medge','3.0.0-3')] if legacy else []
            status.write_text('\n\n'.join('\n'.join(f'{k}: {v}' for k,v in dict(fields(n,v),Status='install ok installed').items()) for n,v in existing)+('\n' if existing else ''))
            before=status.read_bytes();index=[]
            for n,v in [*DEPS.items(),('agent-sphere','0.2.0-2'),('agpc-manager','3.1.0-2'),('medge','3.1.0-2'),*existing]:
                if n==missing:continue
                data=fields(n,v);stage=root/(n+v)/'DEBIAN';stage.mkdir(parents=True)
                (stage/'control').write_text('\n'.join(f'{k}: {v}' for k,v in data.items())+'\n')
                deb=repo/f'{n}_{v}_all.deb';subprocess.run(['dpkg-deb','--build',str(stage.parent),str(deb)],check=True,capture_output=True)
                data.update(Filename='./'+deb.name,Size=deb.stat().st_size,SHA256=hashlib.sha256(deb.read_bytes()).hexdigest());index.append('\n'.join(f'{k}: {v}' for k,v in data.items()))
            (repo/'Packages').write_text('\n\n'.join(index)+'\n')
            for p in ('state/lists/partial','cache/archives/partial','log'):(root/p).mkdir(parents=True)
            command=['apt-get','-o',f'Dir::Etc={etc}','-o',f'Dir::State={root}/state','-o',f'Dir::State::status={status}','-o',f'Dir::Cache={root}/cache','-o',f'Dir::Log={root}/log','-o','APT::Architecture=amd64','-o','Acquire::Languages=none','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=','-o','APT::Sandbox::User='+pwd.getpwuid(os.getuid()).pw_name]
            env=dict(os.environ,LC_ALL='C',APT_CONFIG=str(config))
            update=subprocess.run([*command,'update'],capture_output=True,text=True,env=env);self.assertEqual(update.returncode,0,update.stderr)
            result=subprocess.run([*command,'--simulate','--no-remove','install','agent-sphere=0.2.0-2'],capture_output=True,text=True,env=env)
            self.assertEqual(status.read_bytes(),before)
            return result

    def test_fresh_core_does_not_pull_manager_medge_or_desktop(self):
        result=self.plan();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        selected={l.split()[1] for l in result.stdout.splitlines() if l.startswith('Inst ')}
        self.assertEqual(selected,set(DEPS)|{'agent-sphere'},result.stdout)

    def test_changing_ownership_does_not_remove_existing_medge(self):
        result=self.plan(legacy=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertNotIn('Remv ',result.stdout);self.assertNotIn('Inst medge ',result.stdout)

    def test_missing_intelligence_does_not_result_in_partial_core(self):
        result=self.plan(missing='agos');self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
