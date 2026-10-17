"""Reproducible concentration-cap sweep and dong-level equity evaluation.

This is a STATIC supply-opportunity model, not realized passenger or travel effects.
Run after decision_stress.py. All caps use the same screened route universe.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from analyze_medical import scores
from decision_stress import capped_greedy, load_models, measure

ROOT = Path(__file__).resolve().parent
CAPS = (1, 3, 5, 7, 10, None)
BUDGET = 50
REFERENCE = "의료연결 우선"


def dong_metrics(model, origins, routes, allocation):
    """Return one row per dong and equity diagnostics at the fixed base setting."""
    fleet = model["f"]
    a_map = dict(zip(routes, allocation))
    assigned = np.array([a_map.get(r, 0) for r in fleet.route], dtype=int)
    n = fleet.fleet.to_numpy(int)
    low = fleet.low.to_numpy(int)
    before_pair = scores(model["C"], model["walk"], low / n)
    after_pair = scores(model["C"], model["walk"], (low + assigned) / n)
    before = before_pair.reshape(len(origins), model["k"]).mean(axis=1)
    after = after_pair.reshape(len(origins), model["k"]).mean(axis=1)
    delta = np.maximum(after - before, 0.0)
    changed = delta > 1e-10
    seniors = origins.seniors.to_numpy(float)
    bottom = np.zeros(len(origins), dtype=bool)
    bottom[np.argsort(before, kind="stable")[:int(np.ceil(.2 * len(origins)))]] = True
    positive = delta[changed]
    weighted = seniors * delta
    summary = {
        "changed_dongs": int(changed.sum()),
        "changed_dongs_ge_0p01": int((delta >= .01 - 1e-12).sum()),
        "changed_dongs_ge_0p05": int((delta >= .05 - 1e-12).sum()),
        "positive_delta_p10": float(np.quantile(positive, .10)) if positive.size else 0.0,
        "positive_delta_median": float(np.median(positive)) if positive.size else 0.0,
        "seniors_residing_in_changed_dongs": int(seniors[changed].sum()),
        "bottom_20pct_dongs_changed": int((changed & bottom).sum()),
        "bottom_20pct_seniors_weighted_delta": float(weighted[bottom].sum() / seniors[bottom].sum()),
        "top_10_dongs_share_of_weighted_gain": float(np.sort(weighted)[-10:].sum() / weighted.sum()) if weighted.sum() > 1e-12 else 0.0,
    }
    dong = origins[["code", "gu", "dong", "seniors"]].copy()
    dong["index_before"] = before
    dong["index_after"] = after
    dong["delta_index"] = delta
    dong["baseline_bottom_20pct"] = bottom
    return dong, summary


def build_results(origins, models, old_allocations):
    base = models["기본"]
    routes = base["f"].route.astype(str).tolist()
    current = old_allocations[old_allocations.policy == REFERENCE]
    original_map = current.set_index("route").added.to_dict()
    plans = [(REFERENCE, np.array([original_map.get(r, 0) for r in routes], int), None)]
    assert plans[0][1].sum() == BUDGET, "Run decision_stress.py first."
    for cap in CAPS:
        alloc, _ = capped_greedy([base], BUDGET, cap_per_route=cap or 100000)
        plans.append((f"screened_cap_{cap if cap is not None else 'none'}", alloc, cap))
    summary_rows, scenario_rows, allocations, dong_rows = [], [], [], []
    for policy, alloc, cap in plans:
        assert (alloc >= 0).all() and alloc.sum() <= BUDGET
        assert (alloc <= (base["f"].fleet.to_numpy() - base["f"].low.to_numpy())).all()
        if cap is not None:
            assert alloc.max() <= cap
        dong, equity = dong_metrics(base, origins, routes, alloc)
        dong.insert(0, "policy", policy)
        dong_rows.append(dong)
        for scenario, model in models.items():
            record = measure(model, origins, routes, alloc)
            scenario_rows.append({
                "policy": policy, "cap_per_route": cap if cap is not None else "unrestricted",
                "scenario": scenario, "spent": int(alloc.sum()), **record
            })
            if scenario == "기본":
                assert equity["changed_dongs"] == record["changed_dongs"]
                summary_rows.append({
                    "policy": policy, "cap_per_route": cap if cap is not None else "unrestricted",
                    "spent": int(alloc.sum()), "unspent": BUDGET - int(alloc.sum()),
                    "route_count": int((alloc > 0).sum()), "max_added": int(alloc.max()),
                    "base_delta_index": record["delta_index"], **equity
                })
        for i in np.flatnonzero(alloc):
            allocations.append({
                "policy": policy, "route": routes[i], "added": int(alloc[i]),
                "fleet": int(base["f"].fleet.iloc[i]), "low_before": int(base["f"].low.iloc[i])
            })
    summary = pd.DataFrame(summary_rows)
    scenario = pd.DataFrame(scenario_rows)
    original_gain = summary.loc[summary.policy == REFERENCE, "base_delta_index"].iloc[0]
    summary["gain_retained_vs_original_pct"] = 100 * summary.base_delta_index / original_gain
    summary["pareto_dominated_at_base"] = [
        bool(((summary.base_delta_index >= row.base_delta_index - 1e-12)
              & (summary.changed_dongs >= row.changed_dongs)
              & ((summary.base_delta_index > row.base_delta_index + 1e-12)
                 | (summary.changed_dongs > row.changed_dongs))).any())
        for row in summary.itertuples()
    ]
    return summary, scenario, pd.DataFrame(allocations), pd.concat(dong_rows, ignore_index=True)


def main():
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    origins, models = load_models()
    old = pd.read_csv(out / "screened_allocations.csv", dtype={"route": str})
    summary, scenario, allocations, dongs = build_results(origins, models, old)
    summary.to_csv(out / "cap_equity_summary.csv", index=False, encoding="utf-8-sig")
    scenario.to_csv(out / "cap_fixed_scenarios.csv", index=False, encoding="utf-8-sig")
    allocations.to_csv(out / "cap_allocations.csv", index=False, encoding="utf-8-sig")
    dongs.to_csv(out / "cap_dong_changes.csv", index=False, encoding="utf-8-sig")
    base = summary.set_index("policy")
    previous = pd.read_csv(out / "fixed_allocation_stress.csv")
    prev5 = previous[(previous.policy == "예외제외·노선당5대 의료우선") & (previous.scenario == "기본")].iloc[0]
    assert abs(base.loc["screened_cap_5", "base_delta_index"] - prev5.delta_index) < 1e-12
    assert int(base.loc["screened_cap_5", "changed_dongs"]) == int(prev5.changed_dongs)
    manifest = {
        "budget_unit": "50 vehicle replacements, not monetary cost",
        "screening": "All newly calculated cap policies exclude the same 25 official exception routes; original unscreened reference retained.",
        "caps": ["1", "3", "5", "7", "10", "unrestricted"],
        "base": "500 m nearest 3 general hospitals, static shared-route max fleet ratio",
        "secondary_scenarios": list(models),
        "measurement": "Index gain and changed dongs are modeled, NOT verified boardings or hospital travel.",
        "bottom_quintile": "Lowest 20% of 426 dongs by baseline index, not bottom 20% of individuals.",
        "exposure": "Residents in a changed dong, NOT actual benefiting passengers.",
        "gain_retention": "Relative to original medical-first allocation, at the 500 m base condition only.",
        "algorithm": "Greedy route bundles under caps; neither global Pareto-optimality nor real-world feasibility certified.",
        "pilot_status": "No timetable/low-floor vehicle schedule or patient trip outcomes verified by this module."
    }
    (out / "cap_equity_metadata.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))
    print("Saved:", ", ".join(["cap_equity_summary.csv", "cap_fixed_scenarios.csv",
                              "cap_allocations.csv", "cap_dong_changes.csv", "cap_equity_metadata.json"]))


if __name__ == "__main__":
    main()
