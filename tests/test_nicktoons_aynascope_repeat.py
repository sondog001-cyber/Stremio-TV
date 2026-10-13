"""Nicktoons Ayna three-interval read-only workflow regression tests."""
import copy
import json
import pathlib
import unittest
from research import nicktoons_aynascope_repeat as repeat
from research import disney_nicktoons_replacement_hunt as hunt

DATA=json.loads((pathlib.Path(__file__).resolve().parents[1]/"research/disney_nicktoons_replacements_20261013.json").read_text())

class NicktoonsAynaRepeatTests(unittest.TestCase):
    def test_exact_source_fixed_and_not_old_host(self):
        c=repeat.read_candidate(DATA)
        self.assertEqual(c["family"],"aynascope")
        self.assertEqual(c["tvg_id"],"Nicktoons.us")
        self.assertNotIn("41.205.93.154",c["entry_url"])

    def test_three_clean_intervals_only_continuity_not_identity(self):
        fine={"ffmpeg_decoded":True,"continuity_pass":True,"decoded_frames":60,
              "distinct_frame_hashes":60,"possible_short_loops":[],"longest_freeze":1}
        summary=repeat.assess([fine]*3)
        self.assertTrue(summary["all_three_passed"])
        self.assertFalse(summary["actual_us_nicktoons_linear_content_confirmed"])
        self.assertFalse(summary["direct_link_public_reuse_authorized"])
        self.assertFalse(summary["approved_local_test_or_production"])

    def test_one_repeating_window_fails_even_if_decoder_exit_zero(self):
        clean={"ffmpeg_decoded":True,"continuity_pass":True,"decoded_frames":60,
               "distinct_frame_hashes":60,"possible_short_loops":[]}
        bad={**clean,"possible_short_loops":[{"seconds_per_loop":3}]}
        summary=repeat.assess([clean,clean,bad])
        self.assertEqual(summary["passed_count"],2)
        self.assertFalse(summary["all_three_passed"])

    def test_cannot_substitute_another_host_or_url_for_the_reviewed_source(self):
        data=copy.deepcopy(DATA)
        item=next(x for x in data["candidates"] if x["family"]=="aynascope")
        item["entry_url"]="http://8.8.8.8/unknown.m3u8"
        with self.assertRaises(ValueError):
            repeat.read_candidate(data)

if __name__=="__main__":
    unittest.main()
