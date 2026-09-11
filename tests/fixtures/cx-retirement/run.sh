#!/bin/bash
# Empty, network-isolated namespace. No host package database or services.
set -euo pipefail
[ "$#" -eq 5 ] || { echo 'usage: both|disabled|masked new.deb old-mesh.deb historical.deb old1.deb' >&2; exit 2; }
scenario=$1
source_root=$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)
: "${TMPDIR:?set a short workspace TMPDIR}"
fixture_tmp=$(mktemp -d "$TMPDIR/cx-apt.XXXXXX")
trap 'rm -rf "$fixture_tmp"' EXIT
args=(--unshare-all --die-with-parent --uid 0 --gid 0 --tmpfs / --dir /usr --tmpfs /usr/bin --tmpfs /usr/lib --dir /usr/lib/systemd --dir /usr/lib/tmpfiles.d --ro-bind /usr/lib64 /usr/lib64 --symlink usr/bin /bin --symlink usr/sbin /sbin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --tmpfs /usr/sbin --tmpfs /usr/libexec --tmpfs /usr/share --ro-bind /usr/share/dpkg /usr/share/dpkg --ro-bind /usr/share/perl5 /usr/share/perl5 --ro-bind /usr/share/perl /usr/share/perl --dir /etc --dir /var/lib/dpkg --dir /run --proc /proc --dev /dev)
for entry in /usr/lib/*; do
 case "$entry" in /usr/lib/systemd|/usr/lib/tmpfiles.d) continue ;; esac
 args+=(--ro-bind "$entry" "$entry")
done
for tool in gpg curl realpath bash sh dash python3 perl apt-get apt-mark dpkg dpkg-deb dpkg-query dpkg-split dpkg-divert stat chmod chown install mkdir mktemp mv rm cp ln cat sha256sum md5sum touch id readlink true false dirname gzip xz tar cmp sed grep cut find diff awk tr getent wc hostname deb-systemd-helper deb-systemd-invoke; do
 args+=(--ro-bind "/usr/bin/$tool" "/usr/bin/$tool")
done
args+=(--ro-bind /usr/sbin/ldconfig /usr/sbin/ldconfig --ro-bind /usr/sbin/start-stop-daemon /usr/sbin/start-stop-daemon --ro-bind "$source_root/tests/fixtures/cx-retirement/fixture-systemctl.py" /usr/bin/systemctl --dir /packages --ro-bind "$(realpath "$2")" /packages/new.deb --ro-bind "$(realpath "$3")" /packages/old-mesh.deb --ro-bind "$(realpath "$4")" /packages/historical.deb --ro-bind "$(realpath "$5")" /packages/old1.deb --ro-bind /usr/lib/os-release /host-os-release --ro-bind "$source_root/tests/fixtures/medge-archive-keyring.gpg" /fixture-key.gpg --ro-bind "$source_root" /source --bind "$fixture_tmp" /tmp --setenv TMPDIR /tmp --setenv PATH /usr/bin:/bin:/usr/sbin:/sbin --chdir /tmp)
status=0
bwrap "${args[@]}" /bin/sh -eu -c 'touch /.cx-rename-fixture; python3 /source/tests/fixtures/cx-retirement/lifecycle.py "$1"' sh "$scenario" || status=$?
if [ -n "${FIXTURE_LOG_DIR:-}" ]; then
 shopt -s nullglob
 evidence=("$fixture_tmp/"*.json "$fixture_tmp/"*.log)
 if [ ${#evidence[@]} -gt 0 ]; then cp "${evidence[@]}" "$FIXTURE_LOG_DIR/"; fi
fi
exit "$status"
