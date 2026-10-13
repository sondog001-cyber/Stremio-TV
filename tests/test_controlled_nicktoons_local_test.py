"""Only one reviewed Nicktoons AynaScope URL can appear in Local Test."""
import copy
import unittest
import build

URL = "http://tvsen7.aynascope.net/nicktoons/index.m3u8"

def conf(overrides=None):
    return {
        "addon":{"id":"com.example.stremio","version":"1.0","name":"Test","description":"Test"},
        "favorites":[],
        "stream_selection":{"target_hd":2,"target_sd":1,"prefer_distinct_families":True,"prefer_distinct_provider_hosts":True,"primary_family":"iptv-org","fallback_families":[]},
        "local_test_catalog":{
            "enabled": True, "id":"local-test", "name":"🧪 Local Test",
            "target_ids":["Nicktoons.us"], "max_streams_per_channel":3,
            "exclude_provider_hosts":["aynascope.net"],
            "controlled_sources":overrides if overrides is not None else [{
                "tvg_id":"Nicktoons.us","name":"Nicktoons East — AynaScope","family":"aynascope",
                "url":URL,"local_test_only":True,
            }],
        },
    }

def candidate(tvg_id,url):
    return {
        "tvg_id":tvg_id,"name":"Nicktoons","url":url,"family":"iptv-org","source":"Old source",
        "health":{"status":"failed","http_status":403,"detail":"HTTP 403"}
    }

class ControlledNicktoonsLocalTestTests(unittest.TestCase):
    def test_one_local_tile_without_polluting_existing_nicktoons(self):
        config=conf()
        old=candidate("Nicktoons.us","http://old.example.com/old.m3u8")
        other=candidate("CBSSportsNetwork.us","http://tvsen7.aynascope.net/cbssports/index.m3u8")
        rows=[old,other]
        before=copy.deepcopy(rows)
        published=[{"tvg_id":"Nicktoons.us","streams":[old]}]
        channels,report=build.build_local_test_channels(rows,published,config)
        target=[x for x in channels if x["tvg_id"]=="Nicktoons.us"]
        self.assertEqual(len(target),1)
        self.assertEqual(len(target[0]["streams"]),1)
        self.assertEqual(target[0]["streams"][0]["url"],URL)
        self.assertTrue(target[0]["streams"][0]["local_test_only"])
        self.assertTrue(target[0]["id"].startswith("stremiotv_localtest_"))
        self.assertEqual(report["summary"]["controlled_local_test_streams"],1)
        self.assertEqual(rows,before)
        self.assertEqual(published[0]["streams"],[old])
        self.assertIn("aynascope.net",config["local_test_catalog"]["exclude_provider_hosts"])
        result=build.stream_object(target[0]["streams"][0],1)
        self.assertEqual(result["url"],URL)
        self.assertTrue(result["behaviorHints"]["notWebReady"])

    def test_global_block_keeps_all_other_aynascope_sources_hidden(self):
        overrides=[
            {"tvg_id":"CBSSportsNetwork.us","family":"aynascope","url":"http://tvsen7.aynascope.net/cbs/index.m3u8","local_test_only":True},
            {"tvg_id":"Nicktoons.us","family":"aynascope","url":"http://tvsen7.aynascope.net/other/index.m3u8","local_test_only":True},
        ]
        config=conf(overrides)
        config["local_test_catalog"]["target_ids"].append("CBSSportsNetwork.us")
        channels,report=build.build_local_test_channels([
            candidate("Nicktoons.us",URL),
            candidate("CBSSportsNetwork.us","http://tvsen7.aynascope.net/cbs/index.m3u8")
        ],[],config)
        self.assertEqual(channels,[])
        self.assertEqual(report["summary"]["controlled_local_test_streams"],0)

    def test_kill_switch_and_target_pin_override_local_source(self):
        config=conf()
        config["safety_controls"]={"disabled_urls":[URL]}
        channels,report=build.build_local_test_channels([],[],config)
        self.assertEqual(channels,[])
        self.assertEqual(report["summary"]["controlled_local_test_streams"],0)
        config["safety_controls"]={}
        config["local_test_catalog"]["target_ids"]=[]
        channels,_=build.build_local_test_channels([],[],config)
        self.assertEqual(channels,[])

    def test_no_unintended_regular_streams_or_undocumented_variant(self):
        config=conf()
        config["local_test_catalog"]["controlled_sources"].append({
            "tvg_id":"Nicktoons.us","family":"aynascope","url":"http://tvsen7.aynascope.net/nickjr/index.m3u8","local_test_only":True})
        config["local_test_catalog"]["controlled_sources"].append({
            "tvg_id":"Nicktoons.us","family":"aynascope","url":URL+"?token=test","local_test_only":True})
        channels,report=build.build_local_test_channels([],[],config)
        self.assertEqual(len(channels),1)
        self.assertEqual([s["url"] for s in channels[0]["streams"]],[URL])
        self.assertEqual(report["summary"]["controlled_local_test_streams"],1)

if __name__=="__main__":
    unittest.main()
