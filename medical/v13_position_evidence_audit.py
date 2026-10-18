"""V13 audit REAL Seoul bus-position API snapshots already archived on GitHub.

Run: python medical/v13_position_evidence_audit.py
Input: observations/vehicle_timeseries.csv (public route-level aggregate)
These vehicle-type counts may repeat the same buses and DO NOT confirm
stop arrivals, wheelchair boarding, actual headway, or treatment effects.
"""
import csv,datetime as dt,hashlib,json
from collections import defaultdict
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
P=BASE/"observations/vehicle_timeseries.csv"
V13_BASELINE_BLOB="35e3e388795a407c7a1ea35ca6580d653772edc5"

def blob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def audit(path=P):
    data=Path(path).read_bytes()
    seen=set();byroute=defaultdict(lambda:{"polls":0,"snapshots":0,"low":0,"ordinary":0,"stale":0,"weekdays":set(),"hours":set(),"days":set()})
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            route=r["route"];t=dt.datetime.fromisoformat(r["observed_at_kst"])
            key=(route,r["observed_at_kst"],r["query_scope"],r["direction"])
            if key in seen:raise ValueError("DUPLICATED_AGGREGATE_POLL")
            seen.add(key)
            n=int(r["snapshots"]);l=int(r["low_floor_snapshots"]);o=int(r["ordinary_snapshots"]);s=int(r["stale_provider_snapshots"])
            if not(0<=l<=n and 0<=o<=n and 0<=s<=n and l+o+int(r["unknown_type_snapshots"])==n):
                raise ValueError("INCONSISTENT_POSITION_COUNTS")
            x=byroute[route]
            x["polls"]+=1;x["snapshots"]+=n;x["low"]+=l;x["ordinary"]+=o;x["stale"]+=s
            x["days"].add(t.date().isoformat());x["hours"].add(t.hour)
            if t.weekday()<5:x["weekdays"].add(t.date().isoformat())
    routes=[]
    for route,x in sorted(byroute.items(),key=lambda p:int(p[0])):
        routes.append({"route":route,"polls":x["polls"],"vehicle_position_snapshots":x["snapshots"],
          "low_floor_position_snapshots":x["low"],"ordinary_position_snapshots":x["ordinary"],
          "stale_snapshots":x["stale"],"date_count":len(x["days"]),
          "weekday_count":len(x["weekdays"]),"hour_count":len(x["hours"]),
          "evidence_gate":"HOLD_UNTIL_REPEATED_WEEKDAYS_AND_STOP_ARRIVALS"})
    totals={"polls":sum(x["polls"] for x in routes),"routes":len(routes),
      "vehicle_position_snapshots":sum(x["vehicle_position_snapshots"] for x in routes),
      "low_floor_position_snapshots":sum(x["low_floor_position_snapshots"] for x in routes),
      "ordinary_position_snapshots":sum(x["ordinary_position_snapshots"] for x in routes),
      "stale_snapshots":sum(x["stale_snapshots"] for x in routes)}
    result={"source_git_blob_sha":blob(data),"matches_V13_archival_baseline":blob(data)==V13_BASELINE_BLOB,
            "totals":totals,"per_route":routes,
            "verified_stop_arrival_time_series":None,
            "verified_wheelchair_attempt_success_rate":None,
            "causal_policy_effect":None,
            "approved_replacements":0,
            "status":"DESCRIPTIVE_ROUTE_POSITIONS_ONLY_HOLD"}
    return result

if __name__=="__main__":
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
