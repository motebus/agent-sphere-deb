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
    if sys.argv[1:]:
        installer.write_text(wanted)
        (ROOT / 'agent-sphere-apps.sh').write_text(wanted)
    else:
        assert text == wanted, 'embedded installer helper differs from reviewed source'
        assert (ROOT / 'agent-sphere-apps.sh').read_bytes() == installer.read_bytes()


if __name__ == '__main__':
    main()
