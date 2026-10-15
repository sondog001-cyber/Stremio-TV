"""Isolated replacement source candidate validation; cannot publish."""
import copy
import json
import pathlib
import unittest
from unittest import mock

from research import disney_nicktoons_replacement_hunt as hunt

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/"research/disney_nicktoons_replacements_20261013.json").read_text())

class DisneyNicktoonsReplacementHuntTests(unittest.TestCase):
    def test_six_reviewed_independent_gateway_family_pairs(self):
        hunt.validate_registry(DATA)
        self.assertEqual(sum(c["tvg_id"]=="DisneyChannel.us" for c in DATA["candidates"]),3)
        self.assertEqual(sum(c["tvg_id"]=="Nicktoons.us" for c in DATA["candidates"]),3)
        self.assertEqual(len({(c["tvg_id"],c["family"]) for c in DATA["candidates"]}),6)

    def test_no_expiring_signed_tokens_or_account_url(self):
        for candidate in DATA["candidates"]:
            self.assertNotIn("?",candidate["entry_url"])
            self.assertNotIn("@",candidate["entry_url"])
            self.assertTrue(candidate["source_ref"].startswith("https://github.com/"))

    def test_signed_paths_credential_urls_and_duplicated_families_rejected(self):
        invalid=["https://provider.example/x.m3u8?token=secret",
                 "https://user:pass@provider.example/x.m3u8",
                 "http://127.0.0.1/x.m3u8",
                 "http://provider.example/live/name/password/321.m3u8"]
        for url in invalid:
            data=copy.deepcopy(DATA)
            data["candidates"][0]["entry_url"]=url
            with self.subTest(url=url),self.assertRaises(ValueError):
                hunt.validate_registry(data)
        dup=copy.deepcopy(DATA)
        dup["candidates"][1]["family"]="thetvapp"
        with self.assertRaises(ValueError):
            hunt.validate_registry(dup)

    def test_preflight_without_video_does_not_decode_or_promote(self):
        with mock.patch.object(hunt.hls,"probe_manifest",return_value={"stage":"manifest-or-segment-unavailable"}),mock.patch.object(
            hunt,"direct_decoder_test"
        ) as decoder:
            result=hunt.report_for("Nicktoons.us",DATA,decode=True)
        decoder.assert_not_called()
        self.assertEqual(result["attempts"],3)
        self.assertEqual(result["progressing_hls"],0)
        self.assertEqual(result["promotions"],0)
        self.assertTrue(all(not row["production_eligible"] for row in result["candidates"]))

    def test_progressing_hls_decodes_only_after_stable_window(self):
        with mock.patch.object(hunt.hls,"probe_manifest",return_value={
             "stage":"progressing-hls-readable-not-decoded","media_host":"new.example.com"
        }),mock.patch.object(hunt,"direct_decoder_test",return_value={
             "continuity_pass":True,"decoded_frames":60
        }) as dec:
            result=hunt.report_for("DisneyChannel.us",DATA,decode=True)
        self.assertEqual(dec.call_count,3)
        self.assertEqual(result["decoder_continuity_passes"],3)
        self.assertEqual(result["promotions"],0)
        self.assertFalse(any(x["exact_broadcast_identity_confirmed"] for x in result["candidates"]))

    def test_media_only_probe_never_promotes(self):
        c=DATA["candidates"][0]
        with mock.patch.object(hunt.hls,"probe_manifest",return_value={
            "stage":"progressing-hls-readable-not-decoded"
        }):
            result=hunt.inspect_candidate(c,decode=False)
        self.assertFalse(result["local_test_eligible"])
        self.assertFalse(result["production_eligible"])
        self.assertNotIn(c["entry_url"],str(result))

if __name__=="__main__":
    unittest.main()
