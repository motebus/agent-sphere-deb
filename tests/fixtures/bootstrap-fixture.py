#!/usr/bin/python3
"""Executed only in an isolated fixture namespace with fake fixed HTTPS download."""
import hashlib,json,os,pathlib,shutil,socket,subprocess
P=pathlib.Path
assert os.geteuid()==0 and P('/.bootstrap-fixture').is_file()
parent=json.loads(P('/fixture/parent-namespaces.json').read_text())
assert all(os.readlink('/proc/self/ns/'+name)!=identifier for name,identifier in parent.items())
status=dict(line.split(':',1) for line in P('/proc/self/status').read_text().splitlines() if ':' in line)
assert int(status['CapEff'].strip(),16)==0
assert [name for _,name in socket.if_nameindex()]==['lo']
assert not P('/home').exists() and not P('/sys').exists()
F='/fixture/agentsphere-bootstrap.sh';key=P('/etc/apt/keyrings/medge-archive-keyring.gpg');source=P('/etc/apt/sources.list.d/medge.sources');checks=[]
def run(expr,ok=True,extra=None):
 env={'PATH':'/fixture/bin:/usr/bin:/bin','LC_ALL':'C'};env.update(extra or {})
 r=subprocess.run(['/bin/bash','-eu','-c','source '+F+'; '+expr],capture_output=True,text=True,env=env,timeout=20)
 assert (r.returncode==0)==ok,(expr,r.returncode,r.stdout,r.stderr)
 return r
def meta(p):
 m=p.stat();return [hashlib.sha256(p.read_bytes()).hexdigest(),m.st_ino,m.st_uid,m.st_gid,m.st_mode,m.st_mtime_ns,m.st_ctime_ns]
def reset(version='24.04',id='ubuntu'):
 shutil.rmtree('/etc/apt',ignore_errors=True);P('/etc/apt/sources.list.d').mkdir(parents=True)
 P('/etc/os-release').unlink(missing_ok=True);P('/etc/os-release').write_text(f'ID={id}\nVERSION_ID="{version}"\n')
 P('/etc/apt/sources.list.d/ubuntu.sources').write_text('Types: deb\nURIs: https://archive.ubuntu.com/ubuntu\nSuites: noble\nComponents: main\n')
 P('/tmp/curl-log').unlink(missing_ok=True)
reset();ubuntu=P('/etc/apt/sources.list.d/ubuntu.sources');original=meta(ubuntu)
run('agentsphere_apt_bootstrap');assert key.is_file() and source.is_file();assert key.stat().st_mode&0o777==0o644 and source.stat().st_mode&0o777==0o644
assert hashlib.sha256(key.read_bytes()).hexdigest()=='756fc2632c307509b8e5ece665ced7f4d1a58636ac935aefc1e017f7dcfcbfbd'
assert source.read_bytes()==P('/fixture/medge.sources').read_bytes();assert meta(ubuntu)==original
before={str(p):meta(p) for p in (key,source,ubuntu)};downloads=P('/tmp/curl-log').read_bytes();run('agentsphere_apt_bootstrap')
assert before=={str(p):meta(p) for p in (key,source,ubuntu)} and P('/tmp/curl-log').read_bytes()==downloads
checks+=['clean trusted source/key publication','exact repeat preserves bytes/inode/metadata without download']
source.write_text('Types: deb\nURIs: https://custom.invalid/repo\n');before=meta(source);run('agentsphere_apt_bootstrap',False);assert meta(source)==before and P('/tmp/curl-log').read_bytes()==downloads
checks.append('custom source rejected before fetch or overwrite')
reset();key.parent.mkdir();key.write_bytes(b'owner-custom-key');before=meta(key);run('agentsphere_apt_bootstrap',False);assert meta(key)==before and not source.exists() and not P('/tmp/curl-log').exists()
checks.append('custom key rejected without source creation')
reset();alt=P('/etc/apt/sources.list.d/other.list');alt.write_text('deb https://motebus.github.io/download stable main\n');before=meta(alt);run('agentsphere_apt_bootstrap',False);assert meta(alt)==before and not key.exists()
checks.append('ambiguous duplicate source rejected')
reset();key.parent.mkdir();key.write_bytes(P('/fixture/key.gpg').read_bytes());before=meta(key);run('agentsphere_apt_bootstrap');assert meta(key)==before and not P('/tmp/curl-log').exists()
checks.append('missing source repaired using exact existing key offline')
reset();P('/etc/os-release').unlink();P('/etc/os-release').symlink_to('../usr/lib/os-release');run('agentsphere_platform_check');checks.append('canonical Ubuntu os-release symlink admitted')
reset();run('agentsphere_platform_check',False,{'PATH':'/fixture/arm-bin:/fixture/bin:/usr/bin:/bin'});assert not key.exists();checks.append('unsupported CPU architecture rejected before mutation')
reset('26.04');run('agentsphere_platform_check');checks.append('Ubuntu26 amd64 admitted')
reset('24.04','debian');run('agentsphere_apt_bootstrap',False);assert not key.exists() and not source.exists();checks.append('unsupported distribution rejected before mutation')
reset('22.04');run('agentsphere_apt_bootstrap',False);assert not key.exists();checks.append('unsupported Ubuntu release rejected')
reset();run('agentsphere_platform_check',False,{'PATH':'/fixture/missing-gpg'});assert not key.exists();checks.append('missing requirement rejected before mutation')
reset();run('agentsphere_apt_bootstrap',False,{'BAD_KEY':'1'});assert not key.exists() and not source.exists();checks.append('bad downloaded key rejected before publication')
reset();target=P('/etc/owner-key');target.write_bytes(b'untouched');key.parent.mkdir();key.symlink_to(target);before=meta(target);run('agentsphere_apt_bootstrap',False);assert meta(target)==before and key.is_symlink();checks.append('symlinked key refused and target untouched')
run('agentsphere_launch_manager');run('agentsphere_launch_manager --yes');run('agentsphere_launch_manager --invalid',False);checks.append('noTTY and explicit yes skip UI; bad flag rejected')
result={'ok':True,'checks':checks,'isolation':{'private_user_network_mount_namespaces':True,'effective_capabilities':0},'scope':'isolated namespace; fixed download adapter returns reviewed public key; real GPG SHA/fingerprint inspection; no network, APT transaction or host changes'}
print(json.dumps(result))
