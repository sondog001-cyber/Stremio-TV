"""Offline fixture tests for research-only Disney + Nicktoons diagnostics."""
import unittest
from research import disney_fallback_diagnostic as disney
from research import nicktoons_repeat_diagnostic as nick

class DisneyNicktoonsDiagnosticTests(unittest.TestCase):
    def test_disney_duplicate_playlist_labels_not_independent_backups(self):
        url="http://212.5.144.156/disney/index.m3u8"
        rows=[
            {"tvg_id":"DisneyChannel.us@East","url":url,"source":"US","family":"iptv-org","health":{"status":"ok"}},
            {"tvg_id":"DisneyChannel.us@East","url":url,"source":"US Raw","family":"iptv-org","health":{"status":"ok"}},
        ]
        report=disney.assess(rows,{"discovery":{"seed_candidates":[]}},
                             [{"tvg_id":"DisneyChannel.us"}])
        self.assertEqual(report["distinct_tested_playback_urls"],1)
        self.assertEqual(report["matched_inventory_records"],2)
        self.assertEqual(report["duplicate_source_labels"],1)
        self.assertTrue(report["fallback_is_single_point_of_failure"])
        self.assertEqual(report["independent_passing_fallbacks"],0)
        self.assertTrue(report["is_published"])
        self.assertEqual(len(report["source_lineage"][0]["source_labels"]),2)
        self.assertNotIn(url,str(report))

    def test_disney_encrypted_historical_candidate_not_automatically_promoted(self):
        report=disney.assess([],
            {"discovery":{"seed_candidates":[
              {"tvg_id":"DisneyChannel.us","url":"http://feed.example.com/HLS_encr/Disney.m3u8"},
              {"tvg_id":"DisneyChannel.us","url":"http://203.0.113.5/invalid.m3u8"}
            ]}})
        self.assertEqual(report["independent_passing_fallbacks"],0)
        self.assertFalse(report["configured_unverified_fallback_seeds"][0]["candidate_allowed_in_research"])
        self.assertFalse(report["configured_unverified_fallback_seeds"][1]["candidate_allowed_in_research"])

    def test_nicktoons_must_pass_three_independent_windows(self):
        pass_sample={"ffmpeg_decoded":True,"decoder_continuity_pass":True,
                     "sampled_frames":60,"distinct_frame_hashes":60,
                     "possible_short_loops":[],"tested_at":"2026-10-13T10:00:00Z"}
        result=nick.summarize([pass_sample]*3,
            [{"tvg_id":"Nicktoons.us@East","epg_id":"Nicktoons.us2","method":"manual-tvg-id"}],
            [{"tvg_id":"Nicktoons.us@East"}])
        self.assertTrue(result["sustained_continuity_across_all_windows"])
        self.assertTrue(result["epg_mapping_exists"])
        self.assertFalse(result["on_screen_nicktoons_schedule_verified"])
        self.assertFalse(result["local_test_or_production_promotion"])
        failed={**pass_sample,"ffmpeg_decoded":False,"sampled_frames":0}
        report=nick.summarize([pass_sample,pass_sample,failed])
        self.assertEqual(report["continuity_passes"],2)
        self.assertFalse(report["sustained_continuity_across_all_windows"])

    def test_nicktoons_frames_with_repeated_clip_cannot_pass(self):
        sample={"ffmpeg_decoded":True,"decoder_continuity_pass":True,
                "sampled_frames":60,"possible_short_loops":[{"seconds_per_loop":3}]}
        report=nick.summarize([sample,sample,sample])
        self.assertEqual(report["continuity_passes"],0)

if __name__=="__main__":
    unittest.main()
