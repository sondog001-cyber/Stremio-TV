import datetime as dt
import json
import unittest
import build

class FslPublicPlayerTests(unittest.TestCase):
    def setUp(self):
        self.source = {'url': 'https://xstream.st/fslivepro.php?stream=F128', 'tvg_id': 'CBSSportsNetwork.us'}
        self.expiry = int(dt.datetime.now(build.UTC).timestamp()) + 10800
        self.url = f'https://instreams.live/live3/F128/index.m3u8?st=abcdefghijklmnopqrstuv&e={self.expiry}'
    def parse(self, urls):
        return build._parse_fsl_public_player('const streamUrls=' + json.dumps(urls) + ';', self.source)
    def test_preserves_signed_url_and_player_headers(self):
        entry, = self.parse([self.url])
        self.assertEqual(entry['url'], self.url)
        self.assertEqual(entry['tvg_id'], 'CBSSportsNetwork.us')
        self.assertEqual(entry['headers']['Referer'], self.source['url'])
        self.assertEqual(entry['provenance']['expires_at'], self.expiry)
    def test_rejects_short_lifetime(self):
        self.assertEqual(self.parse([self.url.replace(str(self.expiry), str(self.expiry - 600))]), [])
    def test_requires_exact_media_host_path_and_mapping(self):
        for url in [self.url.replace('instreams.live', 'evil.test'), self.url.replace('F128/', 'F191/'), self.url.replace('https:', 'http:'), self.url.replace('instreams.live/', 'user:pass@instreams.live/'), self.url.replace('instreams.live/', 'instreams.live:444/'), self.url + '&key=secret']:
            with self.subTest(url=url): self.assertEqual(self.parse([url]), [])
    def test_does_not_evaluate_page_code(self):
        self.assertEqual(build._parse_fsl_public_player('const streamUrls=fetch("/secret");', self.source), [])
        self.assertEqual(self.parse({'url': self.url}), [])
    def test_rejects_wrong_player_page(self):
        self.source['url'] += '&channel=other'
        self.assertEqual(self.parse([self.url]), [])
    def test_empty_page_has_no_candidates(self):
        self.assertEqual(build._parse_fsl_public_player('', self.source), [])

    def test_reads_fresh_literal_cbs_cdn_without_changing_signature(self):
        fresh = self.url.replace('instreams.live', 'edge1.candyshop.st')
        entry, = self.parse(['https://edge2.candyshop.st/live3/F128/index.m3u8?st=abcdefghijklmnopqrstuv&e=' + str(self.expiry)] * 3 + [fresh])
        self.assertEqual(entry['url'], fresh)
        self.assertEqual(entry['headers']['Referer'], self.source['url'])
        self.assertEqual(entry['family'], 'fsl-public-player')

    def test_new_cdn_retains_lifetime_identity_and_auth_boundaries(self):
        fresh = self.url.replace('instreams.live', 'edge1.candyshop.st')
        for bad in [fresh.replace(str(self.expiry), str(self.expiry - 600)), fresh.replace('F128/', 'F191/'), fresh.replace('edge1.candyshop.st', 'edge1.candyshop.st.evil.test'), fresh + '&auth=token', fresh.replace('https://', 'https://user:pass@')]:
            with self.subTest(url=bad):
                self.assertEqual(self.parse([bad]), [])
