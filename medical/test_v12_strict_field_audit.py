"""Minimal regression: malformed date/time previously inflated apparent success."""
import csv,tempfile,unittest
from pathlib import Path
try:from medical.v12_strict_field_audit import audit,REQUIRED
except ImportError:from v12_strict_field_audit import audit,REQUIRED

PR=[dict(route="343",boarding_stop_id="122000133",period="09:00-11:00",
preregistered_date="2026-10-19",physical_site_verified="YES",collection_authorized="YES",independent_reviewer="TEST_ONLY")]
BASE={k:"" for k in REQUIRED}
BASE.update(record_id="TEST_001",route="343",boarding_stop_id="122000133",observation_date="2026-10-19",
period="09:00-11:00",observation_start_local="09:00",observation_end_local="11:00",
vehicle_arrival_local="09:01",bus_type_observed_Y_N_UNKNOWN="Y",wheelchair_boarding_attempt_Y_N_UNKNOWN="Y",
wheelchair_boarding_success_Y_N_NA_UNKNOWN="Y",field_observer="TEST_OP",source_evidence_reference="TEST_EVIDENCE_001")
class StrictAuditTests(unittest.TestCase):
    def check(self,change=None,blank=False,reg=PR):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"observations.csv"
            with p.open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=sorted(REQUIRED));w.writeheader()
                if not blank:w.writerow({**BASE,**(change or {})})
            return audit(p,reg)
    def test_empty_is_missing_not_zero_percent(self):
        x=self.check(blank=True);self.assertIsNone(x["wheelchair_boarding_success_rate"]);self.assertEqual(x["verified_observations"],0)
    def test_fake_date_is_rejected(self):
        with self.assertRaises(ValueError):self.check({"observation_date":"not-a-date"})
    def test_fake_time_is_rejected(self):
        with self.assertRaises(ValueError):self.check({"vehicle_arrival_local":"not-a-time"})
    def test_unregistered_date_is_rejected(self):
        with self.assertRaises(ValueError):self.check({"observation_date":"2026-10-20"})
    def test_unsourced_is_rejected(self):
        with self.assertRaises(ValueError):self.check({"source_evidence_reference":""})
    def test_plausible_test_is_not_empirical(self):
        x=self.check();self.assertEqual(x["input_rows"],1);self.assertEqual(x["verified_observations"],0)
        self.assertIsNone(x["wheelchair_boarding_success_rate"])
if __name__=="__main__":unittest.main()
