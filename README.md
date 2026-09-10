# Agent Sphere

`agent-sphere 0.2.0-1` is the headless core of the four-package Agent Sphere
system. It composes Agent intelligence, model execution, Codex Mesh and Mote
through native APT/DPKG dependencies.

```text
agent-sphere    Core: AGOS, Codex Mesh, model execution, Mote and local I/O
agent-ultra     Redixs, local Comm/Telegram, Obsidian and vault sync
sphere-manager Dedicated native TUI/CLI backed by MEdge management
agent-apps     Jujue, iAgent, SS-WebOS, MDesk and UChat
```

Core contains no TUI and does not require the manager or desktop applications.
Sphere Manager owns its frontend; MEdge owns the headless management backend
and existing MBox/MDrive/MCP I/O implementation. MEdge is reached through the
manager package dependency, and its admitted I/O still uses MoteD and MLINK.
Exiting the management UI must not stop the backend or Core.

## Core dependency baseline

| Required component | Minimum version |
| --- | --- |
| sphered | 4.1.0-2 |
| moted | 3.6.0-2 |
| mote-proxy | 2.0.0-5 |
| mote-transportd | 2.0.0-6 |
| mlink | 2.1.0-1 |
| mote-secd | 1.0.0-2 |
| agos | 2.0.0-2 |
| model-router | 0.1.0-1 |
| model-llm | 0.1.0-3 |
| cx-agent | 0.3.4-3 |
| mote-mcpd | 3.0.0-3 |
| codex-mesh | 1.0.0-2 |

There are no `Recommends` or `Suggests`. This metapackage owns composition and
contains only documentation. Each dependency owns its executable, service,
configuration and native lifecycle. `mote-mcpd` retains on-demand stdio
`mote mcp`; its package rename creates no daemon or new transport identity.

This source is an **unreleased four-package candidate**. Native Mote MCPd,
CX Agent and Codex Mesh artifacts must satisfy the new floors, and the
four-entry aggregate additionally requires actual Redixs, Comm, Jujue, iAgent,
MEdge management and Sphere Manager artifacts. No alias or empty package may
substitute for those runtimes. Pending exact migration hashes block release
manifest generation. Existing published tags remain immutable.

## Complete installation and migration

The permanent plural `agent-sphere-apps.sh` installer requests all four entries
in one APT transaction: Core `0.2.0-1`, Ultra `0.1.0-1`, Sphere Manager
`0.1.0-1` and Apps `0.2.0-1`. It acquires the pinned unmodified official Obsidian
amd64 DEB, verifies its SHA-256 and Debian metadata, and supplies it to the
same transaction. Obsidian belongs to Ultra and is not rehosted by MoteBus.
APT asks for confirmation. A piped installer reads `/dev/tty`; headless use
requires explicit `--yes`.

Before any download, the installer classifies legacy transport and MCP state.
The same classifiers run again under APT's lock. Unknown package metadata,
hooks, helper bytes, unsafe identity metadata or customized old system MCP
entries stop before DPKG. Diagnostics do not print identity or configuration
values. Python's standard TOML reader is used only by this installer preflight;
it introduces no installed Python daemon or alternate package manager.

Ordinary `mote-chatd 2.0.0-4` owns only its normal env conffile and can be
replaced by the exact transport `2.0.0-6` artifact after its removal hooks are
verified. A protected old locked conffile instead retains the exact
`mote-chatd 2.0.0-6` documentation guard. That record must not be removed or
purged. Fresh hosts require no retention package. The explicit `mote-chatd-`
selector prevents APT from selecting the retention candidate on the ordinary
path. Residual records and repeated installation are supported within the
exact reviewed ownership contract.

The MCP rename supports exact `mote-bridge-mcp 3.0.0-2` metadata and its reviewed
removal hook/helper. The old hook deletes its managed system Codex table, so
only stock or absent old and new entries are admitted. Existing unrelated
system configuration, user/project configuration, locked topology and receipts
remain preserved. Residual obsolete conffile records require the exact
installed `mote-mcpd` successor to own the normal path. No incidental old-record
purge is performed. The runtime keeps legacy configuration/provider/helper
paths while its managed Codex server entry uses the new package name.

The public `cx-node 0.3.3-6` migration retains exact old hook checks and binds
the new CX artifact. The reviewed local CX, Vault Sync and Model LLM renames
remain bounded replacement pairs. APT protocol-v3 checks reject unrelated
removals, retired package installation, downgraded components and any missing
replacement. Changes between preflight and the locked transaction are denied.
Identity files are never edited, diverted or assigned through manual DPKG
metadata changes. Their bytes, inode, ctime and existing access metadata must
survive component migration. An absent bootstrap receipt may be created by
its owning component's existing policy.

Dropping a former dependency does not authorize removing it or running
`autoremove`. Removing a meta removes its documentation only. The historical
full-bundle uninstaller cannot safely remove this composition and must stop
before mutation. Product removal needs a separately reviewed lifecycle and
data-preservation plan.

## Verification and readiness

Package installation does not establish operational identity, source admission,
model inference, Telegram delivery, desktop availability, local I/O or reboot
recovery. Existing runtime profiles and configuration gates remain truthful;
MDrive's bounded local object profile is not automatic access to a real vault.

```sh
python3 scripts/package.py build
python3 -m unittest discover -s tests -v
python3 scripts/check-installer-transaction.py
```

Metadata-only APT fixtures prove Core dependency closure without manager/UI
packages. Installer unit tests exercise four-entry selection and exact
preflight policies. Native DPKG/APT migration fixtures use checksum-pinned old
and new artifacts in disposable namespaces; mocked service observations do
not establish live readiness. The signed aggregate publisher owns actual
full-cohort dependency resolution, public artifact verification and native
host acceptance before activation.
