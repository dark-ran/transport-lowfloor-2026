"""Counterfactual crosswalk: which dong-hospital index pairs depend on each cap-5 route?

Leave-one-selected-route-out while all other allocations stay fixed.
These NONADDITIVE static marginal contributions are not observed trip effects.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from analyze_medical import scores
from decision_stress import load_models

ROOT = Path(__file__).resolve().parent


def marginal_pairs(model, origins, routes, added):
    fleets = model["f"]
    plan = dict(zip(routes, added))
    a = np.array([plan.get(str(route), 0) for route in fleets.route], int)
    n = fleets.fleet.to_numpy(int)
    low = fleets.low.to_numpy(int)
    base = scores(model["C"], model["walk"], low / n)
    full = scores(model["C"], model["walk"], (low + a) / n)
    pairs = model["pairs"]
    result = []
    route_totals = []
    for i in np.flatnonzero(a):
        knock = a.copy()
        knock[i] = 0
        without = scores(model["C"], model["walk"], (low + knock) / n)
        marginal = np.maximum(full - without, 0)
        overall = float(marginal @ model["weights"])
        route = str(fleets.route.iloc[i])
        route_totals.append({"route": route, "added": int(a[i]),
                             "leave_one_out_weighted_index_loss": overall,
                             "positive_pairs": int((marginal > 1e-10).sum())})
        for j in np.flatnonzero(marginal > 1e-10):
            dong_i = int(j // model["k"])
            p = pairs.iloc[j]
            result.append({
                "route": route, "added": int(a[i]),
                "dong_code": str(origins.code.iloc[dong_i]),
                "gu": str(origins.gu.iloc[dong_i]),
                "dong": str(origins.dong.iloc[dong_i]),
                "seniors_in_dong": int(origins.seniors.iloc[dong_i]),
                "hospital_id": str(p.hospital_id),
                "hospital_name": str(p.hospital_name),
                "hospital_rank": int(p["rank"]),
                "base_pair_score": float(base[j]),
                "full_pair_score": float(full[j]),
                "index_loss_without_route": float(marginal[j]),
                "population_weighted_pair_loss": float(marginal[j] * model["weights"][j])
            })
    return pd.DataFrame(result), pd.DataFrame(route_totals)


def main():
    out = ROOT / "results"
    origins, models = load_models()
    model = models["기본"]
    routes = model["f"].route.astype(str).tolist()
    allocations = pd.read_csv(out / "cap_allocations.csv", dtype={"route": str})
    selected = allocations[allocations.policy == "screened_cap_5"]
    added_map = selected.set_index("route").added.to_dict()
    added = np.array([added_map.get(route, 0) for route in routes], int)
    assert added.sum() == 50
    pairs, totals = marginal_pairs(model, origins, routes, added)
    if pairs.empty:
        pairs = pd.DataFrame(columns=["route", "added", "dong_code", "gu", "dong",
            "seniors_in_dong", "hospital_id", "hospital_name", "hospital_rank",
            "base_pair_score", "full_pair_score", "index_loss_without_route",
            "population_weighted_pair_loss"])
    pairs.to_csv(out / "cap5_route_marginal_pairs.csv", index=False, encoding="utf-8-sig")
    totals.to_csv(out / "cap5_route_marginal_totals.csv", index=False, encoding="utf-8-sig")
    summary = {
        "allocated_routes": int((added > 0).sum()),
        "route_pair_counterfactual_records": len(pairs),
        "routes_with_positive_nonadditive_marginal": int((totals.leave_one_out_weighted_index_loss > 1e-12).sum()),
        "logic": "Remove one selected route's hypothetical replacements, hold all other routes' allocations fixed, recalculate static max-ratio index.",
        "caution": "Route marginals overlap and are not additive; no directed service, boarding, waiting, hospital visit or causal impact established.",
        "pilot": "These specific dong-hospital-route pairs are the candidates for separate ordered-direction screening."
    }
    (out / "cap5_route_marginal_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
