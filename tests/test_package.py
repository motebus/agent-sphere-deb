import importlib.util
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_reproducible_build(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as tmp:
            first = package.build(Path(tmp) / "first")
            second = package.build(Path(tmp) / "second")
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_extra_application_dependency_rejected(self):
        altered = package.control()
        altered["Depends"] += ", agos"
        with self.assertRaises(ValueError):
            package.check_control(altered)

    def test_hooks_and_runtime_payload_rejected(self):
        for extra in ["DEBIAN/postinst", "usr/bin/sphere-manager"]:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory(dir=ROOT / "build") as tmp:
                original = package.build(Path(tmp) / "base")
                root = Path(tmp) / "unpacked"
                root.mkdir()
                for flag, target in [("--ctrl-tarfile", root / "DEBIAN"), ("--fsys-tarfile", root)]:
                    target.mkdir(exist_ok=True)
                    # The input is the exact local package just built and verified.
                    with package.archive(original, flag) as arc:
                        arc.extractall(target, filter="data")
                file = root / extra
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("#!/bin/sh\nexit 0\n")
                file.chmod(0o755)
                bad = Path(tmp) / "unexpected.deb"
                subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(root), str(bad)], check=True)
                with self.assertRaises(ValueError):
                    package.verify(bad)


if __name__ == "__main__":
    unittest.main()
