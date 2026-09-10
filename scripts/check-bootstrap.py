#!/usr/bin/env python3
"""Exercise the exact embedded bootstrap in a root-mapped private namespace."""
import json,os,pathlib,shutil,subprocess,tempfile
os.umask(0o022)
ROOT=pathlib.Path(__file__).resolve().parents[1]
source=(ROOT/'agpc.sh').read_text()
fragment=source.split('# BEGIN SIGNED BOOTSTRAP\n',1)[1].split('# END SIGNED BOOTSTRAP\n',1)[0]
with tempfile.TemporaryDirectory(prefix='agpc-bootstrap-') as tmp:
 root=pathlib.Path(tmp);fixture=root/'fixture';fixture.mkdir();evidence=root/'evidence';evidence.mkdir()
 (fixture/'agentsphere-bootstrap.sh').write_text(fragment)
 shutil.copyfile(ROOT/'tests/fixtures/bootstrap-fixture.py',fixture/'test-bootstrap.py')
 shutil.copyfile(ROOT/'tests/fixtures/medge-archive-keyring.gpg',fixture/'key.gpg')
 (fixture/'medge.sources').write_text('Types: deb\nURIs: https://motebus.github.io/download\nSuites: stable\nComponents: main\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/medge-archive-keyring.gpg\n')
 (fixture/'os-release').write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
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
 command=['bwrap','--unshare-all','--new-session','--die-with-parent','--uid','0','--gid','0','--cap-drop','ALL','--clearenv','--tmpfs','/','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/sbin','/sbin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--ro-bind',str(fixture/'os-release'),'/usr/lib/os-release','--dir','/etc','--dir','/tmp','--dir','/var/tmp','--dir','/root','--proc','/proc','--dev','/dev','--ro-bind',str(fixture),'/fixture','--bind',str(evidence),'/evidence','--setenv','PATH','/usr/bin:/bin','--chdir','/tmp','/bin/sh','-eu','-c','touch /.bootstrap-fixture; python3 /fixture/test-bootstrap.py']
 subprocess.run(command,check=True)
 result=json.loads((evidence/'result.json').read_text());assert result['ok'] and len(result['checks'])==15
 print(json.dumps(result))
