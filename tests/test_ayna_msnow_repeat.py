"""Repeat-window QA for AynaOTT's MS NOW candidate."""
import unittest
from research import ayna_msnow_repeat as task

class MSNowWindows(unittest.TestCase):
    def test_three_good_video_windows_are_technical_only(self):
        ok={"passed":True,"frames":60,"short_loops_detected":[],"max_static_seconds":1}
        result=task.summarize([ok,ok,ok],"progressing-hls-readable-not-decoded")
        self.assertTrue(result["all_three_technical_windows_passed"])
        self.assertFalse(result["exact_msnow_us_east_linear_identity_verified"])
        self.assertFalse(result["production_promotion"])

    def test_one_repeated_clip_or_freeze_blocks(self):
        ok={"passed":True,"frames":60,"short_loops_detected":[],"max_static_seconds":1}
        loop={"passed":True,"frames":60,"short_loops_detected":[3],"max_static_seconds":1}
        freeze={"passed":True,"frames":60,"short_loops_detected":[],"max_static_seconds":16}
        for bad in (loop,freeze):
            report=task.summarize([ok,bad,ok],"progressing-hls-readable-not-decoded")
            self.assertEqual(report["windows_passed"],2)
            self.assertFalse(report["all_three_technical_windows_passed"])

    def test_single_window_not_enough(self):
        ok={"passed":True,"frames":60,"short_loops_detected":[],"max_static_seconds":1}
        self.assertFalse(task.summarize([ok],"progressing-hls-readable-not-decoded")["all_three_technical_windows_passed"])

if __name__=="__main__":
    unittest.main()
