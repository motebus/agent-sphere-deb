# Embedded verbatim in agpc.sh; defining these functions performs no mutation.
agentsphere_job_platform_check() {
    command -v systemd-run >/dev/null && command -v systemctl >/dev/null || return 1
    python3 - <<'JOB_PLATFORM'
import os, stat, sys
try:
    for path in ('/', '/var', '/var/lib', '/run', '/run/systemd/system'):
        value=os.lstat(path)
        assert stat.S_ISDIR(value.st_mode) and value.st_uid==0 and not value.st_mode&0o022
except (AssertionError, OSError):
    sys.exit('Detached installation requires running systemd and trusted root-owned directories.')
JOB_PLATFORM
}

agentsphere_run_detached() {
    local stage worker_guard worker_obsidian unit result code count state argument
    stage=$job_stage
    [[ $stage =~ ^/var/lib/agpc-install\.[A-Za-z0-9]{8}$ ]] || return 1
    python3 - "$stage" <<'AGPC_STAGE' || return
import os,stat,sys
m=os.lstat(sys.argv[1])
assert stat.S_ISDIR(m.st_mode) and m.st_uid==0 and m.st_gid==0 and stat.S_IMODE(m.st_mode)==0o700
assert not os.listdir(sys.argv[1])
AGPC_STAGE
    worker_guard=$stage/guard
    worker_obsidian=$stage/obsidian_1.13.7_amd64.deb
    # The existing temporary inputs are root-owned; copy into the durable root
    # stage so caller exit/cleanup cannot remove inputs from the detached job.
    cp -- "$guard" "$worker_guard" || return
    cp -- "$obsidian" "$worker_obsidian" || return
    chmod 0700 "$worker_guard" || return
    chmod 0600 "$worker_obsidian" || return
    write_ssh_readiness_helper > "$stage/ssh-readiness.py" || return
    {
        printf '%s\n' '#!/bin/bash' 'set -euo pipefail' 'umask 077' 'export LC_ALL=C' 'export PATH=/usr/sbin:/usr/bin:/sbin:/bin'
        printf 'stage=%q\n' "$stage"
        printf 'guard=%q\n' "$worker_guard"
        printf 'packages=('
        for argument in "${packages[@]}"; do
            [[ $argument != "$obsidian" ]] || argument=$worker_obsidian
            printf '%q ' "$argument"
        done
        printf ')\n'
        cat <<'AGPC_WORKER'
phase=inputs
finish() {
    code=$?
    trap - EXIT
    python3 - "$stage" "$code" "$phase" <<'AGPC_RESULT' || { [[ $code != 0 ]] || code=1; }
import json, os, sys
stage, code, phase=sys.argv[1:]
body={'schema':'agpc.detached-install-result/v1','exit_code':int(code),'phase':phase,
      'packages_verified':phase in ('ssh','complete'),'ssh_ready':phase=='complete',
      'mote_reachability':'not-tested','full_runtime_ready':False}
path=stage+'/result.json.tmp'
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as file:
    json.dump(body,file,sort_keys=True);file.write('\n');file.flush();os.fsync(file.fileno())
os.rename(path,stage+'/result.json')
fd=os.open(stage,os.O_RDONLY|os.O_DIRECTORY)
try:os.fsync(fd)
finally:os.close(fd)
AGPC_RESULT
    exit "$code"
}
trap finish EXIT
sha256sum --check --status "$stage/inputs.sha256"
phase=apt
apt-get -o "DPkg::Pre-Install-Pkgs::=$guard" \
    -o "DPkg::Tools::Options::$guard::Version=3" \
    -o "DPkg::Tools::Options::$guard::InfoFD=0" \
    -o 'Dpkg::Options::=--force-confold' --yes install "${packages[@]}" </dev/null
phase=package-verification
apt-get check
dpkg --audit > "$stage/dpkg-audit.txt"
test ! -s "$stage/dpkg-audit.txt"
python3 - "${packages[@]}" > "$stage/packages.json" <<'AGPC_PACKAGES'
import json,subprocess,sys
records=[]
for argument in sys.argv[1:]:
    if not argument.startswith(('agent-sphere=','agent-ultra=','agpc-manager=','agent-apps=')):continue
    name, version=argument.split('=',1)
    fields=subprocess.check_output(['dpkg-query','-W','-f=${Version}\n${Status}',name],text=True).splitlines()
    if fields!=[version,'install ok installed']:sys.exit('Expected AGPC entry package is not fully configured: '+name)
    records.append({'name':name,'version':version,'configured':True})
assert len(records)==4
print(json.dumps({'schema':'agpc.installed-entries/v1','packages':records,'full_runtime_ready':False},sort_keys=True))
AGPC_PACKAGES
phase=ssh
if python3 "$stage/ssh-readiness.py" --ensure > "$stage/ssh.json"; then
    :
else
    code=$?
    cat "$stage/ssh.json"
    exit "$code"
fi
phase=complete
AGPC_WORKER
    } > "$stage/worker" || return
    chmod 0600 "$stage/worker" "$stage/ssh-readiness.py" || return
    sha256sum "$stage/guard" "$stage/worker" "$stage/ssh-readiness.py" "$worker_obsidian" > "$stage/inputs.sha256" || return
    chmod 0600 "$stage/inputs.sha256" || return
    unit=agpc-install-${stage##*.}
    printf 'Installation job: %s\nLog: %s/install.log\nResult: %s/result.json\n' "$unit" "$stage" "$stage"
    # No PTY/session binding: systemd owns the worker independently of this SSH
    # caller. The caller never removes its durable stage or stops its unit.
    systemd-run --quiet --no-block --unit="$unit" --service-type=exec \
        --property=UMask=0077 --property="StandardOutput=append:$stage/install.log" \
        --property=StandardError=inherit -- /bin/bash "$stage/worker" || return
    trap 'printf "Installation continues independently; inspect %s/result.json and %s/install.log.\n" "$stage" "$stage" >&2; exit 130' INT TERM HUP
    for ((count=0; count<3600; count++)); do
        if [[ -f $stage/result.json && ! -L $stage/result.json ]]; then
            code=$(python3 - "$stage/result.json" <<'AGPC_OBSERVE'
import json,os,stat,sys
fd=os.open(sys.argv[1],os.O_RDONLY|os.O_NOFOLLOW)
with os.fdopen(fd) as file:
    st=os.fstat(file.fileno());assert stat.S_ISREG(st.st_mode) and st.st_uid==0 and st.st_gid==0 and st.st_nlink==1 and not st.st_mode&0o077 and st.st_size<=4096
    result=json.load(file)
assert result['schema']=='agpc.detached-install-result/v1' and type(result['exit_code']) is int and 0<=result['exit_code']<=255
print(result['exit_code'])
AGPC_OBSERVE
            ) || return
            trap - INT TERM HUP
            if [[ $code != 0 ]]; then
                printf 'Installation job failed (exit %s); retained log: %s/install.log\n' "$code" "$stage" >&2
                tail -n 8 "$stage/install.log" >&2
            fi
            return "$code"
        fi
        state=$(systemctl show "$unit" --property=ActiveState --value) || state=unknown
        if ((count>2)) && [[ $state == failed || $state == inactive || $state == unknown || -z $state ]]; then
            trap - INT TERM HUP
            printf 'Installation result is unavailable; inspect %s/install.log and systemd unit %s.\n' "$stage" "$unit" >&2
            return 1
        fi
        sleep 1
    done
    trap - INT TERM HUP
    printf 'Installation is still running; inspect %s/result.json. The worker was not interrupted.\n' "$stage" >&2
    return 1
}
