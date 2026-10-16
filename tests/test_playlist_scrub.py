import datetime as dt
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import playlist_scrub as scrub


NOW = dt.datetime(2026, 10, 15, tzinfo=dt.timezone.utc)
ROSTER = ["History.us", "USANetwork.us", "NationalGeographic.us", "Fox.us@WTXFTV"]


def entry(tvg="History.us@East", url="https://media.example.com/history/index.m3u8", **kw):
    return {"tvg_id": tvg, "url": url, "headers": {}, "family": "iptv-org", **kw}


def sources(*entries, status="ok"):
    return [({"name": "Public list", "url": "https://example.com/us.m3u", "status": status}, list(entries))]


class PlaylistScrubTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_first_inventory_is_not_claimed_as_new_discoveries(self):
        report, seen = scrub.run(self.config, ROSTER, {}, [], sources(entry()), NOW)
        self.assertEqual(report["summary"]["new_candidates"], 0)
        self.assertEqual(report["summary"]["initial_inventory_candidates"], 1)
        self.assertEqual(len(seen), 1)

    def test_replay_deduplicates_across_lists_and_finds_only_new_channel_urls(self):
        _, seen = scrub.run(self.config, ROSTER, {}, [], sources(entry()), NOW)
        more = sources(entry(), entry(url="https://new.example.com/history.m3u8"))
        more += sources(entry())
        report, updated = scrub.run(self.config, ROSTER, {"seen": seen}, [], more, NOW)
        self.assertEqual(report["summary"]["safe_exact_candidates"], 2)
        self.assertEqual(report["summary"]["new_candidates"], 1)
        self.assertEqual(report["summary"]["new_provider_hosts"], 1)
        self.assertEqual(len(updated), 2)

    def test_current_build_candidates_are_not_mislabeled_as_new(self):
        with patch.object(scrub.build, "_probe_stream") as probe:
            report, _ = scrub.run(self.config, ROSTER, {"seen": {}}, [entry()], sources(entry()), NOW, 3)
        self.assertEqual(report["summary"]["new_candidates"], 0)
        probe.assert_not_called()

    def test_unprobed_new_candidate_remains_queued_after_becoming_known(self):
        _, seen = scrub.run(self.config, ROSTER, {}, [], sources(entry()), NOW)
        with patch.object(scrub.build, "_probe_stream", return_value={"status": "failed"}) as probe:
            report, _ = scrub.run(self.config, ROSTER, {"seen": seen}, [], sources(entry()), NOW, 3)
        self.assertEqual(report["summary"]["new_candidates"], 0)
        probe.assert_called_once()

    def test_failed_or_empty_playlist_does_not_erase_history(self):
        _, seen = scrub.run(self.config, ROSTER, {}, [], sources(entry()), NOW)
        report, updated = scrub.run(self.config, ROSTER, {"seen": seen}, [], sources(status="failed"), NOW)
        self.assertEqual(report["summary"]["playlist_errors"], 1)
        self.assertEqual(updated, seen)

    def test_no_west_foreign_fast_or_wrong_affiliate_substitution(self):
        samples = [entry("History.us@West"), entry("HistoryLatinAmerica.us@Panregional"),
                   entry("HistoryHit.uk"), entry("Fox.us@WNYW"), entry("Fox.us@WTXFTV"),
                   entry("NationalGeographic.us@HDEast")]
        report, _ = scrub.run(self.config, ROSTER, {}, [], sources(*samples), NOW)
        self.assertEqual({r["tvg_id"] for r in report["candidates"]},
                         {"Fox.us@WTXFTV", "NationalGeographic.us"})

    def test_explicit_identity_rejections_apply_even_with_matching_playlist_id(self):
        self.config["curation"]["identity_rules"]["History.us"] = {
            "accept": ["History"], "reject": ["History Vault"]}
        report, _ = scrub.run(self.config, ROSTER, {}, [],
                              sources(entry(name="History Vault")), NOW)
        self.assertEqual(report["candidates"], [])

    def test_credentials_kill_switch_and_quarantine_are_not_exposed_or_probed(self):
        url = entry()["url"]
        self.config["curation"]["stream_quarantine"].append({"tvg_id": "History.us", "url": url})
        samples = [entry(), entry(url="https://example.com/live/secretuser/secretpass/12.m3u8"),
                   entry(url="https://secretuser:secretpass@example.com/x.m3u8"),
                   entry(headers={"Authorization": "Bearer secret"}),
                   entry(url="https://example.com/x.m3u8?password=secret"),
                   entry(url="http://example.com:2095/secretuser/secretpass/164"),
                   entry(url="https://example.com/live.php?mac=00:11:22:33:44:55"),
                   entry(url="http://example.com/123456/987654/123.ts"),
                   entry(url="https://example.com/x.m3u8?e=1600000000&token=secret"),
                   entry(url="https://proxy.workers.dev/history.m3u8")]
        report, seen = scrub.run(self.config, ROSTER, {}, [], sources(*samples), NOW, 3)
        self.assertEqual(report["candidates"], [])
        self.assertEqual(seen, {})
        self.assertNotIn("secret", json.dumps(report))

    def test_bounded_decoder_triage_preserves_failure_and_does_not_grant_override(self):
        samples = [entry(url=f"https://media.example.com/{i}.m3u8", local_verified_override=True)
                   for i in range(5)]
        with patch.object(scrub.build, "_probe_stream", return_value={"status": "ok"}) as health, \
             patch.object(scrub.build, "_validate_direct_media_survival",
                          return_value={"status": "failed", "continuity_failure": "direct-media-repeated-clip"}) as decoder:
            report, seen = scrub.run(self.config, ROSTER, {}, [], sources(*samples), NOW, 99)
        self.assertEqual(health.call_count, 3)
        self.assertEqual(decoder.call_count, 3)
        checked = [x for x in seen.values() if x.get("probe")]
        self.assertEqual(len(checked), 3)
        for row in checked:
            self.assertFalse(row["probe"]["production_approved"])
            self.assertEqual(row["probe"]["decoder"]["continuity_failure"], "direct-media-repeated-clip")
            self.assertNotIn("local_verified_override", row)

    def test_already_probed_candidate_does_not_consume_next_probe_budget(self):
        samples = sources(entry())
        with patch.object(scrub.build, "_probe_stream", return_value={"status": "failed"}) as health:
            _, seen = scrub.run(self.config, ROSTER, {}, [], samples, NOW, 3)
            report, _ = scrub.run(self.config, ROSTER, {"seen": seen}, [], samples, NOW, 3)
        self.assertEqual(health.call_count, 1)
        self.assertEqual(report["summary"]["media_probes"], 0)

    def test_source_failures_are_reported_without_exception_secrets(self):
        with patch.object(scrub.build, "_fetch_public_text", side_effect=ValueError("secret header")):
            row, entries = scrub.scan_source({"name": "source", "url": "https://example.com/a.m3u"})
        self.assertEqual(entries, [])
        self.assertEqual(row["error_type"], "ValueError")
        self.assertNotIn("secret", json.dumps(row))

    def test_search_continues_past_known_lists_and_stops_after_target_batch(self):
        old = {"seen": {"old": {"url": entry()["url"]}}}
        lists = [{"name": str(i), "url": f"https://example.com/{i}.m3u"} for i in range(12)]
        def scan(source):
            i = int(source["name"])
            rows = [entry()] if i < 4 else [entry(url=f"https://media.example.com/{i}.m3u8")]
            return {**source, "status": "ok"}, rows
        with patch.object(scrub, "scan_source", side_effect=scan) as fetch:
            result, info = scrub.scan_until_target(self.config, ROSTER, old, [], lists, NOW, target=3)
        self.assertEqual(fetch.call_count, 8)
        self.assertEqual(info["new_stream_links"], 4)
        self.assertEqual(info["stop_reason"], "target-reached")
        self.assertTrue(info["target_met"])

    def test_search_exhaustion_does_not_invent_new_links(self):
        lists = [{"name": "same", "url": "https://example.com/a.m3u"}] * 5
        with patch.object(scrub, "scan_source", return_value=sources(entry())[0]) as fetch:
            _, info = scrub.scan_until_target(self.config, ROSTER, {}, [], lists, NOW)
        self.assertEqual(fetch.call_count, 5)
        self.assertEqual(info["new_stream_links"], 0)
        self.assertEqual(info["stop_reason"], "sources-exhausted")
        self.assertFalse(info["target_met"])

    def test_search_deadline_saves_completed_batch(self):
        lists = [{"name": "x", "url": "https://example.com/a.m3u"}] * 8
        with patch.object(scrub, "scan_source", return_value=sources(entry())[0]), \
             patch.object(scrub.time, "monotonic", side_effect=[0, 0, 601]):
            result, info = scrub.scan_until_target(self.config, ROSTER, {}, [], lists, NOW)
        self.assertEqual(len(result), 4)
        self.assertEqual(info["stop_reason"], "time-budget")

    def test_target_counts_unique_urls_not_headers_or_channel_aliases(self):
        url = entry()["url"]
        rows = [{"newness": "new", "url": url}, {"newness": "new", "url": url},
                {"newness": "new", "url": "https://media.example.com/new.m3u8"}]
        self.assertEqual(scrub.new_link_count(rows, {}, []), 2)
        self.assertEqual(scrub.new_link_count(rows, {"seen": {"old": {"url": url}}}, []), 1)
        self.assertEqual(scrub.new_link_count(rows, {}, [{"url": url}]), 1)

    def test_prior_artifact_from_pr_cannot_poison_persistent_state(self):
        class API:
            repository = "owner/repo"
            def get(self, path, binary=False):
                if path.startswith("actions/artifacts?"):
                    return {"artifacts": [{"id": 1, "workflow_run": {"id": 10, "head_branch": "main"}}]}
                if path == "actions/runs/10":
                    return {"event": "pull_request", "head_branch": "main", "path": scrub.WORKFLOW}
                raise AssertionError("Must not download untrusted artifact")
        state, info = scrub.load_previous(API(), 20, "main")
        self.assertEqual(state, {})
        self.assertEqual(info["status"], "initial-inventory")

    def test_guard_failed_production_can_supply_next_inventory(self):
        state = {"version": 1, "repository": "owner/repo", "run_id": "10", "seen": {}}
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(scrub.STATE_FILE, json.dumps(state))
        class API:
            repository = "owner/repo"
            def get(self, path, binary=False):
                if path.startswith("actions/artifacts?"):
                    return {"artifacts": [{"id": 1, "workflow_run": {"id": 10, "head_branch": "main"}}]}
                if path == "actions/runs/10":
                    return {"event": "schedule", "conclusion": "failure", "head_branch": "main", "path": scrub.WORKFLOW}
                return archive.getvalue()
        loaded, info = scrub.load_previous(API(), 20, "main")
        self.assertEqual(loaded, state)
        self.assertEqual(info["run_id"], 10)


if __name__ == "__main__":
    unittest.main()
