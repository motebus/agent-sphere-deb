Agent Sphere 0.1.0-6 composes six system components, including native MEdge
(MBox + MDrive + MCP), MoteD admission and MLINK. The companion installer
installs Agent Sphere and the thirteen-component Agent Apps composition in
one APT transaction with a verified official Obsidian DEB.

The installer now checks exact protected legacy DPKG ownership before any
download or package transaction. Unsupported old-name records, partial DPKG
states and missing/symlinked protected files stop early instead of reaching
a failing retention-package preinst. Earlier releases remain immutable.

This is an initial composition prerelease. Runtime admission, model backend
configuration, real Vault integration and reboot acceptance remain separate.
Legacy protected transport identity is preserved by a documentation-only
ownership record. Coordinated signed APT publication belongs to motebus/download.
