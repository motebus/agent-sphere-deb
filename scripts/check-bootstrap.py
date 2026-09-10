#!/usr/bin/env python3
"""Exercise the exact embedded bootstrap in a root-mapped private namespace."""
import json,os,pathlib,shutil,subprocess,sys,tempfile
os.umask(0o022)
ROOT=pathlib.Path(__file__).resolve().parents[1]
source=(ROOT/'agpc.sh').read_text()
fragment=source.split('# BEGIN SIGNED BOOTSTRAP\n',1)[1].split('# END SIGNED BOOTSTRAP\n',1)[0]
with tempfile.TemporaryDirectory(prefix='agpc-bootstrap-') as tmp:
 root=pathlib.Path(tmp)
 # Public fixture inputs must be traversable after namespace capability drop.
 root.chmod(0o755)
 fixture=root/'fixture';fixture.mkdir()
 (fixture/'parent-namespaces.json').write_text(json.dumps({name:os.readlink('/proc/self/ns/'+name) for name in ('user','net','mnt')}))
 (fixture/'agentsphere-bootstrap.sh').write_text(fragment)
 shutil.copyfile(ROOT/'tests/fixtures/bootstrap-fixture.py',fixture/'test-bootstrap.py')
 shutil.copyfile(ROOT/'tests/fixtures/medge-archive-keyring.gpg',fixture/'key.gpg')
 (fixture/'medge.sources').write_text('Types: deb\nURIs: https://motebus.github.io/download\nSuites: stable\nComponents: main\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/medge-archive-keyring.gpg\n')
 for name in ['bin','missing-gpg','arm-bin']:(fixture/name).mkdir()
 (fixture/'arm-bin/dpkg').write_text('#!/bin/sh\ntest "$1" = --print-architecture\nprintf "arm64\\n"\n');(fixture/'arm-bin/dpkg').chmod(0o755)
 (fixture/'bin/curl').write_text('''#!/usr/bin/python3
import os,pathlib,sys
args=sys.argv[1:]
assert args[-1]=='https://motebus.github.io/download/medge-archive-keyring.gpg'
assert args[args.index('--proto')+1]=='=https' and args[args.index('--proto-redir')+1]=='=https'
assert args[args.index('--max-filesize')+1]=='131072'
pathlib.Path('/tmp/curl-log').write_text('reviewed-fixed-key-download\\n')
pathlib.Path(args[args.index('--output')+1]).write_bytes(b'bad' if os.environ.get('BAD_KEY') else pathlib.Path('/fixture/key.gpg').read_bytes())
''');(fixture/'bin/curl').chmod(0o755)
 for name in ['apt-get','curl','sha256sum','dpkg','dpkg-deb','dpkg-query','mktemp','chmod','realpath','stat','python3']:(fixture/'missing-gpg'/name).symlink_to('/usr/bin/'+name)
 command=['bwrap','--unshare-all','--unshare-user','--new-session','--die-with-parent','--uid','0','--gid','0','--cap-drop','ALL','--clearenv','--tmpfs','/','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/sbin','/sbin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--ro-bind-data','0','/usr/lib/os-release','--dir','/etc','--dir','/tmp','--dir','/var/tmp','--dir','/root','--proc','/proc','--dev','/dev','--ro-bind',str(fixture),'/fixture','--setenv','PATH','/usr/bin:/bin','--chdir','/tmp','/bin/sh','-eu','-c','touch /.bootstrap-fixture; python3 /fixture/test-bootstrap.py']
 # Ubuntu CI can require privileged namespace creation. Only the fixed bwrap
 # command runs through sudo; the child drops all capabilities and receives no
 # writable host mounts. No host security policy is changed.
 privilege=os.environ.get('AGPC_BOOTSTRAP_NAMESPACE_SUDO','0')
 if privilege not in ('0','1'):raise SystemExit('invalid namespace privilege setting')
 if privilege=='1':command=['sudo','-n','--',*command]
 # stdin becomes a private root-owned read-only file, independent of host UID.
 completed=subprocess.run(command,input='ID=ubuntu\nVERSION_ID="24.04"\n',capture_output=True,text=True)
 if completed.returncode:
  sys.stderr.write(completed.stderr)
  completed.check_returncode()
 result=json.loads(completed.stdout);assert result['ok'] and len(result['checks'])==14
 assert result['isolation']=={'private_user_network_mount_namespaces':True,'effective_capabilities':0}
 print(json.dumps(result))
