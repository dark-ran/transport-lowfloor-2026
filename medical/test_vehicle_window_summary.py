"""Offline grouped observation ratios, not fleet share or measured headways."""
import unittest
from vehicle_window_summary import build
class WindowSummaryTests(unittest.TestCase):
 def test_success_and_errors_separated(self):
  base={"observed_at_kst":"2026-10-19T08:05:00+09:00","route":"662",
        "direction":"route_all","query_scope":"full","status":"success_with_snapshots",
        "snapshots":"8","low_floor_snapshots":"6","ordinary_snapshots":"2","unknown_type_snapshots":"0"}
  result=build([base,{**base,"observed_at_kst":"2026-10-19T08:10:00+09:00","status":"api_error_or_missing",
                "snapshots":"0","low_floor_snapshots":"0","ordinary_snapshots":"0"}])
  self.assertEqual(len(result),1);self.assertEqual(result[0]["polls"],2)
  self.assertEqual(result[0]["successful_polls"],1)
  self.assertEqual(result[0]["failed_polls"],1)
  self.assertEqual(result[0]["observed_low_floor_share"],.75)
  self.assertEqual(result[0]["mean_snapshot_vehicles_per_successful_poll"],8.0)
if __name__=="__main__":unittest.main()
