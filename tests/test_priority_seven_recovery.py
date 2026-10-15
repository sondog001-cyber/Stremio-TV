"""Strict exact-identity recovery staging: no bypass, no remapping regional channels."""
import json
import unittest
from pathlib import Path
import build

class PrioritySevenStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads(Path("config.json").read_text())
        cls.manual=json.loads(Path("manual_sources.json").read_text())["streams"]

    def test_natgeo_hd_east_maps_only_to_us_natgeo(self):
        aliases=self.config["curation"]["canonical_id_aliases"]
        self.assertEqual(aliases["NationalGeographic.us@HDEast"],"NationalGeographic.us")
        examples=[
            {"tvg_id":"NationalGeographic.us@HDEast","url":"http://198.58.104.90:8989/natgeo/index.m3u8","name":"Nat Geo HD East","family":"iptv-org"},
            {"tvg_id":"NationalGeographicLatinAmerica.us@Panregional","url":"http://example.test/latam.m3u8","name":"NatGeo Latin America","family":"iptv-org"},
            {"tvg_id":"NationalGeographicWild.us@HDEast","url":"http://example.test/wild.m3u8","name":"NatGeo Wild","family":"iptv-org"},
        ]
        mapped=build.canonicalize_approved_sources(examples,self.config)
        self.assertEqual(mapped[0]["tvg_id"],"NationalGeographic.us")
        self.assertNotEqual(mapped[1]["tvg_id"],"NationalGeographic.us")
        self.assertNotEqual(mapped[2]["tvg_id"],"NationalGeographic.us")

    def test_history_two_hosts_are_unprivileged_full_linear_backups(self):
        expected={
            "https://tvsen5.aynascope.net/historyen/index.m3u8",
            "https://tvsen3.aynaott.com/np3JstRE/index.m3u8",
        }
        matches=[x for x in self.manual if x.get("url") in expected]
        self.assertEqual({x["url"] for x in matches},expected)
        for row in matches:
            self.assertEqual(build.canonical_tvg_id(row["tvg_id"]),"history.us")
            self.assertEqual(row["content_kind"],"full-linear")
            self.assertNotIn("local_verified_override",row)
            self.assertFalse(row.get("local_test_only",False))
        curated,rejected=build.curate_entries(build.canonicalize_approved_sources(matches,self.config),self.config)
        self.assertEqual(len(curated),2,f"History rejected: {rejected!r}")

    def test_previous_four_and_guards_still_staged(self):
        ids={"BigTenNetwork.us@SD","OneAmericaNewsNetwork.us@SD","SECNetwork.us@SD","ScienceChannel.us"}
        self.assertTrue(ids.issubset({r.get("tvg_id") for r in self.manual}))
        self.assertGreaterEqual(self.config["deployment_guard"]["minimum_channels"],86)
        self.assertTrue(self.config["deployment_guard"]["enabled"])
        self.assertTrue(self.config["stream_health"]["require_passed_only"])
        self.assertTrue(self.config["stream_health"]["primary_playback_qa"]["enabled"])
        required=set(self.config["deployment_guard"]["required_channel_ids"])
        self.assertTrue({"NationalGeographic.us","History.us","DisneyChannel.us"}.issubset(required))

    def test_failed_cooking_and_e_candidates_do_not_enter_release(self):
        excluded={
            "https://tvsen7.aynascope.net/cooking/index.m3u8",
            "https://cache0.wonvt.st/live/15a0cd61f3w7um0229g5g/master.m3u8",
        }
        self.assertFalse(excluded & {r.get("url") for r in self.manual})

if __name__=="__main__":unittest.main()
