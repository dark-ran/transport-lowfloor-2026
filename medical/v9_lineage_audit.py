"""V9 source-of-truth correction for legacy V3 2026_board_geolinked.

Legacy value 4,874 for route 1124 is 800m general-hospital-adjacent
boarding; it is NOT 2025 same-route stop ID matching (55,259).

Usage: python medical/v9_lineage_audit.py --may-2026 /path/to/2026_may.csv
The 2026 CSV is separate; 2025 static GIS data are stored in medical/data/.
"""
import argparse,csv,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXPECTED_MAY26_SHA="071eca2a6a1f5e306a78b3b945c7b62fdaeb1dd6c8ad7647f92f0ca803c665dc"

def records(path,encoding="utf-8-sig"):
    with open(path,encoding=encoding,newline="") as f:yield from csv.DictReader(f)

def haversine(lon1,lat1,lon2,lat2):
    p=math.pi/180
    a=math.sin((lat2-lat1)*p/2)**2+math.cos(lat1*p)*math.cos(lat2*p)*math.sin((lon2-lon1)*p/2)**2
    return 12742000*math.asin(min(1,math.sqrt(a)))

def static_1124(route_stops,hospitals):
    ss={}
    for s in records(route_stops):
        if s["route"]=="1124":ss[s["stop_id"]]=(float(s["lon"]),float(s["lat"]))
    hh=[(h["name"],float(h["lon"]),float(h["lat"])) for h in records(hospitals)
        if h["kind"]=="종합병원" and h["approval_date"]<="2025-05-31"
        and h["approval_date"] and h["lon"] and h["lat"]]
    if len(ss)!=37 or len(hh)!=59:raise ValueError("Source inventories changed; review before comparison")
    nearest={}
    for sid,(lon,lat) in ss.items():
        d,name=min((haversine(lon,lat,x,y),name) for name,x,y in hh)
        nearest[sid]={"nearest_hospital":name,"distance_m":d}
    return nearest

def summarize(may2026,stop_data):
    total=matched=near800=0;detail=[]
    with open(may2026,encoding="cp949",newline="") as f:
        reader=csv.DictReader(f)
        cols=[c for c in reader.fieldnames if c.endswith("시승차총승객수")]
        if len(cols)!=24:raise ValueError("Incorrect month schema")
        for row in reader:
            if row["노선번호"].strip()!="1124":continue
            if row["사용년월"]!="202605":raise ValueError("Wrong date")
            n=sum(int(row[c]) for c in cols)
            sid=row["표준버스정류장ID"].strip()
            total+=n
            if sid in stop_data:
                matched+=n
                if stop_data[sid]["distance_m"]<=800:
                    near800+=n
                    detail.append({"stop_id":sid,"stop_name":row["역명"],"boardings":n,
                       "nearest_hospital":stop_data[sid]["nearest_hospital"],
                       "distance_m":round(stop_data[sid]["distance_m"],4)})
    return {"route":"1124","2026_may_all_boardings":total,
       "boardings_same_route_2025_stop_id":matched,
       "boardings_at_stops_within_800m_general_hospital":near800,
       "legacy_v3_column_name":"2026_board_geolinked",
       "legacy_v3_4874_is_not_geographic_join_success":True,
       "spatial_stops":detail}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--may-2026",type=Path,required=True)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    if hashlib.sha256(args.may_2026.read_bytes()).hexdigest()!=EXPECTED_MAY26_SHA:
        raise ValueError("Official data snapshot hash differs; do not silently mix versions")
    result=summarize(args.may_2026,static_1124(ROOT/"data/route_stops.csv",ROOT/"data/hospitals.csv"))
    if (result["2026_may_all_boardings"],result["boardings_same_route_2025_stop_id"],
        result["boardings_at_stops_within_800m_general_hospital"],len(result["spatial_stops"]))!=(55579,55259,4874,6):
        raise ValueError("Expected baseline not reproduced")
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
