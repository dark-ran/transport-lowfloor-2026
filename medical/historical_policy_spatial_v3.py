"""V3: general-hospital spatial demand and policy-choice sensitivity audit.

Run with two original Seoul monthly CP949 CSVs (2025-05 and 2026-05).
The source route stops and licensed hospitals already exist under medical/data/.
This evaluates *fixed* 50-bus policies, not actual low-floor boarding effects.
"""
import argparse
import csv
from collections import Counter, defaultdict
from math import asin,cos,radians,sin,sqrt
import json
from pathlib import Path

try:
    import historical_policy_demand as previous
except ModuleNotFoundError:
    from medical import historical_policy_demand as previous

POLICIES=previous.POLICIES
RADII=(300,500,800)


def csv_records(path,encoding="utf-8-sig"):
    with Path(path).open(encoding=encoding,newline="") as f:
        yield from csv.DictReader(f)


def haversine_m(a,b,c,d):
    a,b,c,d=map(radians,(a,b,c,d))
    u=sin((d-b)/2)**2+cos(b)*cos(d)*sin((c-a)/2)**2
    return 12742000*asin(min(1,sqrt(u)))


def proximity(stop_file,hospital_file,universe):
    hospitals=[]
    for h in csv_records(hospital_file):
        if h["kind"]!="종합병원" or not h["approval_date"] or h["approval_date"]>"2025-05-31":
            continue
        try:
            lon,lat=float(h["lon"]),float(h["lat"])
        except (TypeError,ValueError):
            continue
        if 125<lon<129 and 36<lat<39:
            hospitals.append((h["name"],lon,lat))
    if not hospitals:raise ValueError("No eligible general-hospital coordinates")
    point={};route_stops=defaultdict(set);conflicts=set()
    for s in csv_records(stop_file):
        route=s["route"].strip();sid=s["stop_id"].strip()
        if route not in universe or not sid:continue
        try:lon,lat=float(s["lon"]),float(s["lat"])
        except (ValueError,TypeError):continue
        if not(125<lon<129 and 36<lat<39):continue
        route_stops[route].add(sid)
        if sid in point and haversine_m(lon,lat,*point[sid])>20:conflicts.add(sid)
        point.setdefault(sid,(lon,lat))
    if not point:raise ValueError("No mapped route stops")
    near={}
    for sid,(lon,lat) in point.items():
        distance,name=min((haversine_m(lon,lat,x,y),name) for name,x,y in hospitals)
        near[sid]=(distance,name)
    audit=dict(hospitals=len(hospitals),static_route_stops=len(point),
               stop_count_within_radius={str(r):sum(x[0]<=r for x in near.values()) for r in RADII},
               duplicate_stop_coordinate_conflicts=sorted(conflicts))
    return near,route_stops,audit


def observed_near_stops(may26,universe,near,route_stops):
    cols_b=[f"{h:02d}시승차총승객수" if h==0 else f"{h}시승차총승객수" for h in range(24)]
    cols_a=[f"{h:02d}시하차총승객수" if h==0 else f"{h}시하차총승객수" for h in range(24)]
    route={r:{radius:dict(activity=0,mid_activity=0) for radius in RADII} for r in universe}
    match=defaultdict(int);hospital_activity=Counter();named_activity=defaultdict(int)
    for x in csv_records(may26,"cp949"):
        if x["사용년월"]!="202605":raise ValueError("Only 2026 May is valid")
        r=x["노선번호"].strip();sid=x["표준버스정류장ID"].strip()
        if r not in universe:continue
        b=[int(x[k]) for k in cols_b];a=[int(x[k]) for k in cols_a]
        if "병원" in x["역명"] and "동물병원" not in x["역명"]:
            named_activity[r]+=sum(b)+sum(a)
        if sid not in route_stops.get(r,set()) or sid not in near:continue
        if min(b+a)<0:raise ValueError("Negative count")
        match[r]+=sum(b)
        dist,hname=near[sid]
        for radius in RADII:
            if dist<=radius:
                route[r][radius]["activity"]+=sum(b)+sum(a)
                route[r][radius]["mid_activity"]+=sum(b[10:17])+sum(a[10:17])
        if dist<=500:hospital_activity[hname]+=sum(b)+sum(a)
    return route,dict(match),hospital_activity,dict(named_activity)


def compare(policies,older,newer,geo,named_activity):
    universe=set().union(*(x.keys() for x in policies.values()))
    funcs={
        "all_board":lambda r:newer[r]["board"],
        "mid_board":lambda r:newer[r]["mid"],
        "hospital_name_activity":lambda r:named_activity.get(r,0),
    }
    for radius in RADII:
        funcs[f"hospital_{radius}m_activity"]=lambda r,radius=radius:geo[r][radius]["activity"]
        funcs[f"hospital_{radius}m_mid_activity"]=lambda r,radius=radius:geo[r][radius]["mid_activity"]
    denom={k:sum(f(r) for r in universe) for k,f in funcs.items()}
    if any(v<=0 for v in denom.values()):raise ValueError("Empty denominator in hospital-demand comparison")
    older_total=sum(older[r]["board"] for r in universe)
    summaries=[]
    for cap,p in ((3,"screened_cap_3"),(5,"screened_cap_5"),(7,"screened_cap_7")):
        values=policies[p]
        row={"policy":p,"route_cap":cap,"allocated_routes":len(values),
             "replacements":sum(v[0] for v in values.values()),"fixed_universe_boardings":denom["all_board"]}
        for name,f in funcs.items():
            row[name+"_denominator"]=denom[name]
            row[name+"_gain_pp"]=100*sum(f(r)*added/fleet for r,(added,fleet) in values.items())/denom[name]
        row["all_board_2025_gain_pp"]=100*sum(older[r]["board"]*a/f for r,(a,f) in values.items())/older_total
        summaries.append(row)
    loo=[]
    for removed in sorted(universe,key=int):
        row={"removed_route":removed}
        for metric in ("all_board","hospital_500m_activity"):
            fn=funcs[metric]
            d=denom[metric]-fn(removed)
            if d<=0:raise ValueError("Leave-one-out denominator is empty")
            scores={p:100*sum(fn(r)*a/f for r,(a,f) in policies[p].items() if r!=removed)/d for p in POLICIES}
            for p in POLICIES:row[p+"_"+metric+"_pp"]=scores[p]
            row[metric+"_winner"]=max(scores,key=scores.get)
        loo.append(row)
    return summaries,loo


