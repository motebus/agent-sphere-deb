# Agent Sphere

Agent Sphere is the system substrate that turns a Linux host into an
UltraOne-connected Agent Computer.

```text
Agent Computer = Agent Sphere + Agent App
agent-sphere.deb = Mote Runtime + MEdge + MLINK
Mote Runtime = sphered + moted + mote-proxy + mote-transportd
```

`agent-sphere` is a dependency-only Debian package. It installs documentation
and declares six direct dependencies. It has no executable, daemon, systemd
unit, maintainer script, runtime configuration, credentials, or package manager.

| Plane | Package | Initial dependency floor |
| --- | --- | --- |
| Transport / communication | sphered: native MoteBus/DC foundation | 4.1.0-2 |
| Transport / communication | moted: Host Mote Endpoint | 3.5.0-8 |
| Transport / communication | mote-proxy: Mote Access Endpoint | 2.0.0-5 |
| Transport / communication | mote-transportd: D/MSG runtime | 2.0.0-5 |
| Agentic Edge | medge: edge execution | 2.0.0-2 |
| Local I/O | mlink: device and local I/O | 2.0.0-3 |

Five initial floors come from the public
[medge-v5.9.0-8 component release](https://github.com/motebus/download/releases/tag/medge-v5.9.0-8).
The renamed `mote-transportd 2.0.0-5` component is supplied alongside this
release. `component-baseline.json` records the six artifact identities and
digests. These are reference versions, not an assertion of end-to-end runtime
compatibility for all future component releases. Ordinary Linux dependencies,
including Docker in the current MEdge package, remain component-owned.

AGOS, SS-WebOS, MDesk, Jujue, Codex, MCP application capabilities, UltraOne
Comm/Ops, and Ultravisor are outside this package. The second top-level
installation package, `agent-app`, is designed to compose `agos`, `ss-webos`,
`mdesk`, `mote-bridge-mcp`, and `cx-node`, with optional separate `model-node`.
Its compatible AGOS implementation is pending, so this initial release does
not claim a complete two-package Agent Computer installation. Agent App owns application
composition. Each component retains its own source and release lifecycle.

## Install the initial release

This repository publishes GitHub release assets. Signed APT distribution
uses the existing MoteBus download repository through a separately approved
additive package publication. It preserves the legacy component bundles.
After the signed APT publication succeeds, the system entry command is:

```sh
sudo apt-get update
sudo apt-get install agent-sphere
```

APT then selects all six runtime dependencies automatically. The complete
`apt install agent-sphere agent-app` product entry remains pending the
compatible AGOS/App release. Before the additive APT publication, the
following local-file procedure is available for packaging evaluation. Five existing components must be available from the
configured, signature-verified MoteBus component APT repository described in
the [component distribution documentation](https://github.com/motebus/download#trust-chain).
The initial component baseline is published for Ubuntu amd64; `Architecture:
all` describes this documentation-only metapackage, not availability of the
components on every architecture or Linux distribution.

Download `agent-sphere_0.1.0-1_all.deb`,
`mote-transportd_2.0.0-5_amd64.deb`, `agent-sphere-app.sh`, `SHA256SUMS`, and `release-manifest.json` from this repository's GitHub release, then run in the
download directory:

```sh
sha256sum --check SHA256SUMS
sudo apt-get update
sudo apt-get install --no-install-recommends --no-remove ./agent-sphere_0.1.0-1_all.deb ./mote-transportd_2.0.0-5_amd64.deb
```

The checksum identifies the release bytes; it is not an independent signature.
Use the official HTTPS release and its recorded GitHub Actions build provenance.
The metapackage embeds no component binaries. APT resolves the local renamed
component plus the five existing packages from their configured repositories.
The separate `agent-sphere-app.sh` installer uses native APT and is not
installed by the metapackage. There is no new updater or runtime wrapper.

`mote-transportd` is the renamed D/MSG package. Its existing `mote-chatd`
executable, app protocol, configuration paths and journal remain unchanged.
The new `mote-transportd.service` has independent Debian enablement state,
so purging the old package cannot remove the new unit's startup links. Versioned `Provides: mote-chatd` preserves existing client package
dependencies; `Conflicts/Replaces` ensures only one physical runtime owner.
On a host with the old physical package installed, the no-removal command
above deliberately fails. Review an APT migration plan that replaces only
`mote-chatd` before installing on that host; do not allow unrelated removals.

Removing the metapackage removes its documentation. DPKG does not remove its
dependencies as part of that removal. A later, separate APT autoremove may
consider automatically installed packages; review that plan before running it.

## Install Sphere and App together

`agent-sphere-app.sh` is the single installer entry for the two top-level
packages. With the official signed MoteBus APT repository configured, download
the release assets, verify `SHA256SUMS`, then run:

```sh
sudo bash ./agent-sphere-app.sh
```

It updates APT metadata, checks a no-removal installation plan for both
`agent-sphere` and `agent-app`, then installs both in one APT invocation.
APT asks for confirmation; pass `--yes` explicitly for unattended installation.
The script does not configure repositories, provision identities, or replace
component service management. It cannot install both packages until the
compatible `agent-app` release is available; it fails before package installation
if either package or its dependency graph cannot be resolved.

## Status and known implementation gaps

Version 0.1.0-1 is an initial composition prerelease, not Agent Sphere v1.0
runtime acceptance. Successful APT configuration means the packages are
installed; it does not mean the host is Sphere Ready.

- Current MEdge still describes the older APort/Qbix assembly. The new native
  MEdge design must separate AGOS-owned admission from edge execution.
- Current MEdge does not automatically enable/start its service and expects an
  existing external Docker `ag-net` network. These lifecycle dependencies need
  a component-owned design and implementation update.
- Current MLINK leaves its service and device adapters disabled by default.
  Device enrollment and MoteD admission remain separate requirements.
- Host identity/trust provisioning, a reachable UltraOne peer, D/MSG round trips,
  admitted MEdge-to-MLINK I/O, and reboot recovery need runtime verification.
- Historical `agos 1.0.0-16` requires standalone `qbix`, which current MEdge
  declares incompatible. It is not a compatible Agent App for this baseline.

These gaps are not addressed by adding privileged hooks to the composition
package. Component packages own their units, data, identities, and recovery.
New MEdge and AGOS designs can evolve independently of this package.

Sphere Ready requires installed package state, operational Sphered MoteBus/DC,
running MoteD and reachable host `.mote`, operational Proxy, connected MoteChatD,
bidirectional D/MSG, running MEdge and MLINK, and successful local I/O enumeration.
v1.0 acceptance additionally requires a usable admitted I/O operation and
restoration of these conditions after reboot without manual intervention.

## Build and release

Build tooling uses Python 3, Git, and `dpkg-deb`; none is installed by the
metapackage. Run from the repository root:

```sh
python3 scripts/package.py build
python3 scripts/package.py verify dist/agent-sphere_0.1.0-1_all.deb
python3 -m unittest discover -s tests
```

The build normalizes timestamps, permissions, owner IDs, and archive compression.
CI checks identical rebuilds, rejects payload and dependency boundary violations,
and simulates APT resolution with the signed component repository on Ubuntu
24.04. Dependency simulation does not install services or prove runtime health.

Publication uses the workflow dispatch on committed `main`, passes the build
and dependency checks, then publishes their exact artifacts through the `release`
environment. The release includes both DEBs, the installer, a manifest with commit/run identity,
and SHA-256 checksums. Existing releases are never overwritten. Repository
classification is in `agent-sphere-deb.env`; it is not runtime configuration
and is never included in the DEB.
