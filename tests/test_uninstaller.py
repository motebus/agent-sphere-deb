from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'uninstall.sh'

class UninstallerTests(unittest.TestCase):
    def test_help_describes_preservation_boundary(self):
        result=subprocess.run(['bash',str(SCRIPT),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('preserving configuration',result.stdout)
        self.assertIn('never purges packages',result.stdout)

    def test_unknown_argument_stops_before_mutation(self):
        result=subprocess.run(['bash',str(SCRIPT),'--unknown'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('Unknown argument',result.stderr)

    def test_script_has_no_purge_or_autoremove_transaction(self):
        text=SCRIPT.read_text()
        self.assertIn('apt-get --yes remove',text)
        self.assertNotIn('apt-get --yes purge',text)
        self.assertNotIn('apt-get --yes autoremove',text)
        self.assertIn('Refusing removal of non-AGPC package',text)

if __name__=='__main__':unittest.main()
