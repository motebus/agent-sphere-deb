Agent Sphere 0.1.0-7 fixes installation on an ordinary published
mote-chatd 2.0.0-4 host that has no protected DPKG-owned topology conffile.
It explicitly selects replacement by the existing mote-transportd 2.0.0-6
artifact, while protected legacy owners retain their guarded record.
The ownership classifier is repeated under APT's lock; the normal path
requires exact installed package metadata, reviewed hooks and runtime digest.

The installer also accepts the reviewed public cx-node 0.3.3-6 replacement
with exact lifecycle and destination-artifact checks. Piped interactive use
reads APT confirmation from the controlling terminal; unattended use still
requires explicit --yes.

Real isolated APT/DPKG tests preserve existing topology, normal configuration,
receipt and journal contents, inode and ctime through migration, repeated
installation and old-record purge. Ownership/artifact drift stops before DPKG.
Component DEBs, identities and runtime boundaries are unchanged. This remains
a composition prerelease; live connectivity, owner admission, actual model
execution and reboot readiness require separate acceptance. Prior releases
remain immutable.
