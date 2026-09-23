#!/usr/bin/python3
"""Run the actual worker in a private Linux root and process namespace.

APT, package metadata, systemd and SSH state are explicit command fixtures.
This proves staging, guard integrity, exit status and caller separation,
not native package installation, boot or live systemd/SSH readiness.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

FAKE = r'''#!/usr/bin/python3
import json,os,pathlib,subprocess,sys,time
name=pathlib.Path(sys.argv[0]).name;args=sys.argv[1:]
mode=pathlib.Path('/run/mode').read_text()
if name=='systemd-run':
    os.umask(0o077)
    if mode=='start-fails':sys.exit(43)
    path=next(a.split('append:',1)[1] for a in args if 'StandardOutput=append:' in a)
    assert '--no-block' in args and '--service-type=exec' in args
    assert not any(a in args for a in ('--pty','--pipe','--scope'))
    if mode=='tampered-input':
        with open('/var/lib/agpc-install.ABCDef12/guard','a') as file:file.write('\n# changed after binding\n')
    with open(path,'ab') as log:
        child=subprocess.Popen(args[-2:],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    pathlib.Path('/run/job-pid').write_text(str(child.pid))
elif name=='systemctl':
    if args[0] in ('stop','start'):
        assert args in (['stop','uchatd.service'],['start','uchatd-redis.service'],['start','uchatd.service'])
        with open('/run/uchat-service-calls','a') as file:file.write(json.dumps(args)+'\n')
        sys.exit(0)
    assert args[0]=='show'
    try:
        pid=int(pathlib.Path('/run/job-pid').read_text())
        state=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1][0]
        print('inactive' if state=='Z' else 'active')
    except FileNotFoundError:print('inactive')
elif name=='apt-get':
    with open('/run/apt-calls','a') as file:file.write(json.dumps(args)+'\n')
    if args==['check']:sys.exit(0)
    assert '--yes' in args and 'install' in args and not os.isatty(0)
    pathlib.Path('/run/apt-started').touch()
    if mode=='disconnect':
        while not pathlib.Path('/run/release-worker').exists():time.sleep(0.05)
    if mode=='apt-fails':sys.exit(42)
    hook=next(a.split('=',1)[1] for a in args if a.startswith('DPkg::Pre-Install-Pkgs::='))
    assert 'DPkg::Tools::Options::'+hook+'::Version=3' in args
    assert 'DPkg::Tools::Options::'+hook+'::InfoFD=0' in args
    sys.exit(subprocess.run([hook],input='VERSION 3\n\n',text=True,env={**os.environ,'APT_HOOK_INFO_FD':'0'}).returncode)
elif name=='dpkg':
    assert args==['--audit']
elif name=='dpkg-query':
    assert args[:2]==['-W','-f=${Version}\n${Status}'] and len(args)==3
    print(('wrong' if mode=='version-mismatch' else '1.0')+'\ninstall ok installed',end='')
elif name=='runuser':
    assert args[:4]==['-u','uchatd','--','/usr/sbin/uchatd']
    with open('/run/uchat-runuser-calls','a') as file:file.write(json.dumps(args)+'\n')
    sys.exit(subprocess.run(args[3:]).returncode)
elif name=='uchatd':
    assert len(args)==3 and args[0] in ('init-store','check-store') and args[1:]==['--config','/etc/uchatd/uchatd.json']
    with open('/run/uchat-store-calls','a') as file:file.write(json.dumps(args)+'\n')
    identity=pathlib.Path('/var/lib/uchatd/store.identity.json')
    if args[0]=='init-store':
        if mode=='fresh-init-fails':sys.exit(44)
        if identity.exists():sys.exit(46)
        identity.write_text(json.dumps({'schema':'uchat.fixture-store/v1','id':'initialized-once'}))
        identity.chmod(0o600)
    else:
        if mode=='fresh-check-fails':sys.exit(45)
        assert identity.is_file()
elif name=='setup-default.py':
    assert args==['--user','operator']
    pathlib.Path('/run/uchat-setup-called').touch()
    assert pathlib.Path('/var/lib/uchatd/store.identity.json').is_file()
    print(json.dumps({'configured':True,'fixture_only':True}))
else:raise AssertionError(name)
'''

HARNESS = r'''import hashlib,json,os,pathlib,signal,subprocess,sys,time
os.umask(0o022)
P=pathlib.Path;mode=sys.argv[1];P('/run/mode').write_text(mode)
profile='full' if mode in ('full-success','full-transition','fresh-full') else 'standard'
fresh=mode.startswith('fresh-')
uchat_state='absent' if fresh else 'redis:0.5.0-1'
for name in ('/etc','/run','/var'):P(name).chmod(0o755)
P('/run/systemd/system').mkdir(parents=True)
# Service commands are fixtures; UID0 aliases let native install(1) validate
# ownership arguments inside a root-only user namespace without host accounts.
P('/etc/passwd').write_text('root:x:0:0:root:/root:/bin/bash\nuchatd:x:0:0:fixture:/var/lib/uchatd:/usr/sbin/nologin\n')
P('/etc/group').write_text('root:x:0:\nuchat:x:0:\n')
identity=P('/etc/mote/moted/moted-mchat.env');identity.parent.mkdir(parents=True);identity.write_text('fixture secret identity\n');identity.chmod(0o640)
def snap(p):
    m=p.stat();return [hashlib.sha256(p.read_bytes()).hexdigest(),m.st_ino,m.st_mode,m.st_uid,m.st_gid,m.st_mtime_ns,m.st_ctime_ns,m.st_nlink]
before=snap(identity)
store=P('/var/lib/uchatd/store.identity.json')
store_before=None
if not fresh or mode=='fresh-existing-store':
    store.parent.mkdir(parents=True);store.parent.chmod(0o700)
    store.write_text('{"schema":"uchat.fixture-store/v1","id":"preserve-existing"}\n');store.chmod(0o600)
    store_before=snap(store)
stage=P('/var/lib/agpc-install.ABCDef12');stage.mkdir(parents=True);stage.chmod(0o700)
P('/input').mkdir();P('/input/obsidian').write_bytes(b'exact fixture input')
P('/input/guard').write_text('#!/bin/bash\nset -eu\n[[ ${APT_HOOK_INFO_FD:-} == 0 ]]\nIFS= read -r version\n[[ $version == "VERSION 3" ]]\n')
P('/input/guard').chmod(0o700)
source=P('/source/scripts/detached-install.sh').read_text()
source+=r"""
job_stage=/var/lib/agpc-install.ABCDef12
guard=/input/guard
obsidian=/input/obsidian
agpc_profile=PROFILE_FIXTURE
uchat_state=UCHAT_STATE_FIXTURE
agpc_chat_user=operator
packages=(agent-sphere=1.0 agent-ultra=1.0 agpc-manager=1.0 contextd=1.0 uchatd=1.0 "$obsidian")
if [[ $agpc_profile == full ]]; then packages+=(agpc-apps=1.0); fi
if [[ MODE_FIXTURE == full-transition ]]; then packages+=(agent-apps=1.0); fi
if [[ MODE_FIXTURE == missing-entry ]]; then packages=(agent-sphere=1.0 agent-ultra=1.0 agpc-manager=1.0 uchatd=1.0 "$obsidian"); fi
trap 'rm -rf /input' EXIT
write_ssh_readiness_helper() {
  printf '%s\n' 'import json,pathlib,sys' 'print(json.dumps({"fixture_ssh_state_only":True}))' 'sys.exit(17 if pathlib.Path("/run/mode").read_text()=="ssh-fails" else 0)'
}
agentsphere_job_platform_check || exit 71
if agentsphere_run_detached; then exit 0; else exit "$?"; fi
"""
source=source.replace('PROFILE_FIXTURE',profile).replace('UCHAT_STATE_FIXTURE',uchat_state).replace('MODE_FIXTURE',mode)
P('/run/caller').write_text(source)
if mode=='untrusted-parent':P('/var/lib').chmod(0o777)
with open('/run/caller.log','wb') as output:
    caller=subprocess.Popen(['/bin/bash','/run/caller'],stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True)
    if mode=='disconnect':
        limit=time.monotonic()+15
        while not P('/run/apt-started').exists():
            assert caller.poll() is None and time.monotonic()<limit;time.sleep(0.05)
        os.killpg(caller.pid,signal.SIGHUP)
        assert caller.wait(timeout=5)==130
        assert not (stage/'result.json').exists()
        P('/run/release-worker').touch()
    else:caller.wait(timeout=20)
if mode in ('start-fails','untrusted-parent'):
    assert caller.returncode==(43 if mode=='start-fails' else 71)
    assert not P('/run/apt-started').exists() and not (stage/'result.json').exists()
    result={'exit_code':caller.returncode,'phase':'pre-launch'}
else:
    limit=time.monotonic()+10
    while not (stage/'result.json').exists():
        assert time.monotonic()<limit, P('/run/caller.log').read_text()+((stage/'install.log').read_text() if (stage/'install.log').exists() else '')
        time.sleep(0.05)
    result=json.loads((stage/'result.json').read_text())
    expected={'apt-fails':42,'ssh-fails':17,'tampered-input':1,'version-mismatch':1,'missing-entry':1,
              'fresh-init-fails':44,'fresh-check-fails':45,'fresh-existing-store':46}.get(mode,0)
    assert result['exit_code']==expected,result
    assert result['full_runtime_ready'] is False and result['mote_reachability']=='not-tested'
    if mode=='tampered-input':assert result['phase']=='inputs' and not P('/run/apt-started').exists()
    if mode=='apt-fails':assert result['phase']=='apt' and not (stage/'ssh.json').exists()
    if mode in ('version-mismatch','missing-entry'):assert result['phase']=='package-verification' and not (stage/'ssh.json').exists()
    if mode=='ssh-fails':assert result['phase']=='ssh' and result['packages_verified'] and not result['ssh_ready']
    if not expected:
        assert result['phase']=='complete'
        package_report=json.loads((stage/'packages.json').read_text())
        expected_entries={'agent-sphere','agent-ultra','agpc-manager','contextd','uchatd'}
        if profile=='full':expected_entries.add('agpc-apps')
        if mode=='full-transition':expected_entries.add('agent-apps')
        assert package_report['profile']==profile
        assert {record['name'] for record in package_report['packages']}==expected_entries
        assert len(package_report['packages'])==len(expected_entries)
        assert len(P('/run/apt-calls').read_text().splitlines())==2
    for path in stage.iterdir():
        m=path.lstat();assert m.st_uid==0 and not m.st_mode&0o022,path
store_calls=[json.loads(line) for line in P('/run/uchat-store-calls').read_text().splitlines()] if P('/run/uchat-store-calls').exists() else []
service_calls=[json.loads(line) for line in P('/run/uchat-service-calls').read_text().splitlines()] if P('/run/uchat-service-calls').exists() else []
if mode in ('fresh-init-fails','fresh-check-fails','fresh-existing-store'):
    assert result['phase']=='uchat' and result['packages_verified'] and not result['ssh_ready'],result
    assert not (stage/'ssh.json').exists() and not P('/run/uchat-setup-called').exists()
    assert ['start','uchatd.service'] not in service_calls
    assert [args[0] for args in store_calls]==(['init-store','check-store'] if mode=='fresh-check-fails' else ['init-store'])
if fresh and result['exit_code']==0:
    assert [args[0] for args in store_calls]==['init-store','check-store']
    assert service_calls==[['stop','uchatd.service'],['start','uchatd-redis.service'],['start','uchatd.service']]
    assert P('/run/uchat-setup-called').exists() and store.exists()
    runuser_calls=[json.loads(line) for line in P('/run/uchat-runuser-calls').read_text().splitlines()]
    assert len(runuser_calls)==2 and all(args[:4]==['-u','uchatd','--','/usr/sbin/uchatd'] for args in runuser_calls)
if not fresh:
    assert store_calls==[] and service_calls==[]
    assert not P('/run/uchat-runuser-calls').exists()
if store_before is not None:assert snap(store)==store_before
assert not P('/input').exists()
assert snap(identity)==before
print(json.dumps({'scenario':mode,'passed':True,'result':result,'identity_preserved':True,'service_and_apt_commands':'fixtures','real_linux_namespace':True}))
'''


def main():
    if sys.argv[1:]:
        sys.exit('Usage: check-detached-namespace.py')
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='detached-test-', dir=ROOT / 'build') as temp:
        base = Path(temp)
        fake = base / 'fake'
        fake.write_text(FAKE)
        fake.chmod(0o755)
        harness = base / 'harness.py'
        harness.write_text(HARNESS)
        for mode in ('success', 'full-success', 'full-transition', 'fresh-success', 'fresh-full',
                     'fresh-init-fails', 'fresh-check-fails', 'fresh-existing-store', 'missing-entry',
                     'disconnect', 'apt-fails', 'tampered-input', 'start-fails', 'untrusted-parent',
                     'version-mismatch', 'ssh-fails'):
            privileged = os.environ.get('AGPC_BOOTSTRAP_NAMESPACE_SUDO') == '1'
            # Root CI can isolate mounts/network/PIDs directly. Remapping only
            # UID0 would hide the CI runner-owned private checkout from bwrap.
            isolation = ['--unshare-pid', '--unshare-net', '--unshare-ipc', '--unshare-uts'] if privileged else ['--unshare-all', '--uid', '0', '--gid', '0']
            args = ['bwrap', *isolation, '--die-with-parent',
                    '--clearenv', '--setenv', 'PATH', '/usr/sbin:/usr/bin:/sbin:/bin',
                    '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
                    '--symlink', 'usr/sbin', '/sbin', '--symlink', 'usr/lib', '/lib']
            if Path('/lib64').exists():
                args += ['--symlink', 'usr/lib64', '/lib64']
            args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/etc', '--tmpfs', '/run',
                     '--tmpfs', '/var', '--tmpfs', '/tmp', '--ro-bind', str(ROOT), '/source',
                     '--ro-bind', str(harness), '/harness.py']
            for name in ('apt-get', 'dpkg', 'dpkg-query', 'systemctl', 'systemd-run'):
                args += ['--ro-bind', str(fake), '/usr/bin/' + name]
            # Overlay only service fixture locations; no host executable or
            # package state is changed and real setup/init never runs here.
            args += ['--tmpfs','/usr/sbin','--tmpfs','/usr/libexec','--dir','/usr/libexec/uchat']
            for name in ('runuser','uchatd'):
                args += ['--ro-bind',str(fake),'/usr/sbin/'+name]
            args += ['--ro-bind',str(fake),'/usr/libexec/uchat/setup-default.py',
                     '/usr/bin/python3', '/harness.py', mode]
            if privileged:
                args = ['sudo', '--'] + args
            result = subprocess.run(args, capture_output=True, text=True, timeout=45)
            if result.returncode:
                sys.exit(mode + ': ' + result.stdout + result.stderr)
            print(result.stdout, end='')


if __name__ == '__main__':
    main()
