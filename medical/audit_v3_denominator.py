"""Checks V3 denominator decomposition against prior published max proxy outputs."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def audit(out):
    result = pd.read_csv(out / "v3_denominator_multiroute.csv")
    pairs = pd.read_csv(out / "v3_pair_classification.csv")
    metadata = json.loads((out / "v3_denominator_metadata.json").read_text(encoding="utf-8"))
    old = pd.read_csv(out / "headway_proxy_sensitivity.csv")
    assert len(pairs) == 426 * 3
    assert len(result) == len(old) * 2
    assert abs(pairs.population_weight.sum()-1) < 1e-10
    assert abs(metadata["observable_weight_mass"]+metadata["unobserved_weight_mass"]-1) < 1e-10
    assert set(pairs["class"]) <= {
        "straight_walk_flag", "matched_shared_route",
        "unmatched_only_route", "no_shared_route"
    }
    assert (result["spent"] == 50).all()
    assert result.gain_full_population.ge(-1e-12).all()
    assert result.gain_observable_only.ge(-1e-12).all()
    assert result.gain_no_shared_route.abs().max() < 1e-12
    assert result.gain_straight_walk.abs().max() < 1e-12
    assert (result.rank_full == result.rank_conditional).all()
    pd.testing.assert_series_equal(
        result.sort_values(["policy","reference_min","mode"]).reset_index(drop=True).observable_mass,
        pd.Series(np.repeat(metadata["observable_weight_mass"],len(result)),name="observable_mass"),
        check_exact=False,atol=1e-12)
    # The original V2 max headway proxy is EXACTLY the conditional
    # version of the new V3 max score. This guards against silent drift.
    sub=result[result["mode"]=="max"].copy()
    joined=sub.merge(old,on=["policy","reference_min"],validate="one_to_one")
    assert len(joined)==len(old)
    np.testing.assert_allclose(joined.gain_observable_only,joined.proxy_gain_observable,atol=1e-12,rtol=0)
    np.testing.assert_allclose(joined.gain_full_population,
                               joined.proxy_gain_observable * joined.observable_mass,atol=1e-12,rtol=0)
    receipt={
        "passed":True,
        "compared_v2_proxy_policy_reference_rows":int(len(joined)),
        "checked_v3_policy_reference_modes":int(len(result)),
        "pair_rows":int(len(pairs)),
        "max_proxy_reproduces_v2_observable_gain":True,
        "shared_route_absence_does_not_improve_from_fleet_replacement":True,
        "unconnected_is_model_limitation_not_real_trip_impossibility":True,
        "observed_boarding_or_departure_data":False,
    }
    (out / "v3_denominator_audit.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    return receipt


if __name__=="__main__":
    audit(ROOT/"results")
