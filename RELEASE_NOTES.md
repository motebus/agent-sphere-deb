Agent Sphere 0.3.0-36 fully retires SQLite from native AGPC uChat. Core now
requires `uchat 3.2.0-6` and `uchatd 0.6.0-1`; the daemon package contains no
SQLite importer, runtime dependency, fallback or dual-write path.

Legacy SQLite Inbox files are cache. Upgrade removes the fixed database, WAL,
SHM and journal paths and drops the obsolete `database` configuration field.
The AGPC installer no longer blocks for offline import. It initializes a new
Redis Inbox after replacing a cache-only pre-0.5 daemon, while preserving and
validating an existing Redis store identity.

The signed `mote-chatd 2.0.0-7` retirement bridge remains scoped to reviewed
2.0.0-4/2.0.0-6 installations. AGPC remains 100% native on Linux: DEB/systemd,
no Docker and no `ag-net`. `contextd` stays inside AGPC; CoD Server remains a
cloud service.
