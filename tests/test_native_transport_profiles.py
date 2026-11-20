import datetime as dt
import unittest
from unittest import mock
import build

class NativeTransportProfileTests(unittest.TestCase):
    @staticmethod
    def response(url, data, kind='application/vnd.apple.mpegurl'):
        item = mock.MagicMock()
        item.__enter__.return_value = item
        item.geturl.return_value = url
        item.headers = {'Content-Type': kind}
        item.read.side_effect = lambda limit: data[:limit]
        return item

    def setUp(self):
        self.expiry = int(dt.datetime.now(dt.timezone.utc).timestamp()) + 10800
        self.fsl = f'https://edge1.candyshop.st/live3/F128/index.m3u8?st=abcdefghijklmnopqrstuv&e={self.expiry}'
        self.fsl_headers = {'Referer': 'https://xstream.st/fslivepro.php?stream=F128'}
        self.tvnow = 'https://cache0.wonvt.st/live/0hzz30t0ddti3x1upnrpx/master.m3u8'
        self.ts = (b'\x47' + b'\x00' * 187) * 6

    def test_literal_fsl_feed_requires_native_ts_before_accepting_js_segment_paths(self):
        segment = 'https://edge1.candyshop.st/live3/F128/segment.js'
        playlist = f'#EXTM3U\n#EXTINF:6,\n{segment}\n'.encode()
        responses = [self.response(self.fsl, playlist), self.response(segment, self.ts, 'video/mp2t')]
        with mock.patch('build.urllib.request.urlopen', side_effect=responses):
            url, options = build._verified_native_hls_decoder_input(self.fsl, self.fsl_headers)
        self.assertEqual(url, self.fsl)
        self.assertIn('-extension_picky', options)
        self.assertEqual(options[-1], 'https,tls,tcp,httpproxy')

    def test_fsl_expiry_channel_referrer_and_signature_shape_are_not_relaxed(self):
        bad = [(self.fsl.replace(str(self.expiry), '1'), self.fsl_headers),
               (self.fsl, {'Referer': 'https://xstream.st/fslivepro.php?stream=F191'}),
               (self.fsl.replace('abcdefghijklmnopqrstuv', 'short'), self.fsl_headers),
               (self.fsl + '&password=bad', self.fsl_headers)]
        with mock.patch('build.urllib.request.urlopen') as fetch:
            for url, headers in bad:
                self.assertEqual(build._verified_native_hls_decoder_input(url, headers), (url, []))
        fetch.assert_not_called()

    def test_known_tvnow_profile_accepts_octet_stream_only_with_transport_sync(self):
        segment = 'https://silver-harbor-27.lifeisaware.workers.dev/s/native'
        playlist = f'#EXTM3U\n#EXTINF:6,\n{segment}\n'.encode()
        headers = {'Referer': 'https://tvnow.st/'}
        for media, expected in [(self.ts, True), (b'<html>' + b'0' * 1024, False)]:
            responses = [self.response(self.tvnow, playlist), self.response(segment, media, 'application/octet-stream')]
            with mock.patch('build.urllib.request.urlopen', side_effect=responses):
                url, options = build._verified_native_hls_decoder_input(self.tvnow, headers)
            self.assertEqual(url, self.tvnow)
            self.assertEqual(bool(options), expected)

    def test_unknown_tvnow_channels_or_foreign_segment_hosts_keep_strict_defaults(self):
        with mock.patch('build.urllib.request.urlopen') as fetch:
            url = self.tvnow.replace('0hzz30t0ddti3x1upnrpx', 'unknown')
            self.assertEqual(build._verified_native_hls_decoder_input(url, {'Referer': 'https://tvnow.st/'}), (url, []))
        fetch.assert_not_called()
        playlist = b'#EXTM3U\n#EXTINF:6,\nhttps://foreign.workers.dev/segment\n'
        with mock.patch('build.urllib.request.urlopen', side_effect=[self.response(self.tvnow, playlist)]) as fetch:
            self.assertEqual(build._verified_native_hls_decoder_input(self.tvnow, {'Referer': 'https://tvnow.st/'}), (self.tvnow, []))
            self.assertEqual(fetch.call_count, 1)

    def test_exact_xumo_hallmark_feed_requires_native_media_and_trusted_hosts(self):
        root = 'https://dbrb49pjoymg4.cloudfront.net/v1/master/3fec3e5cac39a52b2132f9c66c83dae043dc17d4/prod_default_xumo-ams-aws/master.m3u8?ads.xumo_channelId=99991709'
        segment = 'https://hls-beacons-us.xumo.com/native-media'
        playlist = f'#EXTM3U\n#EXTINF:6,\n{segment}\n'.encode()
        responses = [self.response(root, playlist), self.response('https://live-content-cf.xumo.com/native.ts', self.ts, 'video/MP2T')]
        with mock.patch('build.urllib.request.urlopen', side_effect=responses):
            url, options = build._verified_native_hls_decoder_input(root, {})
        self.assertEqual(url, root)
        self.assertIn('-extension_picky', options)
        with mock.patch('build.urllib.request.urlopen') as fetch:
            for wrong in [root.replace('99991709', '99999999'), root + '&extra=value', root.replace('cloudfront.net/', 'cloudfront.net.evil.test/')]:
                self.assertEqual(build._verified_native_hls_decoder_input(wrong, {}), (wrong, []))
        fetch.assert_not_called()
        for final, data in [('https://untrusted.test/segment.ts', self.ts), (segment, b'not transport stream' * 50)]:
            responses = [self.response(root, playlist), self.response(final, data, 'video/mp2t')]
            with mock.patch('build.urllib.request.urlopen', side_effect=responses):
                self.assertEqual(build._verified_native_hls_decoder_input(root, {}), (root, []))

if __name__ == '__main__': unittest.main()
