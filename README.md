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
| medge | 3.0.0-3 |
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

The reviewed Vault Sync, CX Agent, Model LLM and ordinary MoteChatD
replacements may remove their former package names. The public CX baseline
`0.3.3-6` and the previously reviewed `0.3.4-1~local20260909` migration are
supported. The public baseline additionally requires its exact installed
removal hooks and the exact published `cx-agent 0.3.4-2` artifact. An APT
protocol-v3 hook checks the final transaction under APT's lock and rejects
unrelated removals, retired package installation and downgrades.

Before downloading, the installer distinguishes three transport states:

- A fresh host has no `mote-chatd` record and needs no retention package.
- A protected legacy conffile owner keeps a documentation-only `mote-chatd`
  record. That record cannot be removed or purged while it protects the file.
- Ordinary published `mote-chatd 2.0.0-4` on amd64 owns only its normal
  `mote-chatd-deb.env`; its locked identity was created outside DPKG ownership.
  With the reviewed removal hooks, an intact safe identity and a complete
  installed or residual state, it migrates directly to the exact published
  `mote-transportd 2.0.0-6` artifact. The installer passes `mote-chatd-` to APT
  so the unrelated retention candidate is not selected. Only the installed
  ordinary runtime may be removed, and only with its replacement present.

The same classifier runs again under APT's lock. Changed ownership, unknown
versions or hooks, incomplete package states, and missing, symlinked or
unsafely owned/writable topology stop before DPKG. Diagnostics request package
metadata, never topology values. The ordinary path does not weaken retention
protection, edit DPKG's database or modify the identity file. Existing normal
configuration, topology, receipt and journal files keep their contents and
metadata, including inode and ctime. An absent creation receipt may be created
by the unchanged component bootstrap.

A piped installer reads interactive APT confirmation from the controlling
terminal. Without a terminal it refuses installation unless `--yes` was
explicitly supplied; piping the script does not grant consent.

Removing a composition package removes its documentation. Component removal
and user-data preservation need the matching signed uninstall contract. The
legacy full-bundle uninstaller cannot remove this composition and must stop
before mutation. Do not purge a protected configuration ownership record.

## Acceptance

Package installation and runtime readiness are separate checks. Version
0.1.0-8 requires MEdge 3.0.0-3, which fixes the provider socket group on hosts
where MoteD has a distinct primary group. Re-running the permanent installer
on a v7 host therefore selects that MEdge update through the new dependency
floor. It does not certify Sphere Ready.
MBox policy and individual I/O endpoints require explicit owner admission.
MDrive initially supports bounded local objects, not advanced XS operations,
remote MDrive publication or automatic access to a real Obsidian Vault.

Sphere Ready additionally requires operational transport and host identity,
bidirectional D/MSG with the intended UltraOne peer, admitted local I/O and
recovery after reboot. AGOS/model backend configuration and actual inference
are separate Apps acceptance. These are not implied by successful packaging.

## Build and verification

`tests/test_legacy_dpkg.py` uses real private-root DPKG records; other installer
I/O is mocked. `scripts/check-installer-transaction.py` checks actual APT action
hooks with disposable packages. `scripts/check-chatd-migration.py` additionally
accepts the three checksum-pinned published old/runtime/retention DEBs via
`--old-deb`, `--runtime-deb` and `--retention-deb`. It tests ordinary installed
and residual migration, protected retention, repeated installation, old-record
purge, ownership drift and artifact drift. All existing transport files retain
SHA-256, inode, mtime, ctime, UID/GID, mode and link count. These offline tests
use empty OS dependency fixtures and a strict systemd observation mock in a
single-UID namespace; they do not prove live service behavior or distinct
service-account isolation. No host package database or service is changed.


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
