"""V11 fixed-source medical 800m GIS audit (2025 stop/GH coordinates, 2026 boarding).

Standalone: python medical/v11_23route_gis.py --may26 <Seoul_2026_May_CP949.csv>
With no --may26, only verifies the static GIS stop cohort (no passenger results).
Not evidence of wheelchair access or medical-purpose trips.
"""
import argparse,csv,math,json
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
EXPECTED={"343":6,"662":24,"674":20,"1124":6,"1135":17,"1213":20,
"1222":17,"2014":21,"2312":46,"3212":23,"3319":18,"3323":16,"3413":32,
"4211":36,"5413":29,"5611":15,"5634":32,"6411":51,"6515":39,
"6620":20,"6629":37,"6648":17,"7211":26}
def rows(path,encoding="utf-8-sig"):
    with Path(path).open(encoding=encoding,newline="") as f:
        yield from csv.DictReader(f)
def distance(a,b,x,y):
    p=math.pi/180
    q=math.sin((y-b)*p/2)**2+math.cos(b*p)*math.cos(y*p)*math.sin((x-a)*p/2)**2
    return 12742000*math.asin(min(1,math.sqrt(q)))
def static_cohort():
    hs=[(float(h["lon"]),float(h["lat"])) for h in rows(ROOT/"data/hospitals.csv")
        if h["kind"]=="종합병원" and h["approval_date"] and h["approval_date"]<="2025-05-31"
        and h["lon"] and h["lat"] and 125<float(h["lon"])<129 and 36<float(h["lat"])<39]
    if len(hs)!=59:raise ValueError("Hospital source cohort changed")
    locations={};association=defaultdict(set)
    for s in rows(ROOT/"data/route_stops.csv"):
        if s["route"] not in EXPECTED:continue
        lon,lat=float(s["lon"]),float(s["lat"])
        if not(125<lon<129 and 36<lat<39):continue
        sid=s["stop_id"];r=s["route"]
        if sid in locations and distance(lon,lat,*locations[sid])>20:
            raise ValueError("Conflicting coordinates for "+sid)
        locations.setdefault(sid,(lon,lat));association[r].add(sid)
    near={sid for sid,(lon,lat) in locations.items()
          if min(distance(lon,lat,x,y) for x,y in hs)<=800}
    cohorts={r:near&association[r] for r in EXPECTED}
    actual={r:len(cohorts[r]) for r in EXPECTED}
    if actual!=EXPECTED:raise ValueError("Static cohort differs: "+repr(actual))
    return cohorts
def monthly(csv26,cohorts):
    counts=defaultdict(int);allcounts=defaultdict(int)
    for x in rows(csv26,"cp949"):
        if x["사용년월"]!="202605":raise ValueError("Not 2026 May")
        r=x["노선번호"].strip()
        if r not in cohorts:continue
        n=sum(int(x[f"{h:02d}시승차총승객수" if h==0 else f"{h}시승차총승객수"]) for h in range(24))
        allcounts[r]+=n
        if x["표준버스정류장ID"].strip() in cohorts[r]:counts[r]+=n
    previous={x["route"]:x for x in rows(ROOT/"results/historical_ridership/v3_route_spatial_evidence.csv")}
    out=[dict(route=r,near800_stop_ids=len(cohorts[r]),all_boardings=allcounts[r],
           recalculated_near800_boardings=counts[r],
           legacy_misnamed_v3_geo_linked=int(previous[r]["2026_board_geolinked"]),
           matches_legacy_misnamed=(counts[r]==int(previous[r]["2026_board_geolinked"])))
         for r in EXPECTED]
    if not all(z["matches_legacy_misnamed"] for z in out):raise AssertionError("V3 mismatch")
    return out
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--may26");a=p.parse_args()
    cohort=static_cohort()
    if a.may26:
        out=monthly(a.may26,cohort)
        print(json.dumps({"verified_routes":len(out),"sum_800m":sum(x["recalculated_near800_boardings"] for x in out),
          "data":[x for x in out]},ensure_ascii=False,indent=2))
    else:
        print(json.dumps({"static_GIS_verified_routes":len(cohort),"observed_2026_boardings":"NOT_CHECKED_WITHOUT_MAY26",
           "stop_counts":{r:len(v) for r,v in cohort.items()}},ensure_ascii=False))
