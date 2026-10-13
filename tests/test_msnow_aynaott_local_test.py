"""MS NOW AynaOTT controlled local test is exact and cannot affect production."""
import copy
import json
import pathlib
import unittest
import build

ROOT=pathlib.Path(__file__).resolve().parents[1]
URL="https://tvsen6.aynaott.com/msnbc/index.m3u8"

def row(tvg_id,url,*,family="test"):
    return {
        "tvg_id":tvg_id,"name":tvg_id,"url":url,"family":family,
        "source":"other","health":{"status":"failed","detail":"HTTP 403 Forbidden","http_status":403},
    }

class MSNowControlledLocalTest(unittest.TestCase):
    def setUp(self):
        self.conf=json.loads((ROOT/"config.json").read_text())

    def test_valid_msnow_local_only_and_no_mutation_of_published(self):
        original=row("MSNOW.us","https://other.example.com/msnow.m3u8")
        incoming=[original]
        published=[{"tvg_id":"MSNOW.us","streams":[original]}]
        before=copy.deepcopy(published)
        channels,report=build.build_local_test_channels(incoming,published,self.conf)
        filtered=[c for c in channels if c.get("tvg_id")=="MSNOW.us"]
        self.assertEqual(len(filtered),1)
        self.assertEqual(len(filtered[0]["streams"]),1)
        stream=filtered[0]["streams"][0]
        self.assertEqual(stream["url"],URL)
        self.assertTrue(stream["local_test_only"])
        self.assertTrue(stream["local_test"])
        self.assertTrue(filtered[0]["id"].startswith("stremiotv_localtest_"))
        self.assertEqual(build.stream_object(stream,1)["url"],URL)
        self.assertEqual(published,before)
        self.assertEqual(report["summary"]["controlled_local_test_streams"],1)

    def test_no_other_channel_allowed_on_same_host(self):
        others=[row("BET.us","https://tvsen6.aynaott.com/bet/index.m3u8",family="aynaott")]
        channels,_=build.build_local_test_channels(others,[],self.conf)
        self.assertFalse(any(c.get("tvg_id")=="BET.us" for c in channels))

    def test_url_and_channel_kill_switch(self):
        disabled=self.conf.setdefault("safety_controls",{})
        disabled["disabled_urls"].append(URL)
        ch,_=build.build_local_test_channels([],[],self.conf)
        self.assertFalse(any(c.get("tvg_id")=="MSNOW.us" for c in ch))
        disabled["disabled_urls"].remove(URL)
        disabled.setdefault("disabled_channels",[]).append("MSNOW.us")
        ch,_=build.build_local_test_channels([],[],self.conf)
        self.assertFalse(any(c.get("tvg_id")=="MSNOW.us" for c in ch))

    def test_unreviewed_host_variant_fails_closed(self):
        row=self.conf["local_test_catalog"]["controlled_sources"][0]
        row["url"]=URL+"?token=example"
        ch,report=build.build_local_test_channels([],[],self.conf)
        self.assertEqual(ch,[])
        self.assertEqual(report["summary"]["controlled_local_test_streams"],0)

    def test_global_nicktoons_exclusion_remains(self):
        self.assertIn("aynascope.net",self.conf["local_test_catalog"]["exclude_provider_hosts"])
        self.assertFalse(any(x.get("tvg_id")=="Nicktoons.us" for x in self.conf["local_test_catalog"]["controlled_sources"]))

if __name__=="__main__":
    unittest.main()
