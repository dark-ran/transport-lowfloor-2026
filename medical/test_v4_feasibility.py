"""Offline unit tests of historical vehicle-capacity stress (not field feasibility)."""
import unittest
try:
    from medical import v4_feasibility as v
except ImportError:
    import v4_feasibility as v

class V4GateTests(unittest.TestCase):
    def test_rounding(self):
        self.assertEqual(v.scenario_capacity(1,.25,"floor"),0)
        self.assertEqual(v.scenario_capacity(1,.25,"ceil"),1)
        self.assertEqual(v.scenario_capacity(6,.5,"floor"),3)
        with self.assertRaises(ValueError):
            v.scenario_capacity(6,1.1,"floor")
    def test_fixed_budget(self):
        a=v.allocations(v.read(v.BASE/"results/cap_allocations.csv"))
        self.assertEqual([len(a[k]) for k in v.P],[22,15,12])
        self.assertTrue(all(sum(x[0] for x in a[p].values())==50 for p in v.P))
    def test_actual_approvals_are_not_fabricated(self):
        a=v.allocations(v.read(v.BASE/"results/cap_allocations.csv"))
        results=v.audit(a,v.read(v.BASE/"results/historical_ridership/v3_route_spatial_evidence.csv"),
                        v.read(v.BASE/"results/v4_implementation_gates.csv"))
        ledgers,checks,summaries,stresses=results
        self.assertEqual([len(ledgers),len(checks),len(summaries),len(stresses)],[23,49,3,24])
        self.assertEqual([s["not_in_v4_15_route_evidence_scope"] for s in summaries],[8,0,1])
        self.assertTrue(all(s["actual_implementation_authorized_vehicles"]==0 for s in summaries))
        self.assertTrue(all(s["actual_verified_slots"]==0 for s in stresses))
        self.assertTrue(all(x["actual_route_go"]=="NO_GO_UNVERIFIED" for x in ledgers))
    def test_existing_archive_scope_missing_not_failed(self):
        a=v.allocations(v.read(v.BASE/"results/cap_allocations.csv"))
        ledgers,*_=v.audit(a,v.read(v.BASE/"results/historical_ridership/v3_route_spatial_evidence.csv"),
                        v.read(v.BASE/"results/v4_implementation_gates.csv"))
        outside=next(x for x in ledgers if x["route"]=="2312")
        self.assertEqual(outside["2025_highfloor_nominal"],8)
        self.assertEqual(outside["policy_7_slots"],7)
        self.assertEqual(outside["vehicle_decommission_eligibility"],"NOT_ASSESSED")
        inside=next(x for x in ledgers if x["route"]=="343")
        self.assertEqual(inside["vehicle_decommission_eligibility"],"NOT_VERIFIED")
if __name__=="__main__":
    unittest.main()
