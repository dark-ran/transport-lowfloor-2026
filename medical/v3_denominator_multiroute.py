"""V3: consistent denominators and sensitivity to the shared-route aggregator.

Do not interpret scores as wait time or boarding probability. 'saturated_union'
is a bounding sensitivity heuristic 1 - product(1 - proxy_route_score),
NOT statistically independent bus-arrival events.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from decision_stress import load_models
from headway_proxy import load_archived_headways

ROOT = Path(__file__).resolve().parent
REF_MINUTES = (10, 15, 20)


def classify_pairs(model, headways):
    c = model["C"]
    walk = model["walk"]
    shared = c.any(axis=1)
    known = np.isfinite(headways)
    known_shared = c[:, known].any(axis=1)
    category = np.select(
        [walk, (~walk) & known_shared, (~walk) & shared, (~walk) & (~shared)],
        ["straight_walk_flag", "matched_shared_route", "unmatched_only_route", "no_shared_route"],
        default="error"
    )
    assert not (category == "error").any()
    return category, walk | known_shared


def proxy_scores(C, walk, ratio, mode):
    x = np.asarray(ratio, float)
    if mode == "max":
        values = np.max(np.where(C, x[None, :], 0.), axis=1)
    elif mode == "saturated_union":
        # A deliberately NON-PROBABILISTIC alternative aggregation. Shared
        # route timing/choice can be correlated, so this is not a service
        # arrival or boarding probability.
        values = 1. - np.prod(np.where(C, 1. - x[None, :], 1.), axis=1)
    else:
        raise ValueError(f"Unknown mode {mode}")
    values = values.copy()
    values[walk] = 1.
    return values


def fixed_allocations(model, folder):
    routes = model["f"].route.astype(str).tolist()
    n = model["f"].fleet.to_numpy(int)
    low = model["f"].low.to_numpy(int)
    data = [
        pd.read_csv(folder / "cap_allocations.csv", dtype={"route": str}),
        pd.read_csv(folder / "screened_allocations.csv", dtype={"route": str})
    ]
    plans = {}
    for frame in data:
        for policy, block in frame.groupby("policy"):
            if policy in plans:
                continue
            assert not block.route.duplicated().any()
            values = block.set_index("route").added.to_dict()
            assert set(values).issubset(set(routes))
            a = np.array([values.get(route, 0) for route in routes], dtype=int)
            assert a.sum() == 50 and (a >= 0).all() and (a <= n - low).all()
            plans[policy] = a
    return plans


def compute_summary(model, origins, headways, plans):
    c = model["C"]
    walk = model["walk"]
    w = model["weights"].copy()
    category, observable = classify_pairs(model, headways)
    covered_mass = float(w[observable].sum())
    assert 0 < covered_mass <= 1
    conditional_w = (w * observable) / covered_mass
    f = model["f"]
    ratio = f.low.to_numpy(float) / f.fleet.to_numpy(float)
    n = f.fleet.to_numpy(float)
    rows = []
    for reference in REF_MINUTES:
        multipliers = np.zeros(len(headways))
        matched = np.isfinite(headways)
        multipliers[matched] = np.minimum(1., reference / headways[matched])
        for mode in ("max", "saturated_union"):
            before = proxy_scores(c, walk, ratio * multipliers, mode)
            for policy, a in plans.items():
                after = proxy_scores(c, walk, (ratio + a/n) * multipliers, mode)
                gain = np.maximum(after - before, 0.)
                rows.append({
                    "policy": policy, "reference_min": reference, "mode": mode,
                    "gain_full_population": float(gain @ w),
                    "gain_observable_only": float(gain @ conditional_w),
                    "observable_mass": covered_mass,
                    "changed_dongs": int((gain.reshape(len(origins), model["k"]).max(axis=1) > 1e-10).sum()),
                    "gain_no_shared_route": float(gain[category == "no_shared_route"] @ w[category == "no_shared_route"]),
                    "gain_matched_shared": float(gain[category == "matched_shared_route"] @ w[category == "matched_shared_route"]),
                    "gain_straight_walk": float(gain[category == "straight_walk_flag"] @ w[category == "straight_walk_flag"]),
                    "spent": int(a.sum())
                })
    result = pd.DataFrame(rows)
    result["rank_full"] = result.groupby(["reference_min", "mode"]).gain_full_population.rank(
        method="min", ascending=False).astype(int)
    result["rank_conditional"] = result.groupby(["reference_min", "mode"]).gain_observable_only.rank(
        method="min", ascending=False).astype(int)
    assert (result.rank_full == result.rank_conditional).all(), "Fixed subset scales all gains identically."
    return result, category, observable


def main():
    out = ROOT / "results"
    origins, models = load_models()
    model = models["기본"]
    routes = model["f"].route.astype(str).tolist()
    headways, _, headway_meta = load_archived_headways(
        ROOT / "raw/노선정보_20261017.csv", routes)
    plans = fixed_allocations(model, out)
    summary, category, observable = compute_summary(model, origins, headways, plans)
    summary.to_csv(out / "v3_denominator_multiroute.csv", index=False, encoding="utf-8-sig")
    pairs = model["pairs"].copy()
    pairs.insert(0, "origin_gu", np.repeat(origins.gu.to_numpy(), model["k"]))
    pairs.insert(1, "origin_dong", np.repeat(origins.dong.to_numpy(), model["k"]))
    pairs.insert(2, "origin_seniors", np.repeat(origins.seniors.to_numpy(), model["k"]))
    pairs["class"] = category
    pairs["nominal_headway_proxy_observable"] = observable
    pairs["population_weight"] = model["weights"]
    pairs.to_csv(out / "v3_pair_classification.csv", index=False, encoding="utf-8-sig")
    m = pd.DataFrame({"class": category, "weight": model["weights"]})
    mass = m.groupby("class").agg(pairs=("weight", "size"), weight=("weight", "sum")).reset_index()
    no_connection = category == "no_shared_route"
    fully_unconnected_dongs = int(no_connection.reshape(len(origins), model["k"]).all(axis=1).sum())
    metadata = {
        "input_model_pairs": int(len(category)),
        "dong_count": int(len(origins)),
        "hospital_pairs_per_dong": int(model["k"]),
        "headway_matched_model_routes": headway_meta["matched_model_routes"],
        "pair_classes": mass.to_dict("records"),
        "full_model_population_weight_sum": float(model["weights"].sum()),
        "observable_weight_mass": float(model["weights"][observable].sum()),
        "unobserved_weight_mass": float(model["weights"][~observable].sum()),
        "all_three_nearest_hospital_pairs_without_shared_route_dongs": fully_unconnected_dongs,
        "unconnected_interpretation": "No model-shared bus route at the specified 500m straight-line endpoints; not proof of impossible travel",
        "comparison": "All policies evaluated on same full 426 x 3 pairs; conditional values divide by same observable mass",
        "max_mode": "Select highest single shared-route proxy value",
        "saturated_union_mode": "1-product(1-route proxy value), a non-probabilistic sensitivity heuristic; route arrivals are not independent",
        "caution": "Not actual wheelchair accessible path, wait time, low-floor frequency, trip success, or deployment effect"
    }
    (out / "v3_denominator_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Pair classes and weight:", mass.to_string(index=False))
    print("Fully unconnected dongs:", fully_unconnected_dongs)
    print(summary[summary.policy.isin(["screened_cap_3", "screened_cap_5", "screened_cap_7", "의료연결 우선"])]
          [["policy","reference_min","mode","gain_full_population","changed_dongs","rank_full"]].to_string(index=False))


if __name__ == "__main__":
    main()
