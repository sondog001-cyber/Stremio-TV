import unittest
from unittest import mock

from research import bravo_nicktoons_decoder_research as dec


class DecoderResearchTests(unittest.TestCase):
    def test_decode_empty_or_short_not_approved(self):
        self.assertFalse(dec.inspect_hashes([])["decoder_continuity_pass"])
        self.assertFalse(dec.inspect_hashes([str(i) for i in range(49)])["decoder_continuity_pass"])

    def test_sixty_independent_frames_pass_only_decoder_gate(self):
        d = dec.inspect_hashes([f"{n:032x}" for n in range(60)])
        self.assertTrue(d["decoder_continuity_pass"])
        self.assertEqual(d["distinct_frame_hashes"], 60)

    def test_repeating_three_second_segment_detected(self):
        h = ["a", "b", "c"] * 21
        d = dec.inspect_hashes(h)
        self.assertFalse(d["decoder_continuity_pass"])
        self.assertTrue(d["possible_short_loops"])

    def test_freeze_has_separate_failure(self):
        h = [str(n) for n in range(25)] + ["STILL"] * 16 + [str(n) for n in range(25, 45)]
        d = dec.inspect_hashes(h)
        self.assertFalse(d["decoder_continuity_pass"])
        self.assertGreaterEqual(d["longest_identical_frame_run_seconds"], 15)

    def test_framemd5_parser(self):
        h = dec.collect_hashes(
            "#format: frame checksums\n0, 0, 0, 1, 14400, 1234567890abcdef1234567890abcdef\n"
            "0, 1, 1, 1, 14400, abcdefabcdefabcdefabcdefabcdefab\n"
        )
        self.assertEqual(len(h), 2)
        self.assertEqual(h[0], "1234567890abcdef1234567890abcdef")

    def test_decoder_output_never_promotes(self):
        fake = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(dec.subprocess, "run", return_value=fake):
            result = dec.run("Bravo.us")
        self.assertFalse(result["ffmpeg_decoded"])
        self.assertFalse(result["public_addon_eligible"])
        self.assertEqual(result["promotions"], 0)


if __name__ == "__main__":
    unittest.main()
