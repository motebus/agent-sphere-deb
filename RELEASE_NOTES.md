Agent Sphere 0.2.0-8 retires the reviewed cx-node 0.3.3-1 and codex-mesh
1.0.0-1 packages directly into CX-Mesh 1.2.0-1. Their existing configuration,
identities and work data remain preserved. An obsolete conffile record is
retained through the native residual package lifecycle; no purge or manual
ownership transfer is performed. The old1 cleanup hooks, removal list, drain
executable and state boundaries are verified before and under the APT lock.

The installer also corrects the CX-Mesh and AGPC Manager migration artifact
hashes to their current published versions. Genuine-archive native tests cover
the combined retirement, retained configuration, repeated installation,
disabled/masked services and rejection of altered hooks, ownership or state
paths. Dependency and systemctl fixtures are isolated from live hosts.

The uChat-on-Mesh package set, permanent machine names and independent Inboxes
remain unchanged. Signed APT activation requires the matching aggregate and
Ubuntu installation verification; publication alone does not upgrade a host.
