"""Pilot check: do SELECTED cap-5 replacement routes have ordered outbound/return examples?

Uses ONLY the previously cached 69 TOPIS/BIS routes. No live feeds or complete
network coverage. Never infer a patient benefit, low-floor wait, or a missing path
from a failed lookup. Route-level published headway is not low-floor headway.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from decision_stress import load_models
from validate_cases import candidates

ROOT = Path(__file__).resolve().parent


def first_direct(route_frame, start, end):
    direct, _ = candidates([route_frame], start, end, radius=500)
    return direct[0] if direct else None


def compact_leg(found):
    if found is None:
        return {}
    leg = found["legs"][0]
    return {
        "board": leg["board"], "board_seq": leg["board_seq"],
        "alight": leg["alight"], "alight_seq": leg["alight_seq"],
        "origin_straight_m": round(found["origin_straight_m"], 1),
        "destination_straight_m": round(found["destination_straight_m"], 1),
        "stop_intervals": leg["stop_intervals"]
    }


def main():
    out = ROOT / "results"
    origins, models = load_models()
    m = models["기본"]
    allocations = pd.read_csv(out / "cap_allocations.csv", dtype={"route": str})
    allocations = allocations[allocations.policy == "screened_cap_5"].copy()
    changes = pd.read_csv(out / "cap_dong_changes.csv", dtype={"code": str})
    changes = changes[(changes.policy == "screened_cap_5") & (changes.delta_index > 1e-10)]
    improved = changes.set_index("code")
    pairs = m["pairs"]
    h = pd.read_csv(ROOT / "data/hospitals.csv", dtype={"hospital_id": str}).set_index("hospital_id")
    selected = {}
    for route in json.loads((ROOT / "raw/current_case_stops.json").read_text(encoding="utf-8")):
        df = pd.DataFrame(route["rows"]).sort_values("stationOrd").reset_index(drop=True)
        if df.empty:
            continue
        label = str(df.routNm.iloc[0])
        selected.setdefault(label, []).append(df)
    live = {str(r["routId"]): r for r in json.loads(
        (ROOT / "raw/topis_case_metadata.json").read_text(encoding="utf-8"))}
    route_index = {str(r): i for i, r in enumerate(m["f"].route)}
    origin_index = {str(code): i for i, code in enumerate(origins.code.astype(str))}
    rows = []
    n_pairs_considered = 0
    for a in allocations.itertuples():
        if a.route not in selected:
            continue  # absent from a NON-exhaustive 69-route archive, not evidence of no service
        j = route_index[a.route]
        possible = pairs[pairs.dong_code.astype(str).isin(improved.index)].copy()
        possible = possible[possible.apply(
            lambda p: bool(m["C"][origin_index[str(p.dong_code)] * m["k"] + int(p["rank"]) - 1, j]), axis=1)]
        possible["priority"] = possible.dong_code.astype(str).map(
            lambda code: float(improved.loc[code, "delta_index"] * improved.loc[code, "seniors"]))
        # At most 12 pairs per route; this is a small, nonrepresentative pilot.
        for pair in possible.sort_values("priority", ascending=False).head(12).itertuples():
            n_pairs_considered += 1
            o = origins.iloc[origin_index[str(pair.dong_code)]]
            hospital = h.loc[str(pair.hospital_id)]
            outward = [float(o.lat), float(o.lon)]
            destination = [float(hospital.lat), float(hospital.lon)]
            for frame in selected[a.route]:
                found_out = first_direct(frame, outward, destination)
                found_back = first_direct(frame, destination, outward)
                if not (found_out or found_back):
                    continue
                route_id = str(frame.routeId.iloc[0])
                meta = live.get(route_id, {})
                item = {
                    "dong_code": str(pair.dong_code), "gu": str(o.gu), "dong": str(o.dong),
                    "hospital": str(pair.hospital_name), "route": a.route,
                    "route_id": route_id, "added_in_model": int(a.added),
                    "static_lowfloor_ratio_before": float(a.low_before / a.fleet),
                    "static_lowfloor_ratio_after": float((a.low_before + a.added) / a.fleet),
                    "base_dong_index_gain": float(improved.loc[str(pair.dong_code), "delta_index"]),
                    "weekday_published_route_headway_min": meta.get("norTerms", ""),
                    "outbound_direct": bool(found_out), "return_direct": bool(found_back),
                    "both_directions": bool(found_out and found_back),
                    "outbound_leg": json.dumps(compact_leg(found_out), ensure_ascii=False),
                    "return_leg": json.dumps(compact_leg(found_back), ensure_ascii=False)
                }
                rows.append(item)
    data = pd.DataFrame(rows)
    name = out / "cap5_route_pilot_candidates.csv"
    if not data.empty:
        data = data.sort_values(["both_directions", "base_dong_index_gain"],
                                ascending=[False, False]).drop_duplicates(
                                    ["dong_code", "hospital", "route"])
        data.to_csv(name, index=False, encoding="utf-8-sig")
        sample = data.head(3)[["dong", "hospital", "route", "both_directions",
                              "weekday_published_route_headway_min"]].to_dict("records")
        both = int(data.both_directions.sum())
    else:
        pd.DataFrame(columns=["dong_code", "hospital", "route", "both_directions",
                              "weekday_published_route_headway_min"]).to_csv(
                                  name, index=False, encoding="utf-8-sig")
        sample = []
        both = 0
    matched = sorted(set(allocations.route) & set(selected))
    summary = {
        "allocation": "screened_cap_5, the static 50-replacement policy",
        "matched_allocated_routes_in_cached_69_route_subset": matched,
        "allocated_route_count": int(len(allocations)),
        "tested_route_dong_hospital_pairs": n_pairs_considered,
        "pairs_with_at_least_one_ordered_direct_direction": int(len(data)),
        "pairs_with_both_ordered_direct_directions": both,
        "examples_max_3": sample,
        "scope": "2026-10-17 archived TOPIS/BIS snapshot for three previously chosen districts; missing route/path is UNKNOWN, not unavailable.",
        "distance": "500m straight-line endpoints; not accessible walking route",
        "route_validation": "Increasing stop order, no internal turning point; no live timetable continuity test",
        "headway": "Nominal whole-route service spacing; neither low-floor departure intervals nor measured wait",
        "policy_effect": "Existing 2025 fleet ratio mechanically adjusted by hypothetical bus replacements; no real-world boardings, travel time or empirical effect verified",
        "conclusion": "A route example, if found, establishes limited static plausibility only; NOT causal validation of replacement allocation."
    }
    (out / "cap5_route_pilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
