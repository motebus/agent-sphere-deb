Agent Sphere 0.2.0-1 provides the headless core composition and declarative
agentsphere.target. AGOS, model routing/execution and CX-Mesh belong to the
core. Local Ultra infrastructure, Sphere Manager and user applications have
separate entry packages and native lifecycles.

The canonical agpc.sh installer sets up only missing exact reviewed signed APT
key/source files on Ubuntu 24.04 or 26.04 amd64, then installs all four entry
packages in one guarded APT transaction. agent-sphere-apps.sh remains a
byte-identical compatibility asset. Existing keys, sources, identity files,
configuration and data are preserved; unknown migration states are rejected
before mutation and checked again under APT's lock. Interactive confirmation
reads the controlling terminal, and the manager opens after installation when
one is available. --yes explicitly approves unattended installation and skips
the UI.

The supported initial applications use local iAgent and AGOS APIs. Installation
does not create owner model routes or grant application access. Live readiness
is reported by the component runtimes after owner configuration. Namespace
APT/DPKG, bootstrap, package and protocol tests establish the reviewed package
behavior; they do not establish live fleet admission or reboot readiness.
Previous releases remain immutable.
