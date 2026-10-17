import unittest
import numpy as np,pandas as pd
from decision_stress import capped_greedy

def model(routes,C):
 return {'f':pd.DataFrame({'route':routes,'fleet':[10]*len(routes),'low':[0]*len(routes)}),'C':np.array(C,bool),'walk':np.zeros(len(C),bool),'weights':np.ones(len(C))/len(C)}
class DecisionTests(unittest.TestCase):
 def test_concentration_cap_cannot_be_spent_on_one_high_gain_route(self):
  m=model(['A','B'],[[1,0],[1,0],[0,1]]);a,_=capped_greedy([m],8,5);self.assertEqual(a.sum(),8);self.assertTrue((a<=5).all())
 def test_remaining_slots_are_not_filled_without_index_gain(self):
  m=model(['A','B'],[[1,0],[1,1]]);a,_=capped_greedy([m],8,5);self.assertEqual(a.sum(),5)
 def test_official_exception_is_not_replacement_eligible(self):
  m=model(['1122','A'],[[1,1]]);a,_=capped_greedy([m],4,5);self.assertEqual(a.tolist(),[0,4])
 def test_zero_improvement_scenario_does_not_stall_secondary_objective(self):
  m=model(['A'],[[1]]);u=model(['A'],[[0]]);a,_=capped_greedy([m,u],3,5,True);self.assertEqual(a.tolist(),[3])
if __name__=='__main__':unittest.main()
