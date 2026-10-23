#!/usr/bin/env python3
"""Compare immutable fork revisions with one fixed Gungraun harness."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path('xtask/gungraun')
FIXTURE = Path('xtask/benchmark/benches/fixtures/rspack_sources/antd-mini/antd.min.js.map')


def run(*args, cwd=ROOT, env=None):
    return subprocess.check_output(args, cwd=cwd, env=env, text=True).strip()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def read_summaries(directory, baseline=False):
    cases = {}
    for path in sorted(directory.rglob('summary.json')):
        data = json.loads(path.read_text())
        if data['version'] != '7':
            raise ValueError(f'Unsupported summary schema: {path}')
        identity = data['module_path'] + '::' + data.get('id', '')
        profiles = [p for p in data['profiles'] if p['tool'] == 'Callgrind']
        if identity in cases or len(profiles) != 1:
            raise ValueError(f'Duplicate case or missing Callgrind profile: {identity}')
        values = profiles[0]['data']['total']['metrics']['Ir']['values']
        count = values.get('new')
        if type(count) is not int or count <= 0:
            raise ValueError(f'Missing or invalid instruction count: {identity}')
        if not baseline and (data['baselines'][1] != 'base' or not values.get('old')):
            raise ValueError(f'Missing base comparison: {identity}')
        cases[identity] = values
    if not cases:
        raise ValueError('No benchmark cases matched; no performance comparison was produced')
    return cases


def compare(base, head):
    if base.keys() != head.keys():
        raise ValueError('Base/head benchmark identities differ')
    rows = []
    for case in sorted(base):
        before, after = base[case]['new'], head[case]['new']
        if head[case]['old'] != before:
            raise ValueError(f'Baseline count does not match: {case}')
        rows.append(dict(case=case, base=before, head=after,
                         change_percent=100 * (after / before - 1)))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--filter', default='')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    for sha in (args.base, args.head):
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            parser.error('base and head must be full lowercase commit SHAs')
        subprocess.run(['git', 'fetch', '--no-tags', 'origin', sha], cwd=ROOT, check=True)
        if run('git', 'rev-parse', f'{sha}^{{commit}}') != sha:
            parser.error('revision does not resolve to the requested commit')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    toolchain = tomllib.loads((ROOT / 'rust-toolchain.toml').read_text())['toolchain']['channel']
    harness_files = [ROOT / HARNESS / 'Cargo.toml', ROOT / HARNESS / 'Cargo.lock',
                     *sorted((ROOT / HARNESS / 'benches').rglob('*.rs')), ROOT / FIXTURE,
                     ROOT / 'rust-toolchain.toml', ROOT / '.cargo/config.toml']
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in harness_files}
    env = dict(os.environ, RUSTUP_TOOLCHAIN=toolchain, CARGO_INCREMENTAL='0',
               GUNGRAUN_COLOR='never', CARGO_TARGET_DIR=str(output / 'target'))
    metadata = dict(schema_version=1, repository=os.environ.get('GITHUB_REPOSITORY'),
                    run_id=os.environ.get('GITHUB_RUN_ID'),
                    run_url=f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', 'kdy1/rspack')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}",
                    workflow_sha=run('git', 'rev-parse', 'HEAD'),
                    base_sha=args.base, head_sha=args.head, filter=args.filter,
                    harness_files=hashes, architecture=platform.machine(),
                    platform=platform.platform(), cpu=run('lscpu'),
                    rustc=run('rustc', '-Vv', env=env),
                    runner=run('gungraun-runner', '--version'),
                    valgrind=run('valgrind', '--version'),
                    allocator='system', profile='bench, debug=1', features=[],
                    environment={k: env.get(k) for k in
                                 ('RUSTFLAGS', 'GLIBC_TUNABLES', 'CARGO_INCREMENTAL')},
                    status='running')
    write_json(output / 'metadata.json', metadata)
    home = output / 'profiles'
    try:
        with tempfile.TemporaryDirectory(prefix='rspack-gungraun-') as temp:
            source = Path(temp) / 'source'
            subprocess.run(['git', 'worktree', 'add', '--detach', str(source), args.base],
                           cwd=ROOT, check=True)
            try:
                for label, sha in [('base', args.base), ('head', args.head)]:
                    subprocess.run(['git', 'checkout', '--detach', '--force', sha],
                                   cwd=source, check=True)
                    # Freeze build flags as well as the toolchain, without replacing product files.
                    if (source / '.cargo/config.toml').read_bytes() != (ROOT / '.cargo/config.toml').read_bytes():
                        raise ValueError('Cargo configuration differs from the workflow revision')
                    destination = source / HARNESS
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(ROOT / HARNESS, destination,
                                    ignore=shutil.ignore_patterns('target', '__pycache__'))
                    (source / FIXTURE).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / FIXTURE, source / FIXTURE)
                    command = ['cargo', 'bench', '--locked', '--manifest-path',
                               str(HARNESS / 'Cargo.toml'), '--bench', 'sources', '--',
                               f'--home={home}', '--save-summary=json']
                    command += ['--save-baseline=base'] if label == 'base' else ['--baseline=base']
                    if args.filter:
                        command.append(args.filter)
                    with (output / f'{label}.log').open('w') as log:
                        result = subprocess.run(command, cwd=source, env=env,
                                                stdout=log, stderr=subprocess.STDOUT)
                    print((output / f'{label}.log').read_text(), flush=True)
                    result.check_returncode()
                    snapshots = output / label
                    for summary in home.rglob('summary.json'):
                        target = snapshots / summary.relative_to(home)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(summary, target)
                        # Prevent a head filter mismatch from reusing stale base summaries.
                        summary.unlink()
                    read_summaries(snapshots, baseline=label == 'base')
            finally:
                subprocess.run(['git', 'worktree', 'remove', '--force', str(source)],
                               cwd=ROOT, check=True)
        rows = compare(read_summaries(output / 'base', baseline=True),
                       read_summaries(output / 'head'))
        write_json(output / 'comparison.json', rows)
        report = ['# Gungraun instruction counts', '',
                  f'Base: `{args.base}`; head: `{args.head}`', '',
                  '| Case | Base Ir | Head Ir | Change |', '| --- | ---: | ---: | ---: |']
        report += [f"| {r['case']} | {r['base']} | {r['head']} | {r['change_percent']:+.3f}% |"
                   for r in rows]
        report += ['', 'Negative change means fewer instructions, not a wall-time speedup.',
                   'Performance thresholds do not fail this reporting-only job.']
        (output / 'summary.md').write_text('\n'.join(report) + '\n')
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                summary.write((output / 'summary.md').read_text())
        metadata['status'] = 'complete'
    except Exception as error:
        metadata.update(status='failed', error=str(error))
        raise
    finally:
        write_json(output / 'metadata.json', metadata)
        # Keep profiles and summaries, not compiled binaries, in the artifact.
        shutil.rmtree(output / 'target', ignore_errors=True)


if __name__ == '__main__':
    main()
