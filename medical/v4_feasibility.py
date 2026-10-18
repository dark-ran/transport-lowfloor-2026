"""V4: conditional implementation gates and scenario stresses for fixed 50-bus allocations.

Existing data only. NO external service/API calls; NO assumption that any actual
vehicle may be retired. The outputs are NOT fleet purchase permissions.

Usage from repo root:
python medical/v4_feasibility.py
"""
import argparse,csv,json,math
from pathlib import Path

P=("screened_cap_3","screened_cap_5","screened_cap_7")
GATE_FIELDS={
"vehicle_decommission_eligibility":"bus_vehicle_level_age_or_decommission_verified",
"actual_lowfloor_departures":"bus_vehicle_level_lowfloor_departures_verified",
"depot_charging_clearance":"depot_or_charging_capacity_verified",
"accessible_origin_stop_hospital_path":"accessible_pedestrian_access_verified",
"actual_unit_and_lifecycle_cost":"actual_unit_cost_or_maintenance_cost_verified",
"real_patient_boarding_benefit":"real_patient_boarding_or_benefit_verified"
}
SHARES=(.25,.5,.75,1.)
BASE=Path(__file__).resolve().parent

def read(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as file:
        return list(csv.DictReader(file))

def allocations(rows):
    a={p:{} for p in P}
    inventory={}
    for row in rows:
        p=row["policy"]
        if p not in a:continue
        route=row["route"]
        n,f,l=map(int,(row["added"],row["fleet"],row["low_before"]))
        if route in a[p] or not (0<=l<f and 1<=n<=f-l):
            raise ValueError("Invalid policy or fleet row: "+str(row))
        if route in inventory and inventory[route]!=(f,l):
            raise ValueError("Inconsistent 2025 fleet for "+route)
        inventory[route]=(f,l)
        a[p][route]=(n,f,l)
    if [len(a[p]) for p in P]!=[22,15,12] or any(sum(t[0] for t in a[p].values())!=50 for p in P):
        raise ValueError("Unexpected policies: expected 22/15/12 routes and 50 replacements each")
    return a

def scenario_capacity(remaining,share,rounding):
    if not (0<=share<=1):raise ValueError("Share must be between 0 and 1")
    x=remaining*share
    if rounding=="floor":return min(remaining,math.floor(x+1e-10))
    if rounding=="ceil":return min(remaining,math.ceil(x-1e-10))
    raise ValueError("Rounding must be floor or ceil")

def audit(a,geo_rows,archived_rows):
    geo={x["route"]:x for x in geo_rows}
    old={x["route"]:x for x in archived_rows}
    union=sorted({route for p in P for route in a[p]},key=int)
    if len(old)!=15 or len(geo)<len(union) or set(union)-set(geo):
        raise ValueError("Missing old 15-route gate or 23-route spatial evidence")
    ledger=[];checks=[]
    for route in union:
        selected=[p for p in P if route in a[p]]
        _,fleet,low=a[selected[0]][route]
        gate=old.get(route)
        if gate and (int(gate["2025_fleet"]),int(gate["2025_lowfloor"]))!=(fleet,low):
            raise ValueError("Conflicting older fleet for "+route)
        headway=bool(gate and gate["nominal_2026_route_headway_available"]=="True")
        directional=bool(gate and gate["some_pairs_bidirectional_order_valid"]=="True")
        evidence={label:("NOT_VERIFIED" if gate else "NOT_ASSESSED")
                  for label in GATE_FIELDS}
        # Current V4 is an archive; even positive archived checks do not confer purchase authority.
        if gate and any(gate[field]=="True" for field in GATE_FIELDS.values()):
            raise ValueError("Archived gate changed; refresh evidence and re-review before approval")
        row={
        "route":route,"2025_fleet":fleet,"2025_lowfloor":low,
        "2025_highfloor_nominal":fleet-low,"allocated_by_policies":len(selected),
        "policy_3_slots":a["screened_cap_3"].get(route,(0,))[0],
        "policy_5_slots":a["screened_cap_5"].get(route,(0,))[0],
        "policy_7_slots":a["screened_cap_7"].get(route,(0,))[0],
        "may2026_boardings_all_riders":int(geo[route]["2026_board"]),
        "may2026_general_hospital_500m_stop_activity_all_riders":
            int(geo[route]["general_hospital_500m_activity_2026"]),
        "historical_v4_candidate_scope":"IN_SCOPE" if gate else "NOT_IN_V4_SCOPE",
        "published_nominal_headway_archived_v4":"CONFIRMED" if headway else ("NOT_VERIFIED" if gate else "NOT_ASSESSED"),
        "directional_stop_order_archived":"SOME_PAIRS_EXAMPLE" if directional else ("NO_ARCHIVED_ROUTE_SNAPSHOT" if gate else "NOT_ASSESSED"),
        **evidence,"actual_route_go":"NO_GO_UNVERIFIED",
        "field_check_priority_class":"A_ARCHIVED_DIRECTIONAL_CASE" if directional else ("B_ALREADY_IN_OLD_V4_SCREEN" if gate else "C_EXPAND_EVIDENCE_FIRST")
        }
        ledger.append(row)
        for p in selected:
            checks.append({"policy":p,"route":route,
             "requested_hypothetical_slots":a[p][route][0],
             "historical_highfloor_remaining":fleet-low,
             "actual_eligible_verified":"False",
             "vehicle_records_to_be_checked":a[p][route][0],
             "preapproval_decision":"HOLD","reason":"NO_VEHICLE_LEVEL_EVIDENCE",
             "route_has_2026_nominal_headway_in_old_v4":str(headway),
             "route_has_partial_directional_example":str(directional)})
    summary=[]
    for p in P:
        scope=[x for x in ledger if x["policy_"+p[-1]+"_slots"]>0]
        summary.append({
         "policy":p,"route_count":len(scope),"requested_slots":50,
         "already_in_v4_15_route_evidence_scope":sum(x["historical_v4_candidate_scope"]=="IN_SCOPE" for x in scope),
         "not_in_v4_15_route_evidence_scope":sum(x["historical_v4_candidate_scope"]=="NOT_IN_V4_SCOPE" for x in scope),
         "routes_with_partial_archived_directional_example":sum(x["directional_stop_order_archived"]=="SOME_PAIRS_EXAMPLE" for x in scope),
         "routes_with_all_six_field_gates_verified":0,
         "actual_implementation_authorized_routes":0,
         "actual_implementation_authorized_vehicles":0,
         "decision":"HOLD_NO_FIELD_APPROVAL"})
    stress=[]
    for f in SHARES:
        for mode in ("floor","ceil"):
            for p in P:
                vals=[(added,scenario_capacity(fleet-low,f,mode)) for added,fleet,low in a[p].values()]
                kept=sum(min(req,cap) for req,cap in vals)
                stress.append({
                 "policy":p,"assumed_historical_highfloor_eligible_fraction":f,
                 "rounding_assumption":mode,"requested_slots":50,
                 "hypothetical_slots_within_assumed_route_capacity":kept,
                 "hypothetical_unfilled_slots_no_reallocation":50-kept,
                 "allocated_routes_with_capacity_shortfall":sum(cap<req for req,cap in vals),
                 "actual_verified_slots":0,
                 "interpretation":"PURE_CAPACITY_SENSITIVITY_NOT_OPERATIONAL_APPROVAL"})
    return ledger,checks,summary,stress

def save(path,rows):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)

