import unittest
import numpy as np
import pandas as pd
from policy_extension import dong_metrics
from allocated_route_pilot import first_direct


class ExtensionTests(unittest.TestCase):
    def test_equity_metrics_do_not_count_tiny_changes_as_large(self):
        origins = pd.DataFrame({
            "code": ["01", "02", "03", "04", "05"],
            "gu": ["X"] * 5, "dong": ["a", "b", "c", "d", "e"],
            "seniors": [10, 20, 30, 40, 50]
        })
        model = {
            "f": pd.DataFrame({"route": ["A", "B"], "fleet": [10, 100],
                               "low": [0, 0]}),
            "C": np.array([[1, 0], [0, 1], [1, 1], [0, 0], [0, 0]], bool),
            "walk": np.zeros(5, bool), "k": 1
        }
        dong, summary = dong_metrics(model, origins, ["A", "B"], np.array([5, 1]))
        self.assertEqual(summary["changed_dongs"], 3)
        self.assertEqual(summary["changed_dongs_ge_0p01"], 3)
        self.assertEqual(summary["changed_dongs_ge_0p05"], 2)
        self.assertEqual(summary["seniors_residing_in_changed_dongs"], 60)
        self.assertEqual(summary["bottom_20pct_dongs_changed"], 1)
        self.assertAlmostEqual(summary["bottom_20pct_seniors_weighted_delta"], .5)
        self.assertAlmostEqual(float(dong.iloc[1].delta_index), .01)

    def test_directional_route_order_is_respected(self):
        stops = pd.DataFrame({
            "routNm": ["343"] * 3, "routeId": ["R"] * 3,
            "stationOrd": [1, 2, 3], "posY": [37.5, 37.501, 37.502],
            "posX": [127.0] * 3,
            "turnPlaceStationYn": ["N"] * 3,
            "guganLen": [0, 100, 100],
            "stationId": ["S1", "S2", "S3"],
            "stnName": ["a", "b", "c"], "arsId": ["1", "2", "3"]
        })
        a, b = [37.5, 127.0], [37.502, 127.0]
        forward = first_direct(stops, a, b)
        self.assertIsNotNone(forward)
        self.assertIsNone(first_direct(stops, b, a))


if __name__ == "__main__":
    unittest.main()
