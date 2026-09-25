Agent Sphere 0.3.0-43 selects the canonical AGPC MCP gateway and S rights owner.

- Requires `mote-mcpd >= 3.3.0-1` and `mote-secd >= 1.1.0-1`.
- Removes the dependency on retired `mote-mcp-ultra`; cloud providers belong to `ultra-mcp-xx` behind `ultra-mcp`.
- Preserves every other runtime dependency floor, existing service ownership and administrator configuration.

The gateway package owns migration of existing provider files and configuration. No backend data is purged. Matching signed leaf artifacts are required for installation. This release does not claim new Windows support, full remote M/S acceptance or live host installation.
