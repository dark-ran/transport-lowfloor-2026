"""Generate descriptive KST-hour summaries from committed route snapshot counts."""
import argparse,csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

FIELDS=["date_kst","day_kind","hour_kst","route","direction","query_scope",
        "polls","successful_polls","failed_polls","snapshots",
        "low_floor_snapshots","ordinary_snapshots","unknown_type_snapshots",
        "observed_low_floor_share","mean_snapshot_vehicles_per_successful_poll"]


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
            for field in ("snapshots","low_floor_snapshots","ordinary_snapshots","unknown_type_snapshots"):
                a[field]+=int(r[field])
        else:a["failed_polls"]+=1
    out=[]
    for k,v in sorted(counts.items()):
        total=v["snapshots"];succ=v["successful_polls"]
        out.append(dict(zip(FIELDS,(*k,v["polls"],succ,v["failed_polls"],total,
           v["low_floor_snapshots"],v["ordinary_snapshots"],v["unknown_type_snapshots"],
           round(v["low_floor_snapshots"]/total,6) if total else "",
           round(total/succ,4) if succ else ""))))
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
