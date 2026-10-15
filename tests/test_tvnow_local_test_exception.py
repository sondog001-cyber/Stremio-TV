"""TVNow local-test exception is narrowly confined to the preexisting 17 tagged streams."""
import json, unittest
from pathlib import Path

class TVNowLocalTestExceptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=json.loads(Path("config.json").read_text())
        cls.m=json.loads(Path("manual_sources.json").read_text())["streams"]
    def test_all_preexisting_tvnow_local_verified_feeds_have_test_access(self):
        tvnow=[r for r in self.m if r.get("family")=="tvnow"]
        self.assertEqual(len(tvnow),17)
        targets=set(self.c["local_test_catalog"]["target_ids"])
        self.assertTrue(self.c["local_test_catalog"]["enabled"])
        for r in tvnow:
            self.assertTrue(r.get("local_verified_override"),r["tvg_id"])
            self.assertIn(r["tvg_id"],targets)
    def test_no_new_exceptions_or_credentials(self):
        flags={r["tvg_id"] for r in self.m if r.get("local_verified_override")}
        self.assertEqual(len(flags),19)
        for r in self.m:
            if r.get("family")=="tvnow":
                self.assertEqual(r.get("headers",{}).get("Referer"),"https://tvnow.st/")
                self.assertNotIn("Authorization",r.get("headers",{}))
                self.assertNotIn("Cookie",r.get("headers",{}))
    def test_deployment_guard_remains_original(self):
        guard=self.c["deployment_guard"]
        self.assertTrue(guard["enabled"])
        self.assertEqual(guard["minimum_channels"],86)
        self.assertEqual(set(guard["required_channel_ids"]),
                         {"History.us","DisneyChannel.us","NationalGeographic.us"})
        self.assertTrue(self.c["stream_health"]["require_passed_only"])
        self.assertTrue(self.c["stream_health"]["primary_playback_qa"]["enabled"])

if __name__=="__main__":unittest.main()
