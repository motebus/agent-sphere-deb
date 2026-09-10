# Agent Sphere

`agent-sphere 0.2.0-3` is the headless core of the four-package Agent Sphere
system. It composes Agent intelligence, model execution, CX-Mesh and Mote
through native APT/DPKG dependencies.

```text
agent-sphere    Core: AGOS, CX-Mesh, model execution, Mote and local I/O
agent-ultra     Redixs, local Comm/Telegram, Obsidian and vault sync
agpc-manager Dedicated native TUI/CLI backed by MEdge management
agent-apps     Jujue, iAgent, SS-WebOS, MDesk and UChat
```

Core contains no TUI and does not require the manager or desktop applications.
AGPC Manager owns its frontend; MEdge owns the headless management backend
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
| agos | 2.1.0-1 |
| model-router | 0.1.0-1 |
| model-llm | 0.1.0-3 |
| mote-mcpd | 3.0.0-3 |
| cx-mesh | 1.1.0-1 |

There are no `Recommends` or `Suggests`. This metapackage owns composition and
owns documentation and `agentsphere.target`. Native Debian helpers enable
the target for boot and respect its existing disable or mask; no manager or
TUI is started by Core. APT adds `init-system-helpers (>= 1.54)` for that
lifecycle. Each dependency owns its executable, service and configuration. `mote-mcpd` retains on-demand stdio
`mote mcp`; its package rename creates no daemon or new transport identity.

This is a composition prerelease. Each dependency remains a real native package
with its own release and lifecycle. The complete installer requires the matching
signed `agent-computer-v0.2.0-3` aggregate; publishing this Core source release
alone does not establish fleet or live runtime readiness. Existing published
tags remain immutable.

## Headless startup

`agentsphere.target` wants `sphered.service`, `moted.service`,
`mote-proxy.service`, `mote-transportd.service`, `mlink.service`,
`mote-secd.service`, `agosd.service` and `model-router.service`. It is ordered
after `basic.target` and enabled for `multi-user.target`. Starting the target
requests these required Core units even if they were previously only disabled;
explicit service masks remain authoritative. It does not add `PartOf` or
reverse dependencies from Core to the manager, Ultra, or a desktop.

Model LLM and CX-Mesh execution remain separately owner-enabled. AGPC means
Agent Computer; CX-Mesh connects authorized AGPC peers without changing their
existing identities. A running target is not a readiness assertion: configured
identity, admission and live owner health determine usable capabilities.

## Complete installation and migration

The canonical `agpc.sh` installer requests all four entries
in one APT transaction: Core `0.2.0-3`, Ultra `0.1.0-1`, AGPC Manager
`3.1.0-2` and Apps `0.2.0-1`. It acquires the pinned unmodified official Obsidian
amd64 DEB, verifies its SHA-256 and Debian metadata, and supplies it to the
same transaction. Obsidian belongs to Ultra and is not rehosted by MoteBus.
APT asks for confirmation. A piped installer reads `/dev/tty`; headless use
requires explicit `--yes`. After successful installation, the installer prints
the result and exits. Open `/usr/bin/agpc-manager` manually when needed.
Package services retain their normal systemd lifecycle.
The frontend package and command are `agpc-manager 3.1.0-2`, paired with
`medge 3.1.0-2`; the predecessor is `sphere-manager`. The existing `sphere`
shortcut points to the new command. A clean installed `sphere-manager 3.1.0-1`
amd64 package is the only admitted predecessor: its native executable and
package checksum record and DPKG removal file list must match the reviewed
release, its executable and
shortcut must retain sole package ownership, and it must have no conffiles,
lifecycle hooks or service overrides. The installer checks this state before
downloads and again under APT's lock, requires the exact reviewed replacement
artifact in the same transaction, and rejects retired package reinstallation.
An absent predecessor or its exact empty DPKG relationship record permits a
fresh or repeated install; residual conffile and partial states are refused.

The byte-identical `agent-sphere-apps.sh` asset remains a compatibility entry.

```sh
curl -fsSL https://motebus.github.io/download/agpc.sh | sudo bash
```

Ubuntu 24.04 and 26.04 amd64 are supported. The bootstrap verifies the fixed
public archive key SHA-256 and primary fingerprint and creates only missing
reviewed APT source/key files. Existing exact files retain their bytes and
metadata. Custom or ambiguous sources, keys and symlink destinations are
refused. Required native OS tools, Python 3 with `tomllib`, and GPG must already
be available; a missing prerequisite fails before mutation.

Before any download, the installer classifies legacy transport, MCP and CX state.
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

The CX-Mesh consolidation admits only reviewed `cx-node 0.3.3-4`/`0.3.3-6` or the
`0.3.4-1~local20260909` preview, `cx-agent 0.3.4-2`/`0.3.4-3`, and
`codex-mesh 1.0.0-1`/`1.0.0-2` predecessors. Exact cleanup hooks and transferred
conffiles are checked, as are existing CX/Mesh identity and configuration
metadata. Custom predecessor unit overrides and nonempty drop-ins are refused
before APT; explicit `/dev/null` masks are preserved. Residual records require
the successor to be the sole current owner of transferred conffiles. The same
transaction must install the exact reviewed CX-Mesh artifact. Vault Sync and
Model LLM renames remain bounded replacement pairs. APT protocol-v3 checks reject unrelated
removals, retired package installation, downgraded components and any missing
replacement. Changes between preflight and the locked transaction are denied.
The installer also admits the genuine `cx-node 0.3.3-4` amd64
installed state directly into the same CX-Mesh transaction, without an interim
`0.3.3-6` package installation. Its exact removal file list, checksum record,
native drain executable and lifecycle hooks must match the reviewed release;
the executable must retain sole ownership and have no diversion. An intact
existing native migration receipt excludes recursive legacy-state copying.
Added or obsolete CX conffile ownership remains unsupported. Its exact residual
record is admitted only with the installed CX-Mesh successor, reduced legacy
file list, retained cleanup hook and sole successor executable ownership.

Identity files are never edited, diverted or assigned through manual DPKG
metadata changes. Their bytes, inode, ctime and existing access metadata must
survive component migration. An absent bootstrap receipt may be created by
its owning component's existing policy.

Dropping a former dependency does not authorize removing it or running
`autoremove`. Removing Core or Ultra stops and removes only its startup target
and documentation; it does not stop or remove dependency services or data. The historical
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
