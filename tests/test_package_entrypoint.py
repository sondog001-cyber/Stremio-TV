import unittest
from unittest.mock import patch
from stremio_tv.__main__ import main


class PackageEntrypointTests(unittest.TestCase):
    def test_build_runs_assembly_then_builder(self):
        with patch('sys.argv', ['stremio_tv', 'build', '--fixtures', 'fixtures']), patch('stremio_tv.__main__.subprocess.run') as run:
            run.return_value.returncode = 0
            self.assertEqual(main(), 0)
            self.assertEqual(run.call_count, 2)
            self.assertIn('assemble_build.py', run.call_args_list[0].args[0][1])
            self.assertIn('build.py', run.call_args_list[1].args[0][1])

    def test_failed_assembly_stops_build(self):
        with patch('sys.argv', ['stremio_tv', 'build']), patch('stremio_tv.__main__.subprocess.run') as run:
            run.return_value.returncode = 1
            self.assertEqual(main(), 1)
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
