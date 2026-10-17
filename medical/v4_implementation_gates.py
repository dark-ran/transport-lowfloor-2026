"""V4 deployment evidence-gate dashboard, with no invented feasibility claims.

This is a CHECKLIST of decision prerequisites, NOT route-level operational
approval. A missing field stays UNKNOWN, not passed/failed by assumption.
"""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parent


def compile_gates(allocations,headways,directional,exception_names,expected_budget=50):
    chosen=allocations[allocations.policy=="screened_cap_5"].copy()
    chosen["route"]=chosen.route.astype(str)
    assert chosen.added.sum()==expected_budget and chosen.route.is_unique
    head=headways.copy()
    head["route"]=head.route.astype(str)
    directional=directional.copy()
    directional["route"]=directional.route.astype(str)
    route_status=directional.groupby("route",dropna=False).agg(
        cached_pairs=("snapshot_route_available",lambda x:int(x.fillna(False).sum())),
        bidirectional_pairs=("coverage",lambda x:int((x=="bidirectional").sum())),
        one_direction_pairs=("coverage",lambda x:int((x=="one_direction").sum())),
        no_direct_pairs=("coverage",lambda x:int((x=="no_ordered_direct_in_snapshot").sum()))
    )
    rows=[]
    for a in chosen.itertuples():
        record=head[head.route==a.route]
        assert len(record)==1
        h=record.iloc[0]
        d=route_status.loc[a.route] if a.route in route_status.index else None
        has_static=bool(d is not None and d.cached_pairs>0)
        has_return=bool(d is not None and d.bidirectional_pairs>0)
        old_remainder=int(a.fleet)-int(a.low_before)
        assert old_remainder>=int(a.added)
        assert a.route not in exception_names
        rows.append({
            "route":a.route,"proposed_replacements":int(a.added),
            "2025_fleet":int(a.fleet),"2025_lowfloor":int(a.low_before),
            "2025_highfloor_remaining":old_remainder,
            "official_2026_exception_screen":"not_in_25_exception_list",
            "nominal_2026_route_headway_available":bool(h.headway_matched),
            "2026_nominal_weekday_headway_min":float(h.nominal_weekday_headway_min)
                if bool(h.headway_matched) else None,
            "archived_route_order_available":has_static,
            "some_pairs_bidirectional_order_valid":has_return,
            "cached_pairs_tested":int(d.cached_pairs) if d is not None else 0,
            "cached_bidirectional_pairs":int(d.bidirectional_pairs) if d is not None else 0,
            "bus_vehicle_level_age_or_decommission_verified":False,
            "bus_vehicle_level_lowfloor_departures_verified":False,
            "depot_or_charging_capacity_verified":False,
            "accessible_pedestrian_access_verified":False,
            "actual_unit_cost_or_maintenance_cost_verified":False,
            "real_patient_boarding_or_benefit_verified":False,
            "operational_decision":"hold_for_field_verification"
        })
    return pd.DataFrame(rows)


def main():
    out=ROOT/"results"
    allocations=pd.read_csv(out/"cap_allocations.csv",dtype={"route":str})
    headways=pd.read_csv(out/"headway_matched_routes.csv",dtype={"route":str})
    directional=pd.read_csv(out/"v4_directional_pairs.csv",dtype={"route":str})
    banned=set(json.loads((ROOT/"raw/exception_routes_2026.json").read_text(
        encoding="utf-8"))["routes"])
    table=compile_gates(allocations,headways,directional,banned)
    table.to_csv(out/"v4_implementation_gates.csv",index=False,encoding="utf-8-sig")
    assert len(table)==15 and table.proposed_replacements.sum()==50
    columns=["bus_vehicle_level_age_or_decommission_verified",
             "bus_vehicle_level_lowfloor_departures_verified",
             "depot_or_charging_capacity_verified",
             "accessible_pedestrian_access_verified",
             "actual_unit_cost_or_maintenance_cost_verified",
             "real_patient_boarding_or_benefit_verified"]
    summary={
        "allocated_routes":int(len(table)),
        "hypothetical_replacements":int(table.proposed_replacements.sum()),
        "published_nominal_headway_routes":int(table.nominal_2026_route_headway_available.sum()),
        "snapshot_route_order_routes":int(table.archived_route_order_available.sum()),
        "at_least_one_bidirectional_example_routes":int(table.some_pairs_bidirectional_order_valid.sum()),
        "implementation_gates_met":{k:int(table[k].sum()) for k in columns},
        "field_verified_operational_approvals":0,
        "approved_replacement_decisions":0,
        "explanation":"2025 high-floor remainder and 2026 route nominal interval are not vehicle-by-vehicle replacement eligibility.",
        "exception_scope":"Only excludes IDs/names published in the archived 25-route 2026 exception dataset; not complete approval",
        "gate_state":"All 15 policy candidates stay preliminary and unapproved until real operational/cost/accessibility evidence is available."
    }
    (out/"v4_implementation_metadata.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
