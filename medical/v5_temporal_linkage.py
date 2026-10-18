"""V5: distinguish route-stop ID linkage from hospital-radius activity coverage.

Run with an official 2026-05 Seoul transit-card CSV (CP949):
  python medical/v5_temporal_linkage.py --may-2026 path/to/2026.csv
Uses already versioned medical/data/route_stops.csv; no API calls.
A matching stop ID does not certify 2026 stop name, sequence, accessible path,
or an actual low-floor vehicle arrival. NO causal or vehicle-level claim.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROUTES=("343","662","1124","3413")

def static_ids(path,routes=ROUTES):
    result={r:set() for r in routes}
    with open(path,encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            if row["route"] in result:
                result[row["route"]].add(row["stop_id"].strip())
    if any(not v for v in result.values()):
        raise ValueError("Missing route stop ID inventory")
    return result

def calculate(path,statics,routes=ROUTES):
    data={r:{"route":r,"boardings_total_2026":0,"boardings_same_route_static_id":0,"route_rows":0,
             "matched_rows":0,"static_2025_unique_ids":len(statics[r])} for r in routes}
    with open(path,encoding="cp949",newline="") as f:
        reader=csv.DictReader(f)
        boardcols=[x for x in reader.fieldnames if x.endswith("시승차총승객수")]
        if len(boardcols)!=24:
            raise ValueError("Expected 24 hour boarding count columns")
        for row in reader:
            if row["사용년월"]!="202605":raise ValueError("2026 May CSV required")
            r=row["노선번호"].strip()
            if r not in data:continue
            count=sum(int(row[x].replace(",","")) for x in boardcols)
            if count<0:raise ValueError("Negative count")
            item=data[r];item["route_rows"]+=1;item["boardings_total_2026"]+=count
            if row["표준버스정류장ID"].strip() in statics[r]:
                item["boardings_same_route_static_id"]+=count;item["matched_rows"]+=1
    for r,row in data.items():
        if not row["boardings_total_2026"]:raise ValueError("Zero boardings: "+r)
        row["share_matching_pct"]=round(100*row["boardings_same_route_static_id"]/row["boardings_total_2026"],4)
        row["interpretation"]="SAME_ROUTE_STOP_ID_LINKAGE_NOT_HOSPITAL_800M_COVERAGE"
    return list(data.values())

def main():
    q=argparse.ArgumentParser()
    q.add_argument("--may-2026",required=True,type=Path)
    q.add_argument("--route-stops",type=Path,default=Path(__file__).resolve().parent/"data/route_stops.csv")
    q.add_argument("--output",type=Path)
    args=q.parse_args()
    result=calculate(args.may_2026,static_ids(args.route_stops))
    expected={"343":(222862,222862),"662":(215162,215042),"1124":(55579,55259),"3413":(574339,574339)}
    for row in result:
        if (row["boardings_total_2026"],row["boardings_same_route_static_id"])!=expected[row["route"]]:
            raise ValueError("Historical input/source revision differs for "+row["route"])
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
    print(json.dumps({"status":"PASS_HISTORICAL_LINKAGE_ONLY","rows":result},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
