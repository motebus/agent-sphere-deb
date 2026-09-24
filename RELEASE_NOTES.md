Agent Sphere 0.3.0-35 adds the signed, upgrade-only `mote-chatd 2.0.0-7`
retirement bridge. The installer uses it only for reviewed installed
`mote-chatd 2.0.0-4/2.0.0-6` records whose legacy removal hook protects the
locked configuration, then removes the bridge in the same durable job. It
contains no daemon, does not read the legacy configuration, requires exact
installed `uchatd 0.5.0-1`, and leaves the old configuration as a residual DPKG
record without force or purge.

The reviewed `mote-chatd 2.0.0-4/2.0.0-6` retirement now names exact
`uchatd 0.5.0-1` as its successor. An already installed Redis-backed uchatd
satisfies the replacement check, so the obsolete package is retired without
reinstalling an unrelated transport component.

Agent Sphere 0.3.0-35 verifies that the running local SSH server proves possession
of the ED25519 host identity available for MoteD registration. The installer
validates the default public host key and completes a pinned, unauthenticated
OpenSSH key exchange on 127.0.0.1:22 before reporting SSH readiness.

- A missing host-key pair is generated through OpenSSH. Existing keys are retained;
  incomplete, unsafe or mismatched key state fails readiness without rotation.
- The probe disables authentication, commands, sessions and forwarding. It uses
  temporary protected known_hosts files and never exposes SSH debug contents.
- Custom server keys and a stale running key that differ from the public file
  fail readiness. SSH configuration and existing listeners are preserved.
- The exact installed cx-mesh 2.0.0-2 successor remains admitted when retired
  extension paths are absent and unowned and package metadata matches the
  reviewed native package. Unlisted successors remain refused.
- Retired mote-chatd 2.0.0-4/2.0.0-6 uses exact uchatd 0.5.0-1 as its
  successor, including an already installed Redis-backed daemon, while retaining
  both preflight and APT-lock replacement checks.
- Core retains contextd 0.1.0-27 and durable Redis-backed uchatd. Full adds
  agpc-apps 0.3.0-1 with the existing agent-apps transition. Existing data and
  configuration are preserved; pre-0.5 uchatd still requires offline migration.

This candidate requires MoteD 3.6.0-7 and Mote Proxy 2.0.0-9 for host-public-key
registration and strict trusted resolution. Their exact-main artifacts must be
admitted before component publication. Global installer/cohort activation requires
MoteC readiness and authorized device/S Channel policy; missing authority remains
denied. This installer does not create device authority or establish fleet trust
readiness. Older native preview package cohorts remain separately versioned.
AGPC uses native DEB/systemd installation; local Docker and OCI are not required.
