#!/usr/bin/python3
"""Real APT/DPKG and Debian unit-helper state; no live systemd or Codex calls.
Single mapped UID: service account is fixture UID0, not real identity acceptance.
"""
import hashlib,json,os,subprocess,sys
from pathlib import Path
CONFIG=Path('/etc/cx-node/cx-node.toml');MCHAT=CONFIG.with_name('cx-node-mchat.env')
def run(*args,ok=True):
 p=subprocess.run(args,text=True,capture_output=True)
 assert (p.returncode==0)==ok,(args,p.returncode,p.stdout,p.stderr)
 return p.stdout+p.stderr

def fingerprint(path):
 fd=os.open(path,os.O_RDONLY|os.O_NOATIME|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);h=hashlib.sha256()
  while block:=os.read(fd,65536):h.update(block)
  assert st==os.fstat(fd)
  return dict(sha256=h.hexdigest(),inode=st.st_ino,mtime=st.st_mtime_ns,ctime=st.st_ctime_ns,mode=st.st_mode,uid=st.st_uid,gid=st.st_gid,nlink=st.st_nlink)
 finally:os.close(fd)

def dummy(name,depends=''):
 root=Path('/tmp/build')/name;(root/'DEBIAN').mkdir(parents=True)
 (root/'DEBIAN/control').write_text(f'Package: {name}\nVersion: 99.0\nArchitecture: all\nMaintainer: Fixture <fixture@example.invalid>\nDescription: Isolated dependency fixture\n'+(f'Depends: {depends}\n' if depends else ''))
 doc=root/'usr/share/doc'/name/'fixture';doc.parent.mkdir(parents=True);doc.write_text('fixture\n')
 dest=Path('/tmp')/(name+'.deb');run('dpkg-deb','--build','--root-owner-group',str(root),str(dest));return str(dest)
def apt(*paths):return run('apt-get','-o','APT::Sandbox::User=root','-y','install',*paths)
def installed(name):
 p=subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}',name],text=True,capture_output=True)
 return p.stdout.strip()=='installed'
