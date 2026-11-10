"""Validate no-artifact visual identity workflow does not falsely certify US East."""
import copy
import json
import pathlib
import unittest
from unittest import mock
from research import nicktoons_visual_identity_audit as audit
from research import disney_nicktoons_replacement_hunt as hunt

DATA=json.loads((pathlib.Path(__file__).resolve().parents[1]/"research/disney_nicktoons_replacements_20261013.json").read_text())

class NicktoonsVisualIdentityTests(unittest.TestCase):
    def test_bounded_jpeg_parse_only_and_ignore_noise(self):
        jpeg=b"\xff\xd8"+"sample".encode()+b"\xff\xd9"
        self.assertEqual(audit.split_jpegs(b"noise"+jpeg+jpeg+b"trailing"),[jpeg,jpeg])
        self.assertEqual(audit.split_jpegs(b"\xff\xd8partial"),[])

    def test_channel_bug_is_not_episode_identity(self):
        with mock.patch.object(audit,"ocr_frame",side_effect=[{"nicktoons":True},{"nicktoons":True}]):
            result=audit.analyze_frames([b"one",b"two"])
        self.assertTrue(result["nicktoons_text_seen_on_2_frames"])
        self.assertFalse(result["exact_us_east_episode_verified"])
        self.assertFalse(result["on_screen_program_schedule_verified"])
        self.assertFalse(result["on_screen_logo_verified_by_human"])

    def test_series_title_on_screen_does_not_prove_us_east(self):
        with mock.patch.object(audit,"ocr_frame",return_value={"spongebob":True}):
            result=audit.analyze_frames([b"one"])
        self.assertTrue(result["expected_series_text_seen"])
        self.assertFalse(result["exact_us_east_episode_verified"])

    def test_fixed_audited_candidate_rejects_other_aynascope_endpoint(self):
        wrong=copy.deepcopy(DATA)
        row=next(c for c in wrong["candidates"] if c["family"]=="aynascope")
        row["entry_url"]="http://tvsen7.aynascope.net/disneyjr/index.m3u8"
        with self.assertRaises(ValueError), mock.patch.object(audit,"safe_ffprobe"):
            audit.audit(wrong)

    def test_no_frame_artifact_and_no_permissions_claim(self):
        class FakeRun:
            returncode=0
            stdout=b"\xff\xd8fake\xff\xd9"
        with mock.patch.object(audit,"safe_ffprobe",return_value={"status":"ok"}),mock.patch.object(
            audit.subprocess,"run",return_value=FakeRun()),mock.patch.object(
            audit,"ocr_frame",return_value={"nicktoons":True}):
            result=audit.audit(DATA)
        self.assertFalse(result["capture_frames_saved"])
        self.assertFalse(result["exact_us_nicktoons_east_identity_confirmed"])
        self.assertFalse(result["permission_to_embed_in_public_addon_confirmed"])
        self.assertFalse(result["eligible_for_production"])
        self.assertFalse(result["eligible_for_local_test"])
        self.assertNotIn("fake",str(result))

if __name__=="__main__":
    unittest.main()
