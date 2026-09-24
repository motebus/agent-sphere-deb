#!/bin/bash
set -euo pipefail
export LC_ALL=C
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

usage() {
    cat <<'HELP'
Usage: uninstall.sh [--yes] [--help]
Remove native AGPC product packages while preserving configuration, Inbox/context
state, application data and protected topology. The script never purges packages,
runs autoremove, edits DPKG metadata, or removes Docker/OCI software.
HELP
}

yes=false
while (($#)); do
    case "$1" in
        --yes) yes=true ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done
[[ $(id -u) == 0 ]] || { printf '%s\n' 'Run uninstall.sh as root.' >&2; exit 1; }
[[ $(dpkg --print-architecture) == amd64 ]] || { printf '%s\n' 'Native AGPC uninstall supports amd64 only.' >&2; exit 1; }

# Remove only AGPC product packages. Dependency applications, user data,
# conffiles and retired ownership records remain available to a later install.
products=(agent-sphere agent-ultra agpc-manager agpc-apps agent-apps uchat uchatd contextd)
installed=()
for package in "${products[@]}"; do
    status=$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true)
    [[ $status != installed ]] || installed+=("$package")
done
if ((${#installed[@]} == 0)); then
    printf '%s\n' 'No installed native AGPC product packages were found. Preserved state was not changed.'
    exit 0
fi

plan=$(mktemp /var/tmp/agpc-uninstall-plan.XXXXXXXX)
trap 'rm -f -- "$plan"' EXIT
apt-get --simulate remove "${installed[@]}" > "$plan" || {
    cat "$plan"
    printf '%s\n' 'Unable to produce a safe AGPC removal plan. No package change was started.' >&2
    exit 1
}
cat "$plan"
declare -A allowed=()
for package in "${products[@]}"; do allowed[$package]=1; done
removed=0
while read -r action package rest; do
    [[ $action != Remv ]] || {
        name=${package%%:*}
        [[ -n ${allowed[$name]:-} ]] || {
            printf 'Refusing removal of non-AGPC package: %s\n' "$name" >&2
            exit 1
        }
        removed=$((removed + 1))
    }
done < "$plan"
((removed > 0)) || { printf '%s\n' 'APT did not plan an AGPC package removal.' >&2; exit 1; }

if ! $yes; then
    [[ -t 0 ]] || { printf '%s\n' 'Confirmation requires a terminal; rerun with --yes after reviewing the plan.' >&2; exit 1; }
    read -r -p 'Proceed with the displayed native AGPC removal plan? [y/N] ' answer
    [[ $answer == y || $answer == Y ]] || { printf '%s\n' 'Uninstall cancelled.'; exit 1; }
fi

stage=$(mktemp -d /var/lib/agpc-uninstall.XXXXXXXX)
chmod 0700 "$stage"
printf '%s\n' "${installed[@]}" > "$stage/packages"
chmod 0600 "$stage/packages"
worker=$stage/worker.sh
cat > "$worker" <<'WORKER'
#!/bin/bash
set -euo pipefail
export LC_ALL=C PATH=/usr/sbin:/usr/bin:/sbin:/bin
stage=${1:?}
mapfile -t packages < "$stage/packages"
code=0
apt-get --yes remove "${packages[@]}" > "$stage/uninstall.log" 2>&1 || code=$?
python3 - "$stage" "$code" <<'RESULT'
import json, os, sys
stage, code = sys.argv[1], int(sys.argv[2])
body = {"schema":"agpc.native-uninstall-result/v1", "exit_code":code,
        "packages_removed":code == 0, "data_preserved":True,
        "purge_performed":False, "autoremove_performed":False}
tmp=stage+'/result.json.tmp'
fd=os.open(tmp, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
with os.fdopen(fd,'w') as out:
    json.dump(body,out,sort_keys=True);out.write('\n');out.flush();os.fsync(out.fileno())
os.rename(tmp,stage+'/result.json')
RESULT
exit "$code"
WORKER
chmod 0700 "$worker"
unit=agpc-uninstall-$(basename "$stage" | cut -d. -f2)
systemd-run --quiet --collect --wait --unit "$unit" "$worker" "$stage" || {
    cat "$stage/uninstall.log" >&2 || true
    printf 'Native AGPC uninstall failed; inspect %s/result.json and uninstall.log.\n' "$stage" >&2
    exit 1
}
cat "$stage/result.json"
printf '%s\n' 'Native AGPC packages removed. Configuration, data and protected topology were preserved.'
printf '%s\n' 'You can now install with: curl -fsSL https://motebus.github.io/download/agpc-all.sh | sudo bash'
