import sys,itertools,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from analysis import allocate
class AllocationTest(unittest.TestCase):
 def test_threshold_matches_exhaustive(self):
  rng=np.random.default_rng(42)
  for _ in range(35):
   n=rng.integers(1,6,4);l=np.array([rng.integers(0,int(x)+1) for x in n]);t=float(rng.choice([.25,.5,.75]));b=int(rng.integers(0,7))
   a=allocate(n,l,b,'threshold',t)
   exact=max(sum((l+np.array(z))/n>=t-1e-10) for z in itertools.product(*[range(int(c)+1) for c in n-l]) if sum(z)<=b)
   self.assertEqual(sum((l+a)/n>=t-1e-10),exact)
 def test_all_policy_budget_and_capacity(self):
  n=np.array([2,5,10,4]);l=np.array([0,1,8,4])
  for mode in ['proportional','lowest_ratio','threshold','hybrid']:
   for b in [0,1,5,9,100]:
    a=allocate(n,l,b,mode);self.assertEqual(a.sum(),min(b,int((n-l).sum())));self.assertTrue(np.all(a>=0)&np.all(l+a<=n))
 def test_hybrid_eliminates_zero_if_funded(self):
  n=np.array([2,5,10]);l=np.array([0,0,2]);a=allocate(n,l,2,'hybrid');self.assertTrue(np.all(l+a>0))
if __name__=='__main__':unittest.main()
