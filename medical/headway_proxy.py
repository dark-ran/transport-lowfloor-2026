"""Auxiliary HEADWAY-SCALED STATIC supply index, never a waiting-time model.

The baseline max-ratio index is retained. Here a route's 2025 low-floor fleet
fraction is multiplied by min(1, reference_minutes / 2026 archived NOMINAL
weekday route headway). This is an illustrative frequency penalty, NOT an
estimate of low-floor departure frequency, vehicle arrival probability,
travel-time savings or timetable feasibility.

Unknown, conflicting or inactive route entries are NEVER silently imputed.
All candidate allocations are held fixed; routes are not reoptimized.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from decision_stress import load_models
from analyze_medical import scores
from policy_extension import CAPS

ROOT = Path(__file__).resolve().parent
REFERENCE_MINUTES = (10, 15, 20)
EXTRA_POLICIES = ("예외제외 비례", "예외제외·5조건 강건5대")


def load_archived_headways(path, route_names):
    raw = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    raw.columns = [str(c).replace("\ufeff", "").strip() for c in raw.columns]
    raw = raw.apply(lambda col: col.map(lambda x: str(x).replace("\ufeff", "").strip()))
    required = {"노선ID", "노선명", "배차", "운행여부", "사용여부"}
    assert required.issubset(raw.columns), sorted(required - set(raw.columns))
    active = raw[(raw["운행여부"] == "1") & (raw["사용여부"] == "1")].copy()
    active["minutes"] = pd.to_numeric(active["배차"], errors="coerce")
    active = active[active.minutes.between(2, 120)].copy()
    # Deduplicate repeated copies of the SAME line ID. Conflicting published
    # values even within one line ID are rejected instead of cherry-picked.
    active = active.drop_duplicates(["노선ID", "노선명", "minutes"])
    route_map = {}
    for name, group in active.groupby("노선명", sort=False):
        ids = group["노선ID"].unique()
        vals = group.minutes.unique()
        # One name/one unique route ID and one positive interval. A/B branches
        # and duplicate/reused names are deliberately left unmatched.
        if len(ids) == 1 and len(vals) == 1:
            route_map[name] = (float(vals[0]), str(ids[0]))
    names = list(map(str, route_names))
    values = np.array([route_map.get(n, (np.nan, ""))[0] for n in names], dtype=float)
    id_values = [route_map.get(n, (np.nan, ""))[1] for n in names]
    catalog = pd.DataFrame({
        "route": names, "nominal_weekday_headway_min": values,
        "matched_route_id": id_values,
        "headway_matched": np.isfinite(values)
    })
    diagnostics = {
        "archived_raw_rows": len(raw),
        "archived_active_positive_interval_rows": len(active),
        "matched_model_routes": int(np.isfinite(values).sum()),
        "total_model_routes": len(names),
        "ambiguous_inactive_or_missing_model_routes": int(np.isnan(values).sum()),
        "matching_rule": "exact 2025 route name = one active 2026 BIS route ID with one unique 2..120-minute nominal interval; missing/conflicting/inactive excluded"
    }
    return values, catalog, diagnostics


def headway_scores(model, ratio, headways, reference_minutes):
    assert len(ratio) == len(headways) == model["C"].shape[1]
    penalty = np.zeros(len(ratio), dtype=float)
    valid = np.isfinite(headways)
    penalty[valid] = np.minimum(1., reference_minutes / headways[valid])
    proxy_ratio = np.asarray(ratio, float) * penalty
    return scores(model["C"], model["walk"], proxy_ratio)


def paired_comparison(model, ratio, new_ratio, headways, minutes):
    C = model["C"]
    walk = model["walk"]
    known = np.isfinite(headways)
    known_connection = C[:, known].any(axis=1)
    any_connection = C.any(axis=1)
    observable = walk | known_connection
    # Same observable origin-hospital subset for every policy AND cap.
    weights = model["weights"] * observable
    assert weights.sum() > 0, "No documented route-headway coverage."
    weights /= weights.sum()
    before = headway_scores(model, ratio, headways, minutes)
    after = headway_scores(model, new_ratio, headways, minutes)
    delta = np.maximum(0, after - before)
    return {
        "proxy_before_observable": float(before @ weights),
        "proxy_after_observable": float(after @ weights),
        "proxy_gain_observable": float(delta @ weights),
        "changed_pairs_observable": int(((delta > 1e-10) & observable).sum()),
        "changed_dongs_observable": int(((delta > 1e-10).reshape(-1, model["k"]).any(axis=1)).sum()),
        "matched_model_route_count": int(known.sum()),
        "matched_shared_pair_count": int((known_connection & any_connection).sum()),
        "all_shared_pair_count": int(any_connection.sum()),
        "matched_shared_pair_weight_share": float(model["weights"][known_connection & any_connection].sum()
                                                  / model["weights"][any_connection].sum()) if any_connection.any() else 0.,
        "observable_weight_share_total": float(model["weights"][observable].sum()),
        "unmatched_shared_pair_count": int((any_connection & ~known_connection).sum())
    }


def run(models, raw_headways, cap_allocations, other_allocations):
    model = models["기본"]
    routes = model["f"].route.astype(str).tolist()
    n = model["f"].fleet.to_numpy(int)
    low = model["f"].low.to_numpy(int)
    headways, catalog, meta = load_archived_headways(raw_headways, routes)
    plans = {}
    for data, labels in ((cap_allocations, cap_allocations.policy.unique()),
                         (other_allocations, EXTRA_POLICIES)):
        for policy in labels:
            part = data[data.policy == policy]
            if part.empty:
                raise ValueError(f"Missing fixed allocation {policy}")
            if part.route.duplicated().any():
                raise ValueError(f"Duplicate routes: {policy}")
            a = part.set_index("route").added.to_dict()
            vector = np.array([a.get(route, 0) for route in routes], dtype=int)
            assert vector.sum() == 50 and (vector <= n - low).all()
            plans[str(policy)] = vector
    rows, route_table = [], []
    for name, a in plans.items():
        for i in np.flatnonzero(a):
            route_table.append({
                "policy": name, "route": routes[i], "replacements": int(a[i]),
                "headway_matched": bool(np.isfinite(headways[i])),
                "nominal_headway_min": float(headways[i]) if np.isfinite(headways[i]) else None
            })
        for minutes in REFERENCE_MINUTES:
            scored = paired_comparison(model, low/n, (low+a)/n, headways, minutes)
            rows.append({
                "policy": name, "reference_min": minutes,
                "allocated_routes_with_headway": int((np.isfinite(headways) & (a > 0)).sum()),
                "allocated_buses_with_headway": int(a[np.isfinite(headways)].sum()),
                **scored
            })
    table = pd.DataFrame(rows)
    # Rank candidate FIXED allocations under each headway penalty;
    # this is not a new optimized policy.
    table["proxy_rank"] = table.groupby("reference_min").proxy_gain_observable.rank(
        method="min", ascending=False).astype(int)
    # The original main index comparison is supplied for interpretative
    # context, without pretending that differently scaled index values match.
    return catalog, pd.DataFrame(route_table), table, meta


def main():
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    _, models = load_models()
    caps = pd.read_csv(out / "cap_allocations.csv", dtype={"route": str})
    other = pd.read_csv(out / "screened_allocations.csv", dtype={"route": str})
    catalog, alloc, result, meta = run(
        models, ROOT / "raw/노선정보_20261017.csv", caps, other)
    catalog.to_csv(out / "headway_matched_routes.csv", index=False, encoding="utf-8-sig")
    alloc.to_csv(out / "headway_policy_coverage.csv", index=False, encoding="utf-8-sig")
    result.to_csv(out / "headway_proxy_sensitivity.csv", index=False, encoding="utf-8-sig")
    metadata = {
        **meta,
        "source": "Seoul T-Data public BIS archived route-information CSV, downloaded 2026-10-17",
        "source_url": "https://t-data.seoul.go.kr/dataprovide/trafficdataviewfile.do?data_id=53",
        "fleet_reference": "2025-04-25; time-alignment not verified",
        "formula": "max shared-route [2025 low-floor fleet ratio * min(1, reference_minutes / 2026 nominal published weekday headway)]",
        "references": list(REFERENCE_MINUTES),
        "complete_network": False,
        "unknown_headway": "excluded from proxy (not imputed), observable pair subset is identical for all compared policies",
        "score_scope": "population-weighted normalized index on pairs with at least one matched shared route or within 500m straight-line walk flag",
        "do_not_infer": ["real low-floor departure interval", "passenger wait or arrival probability",
                          "wheelchair boarding", "direction or timetable continuity", "causal travel benefit"],
        "allocation_method": "all existing candidate allocations FIXED, not reoptimized",
        "uncertainty": "2025 fleet and 2026 nominal headways mixed; reference 10/15/20 min is researcher sensitivity, not official standard"
    }
    (out / "headway_proxy_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result[["policy","reference_min","proxy_gain_observable",
                  "changed_dongs_observable","allocated_buses_with_headway",
                  "proxy_rank"]].to_string(index=False))
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
