"""All tests are offline: no player access, no fetching media."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
import live_player_mechanism_audit as a
from unittest.mock import patch

class OfficialPlayerAuditTests(unittest.TestCase):
 def test_live_player_stations_are_not_assumed_verified(self):
  for p in a.WATCH_PAGES:
   with patch.object(a,"safe_fetch",return_value=({"ok":True,"http":200,"body":"Watch live 24/7 <source src='https://cdn.fake/channel.m3u8?token=secret'>","content_type":"text/html","redirected_host":"example.org"},None)):
    r=a.inspect(p)
   self.assertFalse(r["promotable_to_full_network"])
   self.assertFalse(r["exact_live_programme_verified"])
   self.assertNotIn("token=secret",str(r))
 def test_nbc_channels_require_subscriber_auth(self):
  for target in ("Bravo.us","USANetwork.us","E.us"):
   p=next(v for v in a.WATCH_PAGES if v["identity"]==target)
   with patch.object(a,"safe_fetch",return_value=({"ok":True,"http":200,"body":"Watch LIVE","content_type":"text/html","redirected_host":"example.org"},None)):
    result=a.inspect(p)
   self.assertEqual(result["access"],"TVE_subscriber_login_required")
 def test_local_news_not_full_affiliate(self):
  for target in ("WCAU.us","KYW.us"):
   p=next(v for v in a.WATCH_PAGES if v["identity"]==target)
   with patch.object(a,"safe_fetch",return_value=({"ok":True,"http":200,"body":"local news live","content_type":"text/html","redirected_host":"example.org"},None)):
    r=a.inspect(p)
   self.assertEqual(r["access"],"public_news_or_24_7_not_full_affiliate")
 def test_strip_tokens_from_embedded_urls(self):
  u="https://cdn.example.org/path/a.m3u8?jwt=supersecret"
  self.assertEqual(a.redact(u),"https://cdn.example.org/path/a.m3u8")
if __name__=="__main__":unittest.main()
