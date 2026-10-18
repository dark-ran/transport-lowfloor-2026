"""No-network V9 tests for stop-ID versus 800m GIS cohort semantics."""
import unittest
try:from medical import v9_lineage_audit as a
except ImportError:import v9_lineage_audit as a

class V9LineageTests(unittest.TestCase):
    def test_haversine_zero(self):
        self.assertAlmostEqual(a.haversine(127.01,37.53,127.01,37.53),0,places=8)
    def test_2025_static_1124_has_six_stops_near_general_hospital(self):
        s=a.static_1124(a.ROOT/"data/route_stops.csv",a.ROOT/"data/hospitals.csv")
        self.assertEqual(len(s),37)
        self.assertEqual(sum(d["distance_m"]<=800 for d in s.values()),6)
        self.assertEqual(set(sid for sid,d in s.items() if d["distance_m"]<=800),{
            "108000062","108000060","108000118","108000160","108000119","108000121"})
if __name__=="__main__":unittest.main()
