import pathlib,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Bootstrap(unittest.TestCase):
 def test_exact_embedded_bootstrap_in_private_namespace(self):
  subprocess.run(['python3',str(ROOT/'scripts/check-bootstrap.py')],check=True)
 def test_canonical_alias_and_mutation_order(self):
  canonical=(ROOT/'agpc.sh').read_bytes()
  self.assertEqual(canonical,(ROOT/'agent-sphere-apps.sh').read_bytes())
  text=canonical.decode()
  platform=text.index("\nagentsphere_platform_check || fail")
  guards=[text.index('\n'+name+'=$(classify_legacy_') for name in ['legacy_state','mcp_state','cx_state']]
  bootstrap=text.index("\nagentsphere_apt_bootstrap || fail")
  self.assertTrue(platform<min(guards) and max(guards)<bootstrap<text.index('\nobsidian='))
  self.assertNotIn('agentsphere_launch_manager',text)
  self.assertLess(text.index('\napt-get -o '),text.index("\nprintf '%s\\n' 'Use sphere-manager"))
  self.assertNotIn('aipc.sh',text)
