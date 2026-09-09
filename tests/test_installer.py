import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "agent-sphere-apps.sh"
BASH = shutil.which("bash")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "apt-calls.jsonl"
        self.env = dict(os.environ, PATH=str(self.bin), APT_TEST_LOG=str(self.log))
        self.env.pop("APT_TEST_FAIL", None)
        self.env.pop("APT_TEST_UID", None)
        self.write_fake("id", """
import os
import sys
assert sys.argv[1:] == ['-u']
print(os.environ.get('APT_TEST_UID', '0'))
""")
        self.write_fake("apt-get", """
import json
import os
import sys
args = sys.argv[1:]
with open(os.environ['APT_TEST_LOG'], 'a') as out:
    out.write(json.dumps(args) + '\\n')
stage = 'update' if args == ['update'] else 'simulate' if '--simulate' in args else 'install'
sys.exit(42 if os.environ.get('APT_TEST_FAIL') == stage else 0)
""")

    def write_fake(self, name, body):
        target = self.bin / name
        target.write_text(f"#!{sys.executable}\n{body}")
        target.chmod(0o755)

    def run_installer(self, *args):
        return subprocess.run(
            [BASH, str(INSTALLER), *args],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_default_keeps_apt_confirmation_and_installs_both(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [
            ["update"],
            ["--simulate", "--no-remove", "install", "agent-sphere", "agent-apps"],
            ["--no-remove", "install", "agent-sphere", "agent-apps"],
        ])

    def test_yes_requires_explicit_flag(self):
        result = self.run_installer("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1],
                         ["--no-remove", "--yes", "install", "agent-sphere", "agent-apps"])
        self.assertNotIn("--yes", self.calls()[1])

    def test_failed_preflight_never_starts_package_installation(self):
        self.env["APT_TEST_FAIL"] = "simulate"
        result = self.run_installer("--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 2)
        self.assertIn("--simulate", self.calls()[-1])
        self.assertIn("Package installation was not started", result.stderr)

    def test_failed_update_stops_before_preflight(self):
        self.env["APT_TEST_FAIL"] = "update"
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [["update"]])

    def test_install_failure_is_returned_without_fallback(self):
        self.env["APT_TEST_FAIL"] = "install"
        result = self.run_installer()
        self.assertEqual(result.returncode, 42)
        self.assertEqual(len(self.calls()), 3)

    def test_non_root_is_rejected_without_apt(self):
        self.env["APT_TEST_UID"] = "1000"
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("root", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_unknown_arguments_are_rejected_without_apt(self):
        for arg in ("--allow-remove", "--allow-unauthenticated", "-y", "agent-sphere"):
            with self.subTest(arg=arg):
                result = self.run_installer(arg)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Unsupported argument", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_help_does_not_require_root_or_call_apt(self):
        self.env["APT_TEST_UID"] = "1000"
        result = self.run_installer("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("agent-sphere and agent-apps", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_missing_apt_is_rejected(self):
        (self.bin / "apt-get").unlink()
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("apt-get is required", result.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
