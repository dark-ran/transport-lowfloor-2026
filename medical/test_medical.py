import unittest
import numpy as np,pandas as pd
from analyze_medical import distance,scores,greedy_bundle,build
class MedicalChecks(unittest.TestCase):
 def test_distance_and_axes(self):
  d=distance(np.array([[37.,127.]]),np.array([[37.,127.],[38.,127.]]));self.assertAlmostEqual(d[0,0],0);self.assertAlmostEqual(d[0,1],111195,delta=2)
 def test_walk_and_unconnected_pairs(self):
  C=np.array([[1,1],[0,0],[0,0]],bool);s=scores(C,np.array([0,0,1],bool),np.array([.3,.8]));np.testing.assert_allclose(s,[.8,0,1])
 def test_bundle_sees_multi_vehicle_gain(self):
  C=np.array([[1,1]],bool);n=np.array([100,5]);l=np.array([60,2]);a,st=greedy_bundle(C,np.array([0],bool),np.array([1.]),n,l,2);np.testing.assert_array_equal(a,[0,2]);self.assertAlmostEqual(st[0]['gain'],.2)
 def test_capacity_and_unreachable_budget(self):
  for budget in [0,1,10]:
   a,_=greedy_bundle(np.array([[1,0]],bool),np.array([0],bool),np.array([1.]),np.array([2,3]),np.array([1,0]),budget);self.assertLessEqual(a.sum(),budget);self.assertTrue((a<=np.array([1,3])).all());self.assertEqual(a[1],0)
 def test_duplicate_stop_rows_do_not_double_routes(self):
  o=pd.DataFrame({'code':['1'],'seniors':[100],'lat':[37.5],'lon':[127.]});f=pd.DataFrame({'route':['A'],'fleet':[2],'low':[1],'ambiguous_family':[False]});rs=pd.DataFrame({'route':['A','A','A'],'stop_id':['S1','S1','S2'],'lat':[37.5,37.5,37.51],'lon':[127.,127.,127.]});h=pd.DataFrame({'hospital_id':['H'],'name':['hospital'],'lat':[37.51],'lon':[127.]});m=build(o,f,rs,h,k=1);self.assertEqual(m['C'].shape,(1,1));self.assertTrue(m['C'][0,0]);self.assertAlmostEqual(m['weights'].sum(),1)
if __name__=='__main__':unittest.main()
