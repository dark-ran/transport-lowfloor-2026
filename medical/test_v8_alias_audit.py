"""V8 audit regression tests, no external data or online access required."""
import unittest
try:
    from medical import v8_alias_audit as m
except ImportError:
    import v8_alias_audit as m

class AliasAuditV8Tests(unittest.TestCase):
    def test_name_variants_are_not_silently_deduplicated(self):
        rows={
            ("343","100",9):[("A(00009)",40,20),("B(00009)",60,30)],
            ("662","200",4):[("Stable(00004)",80,50)]
        }
        route,aliases=m.analyze(rows,{"343","662"})
        self.assertEqual(len(aliases),1)
        self.assertEqual(route["343"]["all"],100)
        self.assertEqual(route["343"]["max_variant"],60)
        self.assertEqual(route["343"]["min_variant"],40)
        self.assertEqual(route["662"]["all"],80)

    def test_common_denominator_and_no_reallocation(self):
        a={
           "screened_cap_3":{"343":(1,2)},
           "screened_cap_5":{"662":(1,2)},
           "screened_cap_7":{"343":(1,2)}
        }
        counts={"343":{"all":20,"max_variant":10,"min_variant":5},
                "662":{"all":80,"max_variant":80,"min_variant":80}}
        results=m.policy_sensitivity(a,counts)
        source={x["policy"]:x for x in results if x["scenario"]=="all"}
        self.assertEqual({x["denominator"] for x in results if x["scenario"]=="all"},{100})
        self.assertAlmostEqual(source["screened_cap_3"]["demand_weighted_stock_ratio_change_pp"],10)
        self.assertAlmostEqual(source["screened_cap_5"]["demand_weighted_stock_ratio_change_pp"],40)

if __name__=="__main__":
    unittest.main()
