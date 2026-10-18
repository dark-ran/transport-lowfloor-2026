"""Independent, observational review of the V4 50-replacement policy candidates.

Data gates are deliberately strict. No data means HOLD, not zero service.
Only scheduled whole-route polls with fresh provider times are admissible.
Unit = equal-weight valid polls -> KST window -> KST weekday -> route.
This does not re-optimize or validate the original allocation.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
from datetime import datetime
import json
from pathlib import Path

HOURS_WEEKDAY=(8,10,14,17)
MIN_VALID_POLLS_PER_WINDOW=3
MIN_FRESH_SHARE=0.80
MIN_WINDOWS_PER_DAY=2
MIN_WEEKDAYS=7
MIN_DISTINCT_HOURS=3
REVIEW_GAP_THRESHOLD=0.10

FIELDS=("route","proposed_replacements","static_2025_lowfloor_share",
        "scheduled_polls","successful_polls","fresh_known_polls",
        "provider_fresh_share","valid_windows","valid_weekdays",
        "covered_kst_hours","observed_weekday_lowfloor_share",
        "min_day_lowfloor_share","max_day_lowfloor_share",
        "observed_minus_static_percentage_points","evidence_status",
        "policy_review_signal")


def _parse_float(row,key):
    try:return float(row[key])
    except (KeyError,ValueError,TypeError):raise ValueError(f"Invalid {key}")


def _parse_int(row,key):
    try:
        value=int(row[key])
        if value<0:raise ValueError
        return value
    except (KeyError,ValueError,TypeError):raise ValueError(f"Invalid {key}")


def read_csv(path):
    path=Path(path)
    if not path.is_file():return []
    with path.open(encoding="utf-8-sig",newline="") as file:
        return list(csv.DictReader(file))


def review(gates,observations):
    selected={str(g["route"]):g for g in gates}
    if len(selected)!=15:raise ValueError("Expected 15 model-selected routes")
    windows=defaultdict(list)
    route_stats=defaultdict(lambda:defaultdict(int))
    for row in observations:
        route=str(row.get("route",""))
        if route not in selected or row.get("event")!="schedule" or row.get("query_scope")!="full" or row.get("direction")!="route_all":
            continue
        when=datetime.fromisoformat(row["observed_at_kst"].replace("Z","+00:00"))
        if when.tzinfo is None or when.utcoffset().total_seconds()!=9*3600:
            raise ValueError("Observations need explicitly zoned Asia/Seoul local timestamps")
        if when.weekday()>=5 or when.hour not in HOURS_WEEKDAY:continue
        key=(route,when.date().isoformat(),when.hour)
        stats=route_stats[route]
        stats["scheduled_polls"]+=1
        if row["status"] not in ("success_with_snapshots","success_empty"):
            continue
        stats["successful_polls"]+=1
        types=[_parse_int(row,k) for k in ("low_floor_snapshots","ordinary_snapshots","unknown_type_snapshots")]
        if sum(types)!=_parse_int(row,"snapshots"):raise ValueError("Provider vehicle counts do not match snapshots")
        fresh_low=_parse_int(row,"fresh_low_floor_snapshots") if row.get("fresh_low_floor_snapshots") not in (None,"") else 0
        fresh_ordinary=_parse_int(row,"fresh_ordinary_snapshots") if row.get("fresh_ordinary_snapshots") not in (None,"") else 0
        if fresh_low+fresh_ordinary>sum(types):raise ValueError("Fresh vehicle count exceeds total")
        if fresh_low+fresh_ordinary>0:
            stats["fresh_known_polls"]+=1
            windows[key].append((fresh_low/(fresh_low+fresh_ordinary),sum(types),fresh_low+fresh_ordinary))
        else:
            windows[key].append((None,sum(types),0))

    result=[]
    for route,g in sorted(selected.items()):
        fleet=_parse_int(g,"2025_fleet")
        low=_parse_int(g,"2025_lowfloor")
        if fleet<=0 or low>fleet:raise ValueError("Invalid 2025 baseline fleet")
        static=low/fleet
        stats=route_stats[route]
        valid_days=defaultdict(list)
        all_windows=0
        all_fresh=0;all_rows=0
        for (r,date,hour),items in windows.items():
            if r!=route:continue
            all_rows+=sum(x[1] for x in items)
            all_fresh+=sum(x[2] for x in items)
            valid=[x[0] for x in items if x[0] is not None]
            freshness=sum(x[2] for x in items)/max(1,sum(x[1] for x in items))
            if len(valid)<MIN_VALID_POLLS_PER_WINDOW or freshness<MIN_FRESH_SHARE:
                continue
            all_windows+=1
            valid_days[date].append((hour,sum(valid)/len(valid)))
        qualified={day:values for day,values in valid_days.items()
                   if len({x[0] for x in values})>=MIN_WINDOWS_PER_DAY}
        covered=sorted({h for values in qualified.values() for h,_ in values})
        ready=len(qualified)>=MIN_WEEKDAYS and len(covered)>=MIN_DISTINCT_HOURS
        day_means=[sum(v for _,v in vals)/len(vals) for _,vals in qualified.items()]
        observed=sum(day_means)/len(day_means) if ready else None
        gap=(observed-static)*100 if observed is not None else None
        status="READY_DESCRIPTIVE_ONLY" if ready else "HOLD_INSUFFICIENT_REPEATED_EVIDENCE"
        if not ready:signal="NO_POLICY_CHANGE_OR_RERANKING"
        elif observed < static-REVIEW_GAP_THRESHOLD:signal="REVIEW_LOWER_OBSERVED_SHARE"
        elif observed > static+REVIEW_GAP_THRESHOLD:signal="REVIEW_HIGHER_OBSERVED_SHARE"
        else:signal="NO_LARGE_DESCRIPTIVE_DISCREPANCY"
        result.append({
            "route":route,
            "proposed_replacements":_parse_int(g,"proposed_replacements"),
            "static_2025_lowfloor_share":round(static,6),
            "scheduled_polls":stats["scheduled_polls"],
            "successful_polls":stats["successful_polls"],
            "fresh_known_polls":stats["fresh_known_polls"],
            "provider_fresh_share":round(all_fresh/all_rows,6) if all_rows else None,
            "valid_windows":all_windows,
            "valid_weekdays":len(qualified),
            "covered_kst_hours":",".join(map(str,covered)),
            "observed_weekday_lowfloor_share":round(observed,6) if observed is not None else None,
            "min_day_lowfloor_share":round(min(day_means),6) if ready else None,
            "max_day_lowfloor_share":round(max(day_means),6) if ready else None,
            "observed_minus_static_percentage_points":round(gap,2) if gap is not None else None,
            "evidence_status":status,"policy_review_signal":signal
        })
    return result


def save(gates_path,observations_path,output_csv,output_json):
    rows=review(read_csv(gates_path),read_csv(observations_path))
    output_csv=Path(output_csv);output_csv.parent.mkdir(parents=True,exist_ok=True)
    with output_csv.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    ready=sum(x["evidence_status"]=="READY_DESCRIPTIVE_ONLY" for x in rows)
    summary={
       "status":"DESCRIPTIVE_REVIEW_AVAILABLE" if ready else "HOLD_NO_SUFFICIENT_OBSERVATION",
       "route_count":len(rows),"descriptive_evidence_ready_routes":ready,
       "current_fleet_replacement_decision":"HOLD_ALL_15_UNTIL_FIELD_VERIFICATION",
       "existing_50_bus_allocation":"UNCHANGED_STATIC_HYPOTHESIS",
       "thresholds":{"min_weekdays":MIN_WEEKDAYS,"min_kst_hours":MIN_DISTINCT_HOURS,
                     "min_valid_polls_per_window":MIN_VALID_POLLS_PER_WINDOW,
                     "min_windows_per_day":MIN_WINDOWS_PER_DAY,
                     "minimum_fresh_fraction_per_window":MIN_FRESH_SHARE},
       "observation_weighting":"Equal valid polls within eligible windows; equal windows within weekday; equal weekdays within route",
       "limitations":[
           "Position snapshot composition is NOT departure or boarding frequency.",
           "No causal effect, true headway, individual waiting time or accessibility measurement.",
           "2025 authorized fleet share and 2026 observed active-vehicle composition have different denominators and reference periods.",
           "No allocation is automatically recalculated from preliminary descriptive gaps.",
           "Missing, stale, unknown-time, zero-vehicle and unscheduled observations do not establish zero bus service.",
           "Repeated vehicles and serial route collection reduce independence and simultaneous comparability.",
           "7 weekdays and coverage gates are research screening conventions, not statistical confidence intervals."
       ],
       "route_evidence":rows,
    }
    Path(output_json).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--gates",type=Path,required=True)
    p.add_argument("--observations",type=Path,required=True)
    p.add_argument("--output-csv",type=Path,required=True)
    p.add_argument("--output-json",type=Path,required=True)
    a=p.parse_args()
    s=save(a.gates,a.observations,a.output_csv,a.output_json)
    print(json.dumps({"status":s["status"],"ready_routes":s["descriptive_evidence_ready_routes"],
                      "routes":s["route_count"]},ensure_ascii=False))

if __name__=="__main__":main()
