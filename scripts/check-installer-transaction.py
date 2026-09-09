#!/usr/bin/env python3
"""Offline real APT/DPKG checks in a disposable user namespace, never the host."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(args, success=True, env=None):
    result = subprocess.run(args, capture_output=True, text=True, env=dict(os.environ, LC_ALL='C', **(env or {})))
    if (result.returncode == 0) != success:
        raise AssertionError(f'{args}: {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result.stdout + result.stderr


def package(base, name, version, conflicts=None):
    tree = base / ('tree-' + name)
    control = tree / 'DEBIAN'
    control.mkdir(parents=True)
    (control / 'control').write_text(
        f'Package: {name}\nVersion: {version}\nArchitecture: all\n'
        'Maintainer: Test Fixture <test@example.invalid>\nDescription: Offline transaction fixture\n'
        + (f'Conflicts: {conflicts}\n' if conflicts else ''))
    output = base / f'{name}_{version}_all.deb'
    run(['dpkg-deb', '--build', '--root-owner-group', str(tree), str(output)])
    return str(output)


def in_namespace():
    base = Path('/tmp/fixture')
    assert os.geteuid() == 0 and (base / 'namespace-marker').read_text() == 'agent-computer-apt-fixture'
    guard = base / 'guard'
    text = (ROOT / 'agent-sphere-apps.sh').read_text()
    guard.write_text(text.split("<<'GUARD'\n", 1)[1].split('\nGUARD\n', 1)[0] + '\n')
    guard.chmod(0o700)
    evidence = []
    for scenario in ('vault-rename', 'unrelated-removal', 'chatd-removal'):
        case = base / scenario
        case.mkdir()
        root = case / 'root'
        admin = root / 'var/lib/dpkg'
        admin.mkdir(parents=True)
        (admin / 'status').touch()
        (admin / 'updates').mkdir()
        cache = case / 'cache'
        (cache / 'archives/partial').mkdir(parents=True)
        etc = case / 'etc'
        (etc / 'sources.list.d').mkdir(parents=True)
        (etc / 'apt.conf.d').mkdir()
        (etc / 'preferences.d').mkdir()
        (etc / 'sources.list').touch()
        (case / 'log').mkdir()
        apt_config = case / 'apt.conf'
        apt_config.write_text(f'Dir::Etc "{etc}";\n')
        oldname = 'mote-chatd' if scenario == 'chatd-removal' else 'mote-sync'
        old = package(case, oldname, '2.0.0-4' if scenario == 'chatd-removal' else '1.1.0-2')
        keeper = package(case, 'fixture-keeper', '1.0')
        new = package(case, 'mote-vault-sync', '1.1.0-3',
                      oldname + (', fixture-keeper' if scenario == 'unrelated-removal' else ''))
        run(['dpkg', '--root=' + str(root), '--log=' + str(case / 'dpkg.log'), '--install', old, keeper])
        before = (admin / 'status').read_bytes()
        args = ['apt-get', '--yes', '-o', 'Dir::Etc=' + str(etc),
                '-o', 'Dir::State=' + str(case / 'state'),
                '-o', 'Dir::State::status=' + str(admin / 'status'),
                '-o', 'Dir::Cache=' + str(cache), '-o', 'Dir::Log=' + str(case / 'log'),
                '-o', 'APT::Architecture=amd64', '-o', 'APT::Sandbox::User=root',
                '-o', 'DPkg::Options::=--root=' + str(root),
                '-o', 'DPkg::Options::=--log=' + str(case / 'dpkg.log'),
                '-o', 'DPkg::Pre-Install-Pkgs::=' + str(guard),
                '-o', 'DPkg::Tools::Options::' + str(guard) + '::Version=3',
                '-o', 'DPkg::Tools::Options::' + str(guard) + '::InfoFD=0',
                'install', new]
        accepted = scenario == 'vault-rename'
        output = run(args, success=accepted, env={'APT_CONFIG': str(apt_config)})
        (case / 'apt.log').write_text(output)
        status = run(['dpkg-query', '--admindir=' + str(admin), '-W', '-f=${binary:Package}\t${db:Status-Abbrev}\n'])
        if accepted:
            assert 'mote-vault-sync\tii ' in status, status
            assert 'fixture-keeper\tii ' in status, status
            assert 'mote-sync\tii ' not in status, status
        else:
            rejected = 'mote-chatd' if scenario == 'chatd-removal' else 'fixture-keeper'
            assert 'transaction refused: removal of ' + rejected in output, output
            assert (admin / 'status').read_bytes() == before, 'DPKG state changed before guard rejection'
        evidence.append({'scenario': scenario, 'passed': True, 'actual_apt_dpkg': True,
                         'host_modified': False, 'status': status})
    (base / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


def main():
    if sys.argv[1:] == ['--inside-namespace']:
        in_namespace()
        return
    if not shutil.which('bwrap'):
        raise SystemExit('bubblewrap is required for isolated real APT verification')
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='apt-transaction-', dir=ROOT / 'build') as directory:
        temporary = Path(directory)
        (temporary / 'namespace-marker').write_text('agent-computer-apt-fixture')
        output = run(['bwrap', '--unshare-all', '--uid', '0', '--gid', '0',
                      '--ro-bind', '/', '/', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                      '--bind', str(temporary), '/tmp/fixture',
                      sys.executable, str(Path(__file__).resolve()), '--inside-namespace'])
        print(output)
        shutil.copyfile(temporary / 'evidence.json', ROOT / 'build/apt-transaction-evidence.json')
        for log in temporary.glob('*/apt.log'):
            shutil.copyfile(log, ROOT / 'build' / ('apt-' + log.parent.name + '.log'))

if __name__ == '__main__':
    main()
