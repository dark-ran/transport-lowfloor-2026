import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from headway_proxy import load_archived_headways, headway_scores, paired_comparison
from decision_stress import capped_greedy


class HeadwayAndFeasibilityChecks(unittest.TestCase):
    def test_conservative_route_match(self):
        rows=pd.DataFrame([
            ["1","343","10","1","1"],
            ["2","3413","8","1","1"],
            ["3","3413","13","1","1"],
            ["4","BAD","0","1","1"],
            ["5","INACTIVE","15","0","1"],
            ["6","GOOD","20","1","1"]],
            columns=["노선ID","노선명","배차","운행여부","사용여부"])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"routes.csv"
            rows.to_csv(path,index=False,encoding="utf-8-sig")
            v,c,meta=load_archived_headways(path,["343","3413","BAD","INACTIVE","GOOD"])
        self.assertEqual(meta["matched_model_routes"],2)
        self.assertAlmostEqual(v[0],10)
        self.assertTrue(np.isnan(v[1:4]).all())
        self.assertAlmostEqual(v[4],20)

    def test_penalty_ranks_frequency_not_only_ratio(self):
        m={"C":np.array([[1,1]],bool),"walk":np.array([False]),
           "weights":np.array([1.]),"k":1}
        before=headway_scores(m,np.array([.9,.6]),np.array([30.,5.]),15)
        self.assertAlmostEqual(before[0],.6)  # max(.9 * .5, .6 * 1)
        equal=headway_scores(m,np.array([.9,.6]),np.array([np.nan,5.]),15)
        self.assertAlmostEqual(equal[0],.6)

    def test_identical_observed_subset_for_all_allocations(self):
        m={"C":np.array([[1,0],[0,1]],bool),
           "walk":np.array([False,False]),
           "weights":np.array([.7,.3]),"k":1}
        d=paired_comparison(m,np.array([.2,.5]),np.array([.4,.5]),
                            np.array([10.,np.nan]),15)
        self.assertAlmostEqual(d["observable_weight_share_total"],.7)
        self.assertEqual(d["unmatched_shared_pair_count"],1)
        self.assertAlmostEqual(d["proxy_gain_observable"],.2)

    def test_per_route_caps_are_applied(self):
        model={"f":pd.DataFrame({"route":["A","B"],"fleet":[10,10],"low":[0,0]}),
               "C":np.array([[1,0],[0,1]],bool),
               "walk":np.array([False,False]),
               "weights":np.array([.8,.2])}
        a,_=capped_greedy([model],budget=7,cap_per_route=5,
                          cap_by_route=np.array([2,4]))
        self.assertLessEqual(a[0],2)
        self.assertLessEqual(a[1],4)
        self.assertEqual(int(a.sum()),6)

    def test_missing_headway_is_not_zero_assumed_coverage(self):
        m={"C":np.array([[0,1]],bool),"walk":np.array([False]),
           "weights":np.array([1.]),"k":1}
        with self.assertRaises(AssertionError):
            paired_comparison(m,np.array([.2,.5]),np.array([.4,.5]),
                              np.array([10.,np.nan]),15)


if __name__=="__main__":
    unittest.main()
