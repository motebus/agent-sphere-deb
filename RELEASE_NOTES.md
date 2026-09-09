Agent Sphere 0.1.0-8 requires MEdge 3.0.0-3, correcting the provider socket
group on hosts where MoteD has a distinct primary group. The new metapackage
and installer floor ensure a rerun upgrades an already installed v7 host;
merely publishing a newer dependency would leave the old satisfied version
installed.

The installer retains the reviewed ordinary MoteChatD and public CX migration
checks, artifact digests and interactive confirmation behavior. Other component
floors and identities remain unchanged. The matching signed Agent Computer
aggregate owns the exact MEdge artifact pin and package-distribution gates.
Previous package and installer releases remain immutable.

Native APT resolver tests cover the old satisfied dependency, the forced v8
upgrade, repeat installation and failure when corrected MEdge is unavailable.
These checks do not establish live owner admission, connectivity or reboot
readiness. This remains a composition prerelease.
