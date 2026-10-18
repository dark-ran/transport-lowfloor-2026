"""V4 acceptance tests: distinguish snapshots, unknown data, and reality claims."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from v4_directional_audit import direct_leg
from v4_implementation_gates import compile_gates
from v4_vehicle_snapshot import normalize_xml, manifest


class V4EvidenceTests(unittest.TestCase):
    def test_direction_order_is_not_symmetric(self):
        d=pd.DataFrame({
            "posY":[37.50,37.51,37.52],
            "posX":[127.,127.,127.],
            "stationOrd":[1,2,3],
            "stnName":["A","B","C"],
            "arsId":["1","2","3"],
            "routeId":["11","11","11"],
            "turnPlaceStationYn":["N","N","N"]
        })
        self.assertIsNotNone(direct_leg(d,[37.5,127.],[37.52,127.]))
        self.assertIsNone(direct_leg(d,[37.52,127.],[37.5,127.]))

    def test_vehicle_type_parser_no_boarding_inference(self):
        request={"route":"343","route_id":"100","direction":"outbound","boarding_seq":7}
        payload=b"""<ServiceResult><msgHeader><headerCd>0</headerCd></msgHeader><msgBody>
        <itemList><vehId>PRIVATE123</vehId><busType>1</busType><sectOrd>6</sectOrd>
        <stopFlag>1</stopFlag><dataTm>2026-10-18 09:01:03</dataTm>
        <plainNo>DO-NOT-PUBLISH</plainNo></itemList></msgBody></ServiceResult>"""
        rows=normalize_xml(payload,request,"2026-10-18T00:01:04+00:00","local-salt-example-only")
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["vehicle_type"],"low_floor")
        self.assertFalse(r["confirmed_boarding"])
        self.assertFalse(r["confirmed_at_boarding_stop"])
        self.assertNotIn("PRIVATE123",str(rows))
        self.assertNotIn("DO-NOT-PUBLISH",str(rows))

    def test_invalid_provider_response_rejected(self):
        request={"route":"343","route_id":"100","direction":"outbound","boarding_seq":7}
        with self.assertRaises(ValueError):
            normalize_xml(
                b"<ServiceResult><msgHeader><headerCd>7</headerCd></msgHeader></ServiceResult>",
                request,"2026-10-18T00:00:00Z","local-salt-example-only")

    def test_unknown_vehicle_type_stays_unknown(self):
        req={"route":"662","route_id":"2","direction":"return","boarding_seq":20}
        xml=b"<ServiceResult><itemList><vehId>A</vehId><busType>9</busType></itemList></ServiceResult>"
        self.assertEqual(normalize_xml(xml,req,"2026-10-18T00:00:00Z","local-salt-example-only")[0]["vehicle_type"],"unknown")

    def test_six_evidence_gates_do_not_pass_from_nominal_headway(self):
        route="343"
        allocations=pd.DataFrame({"policy":["screened_cap_5"],"route":[route],
                                  "added":[5],"fleet":[18],"low_before":[12]})
        hw=pd.DataFrame({"route":[route],"headway_matched":[True],
                         "nominal_weekday_headway_min":[15]})
        directional=pd.DataFrame({"route":[route],"snapshot_route_available":[True],
                                  "coverage":["bidirectional"]})
        result=compile_gates(allocations,hw,directional,set(),expected_budget=5)
        self.assertTrue(bool(result.iloc[0].some_pairs_bidirectional_order_valid))
        self.assertFalse(bool(result.iloc[0].actual_unit_cost_or_maintenance_cost_verified))
        self.assertFalse(bool(result.iloc[0].bus_vehicle_level_lowfloor_departures_verified))
        self.assertEqual(result.iloc[0].operational_decision,"hold_for_field_verification")

    def test_manifest_does_not_request_more_than_two_directions_per_route(self):
        entry={
            "route":"343","route_id":"100","dong":"D","hospital":"H",
            "both_directions":True,"base_dong_index_gain":.2,
            "outbound_leg":'{"board":"A","board_seq":15}',
            "return_leg":'{"board":"B","board_seq":75}'
        }
        data=pd.DataFrame([entry])
        whole=manifest(data)
        self.assertEqual(len(whole),1)
        self.assertEqual(whole[0]["direction"],"route_all")
        self.assertNotIn("startOrd",whole[0])
        self.assertNotIn("endOrd",whole[0])
        section=manifest(data,scope="section")
        self.assertEqual(len(section),2)
        self.assertEqual({z["direction"] for z in section},{"outbound","return"})


if __name__=="__main__":
    unittest.main()