def main():
    q=argparse.ArgumentParser()
    q.add_argument("--allocations",type=Path,default=BASE/"results/cap_allocations.csv")
    q.add_argument("--spatial",type=Path,default=BASE/"results/historical_ridership/v3_route_spatial_evidence.csv")
    q.add_argument("--old-gates",type=Path,default=BASE/"results/v4_implementation_gates.csv")
    q.add_argument("--output",type=Path,default=BASE/"results/operational_v4")
    args=q.parse_args()
    rows=audit(allocations(read(args.allocations)),read(args.spatial),read(args.old_gates))
    args.output.mkdir(parents=True,exist_ok=True)
    for name,part in zip(("v4_route_gate_ledger.csv","v4_policy_candidate_checks.csv",
                          "v4_policy_readiness_summary.csv","v4_historical_eligibility_stress.csv"),rows):
        save(args.output/name,part)
    summary=rows[2]
    stress=rows[3]
    assert [x["route_count"] for x in summary]==[22,15,12]
    assert [x["not_in_v4_15_route_evidence_scope"] for x in summary]==[8,0,1]
    assert [x["hypothetical_slots_within_assumed_route_capacity"] for x in stress
            if x["assumed_historical_highfloor_eligible_fraction"]==.5
            and x["rounding_assumption"]=="floor"]==[31,22,23]
    print(json.dumps({"result":"PASS_HYPOTHETICAL_ONLY","summary":summary,
      "stress_rows":len(stress)},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
