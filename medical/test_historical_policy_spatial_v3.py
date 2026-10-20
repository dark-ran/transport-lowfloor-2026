"""No-network V3 regression checks; source CSVs remain external."""
import csv
import tempfile
import unittest
from pathlib import Path

try:
    import historical_policy_spatial_v3 as mod
except ModuleNotFoundError:
    from medical import historical_policy_spatial_v3 as mod


class SpatialV3Tests(unittest.TestCase):
    def test_distance_scale(self):
        self.assertAlmostEqual(mod.haversine_m(127,37.5,127,37.5),0,places=9)
        self.assertGreater(mod.haversine_m(127,37.5,127.013,37.5),1000)

    def test_late_hospitals_are_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);st=d/"st.csv";h=d/"h.csv"
            st.write_text("route,stop_id,lon,lat\n123,001,127,37.5\n123,001,127,37.5\n",encoding="utf-8")
            h.write_text("name,kind,approval_date,lon,lat\nA,종합병원,2025-01-01,127,37.5\nB,종합병원,2026-01-01,127,37.5\n",encoding="utf-8")
            near,routes,audit=mod.proximity(st,h,{"123"})
            self.assertEqual(audit["hospitals"],1)
            self.assertEqual(audit["static_route_stops"],1)
            self.assertLess(near["001"][0],1)

    def test_four_objective_weight_grid(self):
        s=[{"policy":p,"all_board_gain_pp":v,"hospital_500m_activity_gain_pp":4-v}
           for p,v in (("screened_cap_3",3),("screened_cap_5",2),("screened_cap_7",1))]
        eq={p:{"base_delta_index":float(v),"changed_dongs":4-v}
            for p,v in (("screened_cap_3",1),("screened_cap_5",2),("screened_cap_7",3))}
        rows,meta=mod.weight_screen(s,eq)
        self.assertEqual(len(rows),286)
        self.assertAlmostEqual(sum(meta["fractional_winner_counts"].values()),286)
        self.assertTrue(all(abs(sum(v for k,v in row.items() if k.startswith("weight_"))-1)<1e-10 for row in rows))

    def test_original_csv_extract_to_spatial_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"may.csv"
            fields=['사용년월','노선번호','표준버스정류장ID','역명',*mod.previous.BOARD,*mod.previous.ALIGHT]
            with path.open('w',encoding='cp949',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
                for route in ['101','102']:
                    writer.writerow({**dict.fromkeys(fields,1),'사용년월':'202605','노선번호':route,'표준버스정류장ID':route,'역명':'병원'})
            data=mod.previous.extract(path,2026,{'101','102'})
            policies={p:{'101':(1,2),'102':(1,2)} for p in mod.POLICIES}
            geo={r:{radius:{'activity':48,'mid_activity':14} for radius in mod.RADII} for r in data}
            summaries,loo=mod.compare(policies,data,data,geo,{'101':48,'102':48})
            self.assertEqual(len(loo),2)
            self.assertTrue(all(x['all_board_gain_pp']==50 for x in summaries))

    def test_policy_gain_same_denominator(self):
        opts={p:{"101":(1,2)} for p in mod.POLICIES}
        a={"101":{"board":10,"mid":5}}
        geo={"101":{radius:{"activity":8,"mid_activity":4} for radius in mod.RADII}}
        with self.assertRaises(ValueError):
            mod.compare(opts,a,a,geo,{"101":8})  # cannot score an empty holdout universe


if __name__=="__main__":
    unittest.main()
