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
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'xtask/gungraun'))
from prepare import prepare

ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path('xtask/gungraun')
FIXTURE = Path('xtask/benchmark/benches/fixtures/rspack_sources/antd-mini/antd.min.js.map')
SUITES = ('sources', 'all', 'benches', 'rspack_sources', 'walltime')


def select_catalog(catalog, name_filter):
    selected = [case for case in catalog if name_filter in case[1]]
    if not selected:
        raise ValueError('No benchmark cases matched; no performance comparison was produced')
    identities = [(entry.replace('/', '_'), re.sub(r'[^a-zA-Z0-9]', '_', name))
                  for entry, name in selected]
    if len(set(identities)) != len(identities):
        raise ValueError('Benchmark IDs collide after Gungraun normalization')
    if any(len(entry) > 120 or len(name) > 120 for entry, name in identities):
        raise ValueError('Benchmark ID exceeds Gungraun limit')
    return selected


def build_features(artifacts):
    features = {}
    for artifact in artifacts:
        features.setdefault(artifact['package_id'], set()).add(tuple(sorted(artifact['features'])))
    # A package can be compiled with different host/target feature sets. Preserve
    # each set without depending on Cargo's parallel artifact emission order.
    return {package: [list(config) for config in sorted(configs)]
            for package, configs in sorted(features.items())}


def build_executable(command, target, source, env, log):
    with log.open('w') as stderr:
        result = subprocess.run(command, cwd=source, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=stderr)
    log.with_suffix('.jsonl').write_text(result.stdout)
    result.check_returncode()
    artifacts = [message for line in result.stdout.splitlines()
                 if (message := json.loads(line)).get('reason') == 'compiler-artifact']
    executables = [message['executable'] for message in artifacts
                   if message['target']['name'] == target
                   and message.get('executable')]
    if len(executables) != 1:
        raise ValueError('Expected exactly one current benchmark executable')
    return executables[0], build_features(artifacts)


def build_driver(source, env, log):
    command = ['cargo', 'bench', '--locked', '-p', 'rspack_benchmark', '--features', 'gungraun',
               '--bench', 'gungraun_driver', '--profile', 'codspeed', '--no-run',
               '--message-format=json']
    return build_executable(command, 'gungraun_driver', source, env, log)


