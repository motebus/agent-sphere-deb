Agent Sphere 0.1.0-1 is the initial system composition prerelease.

The architecture-independent `agent-sphere` package declares six direct
dependencies: `sphered`, `moted`, `mote-proxy`, `mote-transportd`, `medge`, and `mlink`.
It contains documentation only. Components retain their own services,
configuration, state, and release lifecycles.

Download all three release assets and verify `SHA256SUMS`. With the signed
MoteBus component APT repository configured, install the local DEB with
`sudo apt-get install --no-install-recommends --no-remove ./agent-sphere_0.1.0-1_all.deb`.
This repository does not yet publish an APT index for bare `apt install agent-sphere`.

Validation covers package contents and metadata, identical local rebuilds,
negative package-boundary tests, and APT dependency simulation on Ubuntu 24.04
amd64. The published manifest binds the artifact to its committed `main`
revision and GitHub Actions run.

Sphere Ready and v1.0 reboot acceptance remain unverified. Current MEdge and
MLINK require lifecycle work; MEdge also expects an existing Docker `ag-net`.
Historical `agos 1.0.0-16` is incompatible with the current MEdge package's
replacement of standalone `qbix`. New MEdge and AGOS designs are separate
implementation work and are not shipped in this release.
