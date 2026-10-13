"""Nicktoons promotion is exact, reversible, and isolated."""
import json
import pathlib
import unittest
import build

ROOT=pathlib.Path(__file__).resolve().parents[1]
NEW="http://tvsen7.aynascope.net/nicktoons/index.m3u8"
OLD="http://41.205.93.154/NICKTOONS/index.m3u8"

class NicktoonsPromotionTests(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads((ROOT/"config.json").read_text())
        self.manual=json.loads((ROOT/"manual_sources.json").read_text())

    def test_only_one_locally_verified_manual_nicktoons(self):
        rows=[s for s in self.manual["streams"] if s["tvg_id"]=="Nicktoons.us"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["url"],NEW)
        self.assertTrue(rows[0]["local_verified_override"])
        self.assertEqual(rows[0]["family"],"aynascope")

    def test_exact_channel_scoped_old_loop_quarantine(self):
        old={"url":OLD,"tvg_id":"Nicktoons.us","name":"Nicktoons"}
        other={"url":OLD,"tvg_id":"OtherChannel.us","name":"Other Channel"}
        replacement={"url":NEW,"tvg_id":"Nicktoons.us","name":"Nicktoons"}
        kept,quarantine=build.apply_stream_quarantine([old,other,replacement],self.cfg)
        self.assertEqual(kept,[other,replacement])
        self.assertEqual(len(quarantine),1)
        self.assertEqual(quarantine[0]["url"],OLD)

    def test_new_primary_selection_and_stremio_direct_url(self):
        old={"url":OLD,"name":"Nicktoons","tvg_id":"Nicktoons.us",
             "quality":"HD","family":"iptv-org","source":"Old looping feed",
             "content_kind":"full-linear","priority":1,
             "stability":{"rank":2,"passes":1,"samples":3}}
        new=next(x for x in self.manual["streams"] if x["url"]==NEW).copy()
        new["stability"]={"rank":1,"passes":9,"samples":9,"last_decoder_result":"pass"}
        good,bad=build.apply_stream_quarantine([new,old],self.cfg)
        self.assertEqual(len(good),1)
        selected=build.select_streams(good,3,self.cfg,channel_id="Nicktoons.us")
        self.assertEqual(selected[0]["url"],NEW)
        self.assertEqual(build.stream_object(selected[0],1)["url"],NEW)

    def test_keep_global_aynascope_local_test_exclusion(self):
        local=self.cfg["local_test_catalog"]
        self.assertIn("aynascope.net",local["exclude_provider_hosts"])
        self.assertFalse(any(
            row.get("tvg_id") == "Nicktoons.us"
            for row in (local.get("controlled_sources") or [])
        ))
        self.assertFalse(any(x.get("url")==NEW for x in (local.get("controlled_sources") or [])))

    def test_no_other_channel_preferences_changed_by_nicktoons_rule(self):
        self.assertIn("Nicktoons.us",self.cfg["stream_selection"]["channel_preferences"])
        self.assertEqual(
            build.channel_preference_rules(self.cfg,"Nicktoons.us")[0]["family"],
            "aynascope"
        )
        self.assertNotEqual(
            build.channel_preference_rules(self.cfg,"DisneyChannel.us")[0]["family"],
            "aynascope"
        )

if __name__=="__main__":
    unittest.main()
