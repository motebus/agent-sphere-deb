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
else:raise AssertionError(name)
'''

HARNESS = r'''import hashlib,json,os,pathlib,signal,subprocess,sys,time
os.umask(0o022)
P=pathlib.Path;mode=sys.argv[1];P('/run/mode').write_text(mode)
for name in ('/etc','/run','/var'):P(name).chmod(0o755)
P('/run/systemd/system').mkdir(parents=True)
identity=P('/etc/mote/moted/moted-mchat.env');identity.parent.mkdir(parents=True);identity.write_text('fixture secret identity\n');identity.chmod(0o640)
def snap(p):
    m=p.stat();return [hashlib.sha256(p.read_bytes()).hexdigest(),m.st_ino,m.st_mode,m.st_uid,m.st_gid,m.st_mtime_ns,m.st_ctime_ns,m.st_nlink]
before=snap(identity)
stage=P('/var/lib/agpc-install.ABCDef12');stage.mkdir(parents=True);stage.chmod(0o700)
P('/input').mkdir();P('/input/obsidian').write_bytes(b'exact fixture input')
P('/input/guard').write_text('#!/bin/bash\nset -eu\n[[ ${APT_HOOK_INFO_FD:-} == 0 ]]\nIFS= read -r version\n[[ $version == "VERSION 3" ]]\n')
P('/input/guard').chmod(0o700)
source=P('/source/scripts/detached-install.sh').read_text()
source+=r"""
job_stage=/var/lib/agpc-install.ABCDef12
guard=/input/guard
obsidian=/input/obsidian
packages=(agent-sphere=1.0 agent-ultra=1.0 agpc-manager=1.0 agent-apps=1.0 "$obsidian")
trap 'rm -rf /input' EXIT
write_ssh_readiness_helper() {
  printf '%s\n' 'import json,pathlib,sys' 'print(json.dumps({"fixture_ssh_state_only":True}))' 'sys.exit(17 if pathlib.Path("/run/mode").read_text()=="ssh-fails" else 0)'
}
agentsphere_job_platform_check || exit 71
if agentsphere_run_detached; then exit 0; else exit "$?"; fi
"""
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
    expected=42 if mode=='apt-fails' else 17 if mode=='ssh-fails' else 1 if mode in ('tampered-input','version-mismatch') else 0
    assert result['exit_code']==expected,result
    assert result['full_runtime_ready'] is False and result['mote_reachability']=='not-tested'
    if mode=='tampered-input':assert result['phase']=='inputs' and not P('/run/apt-started').exists()
    if mode=='apt-fails':assert result['phase']=='apt' and not (stage/'ssh.json').exists()
    if mode=='version-mismatch':assert result['phase']=='package-verification' and not (stage/'ssh.json').exists()
    if mode=='ssh-fails':assert result['phase']=='ssh' and result['packages_verified'] and not result['ssh_ready']
    if not expected:
        assert result['phase']=='complete'
        assert len(json.loads((stage/'packages.json').read_text())['packages'])==4
        assert len(P('/run/apt-calls').read_text().splitlines())==2
    for path in stage.iterdir():
        m=path.lstat();assert m.st_uid==0 and not m.st_mode&0o022,path
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
        for mode in ('success', 'disconnect', 'apt-fails', 'tampered-input', 'start-fails', 'untrusted-parent', 'version-mismatch', 'ssh-fails'):
            args = ['bwrap', '--unshare-all', '--die-with-parent', '--uid', '0', '--gid', '0',
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
            args += ['/usr/bin/python3', '/harness.py', mode]
            if os.environ.get('AGPC_BOOTSTRAP_NAMESPACE_SUDO') == '1':
                args = ['sudo', '--'] + args
            result = subprocess.run(args, capture_output=True, text=True, timeout=45)
            if result.returncode:
                sys.exit(mode + ': ' + result.stdout + result.stderr)
            print(result.stdout, end='')


if __name__ == '__main__':
    main()
