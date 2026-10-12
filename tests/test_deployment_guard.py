import unittest

from deployment_guard import evaluate_deployment_guard


class DeploymentGuardTests(unittest.TestCase):
    def setUp(self):
        self.config = {"deployment_guard": {
            "enabled": True, "minimum_channels": 88,
            "required_channel_ids": [
                "Bravo.us", "HallmarkChannel.us",
                "DisneyChannel.us", "NationalGeographic.us", "History.us",
            ],
        }}
        self.published = [
            {"tvg_id": "Bravo.us@East"},
            {"tvg_id": "HallmarkChannel.us@East"},
            {"tvg_id": "DisneyChannel.us"},
            {"tvg_id": "NationalGeographic.us"},
            {"tvg_id": "History.us@East"},
        ] + [{"tvg_id": "Other%03d.us" % n} for n in range(83)]

    def test_passing_88_channel_baseline_and_suffix_id(self):
        self.assertEqual(
            evaluate_deployment_guard(self.config, {"channels": 88}, self.published),
            [],
        )

    def test_blocks_86_channel_regression(self):
        dropped = [c for c in self.published if not c["tvg_id"].startswith(("Bravo.", "HallmarkChannel."))]
        errors = evaluate_deployment_guard(self.config, {"channels": 86}, dropped)
        self.assertTrue(any("below established floor" in err for err in errors))
        self.assertTrue(any("Bravo.us" in err and "HallmarkChannel.us" in err for err in errors))

    def test_blocks_loss_of_critical_identity_even_with_88_channels(self):
        altered = self.published[1:] + [{"tvg_id": "OtherReplacement.us"}]
        errors = evaluate_deployment_guard(self.config, {"channels": 88}, altered)
        self.assertTrue(any("Bravo.us" in err for err in errors))

    def test_blocks_inconsistent_reported_channel_count(self):
        errors = evaluate_deployment_guard(self.config, {"channels": 88}, self.published[:-1])
        self.assertTrue(any("diagnostics list" in err for err in errors))

    def test_disabled_guard_does_not_block(self):
        self.config["deployment_guard"]["enabled"] = False
        errors = evaluate_deployment_guard(self.config, {"channels": 0}, [])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
