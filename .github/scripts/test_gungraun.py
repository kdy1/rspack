import json
from pathlib import Path
import tempfile
import unittest

from gungraun import (build_features, check_swc_next_lock, compare, read_summaries, select_catalog,
                      swc_next_ids, swc_next_patch)
from prepare import adapt, prepare, registered_entries


class ComparisonTests(unittest.TestCase):
    def test_exact_comparison(self):
        self.assertEqual(compare({'a': {'new': 100}}, {'a': {'new': 90, 'old': 100}})[0]['head'], 90)

    def test_missing_case(self):
        with self.assertRaisesRegex(ValueError, 'identities differ'):
            compare({'a': {'new': 100}}, {})

    def test_wrong_baseline(self):
        with self.assertRaisesRegex(ValueError, 'Baseline count'):
            compare({'a': {'new': 100}}, {'a': {'new': 90, 'old': 99}})

    def test_summary_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = dict(version='7', module_path='sources::concat_add', id='few',
                        baselines=[None, 'base'], profiles=[dict(tool='Callgrind', data=dict(
                            total=dict(metrics={'Ir': {'values': {'new': 90, 'old': 100}}})))])
            path = root / 'summary.json'
            path.write_text(json.dumps(data))
            self.assertEqual(read_summaries(root)['sources::concat_add::few']['new'], 90)
            data['version'] = '6'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Unsupported summary schema'):
                read_summaries(root)
            data['version'] = '7'
            data['profiles'][0]['data']['total']['metrics']['Ir']['values']['new'] = 0
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'invalid instruction count'):
                read_summaries(root)

    def test_empty_filter_result(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'No benchmark cases matched'):
                read_summaries(Path(directory))

    def test_catalog_filter_and_collisions(self):
        catalog = [('cases/bundle', 'bundle/react-development'), ('stages/hashes', 'rust@hashes')]
        self.assertEqual(select_catalog(catalog, 'hashes'), [catalog[1]])
        with self.assertRaisesRegex(ValueError, 'No benchmark cases matched'):
            select_catalog(catalog, 'missing')
        with self.assertRaisesRegex(ValueError, 'IDs collide'):
            select_catalog([('case', 'a-b'), ('case', 'a_b')], '')

    def test_build_features_ignore_artifact_order(self):
        artifacts = [dict(package_id='serde', features=['std', 'derive']),
                     dict(package_id='serde', features=['derive'])]
        self.assertEqual(build_features(artifacts), build_features(reversed(artifacts)))
        self.assertEqual(build_features(artifacts)['serde'], [['derive'], ['derive', 'std']])

    def test_adapter_preserves_routines(self):
        routine = 'b.iter_batched(|| setup(), |input| run(input), criterion::BatchSize::PerIteration);'
        adapted = adapt('use rspack_benchmark::Criterion;\n' + routine + '\ncriterion_group!(case, bench);')
        self.assertIn('use crate::adapter::Criterion;', adapted)
        self.assertIn(routine.replace('criterion::', 'crate::adapter::'), adapted)
        self.assertNotIn('criterion_group!', adapted)

    def test_unrecognized_registration_fails(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported benchmark registration'):
            registered_entries('criterion_main!(benchmark_setup, custom::new_group);')

    def test_full_harness_overlay_keeps_production(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'xtask/benchmark').mkdir(parents=True)
            production = source / 'crates/production.rs'
            production.parent.mkdir()
            production.write_text('unchanged production')
            prepare(root, source)
            self.assertEqual(production.read_text(), 'unchanged production')
            driver = source / 'xtask/benchmark/benches/gungraun_generated/main.rs'
            self.assertIn('cases::persistent_cache_restore::bench', driver.read_text())
            self.assertIn('stages::real_content_hash::bench', driver.read_text())
            self.assertIn('walltime::threejs_10x_bundle_benchmark', driver.read_text())
            self.assertIn('gungraun_driver', (source / 'xtask/benchmark/Cargo.toml').read_text())

    def test_swc_next_patch_is_the_only_allowed_manifest_difference(self):
        rev = 'a' * 40
        root = '[workspace]\nmembers = []\n'
        entry = f'swc_next_simd = {{ git = "https://github.com/kdy1/swc-next", rev = "{rev}" }}\n'
        self.assertIsNone(swc_next_patch(root, root))
        self.assertEqual(swc_next_patch(root, root + '\n[patch.crates-io]\n' + entry)['swc_next_simd']['rev'], rev)
        for bad in (root + 'members = 1\n', root.replace('[]', '["x"]'),
                    root + '\n[patch.crates-io]\n' + entry.replace('swc_next_simd', 'serde'),
                    root + '\n[patch.crates-io]\n' + entry.replace('kdy1', 'someone'),
                    root + '\n[patch.crates-io]\n' + entry.replace(rev, 'main'),
                    root + '\n[patch.crates-io]\n' + entry + '\n[profile.release]\nlto = true\n'):
            with self.assertRaises(ValueError):
                swc_next_patch(root, bad)

    def test_swc_next_lock_may_only_change_swc_next_packages(self):
        rev = 'b' * 40
        patch = {'swc_next_simd': dict(git='https://github.com/kdy1/swc-next', rev=rev)}
        before = ('[[package]]\nname = "serde"\nversion = "1.0.0"\n\n[[package]]\nname = "swc_next_simd"\n'
                  'version = "0.3.0"\nsource = "registry+https://github.com/rust-lang/crates.io-index"\n')
        git = f'git+https://github.com/kdy1/swc-next?rev={rev}#{"c" * 40}'
        after = before.replace('0.3.0', '0.3.2').replace(
            'registry+https://github.com/rust-lang/crates.io-index', git)
        check_swc_next_lock(before, after, patch)
        with self.assertRaisesRegex(ValueError, 'other than swc_next'):
            check_swc_next_lock(before, after.replace('1.0.0', '1.0.1'), patch)
        with self.assertRaisesRegex(ValueError, 'requested git revision'):
            check_swc_next_lock(before, before, patch)
        self.assertEqual(swc_next_ids({'registry+https://x#swc_next_simd@0.3.0': 1}),
                         swc_next_ids({f'git+https://y?rev={rev}#swc_next_simd@0.3.2': 1}))


if __name__ == '__main__':
    unittest.main()
