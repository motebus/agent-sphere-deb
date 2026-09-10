Agent Sphere 0.2.0-5 makes the final installation transaction independent of the
invoking SSH session. After the reviewed plan is confirmed, a systemd job runs
APT and the final checks using root-private, hash-bound inputs. Durable logs and
an atomic result retain the original exit status, including failures. The
installer prints recovery paths and never launches the manager automatically.

The final check validates the installed OpenSSH configuration, preserves the
existing socket/service activation choice, enables and starts that valid path,
and requires an SSH banner from the existing local MoteD target 127.0.0.1:22.
Service masks and invalid owner configuration cause a visible failure. Keys,
authentication, listener settings and firewall rules remain unchanged; the check
does not establish external Mote reachability or full runtime readiness.

All native component versions and reviewed migration contracts remain unchanged,
including genuine obsolete CX6 ownership and native residual/repeat handling.
The durable job directory is created before migration snapshots, so its creation
does not invalidate their protected parent metadata. APT and the existing
protocol-v3 guard remain responsible for the exact package transaction.

Validation distinguishes actual isolated Linux caller/worker behavior and
OpenSSH configuration/banner checks from fixture systemd/package observations.
Privileged CI must pass the real daemon/banner gate. No live host rollout,
reboot acceptance, O/error-report delivery or Telegram event is included.
Canonical downloads change only with the matching signed aggregate release.
