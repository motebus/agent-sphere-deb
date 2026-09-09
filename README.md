# Agent Sphere

Agent Sphere is the system substrate that turns a Linux host into an
UltraOne-connected Agent Computer.

```text
Agent Computer = agent-sphere.deb + agent-apps.deb

agent-sphere.deb
├── sphered               native MoteBus/DC foundation
├── moted                 Host Mote Endpoint and admitted local broker
├── mote-proxy            outbound Mote access
├── mote-transportd       D/MSG runtime
├── medge                 MBox + MDrive + MCP
└── mlink                 local device and I/O mechanics
```

The metapackage owns composition. It contains documentation and six direct
Debian dependencies, with no daemon, hooks, updater or package manager.
APT/DPKG resolve packages; each component owns its systemd lifecycle.

MEdge is one native runtime containing MBox command admission and dispatch,
MDrive local storage, and a fixed MCP extension. Its MCP extension uses the
separate Apps-owned Mote Bridge MCP. AGOS reaches admitted local operations
through MoteD. MLINK owns the device mechanics below MEdge.

## Package baseline

| Component | Minimum version |
| --- | --- |
| sphered | 4.1.0-2 |
| moted | 3.6.0-2 |
| mote-proxy | 2.0.0-5 |
| mote-transportd | 2.0.0-6 |
| medge | 3.0.0-2 |
| mlink | 2.1.0-1 |

`component-baseline.json` records these floors. Exact component artifacts and
source-build provenance belong to the coordinated
[MoteBus distribution](https://github.com/motebus/download).
The initial component set targets Ubuntu amd64. `Architecture: all` describes
this documentation-only metapackage, not every component's platform support.

## Install both entry packages

The second entry package, `agent-apps`, composes AGOS, Model Router, Model LLM,
CX Agent, SS-WebOS, MDesk, Obsidian, UChat, Mote Bridge MCP, the Vault Sync pair,
Mote SecD and Codex Mesh. AGOS runs agents and governs agent/model resources;
Model Router combines routing and resource scheduling; Model LLM owns inference.

After the coordinated release is available in the configured signed MoteBus
APT repository, download and verify the release installer, then run:

```sh
sudo bash ./agent-sphere-apps.sh
```

The installer downloads the pinned unmodified official Obsidian DEB, checks
its SHA-256 and Debian metadata, and supplies it to the same APT transaction
as `agent-sphere` and `agent-apps`. MoteBus does not redistribute Obsidian.
APT asks for confirmation; `--yes` supports unattended installation.
The installer fails before DPKG if dependencies cannot resolve or the reviewed
transaction boundary is violated. It does not select an Obsidian Vault,
activate a plugin, provision identity or grant runtime access.

Only the reviewed Vault Sync, CX Agent and Model LLM package replacements may
remove their former package names. An APT protocol-v3 hook checks the final
transaction under the APT lock and rejects other removals, retired package
installation and downgrades. On hosts with legacy `mote-chatd` ownership, a
separate documentation-only record preserves the locked configuration; the
single runtime belongs to `mote-transportd`. The old record is not removed.

Removing a composition package removes its documentation. Component removal
and user-data preservation need the matching signed uninstall contract. The
legacy full-bundle uninstaller cannot remove this composition and must stop
before mutation. Do not purge a protected configuration ownership record.

## Acceptance

Package installation and runtime readiness are separate checks. Version
0.1.0-5 composes the initial native profile; it does not certify Sphere Ready.
MBox policy and individual I/O endpoints require explicit owner admission.
MDrive initially supports bounded local objects, not advanced XS operations,
remote MDrive publication or automatic access to a real Obsidian Vault.

Sphere Ready additionally requires operational transport and host identity,
bidirectional D/MSG with the intended UltraOne peer, admitted local I/O and
recovery after reboot. AGOS/model backend configuration and actual inference
are separate Apps acceptance. These are not implied by successful packaging.

## Build and verification

```sh
python3 scripts/package.py build
python3 -m unittest discover -s tests -v
python3 scripts/check-installer-transaction.py
```

Build tooling is not a runtime dependency. CI verifies reproducible package
bytes, exact composition, absence of hooks/runtime payload, and installer
checks. The offline transaction fixture uses real APT/DPKG in an isolated
namespace. The aggregate publisher owns signed-index dependency resolution
and clean Ubuntu installation gates before public APT activation. Existing
published release tags remain immutable.
