"""Generate descriptive KST-hour summaries from committed route snapshot counts."""
import argparse,csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

FIELDS=["date_kst","day_kind","hour_kst","route","direction","query_scope",
        "polls","successful_polls","failed_polls","snapshots",
        "low_floor_snapshots","ordinary_snapshots","unknown_type_snapshots",
        "observed_low_floor_share","mean_snapshot_vehicles_per_successful_poll",
        "fresh_low_floor_snapshots","fresh_ordinary_snapshots","stale_provider_snapshots",
        "unknown_time_snapshots","future_time_snapshots","fresh_low_floor_share",
        "provider_fresh_record_share"]


def build(rows):
    counts=defaultdict(lambda:defaultdict(int))
    for r in rows:
        dt=datetime.fromisoformat(r["observed_at_kst"])
        if dt.tzinfo is None:raise ValueError("KST offset required")
        k=(dt.date().isoformat(),"weekend" if dt.weekday()>=5 else "weekday",
           f"{dt.hour:02d}",r["route"],r["direction"],r["query_scope"])
        a=counts[k];a["polls"]+=1
        if r["status"] in ("success_with_snapshots","success_empty"):
            a["successful_polls"]+=1
            for field in ("snapshots","low_floor_snapshots","ordinary_snapshots","unknown_type_snapshots",
                          "fresh_low_floor_snapshots","fresh_ordinary_snapshots","stale_provider_snapshots",
                          "unknown_time_snapshots","future_time_snapshots"):
                a[field]+=int(r.get(field) or 0)
        else:a["failed_polls"]+=1
    out=[]
    for k,v in sorted(counts.items()):
        total=v["snapshots"];succ=v["successful_polls"]
        known=v["low_floor_snapshots"]+v["ordinary_snapshots"]
        fresh=v["fresh_low_floor_snapshots"]+v["fresh_ordinary_snapshots"]
        # The displayed type share excludes unknown vehicle types.
        # Fresh share additionally excludes stale/unknown provider timestamps.
        out.append(dict(zip(FIELDS,(*k,v["polls"],succ,v["failed_polls"],total,
           v["low_floor_snapshots"],v["ordinary_snapshots"],v["unknown_type_snapshots"],
           round(v["low_floor_snapshots"]/known,6) if known else "",
           round(total/succ,4) if succ else "",
           v["fresh_low_floor_snapshots"],v["fresh_ordinary_snapshots"],
           v["stale_provider_snapshots"],v["unknown_time_snapshots"],v["future_time_snapshots"],
           round(v["fresh_low_floor_snapshots"]/fresh,6) if fresh else "",
           round((fresh)/total,6) if total else ""))))
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    with a.input.open(encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    groups=build(rows)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(groups)
    print("KST route-hour groups:",len(groups))

if __name__=="__main__":main()
