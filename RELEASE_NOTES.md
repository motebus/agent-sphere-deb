Agent Sphere 0.3.0-38 fixes the native mote-chatd retirement transaction and admits the exact residual MCP state left when
`mote-mcpd 3.1.0-1` has been removed but its configuration is retained. The
installer binds the obsolete `mote-bridge-mcp 3.0.0-2` record to that exact
successor owner, architecture and version, then lets the signed APT transaction
restore `mote-mcpd` while preserving the managed MCP identity and conffiles.
Other residual versions, architectures, incomplete DPKG states and unexpected
ownership remain refused.

The bridge accepts only reviewed installed uchatd baselines (0.4.0-2, 0.5.0-1 or 0.6.0-1) before the transaction; its package dependency still requires the Redis-only uchatd 0.6.0-1 successor.

This release also retains the complete SQLite retirement from 0.3.0-36. Core
requires `uchat 3.2.0-6` and `uchatd 0.6.0-1`; the daemon package contains no
SQLite importer, runtime dependency, fallback or dual-write path.

Legacy SQLite Inbox files are cache. Upgrade removes the fixed database, WAL,
SHM and journal paths and drops the obsolete `database` configuration field.
The AGPC installer no longer blocks for offline import. It initializes a new
Redis Inbox after replacing a cache-only pre-0.5 daemon, while preserving and
validating an existing Redis store identity.

The signed `mote-chatd 2.0.0-8` retirement bridge remains scoped to reviewed
2.0.0-4, 2.0.0-6 and interrupted 2.0.0-7 bridge installations. AGPC remains 100% native on Linux: DEB/systemd,
no Docker and no `ag-net`. `contextd` stays inside AGPC; CoD Server remains a
cloud service.