def weight_screen(summaries,equity):
    metrics={
        "medical":{p:equity[p]["base_delta_index"] for p in POLICIES},
        "breadth":{p:equity[p]["changed_dongs"] for p in POLICIES},
        "general_demand":{x["policy"]:x["all_board_gain_pp"] for x in summaries},
        "hospital_500m":{x["policy"]:x["hospital_500m_activity_gain_pp"] for x in summaries}
    }
    scaled={}
    for key,raw in metrics.items():
        low,high=min(raw.values()),max(raw.values())
        scaled[key]={p:((raw[p]-low)/(high-low) if high>low else 0) for p in POLICIES}
    wins=Counter();rows=[]
    for a in range(11):
        for b in range(11-a):
            for c in range(11-a-b):
                d=10-a-b-c
                w=dict(zip(metrics,(a/10,b/10,c/10,d/10)))
                scores={p:sum(w[k]*scaled[k][p] for k in metrics) for p in POLICIES}
                best=max(scores.values());top=[p for p in POLICIES if abs(scores[p]-best)<1e-12]
                for p in top:wins[p]+=1/len(top)
                rows.append({**{"weight_"+k:v for k,v in w.items()},
                            "winners":";".join(top),
                            **{p+"_score":scores[p] for p in POLICIES}})
    return rows,{"weighting_scenarios":len(rows),"fractional_winner_counts":dict(wins),
                 "criteria":metrics,"normalization":"Min-max among only three candidate policies"}


def write_csv(path,rows):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--may-2025",type=Path,required=True)
    parser.add_argument("--may-2026",type=Path,required=True)
    folder=Path(__file__).resolve().parent
    parser.add_argument("--allocations",type=Path,default=folder/"results/cap_allocations.csv")
    parser.add_argument("--equity",type=Path,default=folder/"results/cap_equity_summary.csv")
    parser.add_argument("--route-stops",type=Path,default=folder/"data/route_stops.csv")
    parser.add_argument("--hospitals",type=Path,default=folder/"data/hospitals.csv")
    parser.add_argument("--output",type=Path,default=folder/"results/historical_ridership")
    args=parser.parse_args()
    policies=previous.allocation(args.allocations)
    universe=set().union(*(x.keys() for x in policies.values()))
    older=previous.extract(args.may_2025,2025,universe)
    newer=previous.extract(args.may_2026,2026,universe)
    near,routes,geo_audit=proximity(args.route_stops,args.hospitals,universe)
    spatial,matched,hospital_activity,named=observed_near_stops(args.may_2026,universe,near,routes)
    summaries,loo=compare(policies,older,newer,spatial,named)
    equity={x["policy"]:{"base_delta_index":float(x["base_delta_index"]),"changed_dongs":int(x["changed_dongs"])}
            for x in csv_records(args.equity) if x["policy"] in POLICIES}
    grid,weight_meta=weight_screen(summaries,equity)
    args.output.mkdir(parents=True,exist_ok=True)
    write_csv(args.output/"v3_spatial_policy_summary.csv",summaries)
    write_csv(args.output/"v3_leave_one_route_out.csv",loo)
    write_csv(args.output/"v3_objective_weight_grid.csv",grid)
    route_rows=[]
    for route in sorted(universe,key=int):
        x={"route":route,"boardings_2025":older[route]["board"],
           "boardings_2026":newer[route]["board"],"boardings_geolinked_2026":matched.get(route,0),
           "hospital_name_activity":named.get(route,0)}
        for radius in RADII:
            x[f"general_hospital_{radius}m_activity"]=spatial[route][radius]["activity"]
        route_rows.append(x)
    write_csv(args.output/"v3_route_spatial_evidence.csv",route_rows)
    result={
        "status":"COMPARED_FIXED_POLICY_SCENARIOS_NOT_ACTUAL_PASSENGER_EFFECT",
        "routes_union":len(universe),"2026_ride_records":sum(x["board"] for x in newer.values()),
        "geo_audit":geo_audit,"2026_geolinked_boarding_coverage":
            sum(matched.values())/sum(x["board"] for x in newer.values()),
        "loo_winners":{k:dict(Counter(x[k] for x in loo)) for k in ("all_board_winner","hospital_500m_activity_winner")},
        "weight_sensitivity":weight_meta,
        "limitations":["500m is straight-line distance, not accessible walking route",
          "Hospital-adjacent activity is not medical-purpose trips",
          "2025 fleet and stop geometry and 2026 May ridership mix reference periods",
          "2026 active license register does not prove each hospital was open throughout 2025",
          "Hypothetical replacements ignore actual fleet retirement, operator and cost constraints",
          "Leave-one-out drops contributions without re-allocating 50 vehicles",
          "Weight-grid preferences are not elicited from actual stakeholders"]}
    (args.output/"v3_spatial_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"summaries":summaries,"audit":result},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
