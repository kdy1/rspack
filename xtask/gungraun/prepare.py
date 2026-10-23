"""Overlay fixed benchmark plumbing without replacing production sources."""

from pathlib import Path
import re
import shutil


def adapt(text):
    # The existing routines retain setup, assertions, and measured closures verbatim.
    text = re.sub(r'use criterion::criterion_group;\n', '', text)
    text = re.sub(r'criterion_(?:group|main)!\([^;]*\);', '', text, flags=re.S)
    text = text.replace(', criterion_group, criterion_main', '')
    return text.replace('rspack_benchmark::Criterion', 'crate::adapter::Criterion').replace(
        'criterion::', 'crate::adapter::')


def prepare(workflow, source):
    benchmark = source / 'xtask/benchmark'
    fixed = workflow / 'xtask/benchmark'
    # Benchmark code and fixtures are harness inputs, never production implementations.
    if benchmark.resolve() != fixed.resolve():
        shutil.rmtree(benchmark)
        shutil.copytree(fixed, benchmark, ignore=shutil.ignore_patterns('target', 'gungraun_generated'))
    destination = benchmark / 'benches/gungraun_generated'
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir()
    for directory in ('groups', 'cases', 'stages', 'build_chunk_graph'):
        original = fixed / ('benches' if directory in ('groups', 'build_chunk_graph') else '') / directory
        shutil.copytree(original, destination / directory)
    for path in destination.rglob('*.rs'):
        path.write_text(adapt(path.read_text()))
    with (destination / 'groups/mod.rs').open('a') as file:
        file.write('\npub mod rspack_sources;\n')
    with (destination / 'groups/bundle.rs').open('a') as file:
        file.write('\npub mod threejs_10x;\n')
    walltime = (fixed / 'benches/walltime.rs').read_text()
    walltime = re.sub(r'#\[path = "walltime_groups/mod.rs"\]\nmod groups;', '', walltime)
    walltime = walltime.replace('fn threejs_10x_bundle_benchmark', 'pub fn threejs_10x_bundle_benchmark')
    (destination / 'walltime.rs').write_text(adapt(walltime))
    shutil.copyfile(workflow / 'xtask/gungraun/driver/adapter.rs', destination / 'adapter.rs')
    entries = []
    main = (fixed / 'benches/benches.rs').read_text().split('criterion_main!(', 1)[1]
    for family, name in re.findall(r'(cases|stages)::(\w+)::(?:case|stage)', main):
        entries.append((f'{family}/{name}', f'{family}::{name}::bench', 'benches'))
    entries += [('rspack_sources', 'groups::rspack_sources::rspack_sources_benchmark', 'rspack_sources'),
                ('walltime', 'walltime::threejs_10x_bundle_benchmark', 'walltime')]
    registry = ',\n'.join(f'("{entry}", {function}, "{suite}")' for entry, function, suite in entries)
    driver = '''#![allow(clippy::unwrap_used, dead_code)]
mod adapter;
mod groups;
mod cases;
mod stages;
mod walltime;

fn main() {
    rspack_benchmark::configure_rayon_for_benchmark();
    let args: Vec<String> = std::env::args().skip(1).collect();
    let listing = args.first().is_some_and(|arg| arg == "--list");
    assert_eq!(args.len(), 2, "usage: driver --list SUITE | driver ENTRY CASE");
    let mut criterion = adapter::Criterion {
        entry: String::new(), selected: if listing { None } else { Some(args[1].clone()) },
        cases: Vec::new(), measured: 0,
    };
    let entries: &[(&str, fn(&mut adapter::Criterion), &str)] = &[
REGISTRY
    ];
    for &(entry, register, suite) in entries {
        if (listing && (args[1] == "all" || args[1] == suite)) || (!listing && args[0] == entry) {
            criterion.entry = entry.to_owned();
            register(&mut criterion);
        }
    }
    if listing {
        assert!(!criterion.cases.is_empty(), "suite has no cases");
        println!("GUNGRAUN_CATALOG={}", serde_json::to_string(&criterion.cases).unwrap());
    } else {
        assert_eq!(criterion.measured, 1, "requested case must run exactly once");
    }
}
'''.replace('REGISTRY', registry)
    (destination / 'main.rs').write_text(driver)
    manifest = benchmark / 'Cargo.toml'
    text = manifest.read_text()
    if '\nname = "gungraun_driver"' not in text:
        text = text.replace('[features]', '[features]\ngungraun = []')
        text = text.replace('[dev-dependencies]', '[dev-dependencies]\ngungraun = { version = "=0.20.0", features = ["act"] }')
        text += '\n[[bench]]\nname = "gungraun_driver"\npath = "benches/gungraun_generated/main.rs"\nharness = false\n'
        manifest.write_text(text)
    library = benchmark / 'src/lib.rs'
    library.write_text(library.read_text().replace('#[cfg(codspeed)]', '#[cfg(any(codspeed, feature = "gungraun"))]')
                       .replace('#[cfg(not(codspeed))]', '#[cfg(not(any(codspeed, feature = "gungraun")))]')
                       .replace('pub fn build_tokio_rt()', '#[allow(clippy::needless_return)]\npub fn build_tokio_rt()'))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    prepare(Path(__file__).resolve().parents[2], args.source.resolve())
