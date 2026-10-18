"""V8 audit: test how ambiguous stop-name variants affect 3/5/7-cap model scores.

Usage:
 python medical/v8_alias_audit.py --may-2025 2025_may.csv --may-2026 2026_may.csv
Both CSVs are the official Seoul OA-12913 monthly files, encoded CP949.
A name collision is *not* proof of duplicated passengers. No patient/low-floor claims.
"""
from pathlib import Path
from collections import defaultdict
import argparse,csv,json,re

POLICIES=("screened_cap_3","screened_cap_5","screened_cap_7")
CASES={
 "343":[("병원행 하차","122000286",52),("귀가행 승차","122000288",19)],
 "662":[("병원행 하차","114000258",55),("귀가행 승차","114000221",18)],
 "3413":[("병원행 하차","124000150",88),("귀가행 승차","124000078",13)]
}
def allocations(path):
    a={p:{} for p in POLICIES}
    with open(path,encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            p=row["policy"];r=row["route"]
            if p in a:a[p][r]=(int(row["added"]),int(row["fleet"]))
    if [len(a[p]) for p in POLICIES]!=[22,15,12] or any(sum(x for x,y in a[p].values())!=50 for p in POLICIES):
        raise ValueError("Expected fixed historical 22/15/12 routes and 50 slots each")
    return a
def read_month(path,year,routes):
    result=defaultdict(list)
    with open(path,encoding="cp949",newline="") as f:
        rows=csv.DictReader(f)
        boardcols=[x for x in rows.fieldnames if x.endswith("시승차총승객수")]
        alightcols=[x for x in rows.fieldnames if x.endswith("시하차총승객수")]
        if len(boardcols)!=24 or len(alightcols)!=24:raise ValueError("24 hourly columns required")
        for x in rows:
            if x["사용년월"]!=str(year)+"05":raise ValueError("Wrong month")
            r=x["노선번호"].strip()
            if r not in routes:continue
            raw=x["역명"]
            m=re.search(r"\((\d{4,6})\)\s*$",raw)
            key=(r,x["표준버스정류장ID"].strip(),int(m.group(1)) if m else -1)
            b=sum(int(x[t]) for t in boardcols);a=sum(int(x[t]) for t in alightcols)
            if b<0 or a<0:raise ValueError("Negative board or alight")
            result[key].append((raw,b,a))
    return result
def analyze(rows,routes):
    byroute={r:dict(all=0,max_variant=0,min_variant=0,alias_groups=0,alias_boardings=0) for r in routes}
    aliases=[]
    for (r,sid,seq),vals in rows.items():
        v=byroute[r];total=sum(x[1] for x in vals);names={x[0] for x in vals}
        collision=len(vals)>1 and len(names)>1
        v["all"]+=total
        v["max_variant"]+=max(x[1] for x in vals) if collision else total
        v["min_variant"]+=min(x[1] for x in vals) if collision else total
        if collision:
            v["alias_groups"]+=1;v["alias_boardings"]+=total
            aliases.append(dict(route=r,stop_id=sid,seq=seq,rows=len(vals),
                                names=" | ".join(sorted(names)),boardings_all=total,
                                boardings_max_variant=max(x[1] for x in vals),
                                boardings_min_variant=min(x[1] for x in vals)))
    return byroute,aliases
def policy_sensitivity(policy,route_metrics):
    table=[]
    for mode in ("all","max_variant","min_variant"):
        denominator=sum(x[mode] for x in route_metrics.values())
        for p in POLICIES:
            score=100*sum(route_metrics[r][mode]*n/fleet for r,(n,fleet) in policy[p].items())/denominator
            table.append(dict(policy=p,scenario=mode,denominator=denominator,
                              demand_weighted_stock_ratio_change_pp=round(score,6)))
    return table
def case_stop_checks(month):
    result=[]
    for route,selected in CASES.items():
        for role,sid,seq in selected:
            rows=month.get((route,sid,seq),[])
            if not rows:raise ValueError("Missing example "+str((route,sid,seq)))
            result.append(dict(route=route,role=role,stop_id=sid,seq=seq,
                               name_variants=len({x[0] for x in rows}),
                               source_rows=len(rows),
                               boardings_all=sum(x[1] for x in rows),
                               alightings_all=sum(x[2] for x in rows)))
    return result
def csv_save(p,rows):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)
def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--may-2025",type=Path,required=True)
    arg.add_argument("--may-2026",type=Path,required=True)
    arg.add_argument("--allocation",type=Path,default=Path(__file__).resolve().parent/"results/cap_allocations.csv")
    arg.add_argument("--out",type=Path,default=Path(__file__).resolve().parent/"results/v8")
    args=arg.parse_args()
    p=allocations(args.allocation)
    routes=set().union(*(a.keys() for a in p.values()))
    history={}
    for year,path in ((2025,args.may_2025),(2026,args.may_2026)):
        groups=read_month(path,year,routes)
        route_metrics,aliases=analyze(groups,routes)
        history[year]=(route_metrics,aliases,case_stop_checks(groups))
    if sum(x["all"] for x in history[2025][0].values())!=6037402:raise ValueError("2025 source mismatch")
    if sum(x["all"] for x in history[2026][0].values())!=6282466:raise ValueError("2026 source mismatch")
    output=policy_sensitivity(p,history[2026][0])
    args.out.mkdir(parents=True,exist_ok=True)
    csv_save(args.out/"v8_policy_alias_sensitivity.csv",output)
    csv_save(args.out/"v8_alias_group_details_2026.csv",history[2026][1])
    csv_save(args.out/"v8_example_stops_2026.csv",history[2026][2])
    summary=dict(status="REPRODUCED_HISTORICAL_MONTHLY_COUNTS_NOT_PASSENGER_LEVEL_EFFECT",
                 alias_groups={str(k):len(v[1]) for k,v in history.items()},
                 affected_boardings={str(k):sum(y["alias_boardings"] for y in v[0].values()) for k,v in history.items()},
                 score_table=output,limitations=[
                 "Multi-name stop rows may represent changes or genuine separate records; do not call them duplicate riders",
                 "Stop-level alightings are not medically motivated journeys or actual low-floor usage",
                 "The variant min/max values are hypothetical quality stress tests, not corrected official totals"])
    (args.out/"v8_audit_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
