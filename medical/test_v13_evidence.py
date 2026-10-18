"""V13 source and registry regression tests."""
import unittest
try:
    from medical import v13_position_evidence_audit as s
    from medical import v13_field_registry_audit as r
except ImportError:
    import v13_position_evidence_audit as s
    import v13_field_registry_audit as r

class V13Tests(unittest.TestCase):
    def test_real_api_aggregation_not_arrival(self):
        x=s.audit()
        self.assertIsNone(x["verified_stop_arrival_time_series"])
        self.assertIsNone(x["causal_policy_effect"])
        self.assertEqual(x["approved_replacements"],0)
        if x["matches_V13_archival_baseline"]:
            self.assertEqual(x["totals"]["polls"],30)
            self.assertEqual(x["totals"]["vehicle_position_snapshots"],262)
            self.assertEqual(x["totals"]["low_floor_position_snapshots"],236)
            self.assertEqual(x["totals"]["ordinary_position_snapshots"],26)
    def fixture(self):
        return dict(route="343",boarding_stop_id="122000133",
            direction="hospital_outbound",ars_id="23236",hospital_destination="삼성서울병원",
            period="09:00-11:00",preregistered_date="NOT_SCHEDULED",
            physical_site_verified="NO",collection_authorized="NO",
            independent_reviewer="NOT_ASSIGNED",review_evidence_reference="",
            authorization_evidence_reference="")
    def test_missing_destination_rejected(self):
        a=self.fixture();a["hospital_destination"]=""
        with self.assertRaises(ValueError):r.validate([a])
    def test_wrong_destination_rejected(self):
        a=self.fixture();a["hospital_destination"]="전혀다른병원"
        with self.assertRaises(ValueError):r.validate([a])
    def test_wrong_ars_rejected(self):
        a=self.fixture();a["ars_id"]="WRONG"
        with self.assertRaises(ValueError):r.validate([a])
    def test_syntax_only_cannot_verify_outcomes(self):
        x=r.validate([self.fixture()])
        self.assertEqual(x["independently_verified_observation_count"],0)
        self.assertIsNone(x["empirical_policy_effect"])
if __name__=="__main__":unittest.main()
