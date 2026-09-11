#!/usr/bin/python3
"""Actual historical archives and native DPKG; no status/ownership injection."""
import hashlib,json,os,subprocess,sys,shlex
from pathlib import Path
from test_rename_apt_support import fingerprint,dummy,installed,run

def record():
 return run('dpkg-query','-W','-f=${Version}\n${Architecture}\n${Status}\n${Conffiles}','cx-node')
def metadata():
 result={'record':record(),'config_owner':run('dpkg-query','-S','/etc/cx-node/cx-node.toml').strip(),'drain_owner':run('dpkg-query','-S','/usr/bin/cx').strip(),'files':{}}
 for p in Path('/var/lib/dpkg/info').glob('cx-node.*'):
  result['files'][p.name]={'fingerprint':fingerprint(p),'text':p.read_text() if p.suffix in ['.list','.conffiles'] else None}
 for p in [Path('/usr/bin/cx'),Path('/usr/libexec/cx-node/install-config')]:result['files'][str(p)]={'fingerprint':fingerprint(p)}
 return result
def main():
 assert os.geteuid()==0 and Path('/.cx-rename-fixture').exists()
 os.umask(0o022)
 mode=sys.argv[1];assert mode in ['probe','both','disabled','masked','system-dirs','lab-residual']
 Path('/etc/passwd').write_text('root:x:0:0:root:/root:/bin/sh\ncx-node:x:0:0:fixture:/var/lib/cx-node:/usr/sbin/nologin\n');Path('/etc/group').write_text('root:x:0:\ncx-node:x:0:\n')
 for name in ('/etc/apt/apt.conf.d','/etc/apt/preferences.d','/etc/apt/sources.list.d','/var/lib/apt/lists/partial','/var/cache/apt/archives/partial','/var/log/apt','/var/tmp','/var/lib/dpkg','/run/systemd/system'):
  Path(name).mkdir(parents=True,exist_ok=True)
 Path('/var/lib/dpkg/status').touch();Path('/etc/apt/sources.list').touch();os.environ['DEBIAN_FRONTEND']='noninteractive'
 deps=[dummy(n) for n in ('libc6','libgcc-s1','adduser','moted','mote-bridge-mcp','mote-mcpd','mote-chatd','mote-transportd','systemd','codex','chatgpt','motemcp')];run('dpkg','-i',*deps)
 if mode in ('system-dirs','lab-residual'):
  # Real base packages own these shared directories before CX is installed.
  seed=Path(dummy('system-directory-owner'))
  for directory in ('usr/bin','usr/lib','usr/libexec'):(Path('/tmp/build/system-directory-owner')/directory).mkdir(parents=True,exist_ok=True)
  run('dpkg-deb','--build','--root-owner-group','/tmp/build/system-directory-owner',str(seed));run('dpkg','-i',str(seed))
 run('dpkg','-i','/packages/historical.deb');run('dpkg','-i','/packages/old1.deb')
 if mode=='lab-residual':run('dpkg','-i','/packages/old6.deb')
 run('dpkg','-i','/packages/old-mesh.deb')
 if mode=='lab-residual':
  # Construct the genuine previously migrated 1.1 baseline, without rewriting
  # status, file lists or conffile ownership. The current guarded upgrade follows.
  run('apt-get','-o','APT::Sandbox::User=root','-o','Dpkg::Options::=--force-confold','-y','install','/packages/baseline.deb')
  assert Path('/var/lib/dpkg/info/cx-node.list').read_text()=='/etc/cx-node/cx-node.toml\n'

 expected=' /etc/cx-node/cx-node.toml d137b03f7f14c9c1369d3e85a9062130 obsolete'
 assert record().endswith(expected),record()
 paths=[Path('/etc/cx-node/cx-node.toml'),Path('/etc/cx-node/cx-node-mchat.env'),Path('/etc/mote/codex-mesh/config.json'),Path('/etc/codex/skills/codex-mesh/SKILL.md'),Path('/var/lib/cx-node/state/runtime-migration.json')]
 paths[0].write_text(paths[0].read_text()+'\n# owner obsolete configuration retained\n')
 paths[3].write_text(paths[3].read_text()+'\nOwner review remains required.\n')
 session=Path('/var/lib/cx-node/sessions/retained.json');session.write_text('{"fixture":"retained"}\n');session.chmod(0o600);paths.append(session)
 if mode=='disabled':
  for target in ['multi-user.target','moted.service']:Path('/etc/systemd/system',target+'.wants','cx-node.service').unlink()
  Path('/tmp/active-cx-node.service').write_text('inactive')
 if mode=='masked':Path('/etc/systemd/system/cx-node.service').symlink_to('/dev/null')
 source=Path('/source/agpc.sh').read_text()
 code=source.split("python3 - <<'CX_PREFLIGHT'\n",1)[1].split('\nCX_PREFLIGHT\n',1)[0]
 Path('/tmp/classifier.py').write_text(code)
 negative=[]
 def denied(label):
  status=fingerprint(Path('/var/lib/dpkg/status'))
  protected=fingerprint(Path('/etc/cx-node/cx-node-mchat.env'))
  run('python3','/tmp/classifier.py',ok=False)
  assert status==fingerprint(Path('/var/lib/dpkg/status'))
  assert protected==fingerprint(Path('/etc/cx-node/cx-node-mchat.env'))
  negative.append(label)
 if mode=='lab-residual':
  for name in ('/var/lib/dpkg/info/cx-node.list','/var/lib/dpkg/info/cx-node.postrm'):
   p=Path(name);original=p.read_bytes();p.write_bytes(original+b'\n/etc/foreign\n');denied('changed residual '+name);p.write_bytes(original)
 elif mode!='probe':
  for name in ('/var/lib/dpkg/info/cx-node.list','/var/lib/dpkg/info/cx-node.prerm','/usr/bin/cx'):
   p=Path(name);original=p.read_bytes();p.write_bytes(original+b'\n/etc/mote/foreign/locked-mchat.env\n');denied('changed '+name);p.write_bytes(original)
  config=paths[0];original=config.read_bytes();assert b'path = "/var/lib/cx-node"' in original
  config.write_bytes(original.replace(b'path = "/var/lib/cx-node"',b'path = "/etc/cx-node"'));denied('custom drain state root');config.write_bytes(original)
  marker=Path('/var/lib/cx-node/state/draining')
  assert not marker.exists()
  marker.symlink_to(paths[1]);denied('symlink drain target');marker.unlink()
  os.link(paths[1],marker);denied('hardlink drain target');marker.unlink()
  state=marker.parent;state.rename(state.with_name('state-preserved'));state.symlink_to(state.with_name('state-preserved'))
  denied('symlink state parent');state.unlink();state.with_name('state-preserved').rename(state)
  original_mode=state.stat().st_mode&0o777;state.chmod(0o777);denied('writable state parent');state.chmod(original_mode)
 Path('/etc/os-release').write_bytes(Path('/host-os-release').read_bytes())
 Path('/etc/apt/keyrings').mkdir()
 Path('/etc/apt/keyrings/medge-archive-keyring.gpg').write_bytes(Path('/fixture-key.gpg').read_bytes())
 before={str(p):fingerprint(p) for p in paths}
 classified=run('python3','/tmp/classifier.py').strip() if mode!='probe' else ''
 if mode!='probe':
  bootstrap=source.split('# BEGIN SIGNED BOOTSTRAP\n',1)[1].split('# END SIGNED BOOTSTRAP',1)[0]
  Path('/tmp/bootstrap.sh').write_text(bootstrap+'\nagentsphere_apt_bootstrap\n')
  Path('/tmp/bootstrap.log').write_text(run('bash','/tmp/bootstrap.sh'))
  assert run('python3','/tmp/classifier.py').strip()==classified
 def guard(expected):
  # Use the exact production CX classifier and production v3 transaction guard.
  # The other independent migration classifiers are fixture-absent; their
  # package dependencies are stand-ins and are not acceptance subjects here.
  function=source.split('classify_legacy_cx() {\n',1)[1].split('\nCX_PREFLIGHT\n}',1)[0]
  body=source.split("cat <<'GUARD'\n",1)[1].split('\nGUARD\n',1)[0]
  container=source.split('agentsphere_container_runtime_package() {\n',1)[1].split('\n}\n',1)[0]
  script='#!/bin/bash\nset -euo pipefail\nagentsphere_container_runtime_package() {\n'+container+'\n}\nclassify_legacy_cx() {\n'+function+'\nCX_PREFLIGHT\n}\n'
  for component in ['chatd','mcp','manager']:script+='classify_legacy_'+component+'() { echo absent; }\n'
  script+='expected_legacy_state=absent\nexpected_mcp_state=absent\nexpected_manager_state=absent\nexpected_cx_state='+shlex.quote(expected)+'\n'+body
  Path('/tmp/production-guard').write_text(script);Path('/tmp/production-guard').chmod(0o700)
  return ['-o','DPkg::Pre-Install-Pkgs::=/tmp/production-guard','-o','DPkg::Tools::Options::/tmp/production-guard::Version=3','-o','DPkg::Tools::Options::/tmp/production-guard::InfoFD=0']
 Path('/tmp/installed-metadata.json').write_text(json.dumps(metadata(),indent=2))
 Path('/tmp/plan.log').write_text(run('apt-get','-s','-o','APT::Sandbox::User=root','install','/packages/new.deb'))
 Path('/tmp/transition.log').write_text(run('apt-get','-o','APT::Sandbox::User=root',*(guard(classified) if mode!='probe' else []),'-o','Dpkg::Options::=--force-confold','-y','install','/packages/new.deb'))
 assert installed('cx-mesh') and not installed('cx-node') and not installed('codex-mesh') and not run('dpkg','--audit').strip()
 Path('/tmp/residual-metadata.json').write_text(json.dumps(metadata(),indent=2))
 after={p:fingerprint(Path(p)) for p in before}
 Path('/tmp/preservation.json').write_text(json.dumps({'before':before,'after':after},indent=2))
 assert before==after
 if mode!='probe':
  residual=run('python3','/tmp/classifier.py').strip();assert residual.startswith('cx-node=-,cx-agent=-,codex-mesh=-;')
  assert record().endswith(expected)
  # A native reinstall forces the real residual classifier and v3 guard to
  # run again, while a normal repeat install also resolves without removals.
  Path('/tmp/repeat.log').write_text(run('apt-get','-o','APT::Sandbox::User=root',*guard(residual),'-o','Dpkg::Options::=--force-confold','--reinstall','-y','install','/packages/new.deb'))
  assert before=={p:fingerprint(Path(p)) for p in before}
  assert record().endswith(expected)
  assert run('python3','/tmp/classifier.py').strip().startswith('cx-node=-,cx-agent=-,codex-mesh=-;')
  assert not run('dpkg','--audit').strip()
  assert 'REMOVED' not in run('apt-get','-s','-o','APT::Sandbox::User=root','install','/packages/new.deb')
  if mode=='disabled':assert not Path('/etc/systemd/system/multi-user.target.wants/cx-mesh.service').is_symlink()
  if mode=='masked':assert Path('/etc/systemd/system/cx-mesh.service').readlink()==Path('/dev/null')
  assert Path('/var/lib/cx-node/state/draining').is_file() # Known drain mutation; not Ready evidence.
 value={'schema':'cx1-retirement.native-migration/v1','scenario':mode,'passed':True,'native_chain':['0.3.1-4','0.3.3-1','cx-mesh1.2.0-1'],'no_status_file_edit':True,'no_purge':True,'config_identity_receipt_session_full_metadata_preserved':True,'dependency_standins':True,'systemctl_mocked':True,'single_mapped_uid':True,'live_ready':False,'debs_sha256':{n:hashlib.sha256(Path('/packages/'+n+'.deb').read_bytes()).hexdigest() for n in ['historical','old1','old6','old-mesh','baseline','new']}}
 if mode=='lab-residual':value['native_chain']=['0.3.1-4','0.3.3-1','0.3.3-6','cx-mesh1.1.0-1','cx-mesh1.2.0-1']
 value['system_directory_ownership']=mode in ('system-dirs','lab-residual')
 value['residual_list_sha256']=hashlib.sha256(Path('/var/lib/dpkg/info/cx-node.list').read_bytes()).hexdigest()
 value.update({'production_missing_source_bootstrap':mode!='probe','production_cx_classifier_and_locked_guard':mode!='probe','residual_native_repeat':mode!='probe','denied_before_dpkg':negative,'drain_marker_is_expected_mutation':True})
 Path('/tmp/acceptance.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
if __name__=='__main__':main()
