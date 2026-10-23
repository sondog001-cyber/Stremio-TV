"""Offline tests for research-only VLC/Kodi public-header preprocessing."""
import unittest
from unittest import mock
from research import fresh_origin_discovery as d

def sample(seq):
    return d.parse_hls_snapshot(
        f"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:{seq}\n"
        "#EXTINF:4,\n1.ts\n#EXTINF:4,\n2.ts\n"
    )

class ResearchHeaderParsingTests(unittest.TestCase):
    def test_vlc_headers_only_for_matching_channel(self):
        entries=list(d.parse_m3u(
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="Nicktoons.us",Nicktoons\n'
            '#EXTVLCOPT:http-origin=https://player.example.com\n'
            '#EXTVLCOPT:http-referer=https://player.example.com/\n'
            '#EXTVLCOPT:http-user-agent=Mozilla/5.0\n'
            'https://feed.example.com/live.m3u8\n'
            '#EXTINF:-1 tvg-id="Bravo.us",Bravo\n'
            'https://feed.example.com/bravo.m3u8\n'
        ))
        self.assertEqual(len(entries),2)
        self.assertFalse(entries[0]["invalid"])
        self.assertEqual(entries[0]["url"],"https://feed.example.com/live.m3u8")
        self.assertEqual(entries[0]["public_headers"]["Origin"],"https://player.example.com")
        self.assertEqual(entries[0]["public_headers"]["Referer"],"https://player.example.com/")
        self.assertEqual(entries[1]["public_headers"],{})

    def test_pipe_syntax_and_encoded_url_are_not_sent_to_server(self):
        rows=list(d.parse_m3u(
            '#EXTINF:-1 tvg-id="Nicktoons.us",Nicktoons\n'
            'https://cdn.example.com/mono.m3u8|Origin=https%3A%2F%2Fplayer.example.com&Referer=https%3A%2F%2Fplayer.example.com%2F&User-Agent=Browser%2F1.0\n'
        ))
        self.assertEqual(rows[0]["url"],"https://cdn.example.com/mono.m3u8")
        self.assertEqual(rows[0]["public_headers"]["Referer"],"https://player.example.com/")
        self.assertEqual(rows[0]["public_headers"]["User-Agent"],"Browser/1.0")

    def test_multiple_kodi_pipe_sections(self):
        url,h=d.split_stream_locator('https://cdn.example.com/live.m3u8|Referer="https://site.example.com/"|Origin=https://site.example.com')
        self.assertEqual(url,"https://cdn.example.com/live.m3u8")
        self.assertEqual(h["Origin"],"https://site.example.com")

    def test_secrets_cookies_and_keys_rejected_without_leaking(self):
        bad=[
            'https://feed.example.com/mono.m3u8|Cookie=session%3Dsecret',
            'https://feed.example.com/mono.m3u8|Authorization=Bearer%20secret',
            'https://user:secret@feed.example.com/mono.m3u8',
            'https://feed.example.com/live/a@b.example.com/password/3.m3u8',
            'https://feed.example.com/mono.m3u8|Referer=http://127.0.0.1/',
            'https://feed.example.com/mono.m3u8|Origin=https://site.example.com/?token=secret',
        ]
        for url in bad:
            with self.subTest(url=url):
                row=list(d.parse_m3u('#EXTINF:-1 tvg-id="Nicktoons.us",Nicktoons\n'+url+'\n'))[0]
                self.assertTrue(row["invalid"])
                self.assertEqual(row["url"],"")
                self.assertNotIn("secret",str(row))
        row=list(d.parse_m3u(
            '#EXTINF:-1 tvg-id="Nicktoons.us",Nicktoons\n'
            '#EXTVLCOPT:http-cookie=secret\n'
            'https://cdn.example.com/live.m3u8\n'
        ))[0]
        self.assertTrue(row["invalid"])

    def test_reject_kodi_drm_property(self):
        row=list(d.parse_m3u(
            '#EXTINF:-1 tvg-id="Nicktoons.us",Nicktoons\n'
            '#KODIPROP:inputstream.adaptive.license_key=notallowed\n'
            'https://cdn.example.com/live.m3u8\n'
        ))[0]
        self.assertTrue(row["invalid"])

    @mock.patch.object(d.time,"sleep")
    @mock.patch.object(d,"fetch_media_sample",return_value={"final_media_host":"cdn.example.com","readable":True})
    @mock.patch.object(d,"media_snapshot")
    def test_headers_reach_manifest_and_segment_preflight(self,snap,media,sleep):
        record={"status":200,"final":"https://cdn.example.com/media.m3u8"}
        snap.side_effect=[(record,sample(9)),(record,sample(10))]
        headers={"Referer":"https://player.example.com/"}
        result=d.probe_manifest("https://cdn.example.com/live.m3u8",headers=headers)
        self.assertEqual(result["stage"],"progressing-hls-readable-not-decoded")
        self.assertEqual(snap.call_args_list[0].kwargs["headers"],headers)
        self.assertEqual(snap.call_args_list[1].kwargs["headers"],headers)
        self.assertEqual(media.call_args.kwargs["headers"],headers)
        self.assertFalse(result["authorized_origin_confirmed"])

if __name__=="__main__":
    unittest.main()
