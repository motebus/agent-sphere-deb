Agent Sphere 0.3.0-40 repairs the native `mote-chatd` retirement transaction
when an AGPC still has `uchatd 0.4.0-2`. The signed 2.0.0-9 transition package
can configure against that reviewed baseline, then the guarded APT transaction
upgrades `uchatd` to 0.6.0-1 and removes `mote-chatd`. The installer also
recognizes and recovers the exact `install ok unpacked` 2.0.0-8 state left by
the previous transaction failure. Other incomplete states remain refused.

This release retains the exact residual MCP state support introduced in 0.3.0-39. It applies when
`mote-mcpd 3.1.0-1` has been removed but its configuration is retained. The
installer binds the obsolete `mote-bridge-mcp 3.0.0-2` record to that exact
successor owner, architecture and version, then lets the signed APT transaction
restore `mote-mcpd` while preserving the managed MCP identity and conffiles.
Other residual versions, architectures, incomplete DPKG states and unexpected
ownership remain refused.

The bridge accepts only reviewed installed uchatd baselines (0.4.0-2, 0.5.0-1
or 0.6.0-1). The public installer still pins and verifies the Redis-only uchatd
0.6.0-1 successor in the same durable job.

This release also retains the complete SQLite retirement from 0.3.0-36. Core
requires `uchat 3.2.0-6` and `uchatd 0.6.0-1`; the daemon package contains no
SQLite importer, runtime dependency, fallback or dual-write path.

Legacy SQLite Inbox files are cache. Upgrade removes the fixed database, WAL,
SHM and journal paths and drops the obsolete `database` configuration field.
The AGPC installer no longer blocks for offline import. It initializes a new
Redis Inbox after replacing a cache-only pre-0.5 daemon, while preserving and
validating an existing Redis store identity.

The signed `mote-chatd 2.0.0-9` retirement bridge remains scoped to reviewed
2.0.0-4, 2.0.0-6, interrupted 2.0.0-7, and exact interrupted 2.0.0-8 bridge
installations. AGPC remains 100% native on Linux: DEB/systemd,
no Docker and no `ag-net`. `contextd` stays inside AGPC; CoD Server remains a
cloud service.
