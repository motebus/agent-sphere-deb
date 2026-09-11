#!/usr/bin/python3
"""Verify direct legacy CX retirement with pinned public archives in an isolated namespace."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    'historical.deb': ('deb-v2026.08.25-2', 'cx-node_0.3.1-4_amd64.deb', '06a2507ea7e66d0efc41241e38f94ecf91f930b4bdb48ae34c3f7f3bb82ef020'),
    'old1.deb': ('medge-v5.7.0-5', 'cx-node_0.3.3-1_amd64.deb', '23be77845703665634e82760bf6add620eeb12014b982d91e503caa8e5947d88'),
    'old-mesh.deb': ('agent-computer-v0.1.0-3', 'codex-mesh_1.0.0-1_amd64.deb', '79ea8390ba64a462e2be9df5550969b6a917f4b13bc7ea3ab9c06eb532a55a38'),
    'new.deb': ('agent-computer-v0.2.0-7', 'cx-mesh_1.2.0-1_amd64.deb', 'caa078bdd810580dc8b35380d2fe8abbda6ff6c4338f2a8c8dbbba3051d02af0'),
}


def main():
    with tempfile.TemporaryDirectory(prefix='cx-retirement-') as directory:
        stage = Path(directory)
        # Root namespace mappings cannot traverse runner-owned private checkout
        # parents. Copy only reviewed fixture inputs into this owned stage.
        source = stage/'source'
        fixture = source/'tests/fixtures/cx-retirement'
        fixture.mkdir(parents=True)
        shutil.copyfile(ROOT/'agpc.sh', source/'agpc.sh')
        shutil.copyfile(ROOT/'tests/fixtures/medge-archive-keyring.gpg', source/'tests/fixtures/medge-archive-keyring.gpg')
        for name in ('run.sh','lifecycle.py','test_rename_apt_support.py','fixture-systemctl.py'):
            shutil.copyfile(ROOT/'tests/fixtures/cx-retirement'/name, fixture/name)
        (fixture/'fixture-systemctl.py').chmod(0o755)
        cache = os.environ.get('CX_RETIREMENT_DEB_DIR')
        for name, (tag, asset, digest) in INPUTS.items():
            path = stage/name
            if cache:
                path.write_bytes((Path(cache)/name).read_bytes())
            else:
                subprocess.run(['curl','--fail','--silent','--show-error','--location',
                    '--proto','=https','--proto-redir','=https','--retry','2','--max-time','120',
                    '--output',str(path),f'https://github.com/motebus/download/releases/download/{tag}/{asset}'],check=True)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
        assert hashlib.sha256((ROOT/'tests/fixtures/medge-archive-keyring.gpg').read_bytes()).hexdigest() == '756fc2632c307509b8e5ece665ced7f4d1a58636ac935aefc1e017f7dcfcbfbd'
        for scenario in ('both','disabled','masked'):
            output = stage/scenario; output.mkdir()
            result = subprocess.run(['bash',str(fixture/'run.sh'),scenario,
                str(stage/'new.deb'),str(stage/'old-mesh.deb'),str(stage/'historical.deb'),str(stage/'old1.deb')],
                env=dict(os.environ,TMPDIR='/tmp',FIXTURE_LOG_DIR=str(output)),capture_output=True,text=True,timeout=90)
            if result.returncode:
                raise RuntimeError(result.stdout[-15000:]+'\n'+result.stderr[-15000:])
            receipt = json.loads((output/'acceptance.json').read_text())
            assert receipt['passed'] and receipt['production_cx_classifier_and_locked_guard'] and receipt['residual_native_repeat']
            assert receipt['native_chain'] == ['0.3.1-4','0.3.3-1','cx-mesh1.2.0-1']
            assert len(receipt['denied_before_dpkg']) == 8
            assert receipt['no_purge'] and receipt['config_identity_receipt_session_full_metadata_preserved']
            print('CX retirement passed: '+scenario+'; actual APT/DPKG, production guard, retained configuration, repeat install and eight refusal checks',flush=True)


if __name__ == '__main__':
    main()
