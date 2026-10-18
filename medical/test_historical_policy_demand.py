"""Offline unit checks for the 3/5/7-cap demand screening module."""
from collections import defaultdict
import unittest
from medical import historical_policy_demand as mod


def sample(b,mid,hosp,hmid):
    return {'board':b,'mid':mid,'hosp':hosp,'hosp_mid':hmid,'stops':{'001':b},'rows':1,'hosp_stops':{'001'} if hosp else set()}


class PolicyDemandTests(unittest.TestCase):
    def test_same_fixed_denominator_independent_of_selected_routes(self):
        opts={'screened_cap_3':{'A':(1,2)},'screened_cap_5':{'B':(1,2)},'screened_cap_7':{'A':(1,2)}}
        a={'A':sample(2,2,2,2),'B':sample(8,8,8,8)}
        b={'A':sample(1,1,1,1),'B':sample(9,9,9,9)}
        r=mod.build(opts,a,b)
        self.assertEqual([x['fixed_universe_boardings_2026'] for x in r],[10,10,10])
        self.assertAlmostEqual(r[0]['demand_weighted_gain_pp'],5.)
        self.assertAlmostEqual(r[1]['demand_weighted_gain_pp'],45.)
        self.assertAlmostEqual(r[2]['demand_weighted_gain_pp'],5.)

    def test_detect_empty_hospital_keyword_denominator(self):
        opts={k:{'A':(1,2)} for k in mod.POLICIES}
        a={'A':sample(10,10,0,0)};b={'A':sample(12,12,0,0)}
        with self.assertRaises(ValueError):mod.build(opts,a,b)


if __name__=='__main__':unittest.main()
