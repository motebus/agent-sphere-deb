"""Exercise the exact Manager classifier without reading host configuration."""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import types
import unittest
from unittest import mock

SOURCE=(Path(__file__).resolve().parents[1]/'agpc.sh').read_text()
CODE=SOURCE.split("python3 - <<'MANAGER_PREFLIGHT'\n",1)[1].split('\nMANAGER_PREFLIGHT\n',1)[0]
module=types.ModuleType('embedded_manager_preflight')
exec(compile(CODE,'embedded_manager_preflight','exec'),module.__dict__)


def metadata(mode=stat.S_IFLNK|0o777,uid=0,gid=0,ino=1,nlink=1,size=14):
    return types.SimpleNamespace(st_dev=1,st_ino=ino,st_size=size,st_mode=mode,
        st_uid=uid,st_gid=gid,st_nlink=nlink,st_mtime_ns=1,st_ctime_ns=1)


class ManagerPreflightTests(unittest.TestCase):
    def setUp(self):
        self.record='3.1.0-1|amd64|install ok installed|'
        self.query_code=0;self.owner='sphere-manager';self.link='sphere-manager'
        self.meta=metadata();self.inspected=[];self.changed=False
        def query(args,**kwargs):
            if '-S' in args:return subprocess.CompletedProcess(args,0,self.owner+': '+args[-1]+'\n','')
            return subprocess.CompletedProcess(args,self.query_code,self.record,'')
        def checked(path,mode,digest):
            self.inspected.append((path,mode,digest))
            return ('changed' if self.changed else digest,('fixture',path))
        for patch in (mock.patch.object(module.subprocess,'run',side_effect=query),
                      mock.patch.object(module,'checked',side_effect=checked),
                      mock.patch.object(module.os.path,'lexists',return_value=False),
                      mock.patch.object(module.os,'lstat',side_effect=lambda path:self.meta),
                      mock.patch.object(module.os,'readlink',side_effect=lambda path:self.link)):
            patch.start();self.addCleanup(patch.stop)

    def test_exact_clean_record_pins_native_files_and_fingerprints_changes(self):
        first=module.classify();self.assertRegex(first,r'^installed:sha256:[a-f0-9]{64}$')
        self.assertEqual(self.inspected,[
            ('/usr/bin/sphere-manager',0o755,'85bb3fb568b30fbbcdbae1ddc04ace65e9a3c64e27577b56b6d147d59b2d5b42'),
            ('/var/lib/dpkg/info/sphere-manager.md5sums',0o644,'92be0d236d0be35a9946b0be1e15d762d47758de3af305512be1ab38aa73a8b2')])
        self.changed=True;self.assertNotEqual(module.classify(),first)
        self.changed=False;self.meta=metadata(ino=2);self.assertNotEqual(module.classify(),first)

    def test_only_missing_or_exact_empty_relationship_state_is_absent(self):
        self.query_code=1;self.record='';self.assertEqual(module.classify(),'absent')
        self.query_code=0;self.record='||unknown ok not-installed|';self.assertEqual(module.classify(),'absent')
        self.assertEqual(self.inspected,[])
        for code,record in ((2,''),(1,'unexpected'),(0,'||install ok not-installed|'),
                            (0,'3.1.0-1||unknown ok not-installed|'),(0,'|amd64|unknown ok not-installed|')):
            with self.subTest(code=code,record=record):
                self.query_code=code;self.record=record
                with self.assertRaises(ValueError):module.classify()

    def test_old_versions_partial_or_residual_records_and_conffiles_are_refused(self):
        original=self.record
        for record in (original.replace('3.1.0-1','3.1.0-2'),original.replace('amd64','all'),
                       original.replace('install ok installed','install ok unpacked'),
                       original.replace('install ok installed','deinstall ok config-files'),
                       original+' /etc/owner-config '+32*'a'):
            self.record=record
            with self.assertRaises(ValueError):module.classify()
        self.assertEqual(self.inspected,[])

    def test_any_new_hook_conffile_or_service_override_is_refused_before_files(self):
        paths=[module.INFO+name for name in ('preinst','postinst','prerm','postrm','conffiles')]
        paths += [directory+'/sphere-manager'+suffix for directory in
                  ('/etc/systemd/system','/run/systemd/system','/usr/lib/systemd/system','/lib/systemd/system')
                  for suffix in ('.service','.service.d')]
        for path in paths:
            with self.subTest(path=path),mock.patch.object(module.os.path,'lexists',side_effect=lambda candidate:candidate==path):
                with self.assertRaises(ValueError):module.classify()
        self.assertEqual(self.inspected,[])

    def test_foreign_or_ambiguous_ownership_and_changed_shortcut_are_refused(self):
        for owner in ('owner-other','sphere-manager, owner-other','local diversion'):
            self.owner=owner
            with self.assertRaisesRegex(ValueError,'sole package ownership'):module.classify()
        self.owner='sphere-manager';self.link='owner-custom'
        with self.assertRaisesRegex(ValueError,'shortcut'):module.classify()
        self.link='sphere-manager'
        for value in (metadata(uid=1000),metadata(gid=1000),metadata(mode=stat.S_IFREG|0o755)):
            self.meta=value
            with self.assertRaisesRegex(ValueError,'shortcut'):module.classify()


class ManagerFileTests(unittest.TestCase):
    def test_unsafe_file_metadata_never_opens_payload(self):
        for value in (metadata(mode=stat.S_IFREG|0o777),metadata(mode=stat.S_IFLNK|0o777),
                      metadata(mode=stat.S_IFREG|0o755,uid=1000),metadata(mode=stat.S_IFREG|0o755,gid=1000),
                      metadata(mode=stat.S_IFREG|0o755,nlink=2),metadata(mode=stat.S_IFREG|0o755,size=1048577)):
            with mock.patch.object(module.os,'lstat',return_value=value),mock.patch.object(module.os,'open') as opened:
                with self.assertRaisesRegex(ValueError,'unsafe'):module.checked('/fixture',0o755,'unused')
                opened.assert_not_called()

    def test_real_file_digest_and_no_metadata_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'public-fixture';path.write_bytes(b'reviewed public fixture');path.chmod(0o755)
            original=os.stat(path);real_lstat=os.lstat;real_fstat=os.fstat
            def root_metadata(value):
                fields={name:getattr(value,name) for name in ('st_dev','st_ino','st_size','st_mode','st_uid','st_gid','st_nlink','st_mtime_ns','st_ctime_ns')}
                fields.update(st_uid=0,st_gid=0);return types.SimpleNamespace(**fields)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with mock.patch.object(module.os,'lstat',side_effect=lambda p:root_metadata(real_lstat(p))),mock.patch.object(module.os,'fstat',side_effect=lambda fd:root_metadata(real_fstat(fd))):
                self.assertEqual(module.checked(str(path),0o755,digest)[0],digest)
                with self.assertRaisesRegex(ValueError,'differs'):module.checked(str(path),0o755,'0'*64)
            after=os.stat(path)
            for field in ('st_ino','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_gid','st_nlink'):
                self.assertEqual(getattr(original,field),getattr(after,field))


if __name__=='__main__':unittest.main()
