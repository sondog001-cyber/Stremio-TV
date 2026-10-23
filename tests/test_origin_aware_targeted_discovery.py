"""Local-only tests; must not fetch sources or call ffmpeg."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"research"))
import origin_aware_targeted_discovery as discovery

class OriginAwareDiscoveryTests(unittest.TestCase):
    def test_signed_variants_are_only_one_media_origin(self):
        a="https://EXAMPLE.org:443/LIVE/Foo/index.m3u8?jwt=abc&quality=hd"
        b="https://example.org/LIVE/Foo/index.m3u8?quality=hd&jwt=xyz"
        self.assertEqual(discovery.media_key(a),discovery.media_key(b))
        self.assertNotEqual(discovery.media_key(a),discovery.media_key("https://different.org/LIVE/Foo/index.m3u8?quality=hd"))

    def test_historic_shared_host_excluded(self):
        r={"identity":"Bravo.us","url":"http://23.237.104.106:8080/USA_BRAVO/index.m3u8","playlist":"old"}
        selected,_,rejected,_=discovery.select([r])
        self.assertFalse(selected)
        self.assertEqual(rejected[0]["reason"],"historic-shared-host-unreachable")

    def test_credentials_and_west_identity_not_accepted(self):
        entries=[
            {"identity":"E.us","url":"http://example.org/live/user/password/123.m3u8","playlist":"unsafe"},
            {"identity":"Bravo.us@West","url":"https://example.org/BRAVO/index.m3u8","playlist":"wrong-region"},
        ]
        selected,_,rejected,_=discovery.select(entries)
        self.assertFalse(selected)
        self.assertEqual(len(rejected),1)

    def test_duplicate_playlists_and_same_host_deduplicated(self):
        entries=[
            {"identity":"WPVI.us","url":"https://fl1.moveonjoy.com/PA_PHILADELPHIA_ABC/index.m3u8","playlist":"A"},
            {"identity":"WPVI.us","url":"https://fl1.moveonjoy.com/PA_PHILADELPHIA_ABC/index.m3u8","playlist":"B"},
            {"identity":"WPVI.us","url":"https://fl1.moveonjoy.com/PA_PHILADELPHIA_ABC_ALT/index.m3u8","playlist":"C"},
            {"identity":"WPVI.us","url":"https://different.example/PA_PHILADELPHIA_ABC/index.m3u8","playlist":"D"},
        ]
        selected,unique,_,deferred=discovery.select(entries)
        self.assertEqual(len(unique),3)
        self.assertEqual(len(selected),2)
        self.assertEqual({r["origin"] for r in selected},{"fl1.moveonjoy.com","different.example"})
        self.assertTrue(any(r["reason"]=="same-media-origin-as-selected" for r in deferred))
        self.assertEqual(sorted(next(r["sources"] for r in selected if r["origin"]=="fl1.moveonjoy.com")),["A","B"])

    def test_volatile_hosts_rank_below_distinct_reliable_origins(self):
        rows=[
            {"identity":"DisneyChannel.us","url":"http://212.5.144.156/disney/index.m3u8","playlist":"volatile"},
            {"identity":"DisneyChannel.us","url":"https://fresh.example/DISNEY/index.m3u8","playlist":"fresh"},
        ]
        selected,_,_,_=discovery.select(rows)
        self.assertEqual(selected[0]["origin"],"fresh.example")

    def test_philly_parsing_never_maps_generic_abc(self):
        lines="- [Philadelphia ABC](https://fl1.moveonjoy.com/PA_PHILADELPHIA_ABC/index.m3u8)\n- [Generic ABC](https://example.com/abc/index.m3u8)"
        rows=discovery.extract_markdown_locations(lines)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["identity"],"WPVI.us")

if __name__=="__main__":unittest.main()
