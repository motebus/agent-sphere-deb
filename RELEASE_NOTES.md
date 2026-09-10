Agent Sphere 0.2.0-3 adds the verified direct migration from genuine
`cx-node 0.3.3-4` to the existing `cx-mesh 1.1.0-1` dependency, removing the
separate 0.3.3-6 preparation step for that exact supported state.

The installer checks the old removal file list, hooks, checksum record, native
drain executable and ownership; requires the intact migration receipt; and
rechecks the same fingerprint under APT's lock. The observed residual record
is accepted only with the exact installed successor. Added or obsolete CX
conffile ownership remains refused. No force, purge or DPKG metadata edit is
introduced. All other component versions and migration contracts are unchanged.

Installation reports completion and exits without launching the manager.
Open `agpc-manager` explicitly for owner setup. This is a composition prerelease:
package installation and the tested migrations do not imply configured models,
network channels, Vaults, devices or full live readiness. The canonical download
is updated only through the matching signed aggregate publication.

Validation: 84 source checks, plus actual-package enabled/disabled/masked direct
migration, configuration/identity/session preservation, residual/repeat and
old-purge lifecycle tests. Native fixtures use isolated dependency metadata,
a single mapped UID/GID and mocked systemctl. Previously installed hosts retain
their earlier recorded installation evidence; this release does not claim those
hosts used the new direct path.
