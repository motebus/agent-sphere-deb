# Agent Sphere

`agent-sphere 0.2.0-8` is the headless core of the four-package Agent Sphere
system. It composes Agent intelligence, model execution, CX-Mesh and Mote
through native APT/DPKG dependencies and systemd services. This is the standard
installation: Docker, Podman and other container runtimes are not prerequisites.
The installer refuses a container runtime added to its simulated or locked APT
transaction. Existing unrelated container software and data are left alone;
there is no removal step or alternate installation profile.

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
| cx-mesh | 1.2.0-1 |

There are no `Recommends` or `Suggests`. This metapackage owns composition and
owns documentation and `agentsphere.target`. Native Debian helpers enable
the target for boot and respect its existing disable or mask; no manager or
TUI is started by Core. APT adds `init-system-helpers (>= 1.54)` for that
lifecycle. Each dependency owns its executable, service and configuration. `mote-mcpd` retains on-demand stdio
`mote mcp`; its package rename creates no daemon or new transport identity.

This is a composition prerelease. Each dependency remains a real native package
with its own release and lifecycle. The complete installer requires the matching
signed `agent-computer-v0.2.0-8` aggregate; publishing this Core source release
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
in one APT transaction: Core `0.2.0-8`, Ultra `0.1.0-1`, AGPC Manager
`3.2.0-1` and Apps `0.2.0-3`. Apps requires `uchat >= 3.1.0-1`, bringing `uchatd` and its private Redis
instance into fresh installs and existing AGPC upgrades. The chat daemon owns
Inbox persistence and delivery; CX-Mesh retains execution authority.
The installer acquires the pinned unmodified official Obsidian
amd64 DEB, verifies its SHA-256 and Debian metadata, and supplies it to the
same transaction. Obsidian belongs to Ultra and is not rehosted by MoteBus.
The installer displays the APT simulation and asks for confirmation before
starting the final transaction. A piped installer reads `/dev/tty`; headless use
requires explicit `--yes`. The approved transaction runs noninteractively in a
separate systemd job, so replacing MoteD or losing the invoking SSH session does
not kill APT. The job uses root-private, hash-bound inputs and retains its log,
package observations, SSH report and atomic exit record under
`/var/lib/agpc-install.<random>/`. The caller prints the job name and paths,
observes completion, and returns the job's original exit status. A disconnected
caller can inspect those same files after reconnecting; absence of an exit
record is not success. Do not start another transaction while the job is active.
A one-hour observer timeout does not stop the worker.

After APT finishes, the job checks package consistency, exact configured entry
versions and the existing OpenSSH server. It validates `sshd -t`, enables and
starts the existing `ssh.socket` or `ssh.service` activation path as appropriate,
and requires an SSH banner from `127.0.0.1:22`, the existing local MoteD handoff
target. An explicitly masked service, invalid owner configuration or unavailable
port fails verification visibly. An unused masked socket remains unchanged. An enabled but inactive socket
also remains stopped while its already-running service owns the listener;
its boot enablement and the actual SSH banner are still checked.
Only a missing, trusted `/run/sshd` directory is created for configuration
validation; SSH keys, authentication, listen settings and firewall rules are
not rewritten. No restart or unmask is performed. Mote identity, MoteC resource
resolution and external reachability are separate and remain unverified here.

Successful installation prints the result and exits. Open
`/usr/bin/agpc-manager` manually for deliberate owner setup; no UI is launched.
Component services retain their native package lifecycle.
The frontend package and command are `agpc-manager 3.2.0-1`, paired with
`medge 3.2.0-1`; the predecessor is `sphere-manager`. The existing `sphere`
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
be available, together with a running systemd instance and trusted root-owned
staging directories; a missing prerequisite fails before package mutation.

Before any download, the installer classifies legacy transport, MCP and CX state.
The same classifiers run again under APT's lock. Unknown package metadata,
hooks, helper bytes, unsafe identity metadata or customized old system MCP
entries stop before DPKG. Diagnostics do not print identity or configuration
values.

