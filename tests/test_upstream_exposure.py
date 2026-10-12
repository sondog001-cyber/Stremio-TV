import unittest
from copy import deepcopy

from upstream_exposure import analyze, summary_markdown


def row(tvg_id, streams, hosts, families, pairs=None, **other):
    result = {
        "tvg_id": tvg_id, "name": tvg_id, "stream_count": streams,
        "provider_hosts": hosts, "provider_families": families,
        "host_family_pairs": pairs or [],
        "locally_verified_count": 0, "normal_qa_stream_count": streams,
    }
    result.update(other)
    return result


class ExposureReportTests(unittest.TestCase):
    def setUp(self):
        self.channels = [
            row("MLBNetwork.us", 1, ["provider.test"], ["tvnow"],
                [{"host": "provider.test", "family": "tvnow"}],
                locally_verified_count=1, normal_qa_stream_count=0),
            row("HGTV.us", 2, ["provider.test"], ["tvnow", "mirror"],
                [{"host": "provider.test", "family": "tvnow"},
                 {"host": "provider.test", "family": "mirror"}]),
            row("WHYY.us", 1, ["station.example"], ["official"],
                [{"host": "station.example", "family": "official"}]),
            row("TLC.us", 2, ["provider.test", "alt.example"], ["tvnow", "iptv-org"],
                [{"host": "provider.test", "family": "tvnow"},
                 {"host": "alt.example", "family": "iptv-org"}]),
        ]
        self.status = {"build_id": "b1", "built_at": "2026-10-12T15:00:00Z"}
        self.reliability = {"history": [
            {"build_id": "b0", "lost_ids": ["MLBNetwork.us", "HGTV.us"]},
            {"build_id": "b1", "lost_ids": ["WHYY.us"]},
        ]}

    def test_host_blast_radius_and_unprotected_count(self):
        result = analyze(self.status, {"channels": self.channels}, self.reliability, {})
        hosts = {x["host"]: x for x in result["all_host_failure_risks"]}
        self.assertEqual(hosts["provider.test"]["published_channels_exposed"], 3)
        self.assertEqual(hosts["provider.test"]["channels_without_distinct_host_alternative"], 2)
        self.assertTrue(hosts["provider.test"]["multiple_family_labels_same_host"])
        self.assertEqual(hosts["alt.example"]["published_channels_exposed"], 1)
        self.assertFalse(hosts["alt.example"]["multiple_family_labels_same_host"])
        self.assertEqual(result["summary"]["single_stream_channels"], 2)
        self.assertEqual(result["summary"]["same_host_multi_stream_channels"], 1)
        self.assertEqual(result["summary"]["multi_host_channels_unverified_independence"], 1)

    def test_ranks_vulnerable_channels_without_marking_mirrors_independent(self):
        result = analyze(self.status, {"channels": self.channels}, self.reliability, {})
        priority = result["all_backup_targets"]
        self.assertEqual({x["tvg_id"] for x in priority},
                         {"MLBNetwork.us", "HGTV.us", "WHYY.us"})
        self.assertEqual(priority[0]["tvg_id"], "MLBNetwork.us")
        self.assertTrue(all(row["backup_search_needed"] for row in priority))
        self.assertTrue(result["advisory_only"])
        self.assertTrue(result["no_source_publication_or_ranking_change"])
        self.assertIn("Different DNS hosts", summary_markdown(result))

    def test_per_stream_host_family_evidence_prevents_false_mapping(self):
        channels = deepcopy(self.channels)
        channels[3]["provider_families"] = ["tvnow", "mirror", "iptv-org"]
        result = analyze(self.status, {"channels": channels}, self.reliability, {})
        alt = next(h for h in result["all_host_failure_risks"] if h["host"] == "alt.example")
        self.assertEqual(alt["explicit_source_families"], ["iptv-org"])

    def test_simultaneous_losses_are_not_attributed_to_hosts(self):
        result = analyze(self.status, {"channels": self.channels}, self.reliability, {})
        self.assertEqual(len(result["coincident_channel_losses"]), 1)
        self.assertIn("unknown", result["coincident_channel_losses"][0]["attribution"])

    def test_unknown_host_and_empty_history_are_safe(self):
        channels = [row("Unresolved.us", 1, [], ["unknown"])]
        result = analyze({}, {"channels": channels}, {}, {})
        self.assertEqual(result["all_backup_targets"][0]["exposure"], "single_stream")
        self.assertEqual(result["top_10_host_failure_risks"], [])
        self.assertEqual(result["summary"]["simultaneous_loss_events"], 0)

    def test_source_inputs_not_modified(self):
        redundancy = {"channels": deepcopy(self.channels)}
        orig = deepcopy(redundancy)
        analyze(self.status, redundancy, self.reliability, {})
        self.assertEqual(redundancy, orig)


if __name__ == "__main__":
    unittest.main()
