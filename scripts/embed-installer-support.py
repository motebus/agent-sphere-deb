#!/usr/bin/python3
"""Keep the single-file published installer bound to its reviewed helper sources."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
START = '# BEGIN DETACHED INSTALL SUPPORT\n'
END = '# END DETACHED INSTALL SUPPORT\n'


def expected():
    python = (ROOT / 'scripts/ssh-readiness.py').read_text()
    shell = (ROOT / 'scripts/detached-install.sh').read_text()
    return START + "write_ssh_readiness_helper() {\n    cat <<'AGPC_SSH_READINESS_PY'\n" + python + 'AGPC_SSH_READINESS_PY\n}\n\n' + shell + END


def main():
    if sys.argv[1:] not in ([], ['--write']):
        sys.exit('Usage: embed-installer-support.py [--write]')
    installer = ROOT / 'agpc.sh'
    text = installer.read_text()
    assert text.count(START) == text.count(END) == 1
    before, section = text.split(START)
    _, after = section.split(END)
    wanted = before + expected() + after
    full = wanted.replace('agpc_profile=standard\nagpc_entrypoint=agpc.sh\n',
                          'agpc_profile=full\nagpc_entrypoint=agpc-all.sh\n', 1)
    assert full != wanted, 'missing fixed installer profile'
    if sys.argv[1:]:
        installer.write_text(wanted)
        for name in ('agpc-all.sh', 'agent-sphere-apps.sh'):
            (ROOT / name).write_text(full)
            (ROOT / name).chmod(0o755)
    else:
        assert text == wanted, 'embedded installer helper differs from reviewed source'
        assert (ROOT / 'agpc-all.sh').read_text() == full
        assert (ROOT / 'agent-sphere-apps.sh').read_text() == full


if __name__ == '__main__':
    main()
