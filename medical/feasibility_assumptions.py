"""Fleet-data-bounded *hypothetical* route replacement eligibility study.

No fleet age, cost, depot, road geometry, charging, or vehicle-type information
is available, so fractions of 2025 remaining non-low-floor buses are only
sensitivity assumptions -- never claims of field implementation feasibility.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from decision_stress import capped_greedy, load_models, measure
from policy_extension import dong_metrics

ROOT = Path(__file__).resolve().parent
ASSUMED_ELIGIBLE_FRACTIONS = (0.25, 0.5, 1.0)


def study(origins, model, fractions=ASSUMED_ELIGIBLE_FRACTIONS):
    routes = model["f"].route.astype(str).tolist()
    n = model["f"].fleet.to_numpy(int)
    l = model["f"].low.to_numpy(int)
    available = n - l
    banned = set(json.loads((ROOT/"raw/exception_routes_2026.json").read_text(encoding="utf-8"))["routes"])
    allowed = np.array([route not in banned for route in routes],dtype=bool)
    rows = []
    details = []
    for share in fractions:
        assert 0 < share <= 1
        route_cap = np.floor(available * share).astype(int)
        # Limit max 5 hypothetical replacements/route plus fraction of
        # remaining high-floor vehicles, *then* screen exceptions internally.
        a, steps = capped_greedy([model], 50, 5, False, cap_by_route=route_cap)
        measured = measure(model, origins, routes, a)
        _, equity = dong_metrics(model, origins, routes, a)
        rows.append({
            "eligible_highfloor_fraction_assumed": share,
            "route_max_5": True,
            "spent": int(a.sum()), "unspent": 50-int(a.sum()),
            "eligible_non_exception_route_count": int(((route_cap>0)&allowed).sum()),
            "allocated_route_count": int((a>0).sum()),
            "base_delta_index": measured["delta_index"],
            "changed_dongs": measured["changed_dongs"],
            "changed_dongs_ge_0p05": equity["changed_dongs_ge_0p05"],
            "bottom_20pct_dongs_changed": equity["bottom_20pct_dongs_changed"],
            "bundles": len(steps)
        })
        for j in np.flatnonzero(a):
            details.append({
                "assumed_eligible_fraction": share, "route": routes[j],
                "non_lowfloor_vehicles_2025": int(available[j]),
                "assumed_eligible_cap": int(route_cap[j]),
                "allocated": int(a[j])
            })
    return pd.DataFrame(rows), pd.DataFrame(details)


def main():
    out = ROOT / "results"
    origins, models = load_models()
    summary, route_allocations = study(origins, models["기본"])
    summary.to_csv(out/"feasibility_assumption_stress.csv",
                   index=False, encoding="utf-8-sig")
    route_allocations.to_csv(out/"feasibility_assumption_allocations.csv",
                             index=False, encoding="utf-8-sig")
    metadata = {
        "purpose": "Operational eligibility uncertainty sensitivity, NOT implementation certification",
        "fractions": list(ASSUMED_ELIGIBLE_FRACTIONS),
        "formula": "floor((2025 licensed vehicles - 2025 low-floor vehicles) * researcher fraction) capped at 5 per route",
        "additional_screen": "same official 25 exception routes excluded",
        "budget_unit": "50 hypothetical vehicle replacements, not currency",
        "reoptimized_for_each_eligibility_assumption": True,
        "actual_vehicle_age_known": False,
        "actual_vehicle_type_or_depot_known": False,
        "actual_cost_or_charging_known": False,
        "vehicle_level_decommission_or_replacement_schedule_known": False,
        "limitation": "Fleet composition is 2025 data, operational or 2026 replacement feasibility is not known."
    }
    (out/"feasibility_assumption_metadata.json").write_text(
        json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
