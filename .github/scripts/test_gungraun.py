import json
from pathlib import Path
import tempfile
import tomllib
import subprocess
import unittest
from unittest.mock import patch

from gungraun import annotate_profiles, build_executable, build_features, compare, preserve_binary, read_summaries, select_catalog
from prepare import adapt, prepare, registered_entries


class ComparisonTests(unittest.TestCase):
    def test_executable_comes_from_current_cargo_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sources-old').touch()
            current = root / 'sources-current'
            current.touch()
            message = dict(reason='compiler-artifact', target=dict(name='sources'),
                           executable=str(current), package_id='benchmark', features=[])
            result = subprocess.CompletedProcess([], 0, stdout=json.dumps(message) + '\n')
            with patch('gungraun.subprocess.run', return_value=result):
                executable, _ = build_executable(['cargo'], 'sources', root, {}, root / 'build.log')
            self.assertEqual(executable, str(current))

    def test_workspace_lock_preserves_upstream_dependencies(self):
        root = Path(__file__).resolve().parents[2]
        original = tomllib.loads((root / 'Cargo.lock').read_text())['package']
        fixed = tomllib.loads((root / 'xtask/gungraun/workspace.Cargo.lock').read_text())['package']
        # Cargo qualifies dependency names when the harness adds another version.
        identity = lambda p: (p['name'], p['version'], p.get('source'), p.get('checksum'))
        fixed_ids = {identity(package) for package in fixed}
        for package in original:
            if package.get('source'):
                self.assertTrue(identity(package) in fixed_ids,
                                f'Stale benchmark lockfile: {package["name"]}')

    def test_binary_requires_debug_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'driver'
            executable.write_bytes(b'example executable')
            with patch('gungraun.run', return_value='.symtab'):
                with self.assertRaisesRegex(ValueError, 'lacks debug information'):
                    preserve_binary(executable, root / 'saved')
            with patch('gungraun.run', return_value='.symtab .debug_info'):
                digest = preserve_binary(executable, root / 'saved')
            self.assertEqual(len(digest), 64)
            self.assertEqual((root / 'saved').read_bytes(), executable.read_bytes())

    def test_annotations_select_current_and_saved_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / 'profiles'
            home.mkdir()
            (home / 'callgrind.case.out.base@base').touch()
            with patch('gungraun.subprocess.run') as annotate:
                annotate_profiles(home, root / 'base', baseline=True)
                self.assertEqual(annotate.call_count, 2)
            (home / 'callgrind.case.out').touch()
            with patch('gungraun.subprocess.run') as annotate:
                annotate_profiles(home, root / 'head')
                self.assertEqual(annotate.call_count, 2)
                self.assertTrue(all(call.args[0][-1].endswith('.out')
                                    for call in annotate.call_args_list))

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


if __name__ == '__main__':
    unittest.main()
