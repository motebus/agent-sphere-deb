#!/usr/bin/env bash
set -euo pipefail

# This changes only a disposable GitHub runner's APT configuration.
test "${GITHUB_ACTIONS:-}" = true
test "$(dpkg --print-architecture)" = amd64
mkdir -p build
curl --proto '=https' --tlsv1.2 -fsSL \
  https://motebus.github.io/download/medge-archive-keyring.gpg \
  -o build/medge-archive-keyring.gpg
fingerprint="$(gpg --batch --show-keys --with-colons build/medge-archive-keyring.gpg | awk -F: '$1 == "fpr" {print $10; exit}')"
test "$fingerprint" = AECAA1DCDAF19C7B7FEAF0C082A0E180EDAEA7A0
sudo install -D -m 0644 build/medge-archive-keyring.gpg /etc/apt/keyrings/medge-archive-keyring.gpg
cat > build/mote-components.sources <<'SOURCES'
Types: deb
URIs: https://motebus.github.io/download
Suites: stable
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/medge-archive-keyring.gpg
SOURCES
sudo install -m 0644 build/mote-components.sources /etc/apt/sources.list.d/mote-components.sources
sudo apt-get update
version="$(sed -n 's/^Version: //p' packaging/control)"
apt-get --simulate --no-install-recommends --no-remove install \
  "./dist/agent-sphere_${version}_all.deb" \
  ./dist/mote-transportd_2.0.0-5_amd64.deb > build/apt-plan.txt
cat build/apt-plan.txt
python3 - <<'PY'
from pathlib import Path
import re
text = Path('build/apt-plan.txt').read_text()
planned = set(re.findall(r'^Inst ([a-z0-9+.-]+)', text, re.M))
required = {'agent-sphere', 'sphered', 'moted', 'mote-proxy', 'mote-transportd', 'medge', 'mlink'}
excluded = {'agos', 'agent-app', 'agent-apps', 'mdesk', 'ss-webos', 'jujue', 'codex', 'codex-cli',
            'codex-mesh', 'mcp-run', 'mote-bridge-mcp', 'cx-node', 'uchat', 'qbix', 'mote-chatd'}
assert required <= planned, f'Missing components: {required - planned}'
assert not excluded & planned, f'Unexpected application dependency: {excluded & planned}'
assert not re.search(r'^Remv ', text, re.M), 'Removal is outside composition scope'
print('APT resolved the six components without application packages or removals.')
PY
