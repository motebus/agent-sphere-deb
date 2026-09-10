import importlib.util
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "build").mkdir(exist_ok=True)

    def test_core_excludes_manager_ui_and_local_ultra(self):
        self.assertEqual(len(package.NAMES), 11)
        self.assertTrue({"agos", "model-router", "model-llm", "cx-mesh", "mote-mcpd"}.issubset(package.NAMES))
        self.assertFalse({"medge", "sphere-manager", "agpc-manager", "agent-apps", "agent-ultra", "mdesk", "ss-webos", "obsidian"}.intersection(package.NAMES))
        self.assertNotIn("Recommends", package.control())
        self.assertNotIn("Suggests", package.control())

    def test_unreviewed_migration_artifacts_block_release(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as tmp:
            source = Path(tmp)
            (source / "agpc.sh").write_text("PENDING_REVIEWED_FIXTURE_SHA256")
            with mock.patch.object(package, "ROOT", source):
                with self.assertRaisesRegex(ValueError, "committed-main migration artifacts"):
                    package.manifest(source / "dist")

    def test_reproducible_build(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as tmp:
            first = package.build(Path(tmp) / "first")
            second = package.build(Path(tmp) / "second")
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_extra_application_dependency_rejected(self):
        altered = package.control()
        altered["Depends"] += ", mdesk"
        with self.assertRaises(ValueError):
            package.check_control(altered)

    def test_modified_hooks_and_runtime_payload_rejected(self):
        for extra in ["DEBIAN/postinst", "usr/bin/agpc-manager"]:
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
