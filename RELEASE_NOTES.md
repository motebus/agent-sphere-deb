Agent Sphere 0.2.0-4 adds a narrowly verified migration for genuine
`cx-node 0.3.3-6` installations retaining the historical obsolete
`/etc/cx-node/cx-node.toml` conffile record. The installed and resulting residual
states are both admitted, preserving owner configuration and repeat installs.

The installer binds the exact ownership list, hooks, checksum record and native
drain executable, requires the existing migration receipt and safe state path,
and repeats the same checks under APT's lock. Other obsolete records and unsafe
state paths remain refused. No purge, identity rewrite or DPKG database edit is
introduced. All other component versions and migration contracts are unchanged.
The existing direct old4 and no-conffile old6 paths remain supported.

Installation reports completion and exits without launching the manager.
Open `agpc-manager` explicitly for owner setup. The old drain marker is a
known lifecycle write; installed packages do not imply an undrained or ready
runtime. The canonical download changes only through the matching signed
aggregate publication. Installation-success event delivery is not included.

Validation includes source checks and actual historical DEBs through the final
CX-Mesh replacement, native residual/repeat runs, protected file metadata and
owner unit-policy preservation, and pre-DPKG denials for changed ownership,
hooks, drain executable and unsafe state targets. Native fixtures use isolated
dependency metadata, a single mapped UID/GID and mocked systemctl; no live host
installation or configuration is claimed by these fixtures.
