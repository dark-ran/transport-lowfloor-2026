"""V5 no-network regression for exact route/stop ID linkage denominator."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
try:
    from medical import v5_temporal_linkage as v
except ImportError:
    import v5_temporal_linkage as v

class V5LinkageTests(unittest.TestCase):
    def test_route_specific_ids_not_radius_subset(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"m.csv"
            hs=["사용년월","노선번호","표준버스정류장ID"]+[f"{h:02d}시승차총승객수" if h==0 else f"{h}시승차총승객수" for h in range(24)]
            with p.open("w",newline="",encoding="cp949") as f:
                w=csv.DictWriter(f,fieldnames=hs);w.writeheader()
                for id_,n in [("111",10),("333",20)]:
                    row={x:"0" for x in hs};row.update({"사용년월":"202605","노선번호":"343","표준버스정류장ID":id_,"00시승차총승객수":str(n)})
                    w.writerow(row)
            r=v.calculate(p,{"343":{"111","222"}},routes=("343",))[0]
            self.assertEqual(r["boardings_total_2026"],30)
            self.assertEqual(r["boardings_same_route_static_id"],10)
            self.assertAlmostEqual(r["share_matching_pct"],33.3333,places=4)
    def test_inventory_is_not_every_routes_shared_stops(self):
        p=Path(__file__).resolve().parent/"data/route_stops.csv"
        d=v.static_ids(p)
        self.assertEqual([len(d[r]) for r in v.ROUTES],[69,65,37,101])
if __name__=="__main__":unittest.main()
