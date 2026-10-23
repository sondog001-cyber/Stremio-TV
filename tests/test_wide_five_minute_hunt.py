import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
import five_minute_public_sweep as hunt

class FiveMinuteHuntTests(unittest.TestCase):
    def test_six_distinct_catalog_sweeps(self):
        self.assertEqual(len(hunt.FAMILIES),6)
        self.assertTrue(all(len(x)>=2 for x in hunt.FAMILIES))
        self.assertGreaterEqual(len({y for group in hunt.FAMILIES for y in group}),12)
    def test_targets_restrict_to_exact_networks(self):
        self.assertIn("Bravo.us",hunt.TARGET)
        self.assertIn("WPVI.us",hunt.TARGET)
        self.assertNotIn("USANetworkLatinAmerica.us",hunt.TARGET)
        self.assertNotIn("Bravo.us@West",hunt.TARGET)
if __name__=="__main__": unittest.main()
