"""Exact embedded CX state classification; no host identity or DPKG writes."""
import subprocess,types,unittest
from pathlib import Path
from unittest import mock
SOURCE=(Path(__file__).resolve().parents[1]/'agent-sphere-apps.sh').read_text()
CODE=SOURCE.split("python3 - <<'CX_PREFLIGHT'\n",1)[1].split('\nCX_PREFLIGHT\n',1)[0]
module=types.ModuleType('embedded_cx_preflight');exec(compile(CODE,'embedded_cx_preflight','exec'),module.__dict__)
class CxPreflightTests(unittest.TestCase):
 def setUp(self):
  self.records={'cx-agent':'0.3.4-2\namd64\ninstall ok installed\n','codex-mesh':'1.0.0-1\namd64\ninstall ok installed\n'+'\n'.join(' '+p+' '+v for p,v in module.MESH_FILES.items())}
  self.files=[];self.fingerprint='stable'
  def checked(path,**kwargs):self.files.append((path,kwargs));return [path,self.fingerprint]
  self.inspect=mock.patch.object(module,'checked',side_effect=checked);self.inspect.start();self.addCleanup(self.inspect.stop)
  self.query=mock.patch.object(module,'query',side_effect=lambda name:self.records.get(name));self.query.start();self.addCleanup(self.query.stop)
  self.units=mock.patch.object(module,'unit_policy',return_value={});self.units.start();self.addCleanup(self.units.stop)
  self.exists=mock.patch.object(module.os.path,'lexists',side_effect=lambda p:p in ('/etc/cx-node/cx-node.toml','/etc/cx-node/cx-node-mchat.env'));self.exists.start();self.addCleanup(self.exists.stop)
 def test_reviewed_two_package_merge_binds_hooks_config_and_state(self):
  first=module.classify();self.assertTrue(first.startswith('cx-node=-,cx-agent=0.3.4-2,codex-mesh=1.0.0-1;sha256:'))
  self.assertIn(('/var/lib/dpkg/info/cx-agent.prerm',{'digest':'145f52a16184feb342a77090805af0dabab4230b6e030d8f83349484e9868fdd','mode':0o755}),self.files)
  self.assertIn(('/etc/cx-node/cx-node-mchat.env',{}),self.files)
  self.fingerprint='changed';self.assertNotEqual(module.classify(),first)
 def test_all_reviewed_cx_predecessors_are_narrow(self):
  for name,version in module.REVIEWED:
   if name=='codex-mesh' or version in ('0.3.3-1','0.3.3-4'):continue
   self.records={name:version+'\namd64\ninstall ok installed\n'}
   self.assertIn(name+'='+version+';',module.classify().replace(',codex-mesh=-','').replace(',cx-agent=-','')) if name=='cx-agent' else self.assertIn(name+'='+version,module.classify())
 def test_unknown_versions_partial_states_and_conffiles_are_rejected(self):
  initial=self.records['cx-agent']
  for altered in (initial.replace('0.3.4-2','0.3.4-99'),initial.replace('amd64','all'),initial.replace('installed','unpacked'),initial+' /etc/cx-node/cx-node-mchat.env '+'a'*32):
   self.records['cx-agent']=altered
   with self.assertRaises(ValueError):module.classify()
 def test_residual_mesh_needs_exact_sole_successor_ownership(self):
  self.records={'cx-agent':'0.3.4-2\namd64\ndeinstall ok config-files\n','codex-mesh':'1.0.0-1\namd64\ndeinstall ok config-files\n'+'\n'.join(' '+p+' '+v+' obsolete' for p,v in module.MESH_FILES.items())}
  with self.assertRaisesRegex(ValueError,'exact installed successor'):module.classify()
  self.records['cx-mesh']='1.1.0-1\namd64\ninstall ok installed\n'
  with mock.patch.object(module.subprocess,'run',side_effect=lambda args,**kwargs:subprocess.CompletedProcess(args,0,'cx-mesh: '+args[-1],'')):
   self.assertTrue(module.classify().startswith('cx-node=-,cx-agent=-,codex-mesh=-;'))
  with mock.patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'codex-mesh: wrong','')):
   with self.assertRaisesRegex(ValueError,'sole successor'):module.classify()
 def test_custom_unit_or_changed_hook_is_not_hidden_by_version(self):
  with mock.patch.object(module,'unit_policy',side_effect=ValueError('custom predecessor unit')):
   with self.assertRaisesRegex(ValueError,'custom predecessor'):module.classify()
  with mock.patch.object(module,'checked',side_effect=ValueError('unreviewed CX removal hook')):
   with self.assertRaisesRegex(ValueError,'unreviewed CX'):module.classify()
 def test_new_mesh_cleanup_hook_is_rejected(self):
  with mock.patch.object(module.os.path,'lexists',return_value=True):
   with self.assertRaisesRegex(ValueError,'unexpected Mesh cleanup'):module.classify()
 def test_absent_predecessors_do_not_require_removed_config(self):
  self.records={};self.assertEqual(module.classify(),'absent');self.assertEqual(self.files,[])
