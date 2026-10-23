import json
from pathlib import Path
import tempfile
import unittest

from gungraun import compare, read_summaries


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


if __name__ == '__main__':
    unittest.main()
