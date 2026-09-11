import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class DetachedInstall(unittest.TestCase):
    def test_actual_worker_survives_disconnection_and_preserves_failures(self):
        subprocess.run(['python3', str(ROOT / 'scripts/check-detached-namespace.py')], check=True)

    def test_native_ssh_config_and_banner_in_private_namespace(self):
        subprocess.run(['python3', str(ROOT / 'scripts/check-ssh-namespace.py')], check=True)
