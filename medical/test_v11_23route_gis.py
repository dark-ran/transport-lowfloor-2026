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
if __name__=="__main__":unittest.main()
