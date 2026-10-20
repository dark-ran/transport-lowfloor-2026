"""Static V11 GIS audit tests, no Seoul 2026 raw data needed in repo."""
import unittest
try:from medical import v11_23route_gis as mod
except ImportError:import v11_23route_gis as mod
class V11Tests(unittest.TestCase):
    def test_all_23_static_masks_from_original_coordinates(self):
        masks=mod.static_cohort()
        self.assertEqual(len(masks),23)
        self.assertEqual(sum(map(len,masks.values())),568)
        self.assertEqual([len(masks[x]) for x in ("343","662","1124","3413")],[6,24,6,32])
    def test_great_circle_basics(self):
        self.assertAlmostEqual(mod.distance(127.1,37.5,127.1,37.5),0,places=8)
    def test_spatial_output_then_monthly_audit_distinguishes_denominators(self):
        import csv,tempfile
        from pathlib import Path
        from medical import historical_policy_spatial_v3 as spatial
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);raw=d/'monthly.csv';ref=d/'spatial.csv'
            fields=['사용년월','노선번호','표준버스정류장ID','역명',*spatial.previous.BOARD,*spatial.previous.ALIGHT]
            with raw.open('w',encoding='cp949',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
                for sid,boarding,alighting in [('near',2,3),('far',7,11)]:
                    row=dict.fromkeys(fields,0)
                    row.update({'사용년월':'202605','노선번호':'101','표준버스정류장ID':sid,'역명':'x'})
                    row[spatial.previous.BOARD[0]]=boarding;row[spatial.previous.ALIGHT[0]]=alighting
                    writer.writerow(row)
            observed,matched,_,_=spatial.observed_near_stops(raw,{'101'},{'near':(100,'H'),'far':(1000,'H')},{'101':{'near','far'}})
            self.assertEqual(matched['101'],9)
            self.assertEqual(observed['101'][800]['activity'],5)
            spatial.write_csv(ref,[{'route':'101','boardings_geolinked_2026':matched['101'],'general_hospital_800m_boardings':observed['101'][800]['boardings']}])
            result=mod.monthly(raw,{'101':{'near'}},ref)
            self.assertEqual(result[0]['recalculated_near800_boardings'],2)
            self.assertTrue(result[0]['matches_near800_boardings'])
            spatial.write_csv(ref,[{'route':'101','general_hospital_800m_boardings':9}])
            with self.assertRaises(AssertionError):mod.monthly(raw,{'101':{'near'}},ref)
            spatial.write_csv(ref,[{'route':'101','boardings_geolinked_2026':9}])
            with self.assertRaisesRegex(ValueError,'explicit hospital-800m'):mod.monthly(raw,{'101':{'near'}},ref)
if __name__=="__main__":unittest.main()
