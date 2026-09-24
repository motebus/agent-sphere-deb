Agent Sphere 0.3.0-31 admits the exact installed `cx-mesh 2.0.0-2` successor
when verified residual CX and Codex Mesh conffiles retain their expected sole
ownership. This lets an already upgraded native AGPC continue without a CX
downgrade or package removal.

- agpc.sh requires the native contextd and durable Redis-backed uchatd in Core.
- agpc-all.sh adds agpc-apps 0.3.0-1, upgrading an installed agent-apps name through its exact dependency transition.
- Both profiles preserve configuration, application data, SSH checks and detached installation; codd remains cloud-side.
- Unlisted CX successor versions remain refused before download or package changes.
- Pre-0.5 uchatd installations require their separate offline SQLite-to-Redis cutover. Only verified fresh installs initialize an empty store.

This release carries the reviewed native contextd runtime and matching signed aggregate cohort. AGPC remains native DEB/systemd installation; Docker and OCI are not required on the local host.
