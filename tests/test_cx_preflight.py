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
   if name=='codex-mesh':continue
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
if __name__=='__main__':unittest.main(verbosity=2)
