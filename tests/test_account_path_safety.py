import json
import unittest
import build

class AccountPathSafetyTests(unittest.TestCase):
    def rejected(self, url):
        kept, rejected = build.apply_safety_controls([{'url':url,'tvg_id':'Test.us','headers':{}}], {})
        self.assertEqual(kept, [])
        self.assertEqual(len(rejected), 1)
        return rejected[0]

    def test_global_gate_rejects_account_query_and_email_path(self):
        for url in ['https://media.example.test/live.m3u8?username=dummyuser&password=dummypassword',
                    'https://media.example.test/viewer%40example.test/channel.m3u8']:
            with self.subTest(url=url):
                row=self.rejected(url)
                self.assertTrue(row['reason'].startswith('embedded-account-'))

    def test_global_gate_rejects_xtream_layout_on_standard_and_custom_ports(self):
        for path in ['/live/dummyuser/dummypassword/123.ts', '/dummyuser/dummypassword/123', '/movie/dummyuser/dummypassword/123.mp4']:
            for port in ['', ':25461', ':8080']:
                with self.subTest(path=path,port=port):self.rejected('https://media.example.test'+port+path)

    def test_rejection_report_contains_fingerprint_without_credentials(self):
        for url in ['https://dummyuser:dummypassword@media.example.test/live.m3u8',
                    'https://media.example.test/dummyuser/dummypassword/123',
                    'https://media.example.test/a.m3u8?username=dummyuser&password=dummypassword']:
            row=self.rejected(url)
            serialized=json.dumps(row)
            self.assertNotIn('dummyuser',serialized)
            self.assertNotIn('dummypassword',serialized)
            self.assertEqual(len(row['url_sha256']),64)
            self.assertEqual(row['url'],'https://media.example.test/[credential-url-redacted]')

    def test_public_media_namespaces_and_signed_urls_stay_unchanged(self):
        urls=['https://media.example.test/stream/group/123/master.m3u8',
              'https://media.example.test/api/stream/123',
              'https://media.example.test/live3/F128/index.m3u8?st=publicsignature&e=1999999999',
              'https://media.example.test/live.m3u8?token=public-signature']
        entries=[{'url':url,'tvg_id':'Test.us','headers':{}} for url in urls]
        kept,rejected=build.apply_safety_controls(entries,{})
        self.assertEqual(rejected,[])
        self.assertEqual([x['url'] for x in kept],urls)

    def test_kill_switch_report_also_redacts_account_url(self):
        url='https://media.example.test/dummyuser/dummypassword/123'
        kept,rejected=build.apply_safety_controls([{'url':url,'tvg_id':'Test.us','headers':{}}],{'safety_controls':{'disabled_urls':[url]}})
        self.assertEqual(kept,[])
        self.assertEqual(rejected[0]['reason'],'url-kill-switch')
        self.assertNotIn('dummypassword',json.dumps(rejected))
        self.assertNotIn('dummyuser',json.dumps(rejected))
