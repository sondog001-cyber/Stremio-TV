"""Research-only header recheck: audited identities, different gateway families."""
import unittest
from research import public_header_recheck as h

class HeaderRecheckTests(unittest.TestCase):
    def test_only_exact_dual_id_and_name_evidence(self):
        rows=[
            {"tvg_id":"Nicktoons.us","name":"Nicktoons","url":"https://a.mizhls.ru/live.m3u8","invalid":False,"public_headers":{"Referer":"https://public.example.com/"}},
            {"tvg_id":"Nicktoons.us","name":"Nickelodeon","url":"https://b.mizhls.ru/other.m3u8","invalid":False},
            {"tvg_id":"CBS.Sports.Network.USA.us","name":"CBS Sports Network (CBSSN)","url":"https://n.newkso.ru/mono.m3u8","invalid":False},
            {"tvg_id":"Nicktoons.us","name":"Nicktoons","url":"http://10.1.1.1/test.m3u8","invalid":False},
            {"tvg_id":"Nicktoons.us","name":"Nicktoons","url":"","invalid":True}
        ]
        found=list(h.eligible(rows,"fixture"))
        self.assertEqual([v["tvg_id"] for v in found],["Nicktoons.us","CBSSportsNetwork.us"])
        self.assertEqual(found[0]["gateway_family"],"mizhls.ru")
        self.assertEqual(found[1]["gateway_family"],"newkso.ru")
    def test_never_includes_production_selectable_paths(self):
        self.assertTrue(all(s["url"].startswith("https://raw.githubusercontent.com/") for s in h.SEEDS))
        self.assertLessEqual(h.CAP_TOTAL,8)
        self.assertNotIn("DisneyChannel.us",h.FOCUS)

if __name__=="__main__":
    unittest.main()
