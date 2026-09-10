#!/usr/bin/env python3
"""Actual released DEB migration, offline in disposable single-UID namespaces.

Requires bubblewrap and three checksum-pinned public artifacts. Only the two
transport packages are actual runtimes; OS dependencies are empty fixtures.
Systemd observations are mocked. This proves DPKG ownership/file preservation,
not live service execution or UltraOne readiness. Never installs on the host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PINS={'old':'63987fcc1fae67855e194471ebb0803a7a153eaec141bf429703b575e4bed9a5',
      'runtime':'9c56cade3f014f75876cce126d2ef8c9d5c27a60709ff592ac0e9af9788dd23f',
      'retention':'b6c278fc03eb6c53fbf7569bf58ce636afcef0084ee388e2db08096bf5bef188'}
TARGET=Path('/etc/mote/mote-chatd/mote-chatd-mchat.env')
NORMAL=TARGET.with_name('mote-chatd-deb.env')
JOURNAL=Path('/var/lib/mote/mote-chatd/inbox.ndjson')
RECEIPT=Path('/var/lib/mote-chatd/mchat-created.json')


def run(*args,success=True,env=None):
    p=subprocess.run(args,capture_output=True,text=True,env=env)
    if (p.returncode==0)!=success:raise AssertionError(f'{args}: {p.returncode}\n{p.stdout}\n{p.stderr}')
    return p.stdout+p.stderr


def snapshot(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME)
    try:
        before=os.fstat(fd);data=b''
        while chunk:=os.read(fd,65536):data+=chunk
        after=os.fstat(fd);assert before==after
        return dict(sha256=hashlib.sha256(data).hexdigest(),inode=after.st_ino,
                    mtime_ns=after.st_mtime_ns,ctime_ns=after.st_ctime_ns,mode=after.st_mode,
                    uid=after.st_uid,gid=after.st_gid,nlink=after.st_nlink)
    finally:os.close(fd)


def fixture_package(name,protected=False):
    root=Path('/tmp/build')/name;control=root/'DEBIAN';control.mkdir(parents=True)
    (control/'control').write_text(f'Package: {name}\nVersion: 99.0\nArchitecture: all\nMaintainer: Fixture <fixture@example.invalid>\nDescription: Offline dependency fixture\n')
    if protected:
        (control/'control').write_text((control/'control').read_text().replace('99.0','1.0'))
        f=root/str(TARGET).lstrip('/');f.parent.mkdir(parents=True)
        f.write_text('MCHAT_APPNAME=fixture-app\nMCHAT_EINAME=fixture-edge\nMCHAT_DC=fixture-dc\nMCHAT_IOC=fixture-ioc\nMCHAT_MBGWIP=fixture.invalid:6262\nMCHAT_WATCHLEVEL=0\n');f.chmod(0o640)
        (control/'conffiles').write_text(str(TARGET)+'\n')
    deb=Path('/tmp')/(name+'-fixture.deb')
    run('dpkg-deb','--build','--root-owner-group',str(root),str(deb));return str(deb)


def classifier():
    source=(ROOT/'agent-sphere-apps.sh').read_text()
    start=source.index('classify_legacy_chatd() {')
    result=source[start:source.index('\n}\n',start)+3]
    start=source.index('classify_legacy_mcp() {')
    return result+source[start:source.index('\n}\n',start)+3]


def make_guard(expected):
    source=(ROOT/'agent-sphere-apps.sh').read_text()
    body=source.split("<<'GUARD'\n",1)[1].split('\nGUARD\n',1)[0]
    guard=Path('/tmp/guard');guard.write_text('#!/bin/bash\nset -euo pipefail\n'+classifier()+
                            f"expected_legacy_state='{expected}'\nexpected_mcp_state=absent\n"+body+'\n')
    guard.chmod(0o700);return guard


def setup():
    assert os.geteuid()==0 and Path('/.chatd-migration-fixture').is_file() and not TARGET.exists()
    Path('/etc/passwd').write_text('root:x:0:0:root:/root:/bin/sh\nmote-chatd:x:0:0:fixture:/var/lib/mote/mote-chatd:/usr/sbin/nologin\n')
    Path('/etc/group').write_text('root:x:0:\nmote-chatd:x:0:\n')
    for p in ('/etc/apt/sources.list.d','/etc/apt/apt.conf.d','/etc/apt/preferences.d',
              '/var/lib/apt/lists/partial','/var/cache/apt/archives/partial','/var/log/apt','/run/systemd/system'):
        Path(p).mkdir(parents=True,exist_ok=True)
    Path('/etc/apt/sources.list').touch();Path('/var/lib/dpkg/status').touch()
    run('dpkg','--install',*[fixture_package(n) for n in ('libc6','libgcc-s1','adduser','sphered')])


def inside(scenario):
    setup();os.environ['DEBIAN_FRONTEND']='noninteractive'
    if scenario=='protected-retention':run('dpkg','--install',fixture_package('mote-chatd',protected=True))
    run('dpkg','--install','/packages/old.deb')
    assert snapshot(TARGET)
    conffiles=run('dpkg-query','-W','-f=${Conffiles}','mote-chatd')
    assert (str(TARGET) in conffiles)==(scenario=='protected-retention')
    NORMAL.write_bytes(NORMAL.read_bytes()+b'# administrator fixture setting\n')
    JOURNAL.write_text('{"sequence":1,"message_id":"fixture-retained"}\n');JOURNAL.chmod(0o600)
    if scenario=='ordinary-residual':run('dpkg','--remove','mote-chatd')
    expected=run('bash','-c',classifier()+'\nclassify_legacy_chatd').strip()
    assert expected==('retention:installed' if scenario=='protected-retention' else
                      'ordinary:config-files' if scenario=='ordinary-residual' else 'ordinary:installed'),expected
    guard=make_guard(expected)
    runtime='/packages/runtime.deb'
    if scenario=='ownership-drift':
        # A real package operation changes ownership after preflight. No status
        # file editing: register an otherwise identical reviewed old package's
        # synthetic target as a conffile, then expect the lock-time guard to stop.
        tree=Path('/tmp/changed-old');run('dpkg-deb','-R','/packages/old.deb',str(tree))
        f=tree/str(TARGET).lstrip('/');f.write_bytes(TARGET.read_bytes());f.chmod(0o640)
        with (tree/'DEBIAN/conffiles').open('a') as out:out.write(str(TARGET)+'\n')
        changed=Path('/tmp/changed-old.deb');run('dpkg-deb','--build','--root-owner-group',str(tree),str(changed))
        run('dpkg','--force-confold','--install',str(changed))
    if scenario=='artifact-drift':
        tree=Path('/tmp/changed-runtime');run('dpkg-deb','-R',runtime,str(tree))
        (tree/'usr/share/doc/mote-transportd/artifact-fixture').write_text('changed fixture artifact\n')
        runtime='/tmp/changed-runtime.deb';run('dpkg-deb','--build','--root-owner-group',str(tree),runtime)
    before={str(p):snapshot(p) for p in (TARGET,NORMAL,JOURNAL,RECEIPT)}
    status=Path('/var/lib/dpkg/status').read_bytes()
    args=['apt-get','-y','-o','APT::Sandbox::User=root','-o','Dpkg::Options::=--force-confold',
          '-o',f'DPkg::Pre-Install-Pkgs::={guard}',
          '-o',f'DPkg::Tools::Options::{guard}::Version=3',
          '-o',f'DPkg::Tools::Options::{guard}::InfoFD=0','install',runtime]
    if scenario=='protected-retention':args.append('/packages/retention.deb')
    else:args.append('mote-chatd-')
    accepted=scenario in ('ordinary-installed','ordinary-residual','protected-retention')
    output=run(*args,success=accepted);Path('/tmp/apt.log').write_text(output)
    assert {str(p):snapshot(p) for p in (TARGET,NORMAL,JOURNAL,RECEIPT)}==before,'existing transport state metadata changed'
    if not accepted:
        assert Path('/var/lib/dpkg/status').read_bytes()==status,'guard allowed a DPKG mutation'
        assert ('ownership changed after preflight' if scenario=='ownership-drift' else 'transport artifact changed') in output,output
    else:
        assert run('dpkg-query','-W','-f=${Version} ${db:Status-Status}','mote-transportd')=='2.0.0-6 installed'
        assert run('dpkg-query','-S','/usr/sbin/mote-chatd').strip()=='mote-transportd: /usr/sbin/mote-chatd'
        assert Path('/tmp/active-mote-chatd.service').read_text()=='inactive'
        assert Path('/tmp/active-mote-transportd.service').read_text()=='active'
        assert not Path('/tmp/enabled-mote-chatd.service').exists()
        assert Path('/tmp/enabled-mote-transportd.service').exists()
        assert not run('dpkg','--audit').strip()
        replay_state=run('bash','-c',classifier()+'\nclassify_legacy_chatd').strip()
        make_guard(replay_state)
        replay=run(*args)
        assert {str(p):snapshot(p) for p in (TARGET,NORMAL,JOURNAL,RECEIPT)}==before,'repeat touched existing state'
        if scenario=='protected-retention':
            failure=run('dpkg','--purge','mote-chatd',success=False)
            assert 'owner migration required before removal' in failure
        else:
            # Standard obsolete-record purge must not delete new state/enablement.
            run('dpkg','--purge','mote-chatd')
            assert not Path('/lib/systemd/system/mote-chatd.service').exists()
            assert Path('/tmp/enabled-mote-transportd.service').exists()
        assert {str(p):snapshot(p) for p in (TARGET,NORMAL,JOURNAL,RECEIPT)}==before
    result={'scenario':scenario,'passed':True,'real_apt_dpkg':True,'systemd_mocked':True,
            'single_uid_fixture':True,'host_modified':False,'preserved':before}
    Path('/tmp/evidence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


def main():
    if sys.argv[1:2]==['--inside']:inside(sys.argv[2]);return
    parser=argparse.ArgumentParser(description=__doc__)
    for n in PINS:parser.add_argument('--'+n+'-deb',type=Path,required=True)
    args=parser.parse_args()
    for n,h in PINS.items():
        p=getattr(args,n+'_deb').resolve()
        with p.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==h,(n,'wrong released artifact')
    output=ROOT/'build/chatd-migration';output.mkdir(parents=True,exist_ok=True)
    for scenario in ('ordinary-installed','ordinary-residual','protected-retention','ownership-drift','artifact-drift'):
        with tempfile.TemporaryDirectory(prefix='chatd-',dir=output) as tmp:
            (Path(tmp)/'systemctl').write_text(SYSTEMCTL);(Path(tmp)/'systemctl').chmod(0o755)
            command=['bwrap','--unshare-all','--die-with-parent','--uid','0','--gid','0',
                '--tmpfs','/','--dir','/usr','--ro-bind','/usr/bin','/usr/bin',
                '--tmpfs','/usr/lib','--dir','/usr/lib/systemd',
                '--ro-bind','/usr/lib64','/usr/lib64','--symlink','usr/bin','/bin',
                '--symlink','usr/sbin','/sbin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
                '--tmpfs','/usr/sbin','--ro-bind','/usr/sbin/ldconfig','/usr/sbin/ldconfig',
                '--ro-bind','/usr/sbin/start-stop-daemon','/usr/sbin/start-stop-daemon',
                '--tmpfs','/usr/share','--ro-bind','/usr/share/dpkg','/usr/share/dpkg',
                '--ro-bind','/usr/share/perl5','/usr/share/perl5','--ro-bind','/usr/share/perl','/usr/share/perl',
                '--dir','/etc','--dir','/var/lib/dpkg','--dir','/run','--proc','/proc','--dev','/dev',
                '--ro-bind',str(ROOT),'/source','--ro-bind',str(Path(tmp)/'systemctl'),'/usr/bin/systemctl',
                '--dir','/packages','--bind',tmp,'/tmp','--setenv','TMPDIR','/tmp',
                '--setenv','PATH','/usr/bin:/bin:/usr/sbin:/sbin','--setenv','PYTHONDONTWRITEBYTECODE','1']
            for library in Path('/usr/lib').iterdir():
                if library.name!='systemd':command+=['--ro-bind',str(library),str(library)]
            for n in PINS:command+=['--ro-bind',str(getattr(args,n+'_deb').resolve()),'/packages/'+n+'.deb']
            command+=['--chdir','/tmp','/bin/sh','-eu','-c',
                      'touch /.chatd-migration-fixture; python3 /source/scripts/check-chatd-migration.py --inside "$1"','sh',scenario]
            print(run(*command))
            for name in ('evidence.json','apt.log'):shutil.copyfile(Path(tmp)/name,output/(scenario+'-'+name))

SYSTEMCTL=r'''#!/bin/sh
set -eu
printf '%s\n' "$*" >> /tmp/systemctl-calls
unit=''
for arg in "$@"; do case "$arg" in *.service) unit="$arg" ;; esac; done
case "$unit" in ''|mote-chatd.service|mote-transportd.service) ;; *) exit 98 ;; esac
case " $* " in
 *' show '*) printf 'LoadState=loaded\nActiveState=%s\n' "$(cat /tmp/active-${unit} 2>/dev/null || printf inactive)" ;;
 *' is-enabled '*) test -e "/tmp/enabled-${unit}" ;;
 *' is-active '*) test "$(cat /tmp/active-${unit} 2>/dev/null || printf inactive)" = active ;;
 *' stop '*) printf inactive > "/tmp/active-${unit}" ;;
 *' disable '*) rm -f "/tmp/enabled-${unit}" ;;
 *' enable '*) touch "/tmp/enabled-${unit}" ;;
 *' start '*|*' restart '*|*' try-restart '*) printf active > "/tmp/active-${unit}" ;;
 *' daemon-reload '*) : ;;
 *) echo 'unexpected systemctl fixture call' >&2;exit 98 ;;
esac
'''

if __name__=='__main__':main()
