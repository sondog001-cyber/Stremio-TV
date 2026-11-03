"""A recovered host may be rechecked widely only after genuine canary QA."""
import json
from pathlib import Path
import unittest

import build

ROOT=Path(__file__).resolve().parents[1]

def key(url):
    return (url, ())

HOST="http://23.237.104.106:8080"
PASSING_HOST=HOST+"/USA_BTN/index.m3u8"
RECOVER_A=HOST+"/USA_CMT/index.m3u8"
RECOVER_B=HOST+"/USA_SEC_NETWORK/index.m3u8"
FOREIGN="http://212.5.144.156:8080/history/index.m3u8"


class HostRevivalTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/"config.json").read_text())
        self.settings=self.config["stream_health"]["priority_recovery"]
        self.assertTrue(self.settings["host_revival_enabled"])
        self.assertTrue(self.config["stream_health"]["require_passed_only"])
        self.assertTrue(self.config["stream_health"]["primary_playback_qa"]["enabled"])
        self.assertTrue(self.config["deployment_guard"]["enabled"])
        self.canary={"url": PASSING_HOST, "tvg_id":"BigTenNetwork.us@SD"}
        self.a={"url": RECOVER_A, "tvg_id":"CMT.us@East"}
        self.b={"url": RECOVER_B, "tvg_id":"SECNetwork.us@SD"}
        self.foreign={"url": FOREIGN, "tvg_id":"History.us@East"}
        self.previous={"channels":{
            "0":{"pattern":"CMT.us", "present":False},
            "1":{"pattern":"SECNetwork.us", "present":False},
            "2":{"pattern":"History.us", "present":False},
            "3":{"pattern":"NotMissing.us", "present":True},
        }}
        self.cool={
            key(RECOVER_A):self.a,
            key(RECOVER_B):self.b,
            key(FOREIGN):self.foreign,
        }
        self.pending={
            key(RECOVER_A):{"status":"cooldown"},
            key(RECOVER_B):{"status":"cooldown"},
            key(FOREIGN):{"status":"cooldown"},
        }

    def pick(self, canary_status="ok", *, cooldown=None, other_results=None):
        pending=dict(self.pending)
        if cooldown is not None:
            pending.update(cooldown)
        pending[key(PASSING_HOST)]={"status":canary_status}
        if other_results:
            pending.update(other_results)
        return build.plan_host_revival_probes(
            self.cool, {key(PASSING_HOST):self.canary}, pending,
            self.previous, self.config
        )

    def test_same_origin_canary_unlocks_all_missing_entries(self):
        selected=self.pick()
        self.assertEqual(set(selected), {key(RECOVER_A),key(RECOVER_B)})
        self.assertNotIn(key(FOREIGN),selected)
        self.assertEqual(
            self.settings["max_per_host"],2,
            "The normal two-per-host throttle remains intact",
        )

    def test_failed_canary_never_unlocks_cooldown(self):
        self.assertEqual(self.pick("failed"),{})

    def test_each_candidate_must_still_be_in_cooldown(self):
        selection=self.pick(cooldown={key(RECOVER_A):{"status":"ok"}})
        self.assertNotIn(key(RECOVER_A),selection)
        self.assertIn(key(RECOVER_B),selection)

    def test_no_prior_missing_state_never_unlocks_cooldown(self):
        self.previous={"channels":{}}
        self.assertEqual(self.pick(),{})

    def test_unrelated_nonmissing_id_is_rejected(self):
        notmissing=HOST+"/USA_MTV/index.m3u8"
        self.cool[key(notmissing)]={"url":notmissing,"tvg_id":"NotMissing.us"}
        self.assertNotIn(key(notmissing),self.pick())

    def test_cap_and_disabled_mode_do_not_unlock_everything(self):
        self.settings["max_host_revival_urls_per_build"]=1
        self.assertEqual(len(self.pick()),1)
        self.settings["host_revival_enabled"]=False
        self.assertEqual(self.pick(),{})

    def test_results_never_automatically_pass_a_stream(self):
        selected=self.pick()
        self.assertFalse(any("health" in item for item in selected.values()))
        self.assertTrue(all(
            self.pending[key]["status"]=="cooldown" for key in selected
        ))


if __name__=="__main__":
    unittest.main()
