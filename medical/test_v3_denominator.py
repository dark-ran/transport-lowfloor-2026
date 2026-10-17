"""Pure synthetic tests: V3 is a structural screening, not a transit trip model."""
import unittest
import numpy as np
import pandas as pd
from v3_denominator_multiroute import classify_pairs, proxy_scores, compute_summary


class V3ModelChecks(unittest.TestCase):
    def setUp(self):
        self.origins = pd.DataFrame({
            "code": ["a","b"], "gu":["G","G"], "dong":["A","B"], "seniors":[100,100]
        })
        self.model = {
            "C": np.array([[True,True],[False,False],[True,False],[False,True]],bool),
            "walk": np.array([False,False,True,False]),
            "weights": np.full(4,.25),
            "k":2,
            "f":pd.DataFrame({"route":["101","202"],"fleet":[10,10],"low":[2,5]})
        }
    def test_disconnection_and_missing_status_are_separate(self):
        classes, observable = classify_pairs(self.model,np.array([10.,np.nan]))
        self.assertEqual(classes.tolist(),[
            "matched_shared_route","no_shared_route",
            "straight_walk_flag","unmatched_only_route"])
        self.assertEqual(observable.tolist(),[True,False,True,False])

    def test_union_heuristic_is_not_equal_to_max(self):
        C=np.array([[True,True],[False,False]],bool)
        walk=np.array([False,False])
        x=np.array([.2,.5])
        self.assertAlmostEqual(proxy_scores(C,walk,x,"max")[0],.5)
        self.assertAlmostEqual(proxy_scores(C,walk,x,"saturated_union")[0],.6)
        self.assertEqual(proxy_scores(C,walk,x,"saturated_union")[1],0)

    def test_full_and_conditional_denominators_are_explicit(self):
        model=self.model
        known=np.array([10.,np.nan])
        plan={"p":np.array([2,0]),"q":np.array([0,2])}
        table,classes,obs=compute_summary(model,self.origins,known,plan)
        rows=table[(table.reference_min==10)&(table["mode"]=="max")].set_index("policy")
        self.assertAlmostEqual(float(rows.loc["p","gain_full_population"]),.25*.2)
        self.assertAlmostEqual(float(rows.loc["p","gain_observable_only"]),.1)
        self.assertAlmostEqual(float(rows.loc["q","gain_full_population"]),0)
        self.assertAlmostEqual(float(rows.loc["p","observable_mass"]),.5)
        self.assertEqual(int(rows.loc["p","changed_dongs"]),1)
        self.assertTrue((table.rank_full==table.rank_conditional).all())

    def test_no_route_remains_zero_after_any_replacement(self):
        C=np.array([[False,False],[True,True]],bool)
        walk=np.array([False,False])
        a=proxy_scores(C,walk,np.array([.3,.4]),"saturated_union")
        b=proxy_scores(C,walk,np.array([.8,.9]),"saturated_union")
        self.assertEqual(a[0],0)
        self.assertEqual(b[0],0)


if __name__=="__main__":
    unittest.main()
