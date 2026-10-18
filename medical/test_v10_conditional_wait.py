import unittest
try:from medical import v10_conditional_wait as a
except ImportError:import v10_conditional_wait as a
class V10Tests(unittest.TestCase):
 def test_enumeration(self):self.assertEqual(a.audit(),36)
 def test_343(self):
  self.assertEqual(a.bounds(15,18,12),(12.5,25.0))
  x,y=a.bounds(15,18,17);self.assertAlmostEqual(x,8.333333333333334);self.assertEqual(x,y)
 def test_no_actual_effect_proof(self):
  self.assertEqual(len(a.build()),3)
  self.assertTrue(all(x["hypothetical_change_lower_min"]>0 for x in a.build()))
 def test_invalid(self):
  with self.assertRaises(ValueError):a.bounds(0,18,12)
if __name__=="__main__":unittest.main()
