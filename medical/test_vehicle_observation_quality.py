"""Synthetic freshness cases using provider-local timestamp (KST)."""
import unittest
from vehicle_observation_quality import provider_timestamp, quality_label, summarize_quality

class TimestampQualityTests(unittest.TestCase):
 def test_kst_naive_is_not_utc(self):
  self.assertEqual(provider_timestamp("20261019100500").isoformat(),"2026-10-19T01:05:00+00:00")
  self.assertEqual(provider_timestamp("2026-10-19 10:05:00").isoformat(),"2026-10-19T01:05:00+00:00")
 def test_quality_enforces_freshness_and_unknowns(self):
  req="2026-10-19T01:08:00+00:00"
  rows=[
   {"request_time_utc":req,"provider_observation_time":"20261019100500","vehicle_type":"low_floor"},
   {"request_time_utc":req,"provider_observation_time":"20261019090000","vehicle_type":"ordinary"},
   {"request_time_utc":req,"provider_observation_time":None,"vehicle_type":"ordinary"},
   {"request_time_utc":req,"provider_observation_time":"20261019110500","vehicle_type":"ordinary"}]
  self.assertEqual([quality_label(x) for x in rows],["fresh","stale","unknown_time","future_time"])
  q=summarize_quality(rows)
  self.assertEqual(q["fresh_low_floor_snapshots"],1)
  self.assertEqual(q["stale_provider_snapshots"],1)
  self.assertEqual(q["unknown_time_snapshots"],1)
  self.assertEqual(q["future_time_snapshots"],1)
  self.assertEqual(sum(q.values()),4)
 def test_absent_unparseable_and_explicit_utc(self):
  self.assertIsNone(provider_timestamp("nonsense"))
  self.assertEqual(quality_label({"request_time_utc":"2026-10-19T01:08:00Z",
                                   "provider_observation_time":"2026-10-19T01:07:00Z"}),"fresh")

if __name__=="__main__":unittest.main()
