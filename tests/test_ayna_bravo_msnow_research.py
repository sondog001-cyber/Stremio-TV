"""Offline safety and continuity checks for Ayna-origin research."""
import unittest
from unittest import mock
from research import ayna_bravo_msnow_research as task

class AynaDiscoveryTests(unittest.TestCase):
    def test_exact_channels_and_unsigned_paths(self):
        self.assertEqual(set(task.SOURCES), {"Bravo.us", "MSNOW.us"})
        for item in task.SOURCES.values():
            self.assertEqual(item["url"].count("?"), 0)
            self.assertTrue(item["source"].startswith("https://github.com/"))

    def test_short_loop_and_freeze_detected(self):
        good = [str(i) for i in range(60)]
        self.assertTrue(task.analyze_hashes(good)["decoder_continuity_pass"])
        bad = ["a","b","c"]*20
        self.assertFalse(task.analyze_hashes(bad)["decoder_continuity_pass"])
        self.assertIn(3,task.analyze_hashes(bad)["short_loops_detected"])
        frozen = ["same"] * 60
        self.assertFalse(task.analyze_hashes(frozen)["decoder_continuity_pass"])

    @mock.patch.object(task.hls,"probe_manifest",return_value={"stage":"manifest-or-segment-unavailable","http_status":403})
    @mock.patch.object(task,"decode_direct")
    def test_unplayable_manifest_not_decoded_or_published(self, decoder, probe):
        result=task.check("Bravo.us")
        decoder.assert_not_called()
        self.assertFalse(result["production_promotion"])
        self.assertFalse(result["local_test_promotion"])
        self.assertFalse(result["exact_us_linear_programming_verified"])
        self.assertEqual(result["preflight_http_status"],403)

    @mock.patch.object(task.hls,"probe_manifest",return_value={"stage":"progressing-hls-readable-not-decoded","http_status":200,"media_host":"tvsen7.aynascope.net"})
    @mock.patch.object(task,"decode_direct",return_value={"passed":True,"frames":60})
    def test_decode_pass_still_no_auto_promotion(self, decoder, probe):
        result=task.check("Bravo.us")
        self.assertTrue(result["decoder"]["passed"])
        self.assertFalse(result["production_promotion"])
        self.assertFalse(result["local_test_promotion"])

if __name__=="__main__":
    unittest.main()