class QueryTests(unittest.TestCase):
 def test_only_exact_empty_relationship_record_is_absent(self):
  with mock.patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'\n\nunknown ok not-installed\n','')):
   self.assertIsNone(module.query('cx-node'))
  for record in ('0.3.3-6\n\nunknown ok not-installed\n','\namd64\nunknown ok not-installed\n','\n\ninstall ok not-installed\n','\n\nunknown ok not-installed\n /etc/owned '+ 'a'*32):
   with mock.patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,record,'')):
    self.assertEqual(module.query('cx-node'),record)
class Cx6ObsoleteTests(unittest.TestCase):
 version="0.3.3-6"
 installed_checks=module.CX6_OBSOLETE_INSTALLED
 def setUp(self):
  self.record=self.version+'\namd64\ninstall ok installed\n '+' '.join(module.CX6_OBSOLETE_ROW)
  self.records={'cx-node':self.record};self.seen=[];self.fingerprint='stable'
  def checked(path,**kwargs):self.seen.append((path,kwargs));return [kwargs.get('digest',self.fingerprint),1,1,1,0o100644,0,0,1]
  for name,replacement in [('checked',checked),('query',lambda name:self.records.get(name)),('unit_policy',lambda:{})]:
   patch=mock.patch.object(module,name,side_effect=replacement);patch.start();self.addCleanup(patch.stop)
  self.directory=types.SimpleNamespace(st_dev=1,st_ino=1,st_mtime_ns=1,st_ctime_ns=1,st_mode=0o40750,st_uid=0,st_gid=0,st_nlink=1)
  for target,name,value in [(module.os.path,'lexists',False),(module.os,'lstat',self.directory),(module.pwd,'getpwnam',types.SimpleNamespace(pw_uid=123))]:
   patch=mock.patch.object(target,name,return_value=value);patch.start();self.addCleanup(patch.stop)
  self.drain=mock.patch.object(module,'cx6_drain_state');self.drain.start();self.addCleanup(self.drain.stop)
  self.run=mock.patch.object(module.subprocess,'run',side_effect=self.commands);self.run.start();self.addCleanup(self.run.stop)
 def commands(self,args,**kwargs):
  owner='cx-mesh' if args[-1]=='/usr/bin/cx' and 'deinstall' in self.records['cx-node'] else 'cx-node'
  return subprocess.CompletedProcess(args,0,owner+': '+args[-1]+'\n' if args[0]=='dpkg-query' else '', '')
 def test_exact_installed_obsolete_binds_list_drain_hooks_identity_and_receipt(self):
  first=module.classify();self.assertIn('cx-node='+self.version,first)
  paths={p for p,_ in self.seen}
  self.assertTrue(set(self.installed_checks)<=paths)
  for path in ['/etc/cx-node/cx-node.toml','/etc/cx-node/cx-node-mchat.env','/var/lib/cx-node/state/runtime-migration.json','/var/lib/dpkg/info/cx-node.prerm','/var/lib/dpkg/info/cx-node.postrm']:self.assertIn(path,paths)
  self.fingerprint='changed';self.assertNotEqual(module.classify(),first)
 def test_only_exact_obsolete_record_and_old6_version_are_accepted(self):
  for changed in [self.record.replace(' obsolete',''),self.record.replace('d137b03f7f14c9c1369d3e85a9062130','a'*32),self.record.replace(self.version,'0.3.3-4'),self.record.replace('cx-node.toml','cx-node-mchat.env'),self.record+'\n '+ ' '.join(module.CX6_OBSOLETE_ROW),self.record+'\n /etc/foreign '+'a'*32+' obsolete']:
   with self.subTest(record=changed):
    self.records={'cx-node':changed}
    with self.assertRaisesRegex(ValueError,'conffile ownership'):module.classify()
 def test_native_residual_keeps_old_conffile_owner_but_needs_exact_successor(self):
  self.records={'cx-node':self.record.replace('install ok installed','deinstall ok config-files')}
  with self.assertRaisesRegex(ValueError,'exact installed'):module.classify()
  self.records['cx-mesh']='1.1.0-1\namd64\ninstall ok installed\n'
  self.assertIn('cx-node=-',module.classify())
  self.assertIn(('/var/lib/dpkg/info/cx-node.list',{'digest':module.CX6_OBSOLETE_RESIDUAL_LIST,'mode':0o644,'limit':1048576}),self.seen)
  self.assertFalse(any(p=='/var/lib/dpkg/info/cx-node.prerm' for p,_ in self.seen))
  with mock.patch.object(module.os.path,'lexists',side_effect=lambda p:p.endswith('.prerm')):
   with self.assertRaisesRegex(ValueError,'residual payload'):module.classify()
 def test_ambiguous_owner_diversion_changed_hook_and_extra_ownership_are_denied(self):
  for owner in ['cx-mesh: /etc/cx-node/cx-node.toml','cx-node, other: /etc/cx-node/cx-node.toml','']:
   with mock.patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,owner,'')):
    with self.assertRaisesRegex(ValueError,'sole expected'):module.classify()
  with mock.patch.object(module.subprocess,'run',side_effect=lambda args,**kw:subprocess.CompletedProcess(args,0,'diverted' if args[0]=='dpkg-divert' else 'cx-node: '+args[-1],'')):
   with self.assertRaisesRegex(ValueError,'diverted'):module.classify()
  with mock.patch.object(module.os.path,'lexists',side_effect=lambda p:p.endswith('.conffiles') or p.endswith('.triggers')):
   with self.assertRaisesRegex(ValueError,'ownership or triggers'):module.classify()
  with mock.patch.object(module,'checked',side_effect=ValueError('changed hook')):
   with self.assertRaisesRegex(ValueError,'changed hook'):module.classify()
 def test_unsafe_identity_and_parent_paths_fail_before_removal(self):
  with mock.patch.object(module,'checked',return_value=['sha',1,1,1,0o100644,0,0,2]):
   with self.assertRaisesRegex(ValueError,'link count'):module.classify()
  self.directory.st_mode=0o120777
  with self.assertRaisesRegex(ValueError,'configuration directory'):module.classify()
 def test_no_conffile_old6_retains_existing_path(self):
  self.records={'cx-node':'0.3.3-6\namd64\ninstall ok installed\n'}
  with mock.patch.object(module,'cx6_obsolete_state',side_effect=AssertionError('unnecessary obsolete path')):self.assertIn('cx-node=0.3.3-6',module.classify())
