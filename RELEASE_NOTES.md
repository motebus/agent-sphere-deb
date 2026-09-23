Agent Sphere 0.3.0-1 introduces native standard and full installer profiles.

- agpc.sh requires the native contextd and durable Redis-backed uchatd in Core.
- agpc-all.sh adds agpc-apps 0.3.0-1, upgrading an installed agent-apps name through its exact dependency transition.
- Both profiles preserve configuration, application data, SSH checks and detached installation; codd remains cloud-side.
- Pre-0.5 uchatd installations require their separate offline SQLite-to-Redis cutover. Only verified fresh installs initialize an empty store.

This is source/composition work. contextd 0.1.0-1 is a target floor, not an available runtime artifact. Signed publication and installation acceptance require the real native contextd implementation and matching cohort; no empty substitute is provided.