The installer has a scoped exception to the native Rust runtime policy: its
short-lived Python standard-library helpers parse TOML/JSON, inspect ownership
metadata, and verify OpenSSH without extra parser dependencies. They run from
the reviewed bootstrap or private transaction stage and install no Python daemon
or alternate package manager. They remain installer support; a future replacement
requires its own review and does not change the component runtime language policy.

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

The CX-Mesh consolidation retires the `cx-node` and `codex-mesh` Debian
packages into `cx-mesh`. It admits reviewed `cx-node 0.3.3-1`/`0.3.3-4`/`0.3.3-6` or the
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
Added or obsolete CX conffile ownership remains unsupported for old4. Its exact residual
record is admitted only with the installed CX-Mesh successor, reduced legacy
file list, retained cleanup hook and sole successor executable ownership.

For `cx-node 0.3.3-6` amd64, a separate reviewed native lineage may retain
exactly one obsolete `/etc/cx-node/cx-node.toml` conffile with historical DPKG
digest `d137b03f7f14c9c1369d3e85a9062130`. Its exact installed file list,
checksum record, hooks and native drain executable are checked, together with
sole package ownership, no diversions, an intact migration receipt and trusted
existing configuration/identity files. Owner TOML bytes may differ from the
historical stock digest; that digest identifies the DPKG record, not a request
to reset owner configuration. No other conffile path, flag, digest or version
is admitted by this case.

The old removal hook runs `cx drain`. This case permits only the established
`state.path = "/var/lib/cx-node"`, safe directory parents and a missing or
regular single-link drain marker. Symlinks, hardlinks, unsafe permissions,
custom state roots and changes between preflight and APT's lock are refused.
The drain marker is an intentional lifecycle write; installation does not
establish an undrained or ready runtime. Directory fingerprints may also cause
a safe refusal if a live service changes the state during preparation. The
APT lock is not a freeze of service-owned state or a replacement for native
filesystem race protection.

After native replacement, residual `cx-node 0.3.3-6` retains that same obsolete
record and remains the sole TOML owner. A repeat run requires the exact
installed CX-Mesh successor, the reviewed reduced residual file list and
cleanup hook, no removed payload hooks, and sole successor ownership of the
drain executable. The residual package is never purged: doing so could remove
the still-used owner configuration. The existing no-conffile old6 path is
unchanged.

The historical `cx-node 0.3.3-1` amd64 lineage with that exact obsolete TOML
record can also migrate directly to `cx-mesh 1.2.0-1`. It has separately pinned
old1 file-list, checksum, hook and drain-binary hashes. The same ownership,
state-directory and migration-receipt checks apply before and under the APT
lock. Both legacy runtimes are replaced in one transaction; no interim CX
package, purge or manual DPKG edit is needed. Residual records remain solely to
preserve owner configuration and are accepted on repeated runs. Runtime
compatibility paths inside `cx-mesh` remain supported.

The migration guard binds CX-Mesh 1.2.0-1 and AGPC Manager 3.2.0-1 to their
actual published artifact hashes. Native tests use genuine historical and
successor archives, real APT/DPKG, and the production classifier and locked
transaction guard. Dependency stand-ins, a mapped service UID and a systemctl
fixture keep those tests isolated; live service readiness is a separate check.

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
not establish live readiness. Detached-worker tests use real Linux namespaces
and separate caller/worker processes, with APT and systemd explicitly represented
by command fixtures. An independent test runs the actual OpenSSH configuration
check and daemon in an empty network/filesystem namespace. Privileged CI requires
the actual port-22 banner; a local single-UID namespace may report insufficient
bind or privilege-separation permissions and does not count as that CI gate.
Synthetic SSH configuration and test keys never leave the isolated namespace.
These tests do not prove a reboot, real systemd boot activation or a live Mote
connection. The signed aggregate publisher owns actual
full-cohort dependency resolution, public artifact verification and native
host acceptance before activation.


The installer accepts `--user USER`, defaulting to the authenticated sudo login
account. That account is carried into the detached installation job, where the
native uChat helper configures its protected `@machine-name` after package
verification. No account password is collected by the installer. Root-only
installation without a selected login account reports the required manager
setup. Open AGPC Manager explicitly and select **Mesh → uChat** to configure
membership once and enable chat on that mesh.
