import unittest

from deployment_guard import evaluate_deployment_guard


class DeploymentGuardTests(unittest.TestCase):
    def setUp(self):
        self.config = {"deployment_guard": {
            "enabled": True, "minimum_channels": 86,
            "required_channel_ids": [
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

    def test_passing_86_channel_deployed_baseline_and_suffix_id(self):
        self.assertEqual(
            evaluate_deployment_guard(self.config, {"channels": 86}, self.published[:86]),
            [],
        )

    def test_blocks_regression_below_current_86_channel_floor(self):
        dropped = self.published[:85]
        errors = evaluate_deployment_guard(self.config, {"channels": 85}, dropped)
        self.assertTrue(any("below established floor" in err for err in errors))

    def test_allows_net_gain_even_when_old_failed_channels_are_missing(self):
        # Bravo and Hallmark have been absent from the current live 86-channel deployment.
        # Gaining CBS Sports Network must not be blocked by their historical pins.
        recovered = [c for c in self.published
                     if not c["tvg_id"].startswith(("Bravo.", "HallmarkChannel."))]
        recovered.append({"tvg_id": "CBSSportsNetwork.us"})
        self.assertEqual(len(recovered), 87)
        self.assertEqual(
            evaluate_deployment_guard(self.config, {"channels": 87}, recovered),
            [],
        )

    def test_blocks_loss_of_still_present_critical_identity(self):
        altered = [c for c in self.published if not c["tvg_id"].startswith("History.")]
        altered.append({"tvg_id": "OtherReplacement.us"})
        errors = evaluate_deployment_guard(self.config, {"channels": 88}, altered)
        self.assertTrue(any("History.us" in err for err in errors))

    def test_blocks_inconsistent_reported_channel_count(self):
        errors = evaluate_deployment_guard(self.config, {"channels": 88}, self.published[:-1])
        self.assertTrue(any("diagnostics list" in err for err in errors))

    def test_disabled_guard_does_not_block(self):
        self.config["deployment_guard"]["enabled"] = False
        errors = evaluate_deployment_guard(self.config, {"channels": 0}, [])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