class Cx1ObsoleteTests(Cx6ObsoleteTests):
 version="0.3.3-1"
 installed_checks=module.CX1_OBSOLETE_INSTALLED
 def test_no_conffile_old6_retains_existing_path(self):
  self.records={'cx-node':self.version+'\namd64\ninstall ok installed\n'}
  with self.assertRaisesRegex(ValueError,'obsolete conffile'):module.classify()
 def test_exact_old1_cleanup_hooks_are_required(self):
  module.classify()
  self.assertIn(('/var/lib/dpkg/info/cx-node.prerm',{'digest':'6f8bd5bdd9cd01e2ac11e5eccd3806ec8cf0550702b219ad2fb34f96eb650cd4','mode':0o755}),self.seen)
  self.assertIn(('/var/lib/dpkg/info/cx-node.postrm',{'digest':'70a40e034e0dbed5e29954a848a85541eb648907096da632d4943ce91fbd8cdc','mode':0o755}),self.seen)
class Cx4Tests(unittest.TestCase):
 def setUp(self):
  self.files={};self.seen=[]
  def checked(path,**kwargs):self.seen.append((path,kwargs));return [kwargs.get('digest','fixture'),1,1,1,0o100644,0,0,1]
  self.inspect=mock.patch.object(module,'checked',side_effect=checked);self.inspect.start();self.addCleanup(self.inspect.stop)
  self.exists=mock.patch.object(module.os.path,'lexists',return_value=False);self.exists.start();self.addCleanup(self.exists.stop)
  self.account=mock.patch.object(module.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=123));self.account.start();self.addCleanup(self.account.stop)
 def commands(self,owner):
  return mock.patch.object(module.subprocess,'run',side_effect=lambda args,**kwargs:subprocess.CompletedProcess(args,0,owner+'\n' if args[0]=='dpkg-query' else '', ''))
 def test_installed_exact_list_binary_and_receipt_are_bound(self):
  with self.commands('cx-node: /usr/bin/cx'):module.cx4_state('install ok installed',self.files)
  self.assertIn('/var/lib/dpkg/info/cx-node.list',self.files)
  self.assertIn('/usr/bin/cx',self.files)
  self.assertIn(('/var/lib/cx-node/state/runtime-migration.json',{'uid':123}),self.seen)
 def test_changed_file_missing_receipt_and_extra_ownership_fail(self):
  with self.commands('cx-node: /usr/bin/cx'),mock.patch.object(module,'checked',side_effect=ValueError('changed')):
   with self.assertRaises(ValueError):module.cx4_state('install ok installed',self.files)
  with mock.patch.object(module.os.path,'lexists',return_value=True):
   with self.assertRaisesRegex(ValueError,'ownership or triggers'):module.cx4_state('install ok installed',self.files)
  with self.commands('other: /usr/bin/cx'):
   with self.assertRaisesRegex(ValueError,'sole expected'):module.cx4_state('install ok installed',self.files)
 def test_residual_requires_exact_successor_and_reduced_list(self):
  with mock.patch.object(module,'query',return_value=None):
   with self.assertRaisesRegex(ValueError,'exact installed'):module.cx4_state('deinstall ok config-files',self.files)
  with mock.patch.object(module,'query',return_value='1.1.0-1\namd64\ninstall ok installed\n'),self.commands('cx-mesh: /usr/bin/cx'):
   module.cx4_state('deinstall ok config-files',self.files)
  self.assertEqual(self.files['/var/lib/dpkg/info/cx-node.list'][0],module.CX4_RESIDUAL_LIST)
  self.assertNotIn('/usr/bin/cx',self.files)
if __name__=='__main__':unittest.main(verbosity=2)
