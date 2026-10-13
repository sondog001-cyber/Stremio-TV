"""Offline unit tests for the research-only HLS progression gate."""
import unittest
from unittest import mock
from research import fresh_origin_discovery as d


def media(seq, end="3.ts", target=6):
    return d.parse_hls_snapshot(
        f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:{target}\n"
        f"#EXT-X-MEDIA-SEQUENCE:{seq}\n#EXTINF:6,\n2.ts\n#EXTINF:6,\n{end}\n"
    )


class HlsPreflightTests(unittest.TestCase):
    def test_parse_live_progression_fields(self):
        item = media(81, "next.ts", 5)
        self.assertEqual(item["kind"], "media")
        self.assertEqual(item["sequence"], 81)
        self.assertEqual(item["target_duration"], 5)
        self.assertEqual(item["segments"][-1], "next.ts")

    def test_reject_master_vod_and_keyed_media(self):
        self.assertEqual(d.parse_hls_snapshot(
            "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000\nchild.m3u8")["kind"], "master")
        self.assertEqual(d.parse_hls_snapshot(
            "#EXTM3U\n#EXT-X-ENDLIST\n#EXTINF:5,\na.ts\n#EXTINF:5,\nb.ts")["kind"],
            "on-demand-not-live")
        self.assertEqual(d.parse_hls_snapshot(
            "#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"secret\"\n"
            "#EXTINF:5,\na.ts\n#EXTINF:5,\nb.ts")["kind"], "encrypted-or-keyed")
        self.assertEqual(d.parse_hls_snapshot("<html>not hls</html>")["kind"], "invalid")

    @mock.patch.object(d.time, "sleep")
    @mock.patch.object(d, "fetch_media_sample",
                       return_value={"readable": True, "final_media_host": "origin.example.com"})
    @mock.patch.object(d, "media_snapshot")
    def test_progressing_usable_media_not_approved(self, snapshots, sample, sleep):
        base = {"status": 200, "final": "https://origin.example.com/live.m3u8"}
        snapshots.side_effect = [(base, media(20, "22.ts")),
                                 (base, media(21, "23.ts"))]
        result = d.probe_manifest(base["final"])
        self.assertEqual(result["stage"], "progressing-hls-readable-not-decoded")
        self.assertTrue(result["media_bytes_readable"])
        self.assertFalse(result["original_video_origin_verified"])
        self.assertFalse(result["authorized_origin_confirmed"])
        self.assertEqual(result["sequence_after"], 21)
        self.assertEqual(sample.call_count, 1)
        self.assertEqual(sleep.call_count, 1)

    @mock.patch.object(d.time, "sleep")
    @mock.patch.object(d, "fetch_media_sample")
    @mock.patch.object(d, "media_snapshot")
    def test_stale_manifest_never_samples_video(self, snapshots, sample, _sleep):
        base = {"status": 200, "final": "https://origin.example.com/live.m3u8"}
        snapshots.side_effect = [(base, media(20, "22.ts")),
                                 (base, media(20, "22.ts"))]
        result = d.probe_manifest(base["final"])
        self.assertEqual(result["stage"], "hls-window-not-progressing")
        sample.assert_not_called()


if __name__ == "__main__":
    unittest.main()
