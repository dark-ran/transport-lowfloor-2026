"""V4 nonrepresentative directional audit of selected model-attributable pairs.

Requires only cached route-stop sequence snapshots (69 preselected routes).
Does not assert that a failed path is impossible in the actual transit network.
Unlike prior top-12-per-route pilot, scans ALL route-marginal pairs for which
the assigned route is in the cached snapshot. Checks BOTH ordered directions
independently, with endpoint distance and turning-point constraints.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from validate_cases import distances, valid_leg

ROOT=Path(__file__).resolve().parent
RADIUS_M=500.0


def direct_leg(frame, src, dst, radius=RADIUS_M):
    xy=frame[["posY","posX"]].to_numpy(float)
    start=distances(src,xy)
    end=distances(dst,xy)
    origins=np.flatnonzero(start <= radius)
    targets=np.flatnonzero(end <= radius)
    valid=[(int(i),int(j),float(start[i]),float(end[j]))
           for i in origins for j in targets if valid_leg(frame,int(i),int(j))]
    if not valid:
        return None
    i,j,aa,bb=min(valid,key=lambda z:(z[1]-z[0],z[2]+z[3],z[0],z[1]))
    return {"board":str(frame.stnName.iloc[i]),"alight":str(frame.stnName.iloc[j]),
            "board_seq":int(frame.stationOrd.iloc[i]),"alight_seq":int(frame.stationOrd.iloc[j]),
            "board_ars":str(frame.arsId.iloc[i]),"alight_ars":str(frame.arsId.iloc[j]),
            "start_straight_m":aa,"end_straight_m":bb,
            "route_id":str(frame.routeId.iloc[i])}


def find_legs(frames,src,dst):
    found=[direct_leg(frame,src,dst) for frame in frames]
    found=[r for r in found if r]
    return min(found,key=lambda r:(r["alight_seq"]-r["board_seq"],
                                  r["start_straight_m"]+r["end_straight_m"],
                                  r["route_id"])) if found else None


def analyze(origins,hospitals,marginal,route_snapshots):
    idx_o=origins.set_index("code")
    idx_h=hospitals.set_index("hospital_id")
    rows=[]
    for pair in marginal.itertuples():
        cached=route_snapshots.get(str(pair.route))
        if not cached:
            rows.append({"route":str(pair.route),"dong_code":str(pair.dong_code),
                         "hospital_id":str(pair.hospital_id),"snapshot_route_available":False,
                         "forward_direct":None,"return_direct":None,
                         "coverage":"not_in_69_route_snapshot"})
            continue
        o=idx_o.loc[str(pair.dong_code)]
        h=idx_h.loc[str(pair.hospital_id)]
        src=[float(o.lat),float(o.lon)]
        dst=[float(h.lat),float(h.lon)]
        outward=find_legs(cached,src,dst)
        reverse=find_legs(cached,dst,src)
        rows.append({
            "route":str(pair.route),"dong_code":str(pair.dong_code),
            "dong":str(o.dong),"gu":str(o.gu),"hospital_id":str(pair.hospital_id),
            "hospital":str(pair.hospital_name),
            "snapshot_route_available":True,
            "forward_direct":bool(outward),"return_direct":bool(reverse),
            "outward_leg":json.dumps(outward,ensure_ascii=False) if outward else "",
            "return_leg":json.dumps(reverse,ensure_ascii=False) if reverse else "",
            "model_pair_index_loss_without_route":float(pair.index_loss_without_route),
            "model_population_weighted_pair_loss":float(pair.population_weighted_pair_loss),
            "coverage":"bidirectional" if outward and reverse else
                       ("one_direction" if outward or reverse else "no_ordered_direct_in_snapshot")
        })
    return pd.DataFrame(rows)


def main():
    out=ROOT/"results"
    marginal=pd.read_csv(out/"cap5_route_marginal_pairs.csv",
                         dtype={"route":str,"dong_code":str,"hospital_id":str})
    origins=pd.read_csv(ROOT/"data/origins.csv",dtype={"code":str})
    hospitals=pd.read_csv(ROOT/"data/hospitals.csv",dtype={"hospital_id":str})
    cached={}
    raw=json.loads((ROOT/"raw/current_case_stops.json").read_text(encoding="utf-8"))
    for record in raw:
        frame=pd.DataFrame(record["rows"])
        if not frame.empty:
            frame=frame.sort_values("stationOrd").reset_index(drop=True)
            cached.setdefault(str(frame.routNm.iloc[0]),[]).append(frame)
    checked=analyze(origins,hospitals,marginal,cached)
    assert len(checked)==len(marginal)
    assert (checked.loc[checked.snapshot_route_available,"coverage"] != "not_in_69_route_snapshot").all()
    checked.to_csv(out/"v4_directional_pairs.csv",index=False,encoding="utf-8-sig")
    statuses=checked.coverage.value_counts().to_dict()
    meta={
        "model_attributable_pairs":int(len(checked)),
        "status_counts":{str(k):int(v) for k,v in statuses.items()},
        "cached_route_names":len(cached),
        "model_routes_with_snapshot":sorted(set(marginal.route)&set(cached)),
        "model_routes_missing_snapshot":sorted(set(marginal.route)-set(cached)),
        "logic":"500m straight-line endpoint radius, strictly increasing stop sequence, no crossing an annotated turning point, outbound and return independently",
        "no_direct_found_meaning":"No ordered direct leg in captured route snapshot. Transfers, walking, rail, alternative routes or later service could exist.",
        "empirical_lowfloor_departures_observed":False,
        "representative_sample":False,
        "no_live_bus_query":True
    }
    (out/"v4_directional_metadata.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
