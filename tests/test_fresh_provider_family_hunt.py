"""Research-only tests. No network calls or media downloads."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
import fresh_provider_family_hunt as m

class FreshProviderFamilyTests(unittest.TestCase):
 def test_credential_shapes_are_excluded(self):
  self.assertTrue(m.has_credential_shape("http://iptv.test/live/name/secret/12345.m3u8"))
  self.assertTrue(m.has_credential_shape("https://api.test/api/stream/person@example.com/123/livetv.m3u8"))
  self.assertTrue(m.has_credential_shape("http://iptv.test:443/live/USER/PASS/42"))
  self.assertFalse(m.has_credential_shape("https://media.example.org/BRAVO/index.m3u8"))

 def test_skip_recycled_seeds_and_known_hosts(self):
  rows=[
   {"identity":"Bravo.us","url":"https://gpuserver3.tier1streams.com/BRAVO/index.m3u8","playlist":"already-covered","channel_label":"Bravo"},
   {"identity":"WPVI.us","url":"https://v-pi.theus6tv.tk/hls/6.1/playlist.m3u8","playlist":"historic-dead","channel_label":"ABC Philadelphia"},
   {"identity":"WCAU.us","url":"https://cdn.example.org/news-only.m3u8","playlist":"fast","channel_label":"NBC 10 Philadelphia News"},
  ]
  selected,rejected,_=m.novel_candidates(rows)
  self.assertFalse(selected)
  self.assertEqual(len(rejected),3)

 def test_new_unique_media_origin_has_provenance(self):
  rows=[
   {"identity":"Bravo.us","url":"https://newprovider.example/bravo/index.m3u8","playlist":"A","channel_label":"Bravo"},
   {"identity":"Bravo.us","url":"https://newprovider.example/bravo/index.m3u8","playlist":"B","channel_label":"Bravo"},
   {"identity":"Bravo.us","url":"https://another.example/bravo/index.m3u8","playlist":"C","channel_label":"Bravo"}
  ]
  selected,rejected,_=m.novel_candidates(rows)
  self.assertEqual(len(selected),2)
  self.assertFalse(rejected)
  self.assertEqual(next(x for x in selected if x["origin"]=="newprovider.example")["provenance"],["A","B"])

 def test_unknown_ids_not_inferred(self):
  content='#EXTM3U\n#EXTINF:-1,Philadelphia CBS News\nhttps://fake.example/kyw.m3u8\n#EXTINF:-1 tvg-id="KYWDT1.us@SD",CBS Philadelphia\nhttps://new.example/live/kyw/index.m3u8'
  results=list(m.candidate_rows(content,"test"))
  self.assertEqual(len(results),1)
  self.assertEqual(results[0]["identity"],"KYW.us")
if __name__=="__main__":unittest.main()
