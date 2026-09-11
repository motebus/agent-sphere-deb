#!/usr/bin/python3
"""Check real OpenSSH configuration/banner in a disposable Linux namespace.

Systemd and DPKG observations are explicit fixtures. Privileged CI must also
pass the real daemon/banner gate; a local single-UID namespace records its
privilege-separation limitation instead of claiming that gate passed.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''import hashlib,importlib.util,json,os,pathlib,subprocess,sys,time
os.umask(0o022)
P=pathlib.Path
for path in ('/etc','/run','/var'):P(path).chmod(0o755)
P('/etc/ssh').mkdir();P('/var/empty').mkdir()
P('/etc/passwd').write_text('root:x:0:0:root:/root:/bin/bash\nsshd:x:74:74:sshd:/var/empty:/usr/sbin/nologin\n')
P('/etc/group').write_text('root:x:0:\nsshd:x:74:\n')
P('/etc/ssh/sshd_config').write_text('Port 22\nListenAddress 127.0.0.1\nHostKey /etc/ssh/test_host_key\nPidFile /run/sshd-test.pid\nUsePAM no\nPasswordAuthentication no\nPermitRootLogin no\n')
subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f','/etc/ssh/test_host_key'],check=True)
spec=importlib.util.spec_from_file_location('ssh','/source/scripts/ssh-readiness.py');ssh=importlib.util.module_from_spec(spec);spec.loader.exec_module(ssh)
def snapshot():
    result={}
    for p in P('/etc/ssh').iterdir():
        s=p.lstat();result[str(p)]=[hashlib.sha256(p.read_bytes()).hexdigest(),s.st_ino,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
    return result
before=snapshot()
ssh.trusted_runtime_directory()
assert subprocess.run(['/usr/sbin/sshd','-t'],capture_output=True).returncode==0
assert snapshot()==before
real_command=ssh.command;daemon=None;calls=[];state={'UnitFileState':'disabled','ActiveState':'inactive','LoadState':'loaded','SubState':'dead'}
def unit(name):
    return dict(state) if name=='ssh.service' else {'UnitFileState':'masked','ActiveState':'inactive','LoadState':'masked','SubState':'dead'}
def command(args,timeout=30):
    global daemon
    calls.append(args)
    if args[0].endswith('dpkg-query'):return subprocess.CompletedProcess(args,0,'install ok installed','')
    if args[0].endswith('systemctl'):
        if args[1]=='enable':state['UnitFileState']='enabled'
        elif args[1]=='start':
            daemon=subprocess.Popen(['/usr/sbin/sshd','-D','-e'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=open('/run/sshd.log','wb'))
            state['ActiveState']='active';state['SubState']='running'
        else:raise AssertionError(args)
        return subprocess.CompletedProcess(args,0,'','')
    return real_command(args,timeout)
ssh.command=command;ssh.unit=unit
try:
    report=ssh.ensure_ssh_ready()
    assert snapshot()==before
    assert not any(x in args for args in calls for x in ('restart','unmask','ssh-keygen'))
    if report['error']:
        error=P('/run/sshd.log').read_text()
        if sys.argv[1]=='required':raise AssertionError({'report':report,'daemon_error':error})
        assert report['error']=='loopback-ssh-banner-unavailable',report
        assert any(s in error for s in ('setgroups','setgid','setuid','privilege separation','Operation not permitted','Invalid argument','Bind to port 22 on 127.0.0.1 failed: Permission denied.')),error
        print(json.dumps({'real_configuration_check':True,'real_loopback_banner':'unavailable-local-namespace-privileges','configuration_and_keys_preserved':True,'privileged_ci_gate_required':True}))
    else:
        assert report['loopback_ssh_ready'] and report['boot_enabled'] and not report['full_runtime_ready']
        print(json.dumps({'real_configuration_check':True,'real_loopback_banner':True,'configuration_and_keys_preserved':True,'systemd_and_dpkg_observations':'fixtures','real_linux_namespace':True}))
finally:
    if daemon is not None:daemon.terminate();daemon.wait(timeout=5)
# Invalid owner config must fail before any systemd enable/start operation.
P('/etc/ssh/sshd_config').write_text('UnknownSshOption fixture\n');calls.clear();before=snapshot()
report=ssh.ensure_ssh_ready();assert report['error']=='sshd-configuration-invalid',report
assert not any(a[0].endswith('systemctl') for a in calls) and snapshot()==before
print(json.dumps({'invalid_actual_sshd_configuration_refused':True,'configuration_unchanged':True}))
'''


def main():
    if sys.argv[1:]:sys.exit('Usage: check-ssh-namespace.py')
    if not Path('/usr/sbin/sshd').is_file():sys.exit('OpenSSH server is required for namespace validation.')
    privileged = os.environ.get('AGPC_BOOTSTRAP_NAMESPACE_SUDO') == '1'
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ssh-namespace-',dir=ROOT/'build') as temporary:
        harness=Path(temporary)/'harness.py';harness.write_text(HARNESS)
        args=['bwrap','--die-with-parent','--clearenv','--setenv','PATH','/usr/sbin:/usr/bin:/sbin:/bin']
        if privileged:
            args+=['--unshare-pid','--unshare-net','--unshare-ipc','--unshare-uts','--new-session']
            for cap in ('CAP_SETUID','CAP_SETGID','CAP_SYS_CHROOT','CAP_NET_BIND_SERVICE'):args+=['--cap-add',cap]
        else:args+=['--unshare-all','--uid','0','--gid','0']
        args+=['--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/sbin','/sbin','--symlink','usr/lib','/lib']
        if Path('/lib64').exists():args+=['--symlink','usr/lib64','/lib64']
        args+=['--proc','/proc','--dev','/dev','--tmpfs','/etc','--tmpfs','/run','--tmpfs','/var','--tmpfs','/tmp',
               '--ro-bind',str(ROOT),'/source','--ro-bind',str(harness),'/harness.py',
               '/usr/bin/python3','/harness.py','required' if privileged else 'limited']
        if privileged:args=['sudo','--']+args
        result=subprocess.run(args,text=True,capture_output=True,timeout=45)
        if result.returncode:sys.exit(result.stdout+result.stderr)
        print(result.stdout,end='')


if __name__=='__main__':main()
