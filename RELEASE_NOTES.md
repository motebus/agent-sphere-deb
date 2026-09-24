Agent Sphere 0.3.0-33 admits the exact installed `cx-mesh 2.0.0-2` successor
when the retired Codex Mesh extension paths are absent and unowned, and the
installed successor metadata exactly matches the reviewed native package. This
lets an already upgraded native AGPC continue without a CX downgrade.

The reviewed `mote-chatd 2.0.0-4/2.0.0-6` retirement now names exact
`uchatd 0.5.0-1` as its successor. An already installed Redis-backed uchatd
satisfies the replacement check, so the obsolete package can be removed without
reinstalling an unrelated transport component.

- agpc.sh requires the native contextd and durable Redis-backed uchatd in Core.
- agpc-all.sh adds agpc-apps 0.3.0-1, upgrading an installed agent-apps name through its exact dependency transition.
- Both profiles preserve configuration, application data, SSH checks and detached installation; codd remains cloud-side.
- Unlisted CX successor versions remain refused before download or package changes.
- Pre-0.5 uchatd installations require their separate offline SQLite-to-Redis cutover. Only verified fresh installs initialize an empty store.

This release carries the reviewed native contextd runtime and matching signed aggregate cohort. AGPC remains native DEB/systemd installation; Docker and OCI are not required on the local host.
