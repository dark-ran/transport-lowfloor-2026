"""Offline V6 regression: data inconsistencies must never be presented as resolved."""
import unittest
from medical import v6_evidence_audit as v

class V6Test(unittest.TestCase):
    def test_static_coordinate_set(self):
        source = [{"route":"1124","stop_id":"a","lon":"127.1","lat":"37.5"}]
        ids,geo=v.static_sets(source)
        self.assertEqual(ids["1124"],geo["1124"])
    def test_discrepancy(self):
        old=[{"route":r,"2026_board":"55579","2026_board_geolinked":"4874"} for r in v.ROUTES]
        new=[{"route":r,"monthly_boardings_2026":"55579","boardings_matching_2025_static_stop_id":"55259"} for r in v.ROUTES]
        from collections import defaultdict
        ids=defaultdict(set); geo=defaultdict(set)
        for r in v.ROUTES: ids[r]={"a"};geo[r]={"a"}
        result=v.audit(old,new,ids,geo)
        self.assertEqual(result[2]["gap"],50385)
        self.assertTrue(all(x["decision"]=="RECALCULATION_REQUIRED" for x in result))
    def test_observation_is_not_boarding(self):
        r=v.observations([{"route":"343","day_kind":"weekend","query_scope":"full",
                           "polls":"1","snapshots":"11","low_floor_snapshots":"11",
                           "ordinary_snapshots":"0"}])
        self.assertEqual(r[0]["location_records"],11)
        self.assertEqual(r[0]["measured_accessible_boardings"],"NOT_MEASURED")

if __name__=="__main__": unittest.main()
