import unittest

import build


class ResourceCacheHintTests(unittest.TestCase):
    def test_cached_resource_uses_stremio_epg_refresh_policy(self):
        payload = build.cached_resource({"meta": {"id": "stremiotv_test"}})

        self.assertEqual(payload["meta"]["id"], "stremiotv_test")
        self.assertEqual(payload["cacheMaxAge"], 300)
        self.assertEqual(payload["staleRevalidate"], 1800)
        self.assertEqual(payload["staleError"], 604800)

    def test_cached_resource_does_not_mutate_original_payload(self):
        original = {"metas": []}
        cached = build.cached_resource(original)

        self.assertEqual(original, {"metas": []})
        self.assertIsNot(cached, original)


if __name__ == "__main__":
    unittest.main()
