"""V14: derive real bus-position snapshot summaries directly from original CSV files.

No hardcoded route observations, no network calls, no person or vehicle IDs.
CSV inputs exist at repository observations/{vehicle_timeseries,vehicle_window_summary}.csv.
Git blob SHA verifies the historical source. Evidence is route-wide vehicle
position, NOT stop arrivals, wheelchair boarding, unique buses or medical trips.
"""
import csv,hashlib,json
from datetime import datetime,timedelta
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
FILES={"vehicle_timeseries.csv":"35e3e388795a407c7a1ea35ca6580d653772edc5",
       "vehicle_window_summary.csv":"533d16e06d6127bc6f1f6c018e8d3cf12b631248"}
STUDY_ROUTES={"343","662","674","1124","1135","1213","1222","2014","2312","3212","3319","3323",
"3413","4211","5413","5611","5634","6411","6515","6620","6629","6648","7211"}

def source(path,sha):
    data=path.read_bytes()
    actual=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\x00"+data).hexdigest()
    if actual!=sha:raise ValueError("Pinned historical Git source changed: "+path.name)
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def recalculate(folder=ROOT/"observations"):
    times=source(folder/"vehicle_timeseries.csv",FILES["vehicle_timeseries.csv"])
    windows=source(folder/"vehicle_window_summary.csv",FILES["vehicle_window_summary.csv"])
    data={};tot=defaultdict(int);route=defaultdict(lambda:defaultdict(int));weekdays=set();dates=set()
    for row in times:
        local=datetime.fromisoformat(row["observed_at_kst"])
        utc=datetime.fromisoformat(row["observed_at_utc"])
        if local.utcoffset()!=timedelta(hours=9) or local.astimezone(utc.tzinfo)!=utc:raise ValueError("Timestamp mismatch")
        r=row["route"];key=(local.date().isoformat(),local.hour,r,row["direction"],row["query_scope"])
        if key in data or r not in STUDY_ROUTES:raise ValueError("Duplicate or foreign route")
        n=int(row["snapshots"]);l=int(row["low_floor_snapshots"]);o=int(row["ordinary_snapshots"]);un=int(row["unknown_type_snapshots"])
        if n<0 or n!=l+o+un:raise ValueError("Type counts do not sum")
        stale=int(row["stale_provider_snapshots"])
        if int(row["fresh_low_floor_snapshots"])+int(row["fresh_ordinary_snapshots"])+int(row["fresh_unknown_type_snapshots"])+stale+int(row["unknown_time_snapshots"])+int(row["future_time_snapshots"])!=n:
            raise ValueError("Freshness counts do not sum")
        data[key]=row
        for k,v in (("polls",1),("snapshots",n),("low_floor_snapshots",l),("ordinary_snapshots",o),("stale_provider_snapshots",stale)):
            tot[k]+=v;route[r][k]+=v
        dates.add(local.date().isoformat())
        if local.weekday()<5:weekdays.add(local.date().isoformat())
    found=set()
    for w in windows:
        key=(w["date_kst"],int(w["hour_kst"]),w["route"],w["direction"],w["query_scope"])
        if key in found or key not in data:raise ValueError("Missing or duplicated original window")
        src=data[key]
        for k in ("snapshots","low_floor_snapshots","ordinary_snapshots","stale_provider_snapshots"):
            if int(w[k])!=int(src[k]):raise ValueError("Window/source mismatch: "+k)
        found.add(key)
    if found!=set(data):raise ValueError("Source/window coverage mismatch")
    return {"original_position_rows":len(times),"original_window_rows":len(windows),
            "observed_routes":len(route),"study_routes":len(STUDY_ROUTES),
            "unobserved_routes":sorted(STUDY_ROUTES-set(route),key=int),
            "weekday_days":len(weekdays),"calendar_days":len(dates),
            "three_polls_per_window_met":sum(int(w["successful_polls"])>=3 for w in windows),
            "totals":dict(tot),
            "route_summary":{k:dict(v) for k,v in sorted(route.items(),key=lambda z:int(z[0]))},
            "real_stop_arrival_times":None,"wheelchair_boarding_success_rate":None,
            "causal_policy_effect":None,"policy_status":"HOLD_DESCRIPTIVE_POSITION_SNAPSHOTS_ONLY"}
if __name__=="__main__":print(json.dumps(recalculate(),ensure_ascii=False,indent=2))
