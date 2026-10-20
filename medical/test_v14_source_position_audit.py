"""V14 original bus-position source audit regressions."""
import unittest
try:from medical.v14_source_position_audit import recalculate
except ImportError:from v14_source_position_audit import recalculate
class AuditV14(unittest.TestCase):
 def test_original_rows_crosschecked_not_hardcoded(self):
  r=recalculate()
  self.assertEqual((r["original_position_rows"],r["original_window_rows"]),(30,30))
  self.assertEqual((r["observed_routes"],r["study_routes"]),(15,23))
 def test_observation_counts_and_missing_weekdays(self):
  r=recalculate();self.assertEqual(r["totals"]["snapshots"],262)
  self.assertEqual((r["totals"]["low_floor_snapshots"],r["totals"]["ordinary_snapshots"]),(236,26))
  self.assertEqual(r["weekday_days"],0)
  self.assertEqual(r["three_polls_per_window_met"],0)
 def test_historical_source_tampering_is_rejected(self):
  import tempfile,shutil
  from pathlib import Path
  try:from medical import v14_source_position_audit as module
  except ImportError:import v14_source_position_audit as module
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   for name in module.FILES:shutil.copy2(module.ROOT/'medical/raw/vehicle_history_20261018'/name,folder/name)
   with (folder/'vehicle_timeseries.csv').open('ab') as f:f.write(b'\n')
   with self.assertRaises(ValueError):recalculate(folder)
 def test_no_empirical_relabel(self):
  r=recalculate()
  self.assertIsNone(r["real_stop_arrival_times"])
  self.assertIsNone(r["wheelchair_boarding_success_rate"])
  self.assertIsNone(r["causal_policy_effect"])
if __name__=="__main__":unittest.main()
