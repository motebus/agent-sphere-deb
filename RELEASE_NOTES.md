Agent Sphere 0.1.0-2 updates the application package name to `agent-apps` and
provides `agent-sphere-apps.sh` as the two-package installer. It remains a
system composition prerelease.

The architecture-independent `agent-sphere` package declares six direct
dependencies: `sphered`, `moted`, `mote-proxy`, `mote-transportd`, `medge`, and `mlink`.
It contains documentation only. Components retain their own services,
configuration, state, and release lifecycles.

Download all five release assets and verify `SHA256SUMS`. With the signed
MoteBus component APT repository configured, install the local DEB with
`sudo apt-get install --no-install-recommends --no-remove ./agent-sphere_0.1.0-2_all.deb ./mote-transportd_2.0.0-5_amd64.deb`.
The renamed D/MSG component is included with `mote-transportd.service`. Its
executable, protocol, configuration and journal are preserved; the distinct
unit protects startup from a later purge of the old package. Hosts with the old physical `mote-chatd` package require a
reviewed replacement plan; the fresh-install no-removal command will stop.
Signed APT publication is a separate protected step in the MoteBus download
repository. After it succeeds, `apt install agent-sphere` resolves all six
components automatically. `agent-apps` remains pending compatible AGOS.

The included `agent-sphere-apps.sh` installer runs native APT for
`agent-sphere` and `agent-apps` together. Run `sudo bash ./agent-sphere-apps.sh`
with the signed repository configured. It checks both packages before package
installation, preserves APT confirmation by default, and supports explicit
`--yes`. Until compatible Agent App is published, its preflight reports the
missing dependency instead of installing only Sphere.

Validation covers package contents and metadata, identical local rebuilds,
negative package-boundary tests, and APT dependency simulation on Ubuntu 24.04
amd64. The published manifest binds the artifact to its committed `main`
revision and GitHub Actions run.

Sphere Ready and v1.0 reboot acceptance remain unverified. Current MEdge and
MLINK require lifecycle work; MEdge also expects an existing Docker `ag-net`.
Historical `agos 1.0.0-16` is incompatible with the current MEdge package's
replacement of standalone `qbix`. New MEdge and AGOS designs are separate
implementation work and are not shipped in this release.
