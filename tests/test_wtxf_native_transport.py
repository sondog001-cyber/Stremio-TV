import unittest
from unittest import mock
import build

class Response:
    def __init__(self, url, body, content_type='application/vnd.apple.mpegurl'):
        self.url, self.body = url, body
        self.headers = {'Content-Type': content_type}
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def geturl(self): return self.url
    def read(self, limit): return self.body[:limit]

class WtxfNativeTransportTests(unittest.TestCase):
    host = 'amg00488-foxdigital-fox29philadelphiawtx-vizious-x0v1b.amagi.tv'
    slug = 'amg00488-foxdigital-fox29philadelphiawtx-vizious'
    def setUp(self):
        self.root = f'https://{self.host}/playlist/{self.slug}/playlist.m3u8'
        self.rendition = f'https://{self.host}/native/index.m3u8'
        self.beacon = f'https://{self.host}/beacon/extensionless?redirect_url=segment.ts'
        self.master = f'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080\n{self.rendition}\n'.encode()
        self.playlist = f'#EXTM3U\n#EXTINF:6,\n{self.beacon}\n'.encode()
        self.ts = b''.join(b'\x47' + b'\x00' * 187 for _ in range(6))
    def responses(self, playlist=None, sample=None, content_type='video/MP2T'):
        return [Response(self.root, self.master), Response(self.rendition, playlist or self.playlist), Response(f'https://{self.host}/segment.ts', self.ts if sample is None else sample, content_type)]
    def test_verified_native_ts_uses_scoped_input_options_and_https_only(self):
        with mock.patch('build.urllib.request.urlopen', side_effect=self.responses()) as fetch:
            url, options = build._verified_native_hls_decoder_input(self.root, {})
        self.assertEqual(url, self.rendition)
        self.assertEqual(options, ['-extension_picky', '0', '-protocol_whitelist', 'https,tls,tcp,httpproxy'])
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(fetch.call_args.args[0].get_header('Range'), 'bytes=0-1023')
    def test_other_hosts_insecure_urls_and_lookalikes_keep_strict_decoder(self):
        urls = [self.root.replace('https:', 'http:'), self.root.replace(self.host, self.host + '.example.test'), self.root.replace(self.slug + '/playlist.m3u8', 'other/playlist.m3u8'), self.root + '?token=example', 'https://example.test/playlist.m3u8']
        with mock.patch('build.urllib.request.urlopen') as fetch:
            for url in urls: self.assertEqual(build._verified_native_hls_decoder_input(url, {}), (url, []))
        fetch.assert_not_called()
    def test_external_or_local_segment_uris_do_not_receive_compatibility_options(self):
        for segment in ['https://other.test/media', 'http://127.0.0.1/media', 'file:///etc/passwd']:
            playlist = f'#EXTM3U\n#EXTINF:6,\n{segment}\n'.encode()
            with mock.patch('build.urllib.request.urlopen', side_effect=self.responses(playlist=playlist)) as fetch:
                self.assertEqual(build._verified_native_hls_decoder_input(self.root, {}), (self.root, []))
                self.assertEqual(fetch.call_count, 2)
    def test_encrypted_or_fragmented_media_keeps_strict_decoder(self):
        for tag in ['#EXT-X-KEY:METHOD=AES-128,URI="key"', '#EXT-X-MAP:URI="init.mp4"']:
            playlist = ('#EXTM3U\n' + tag + '\n#EXTINF:6,\n' + self.beacon + '\n').encode()
            with mock.patch('build.urllib.request.urlopen', side_effect=self.responses(playlist=playlist)):
                self.assertEqual(build._verified_native_hls_decoder_input(self.root, {}), (self.root, []))
    def test_images_invalid_transport_and_wrong_content_type_do_not_get_options(self):
        for sample, kind in [(b'\x89PNG' + b'\x00' * 1020, 'video/MP2T'), (b'\x00' * 1024, 'video/MP2T'), (self.ts, 'text/html')]:
            with mock.patch('build.urllib.request.urlopen', side_effect=self.responses(sample=sample, content_type=kind)):
                self.assertEqual(build._verified_native_hls_decoder_input(self.root, {}), (self.root, []))
    def test_network_failure_keeps_strict_decoder(self):
        with mock.patch('build.urllib.request.urlopen', side_effect=OSError('timeout')):
            self.assertEqual(build._verified_native_hls_decoder_input(self.root, {}), (self.root, []))

if __name__ == '__main__': unittest.main()