def run(*args, cwd=ROOT, env=None):
    return subprocess.check_output(args, cwd=cwd, env=env, text=True).strip()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def preserve_binary(executable, destination):
    executable = Path(executable)
    sections = run('readelf', '--sections', '--wide', str(executable))
    if '.debug_info' not in sections or '.symtab' not in sections:
        raise ValueError(f'Measured executable lacks debug information or symbols: {executable}')
    shutil.copyfile(executable, destination)
    destination.with_suffix('.sections.txt').write_text(sections + '\n')
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def annotate_profiles(home, destination, baseline=False):
    destination.mkdir(parents=True, exist_ok=True)
    profiles = [p for p in sorted(home.rglob('callgrind.*'))
                if p.is_file() and '.out' in p.name
                and (baseline or '.base@' not in p.name)]
    if not profiles:
        raise ValueError('No current Callgrind profiles to annotate')
    for profile in profiles:
        relative = profile.relative_to(home)
        for inclusive in ('no', 'yes'):
            report = destination / relative.with_name(relative.name + f'.inclusive-{inclusive}.txt')
            report.parent.mkdir(parents=True, exist_ok=True)
            with report.open('w') as output:
                subprocess.run(['callgrind_annotate', '--show=Ir', '--sort=Ir',
                                '--threshold=100', '--auto=no', '--tree=both',
                                f'--inclusive={inclusive}', str(profile)],
                               stdout=output, check=True)


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
    parser.add_argument('--suite', choices=SUITES, default='sources')
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
    if args.suite != 'sources':
        harness_files += [ROOT / HARNESS / 'prepare.py', ROOT / HARNESS / 'workspace.Cargo.lock',
                          *sorted((ROOT / HARNESS / 'driver').rglob('*.rs')),
                          ROOT / 'scripts/bench/setup.mjs', ROOT / 'xtask/benchmark/Cargo.toml',
                          *sorted(p for p in (ROOT / 'xtask/benchmark').rglob('*')
                                  if p.is_file() and 'gungraun_generated' not in p.parts
                                  and p.suffix in ('.rs', '.json', '.js', '.map', '.css', '.toml'))]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in harness_files}
    env = dict(os.environ, RUSTUP_TOOLCHAIN=toolchain, CARGO_INCREMENTAL='0',
               GUNGRAUN_COLOR='never', CARGO_TARGET_DIR=str(output / 'target'))
    if args.suite != 'sources':
        env.update(BENCH_MODE='simulation', RAYON_NUM_THREADS='1', MIMALLOC_PURGE_DELAY='-1')
        fixture_root = Path(env['RSPACK_BENCHCASES_DIR'])
        if not fixture_root.is_absolute() or not fixture_root.is_dir():
            raise ValueError('RSPACK_BENCHCASES_DIR must identify prepared absolute fixture directory')
        actual_fixture_sha = run('git', 'rev-parse', 'HEAD', cwd=fixture_root)
        if actual_fixture_sha != env.get('GUNGRAUN_FIXTURE_SHA'):
            raise ValueError('Benchmark fixture revision differs from pinned workflow input')
    metadata = dict(schema_version=1, repository=os.environ.get('GITHUB_REPOSITORY'),
                    run_id=os.environ.get('GITHUB_RUN_ID'),
                    run_url=f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', 'kdy1/rspack')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}",
                    workflow_sha=run('git', 'rev-parse', 'HEAD'),
                    base_sha=args.base, head_sha=args.head, filter=args.filter, suite=args.suite,
                    harness_files=hashes, architecture=platform.machine(),
                    platform=platform.platform(), cpu=run('lscpu'),
                    rustc=run('rustc', '-Vv', env=env),
                    runner=run('gungraun-runner', '--version'),
                    valgrind=run('valgrind', '--version'),
                    allocator='system' if args.suite == 'sources' else 'NeverGrowInPlaceAllocator<mimalloc>',
                    profile='bench, debug=1' if args.suite == 'sources' else 'codspeed',
                    features=[] if args.suite == 'sources' else ['gungraun', 'existing benchmark dev-dependency features'],
                    threads='synchronous' if args.suite == 'sources' else 'Tokio current-thread, blocking=8, Rayon=1; all threads instrumented',
                    fixture_revision=os.environ.get('GUNGRAUN_FIXTURE_SHA'),
                    fixture_lock_sha256=None if args.suite == 'sources' else hashlib.sha256(
                        (fixture_root / 'pnpm-lock.yaml').read_bytes()).hexdigest(),
                    environment={k: env.get(k) for k in
                                 ('RUSTFLAGS', 'GLIBC_TUNABLES', 'CARGO_INCREMENTAL', 'CARGO_BUILD_JOBS', 'BENCH_MODE',
                                  'RAYON_NUM_THREADS', 'MIMALLOC_PURGE_DELAY', 'RSPACK_BENCHCASES_DIR')},
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
                    if args.suite != 'sources' and (source / 'Cargo.toml').read_bytes() != (ROOT / 'Cargo.toml').read_bytes():
                        raise ValueError('Workspace dependencies or build profiles differ from the workflow revision')
                    destination = source / HARNESS
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(ROOT / HARNESS, destination,
                                    ignore=shutil.ignore_patterns('target', '__pycache__'))
                    (source / FIXTURE).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / FIXTURE, source / FIXTURE)
                    target = 'sources'
                    if args.suite == 'sources':
                        executable, features = build_executable(
                            ['cargo', 'bench', '--locked', '--manifest-path', str(HARNESS / 'Cargo.toml'),
                             '--bench', 'sources', '--no-run', '--message-format=json'],
                            'sources', source, env, output / f'{label}-build.log')
                        metadata[f'{label}_binary_sha256'] = preserve_binary(
                            executable, output / f'{label}-sources')
                        metadata[f'{label}_build_features'] = features
                        if label == 'head' and features != metadata['base_build_features']:
                            raise ValueError('Base/head Cargo build features differ')
                    if args.suite != 'sources':
                        prepare(ROOT, source)
                        shutil.copyfile(ROOT / HARNESS / 'workspace.Cargo.lock', source / 'Cargo.lock')
                        driver, features = build_driver(source, env, output / f'{label}-build.log')
                        metadata[f'{label}_binary_sha256'] = preserve_binary(
                            driver, output / f'{label}-driver')
                        metadata[f'{label}_build_features'] = features
                        if label == 'head' and features != metadata['base_build_features']:
                            raise ValueError('Base/head Cargo build features differ')
                        discovery = run(driver, '--list', args.suite, cwd=source, env=env)
                        (output / f'{label}-discovery.log').write_text(discovery)
                        catalogs = [line.removeprefix('GUNGRAUN_CATALOG=') for line in discovery.splitlines()
                                    if line.startswith('GUNGRAUN_CATALOG=')]
                        if len(catalogs) != 1:
                            raise ValueError('Expected exactly one benchmark catalog')
                        catalog = select_catalog(json.loads(catalogs[0]), args.filter)
                        catalog_path = output / f'{label}-catalog.json'
                        write_json(catalog_path, catalog)
                        if label == 'head' and catalog != json.loads((output / 'base-catalog.json').read_text()):
                            raise ValueError('Base/head benchmark catalogs differ')
                        env.update(RSPACK_GUNGRAUN_DRIVER=driver, RSPACK_GUNGRAUN_CATALOG=str(catalog_path))
                        metadata[f'{label}_catalog'] = catalog
                        target = 'portfolio'
                    command = ['cargo', 'bench', '--locked', '--manifest-path',
                               str(HARNESS / 'Cargo.toml'), '--bench', target, '--',
                               f'--home={home}', '--save-summary=json']
                    command += ['--save-baseline=base'] if label == 'base' else ['--baseline=base']
                    if args.filter and args.suite == 'sources':
                        command.append(args.filter)
                    with (output / f'{label}.log').open('w') as log:
                        result = subprocess.run(command, cwd=source, env=env,
                                                stdout=log, stderr=subprocess.STDOUT)
                    print((output / f'{label}.log').read_text(), flush=True)
                    result.check_returncode()
                    annotate_profiles(home, output / f'{label}-annotations', baseline=label == 'base')
                    snapshots = output / label
                    for summary in home.rglob('summary.json'):
                        target = snapshots / summary.relative_to(home)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(summary, target)
                        # Prevent a head filter mismatch from reusing stale base summaries.
                        summary.unlink()
                    summaries = read_summaries(snapshots, baseline=label == 'base')
                    if args.suite != 'sources' and len(summaries) != len(catalog):
                        raise ValueError('Measured case count differs from selected catalog')
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
        # Exact measured executables were copied above; remove intermediate build files.
        shutil.rmtree(output / 'target', ignore_errors=True)


if __name__ == '__main__':
    main()
