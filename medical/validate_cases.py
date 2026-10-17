"""Ordered route examples for three screened origins; not a time-dependent router."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent
EARTH=6371008.8

def distances(p,xy):
 a=np.radians(np.asarray(p,float));b=np.radians(np.asarray(xy,float));dy=a[0]-b[:,0];dx=a[1]-b[:,1]
 return EARTH*2*np.arcsin(np.minimum(1,np.sqrt(np.sin(dy/2)**2+np.cos(a[0])*np.cos(b[:,0])*np.sin(dx/2)**2)))

def valid_leg(a,i,j):
 # Do not imply through-running over an announced turning point or wrap the list.
 return i<j and not a.iloc[i+1:j].turnPlaceStationYn.eq('Y').any()

def leg(a,i,j):
 return {'route':str(a.routNm.iloc[0]),'route_id':str(a.routeId.iloc[0]),'board':str(a.stnName.iloc[i]),'board_ars':str(a.arsId.iloc[i]),'board_seq':int(a.stationOrd.iloc[i]),'alight':str(a.stnName.iloc[j]),'alight_ars':str(a.arsId.iloc[j]),'alight_seq':int(a.stationOrd.iloc[j]),'stop_intervals':int(j-i),'route_length_m':int(a.iloc[i+1:j+1].guganLen.sum())}

def candidates(routes,start,end,radius=500):
 info=[]
 for a in routes:
  xy=a[['posY','posX']].to_numpy();info.append((a,distances(start,xy),distances(end,xy)))
 direct=[];transfer=[]
 for a,do,dh in info:
  for i in np.where(do<=radius)[0]:
   for j in np.where(dh<=radius)[0]:
    if valid_leg(a,i,j):direct.append({'transfers':0,'origin_straight_m':float(do[i]),'destination_straight_m':float(dh[j]),'legs':[leg(a,i,j)]})
 first={};second={}
 for a,do,dh in info:
  for i in np.where(do<=radius)[0]:
   for k in range(i+1,len(a)):
    if not valid_leg(a,i,k):break
    first.setdefault(str(a.stationId.iloc[k]),[]).append((a,i,k,float(do[i])))
  for j in np.where(dh<=radius)[0]:
   for l in range(j-1,-1,-1):
    if not valid_leg(a,l,j):break
    second.setdefault(str(a.stationId.iloc[l]),[]).append((a,l,j,float(dh[j])))
 for sid in sorted(first.keys()&second.keys()):
  for a,i,k,walk1 in first[sid]:
   for b,l,j,walk2 in second[sid]:
    if a.routeId.iloc[0]==b.routeId.iloc[0]:continue
    transfer.append({'transfers':1,'origin_straight_m':walk1,'destination_straight_m':walk2,'transfer_platform':sid,'legs':[leg(a,i,k),leg(b,l,j)]})
 def key(x):return (sum(y['route_length_m'] for y in x['legs']),x['origin_straight_m']+x['destination_straight_m'],str(x))
 return sorted(direct,key=key),sorted(transfer,key=key)

def main():
 raw=ROOT/'raw';out=ROOT/'results';o=pd.read_csv(ROOT/'data/origins.csv');h=pd.read_csv(ROOT/'data/hospitals.csv');p=pd.read_csv(out/'origin_hospital_pairs.csv')
 routes=[pd.DataFrame(x['rows']).sort_values('stationOrd').reset_index(drop=True) for x in json.loads((raw/'current_case_stops.json').read_text(encoding='utf-8'))]
 meta=pd.read_csv(raw/'노선정보_20261017.csv',dtype=str).fillna('').map(lambda x:x.replace('\ufeff','').strip());meta.columns=[x.replace('\ufeff','') for x in meta.columns]
 live={x['routId']:x for x in json.loads((raw/'topis_case_metadata.json').read_text(encoding='utf-8'))}
 fleets=pd.read_csv(ROOT/'data/fleets.csv',dtype={'route':str}).set_index('route');results=[];rows=[]
 for dong in ['오류2동','오금동','내곡동']:
  z=o[o.dong==dong].iloc[0];hid=p[p.dong_code==z.code].sort_values('rank').iloc[0].hospital_id;v=h[h.hospital_id==hid].iloc[0]
  for direction,start,end in [('병원행',[z.lat,z.lon],[v.lat,v.lon]),('귀가행',[v.lat,v.lon],[z.lat,z.lon])]:
   dd,tt=candidates(routes,start,end)
   # Show the shortest road-distance example among currently captured routes,
   # with 500m Euclidean endpoint filters. Not fastest/shortest network travel.
   chosen=dd[0] if dd else (tt[0] if tt else None)
   item={'dong':dong,'dong_code':int(z.code),'hospital':v['name'],'direction':direction,'captured_direct_examples':len(dd),'captured_transfer_examples':len(tt),'selected':chosen,'alternative_direct_routes':sorted(set(x['legs'][0]['route'] for x in dd))}
   if chosen:
    for q in chosen['legs']:
     mm=meta[meta['노선ID']==q['route_id']];assert len(mm)==1;mm=mm.iloc[0]
     q['weekday_headway_minutes']=mm['배차'];q['saturday_headway_minutes']=mm['배차(토요일)'];q['holiday_headway_minutes']=mm['배차(공휴일)'];assert q['route_id'] in live
     ll=live[q['route_id']]
     assert [mm['배차'],mm['배차(토요일)'],mm['배차(공휴일)']]==[ll['norTerms'],ll['satTerms'],ll['holTerms']]
     q['first_departure_at_origin']=ll['timeFirst'];q['last_departure_at_origin']=ll['timeLast']
     base=q['route']
     q['fleet_ratio_2025']=float(fleets.loc[base,'low']/fleets.loc[base,'fleet']) if base in fleets.index and not bool(fleets.loc[base,'ambiguous_family']) else None
     rows.append({'dong':dong,'hospital':v['name'],'direction':direction,'transfers':chosen['transfers'],'origin_straight_m':round(chosen['origin_straight_m'],1),'destination_straight_m':round(chosen['destination_straight_m'],1),**q})
   results.append(item)
 report={'source_date':'2026-10-17','source_route_count':len(routes),'origin_points':'2025 administrative dong projected centroid; not resident home','hospital_selection':'nearest general hospital in the original screening','endpoint_radius_m':500,'transfer_rule':'same stationId platform, no inferred walking transfer','path_rule':'strictly increasing stationOrd; no interior turnPlaceStationYn=Y; no list wrapping','selection_rule':'prefer direct if present, then shortest sum of captured guganLen; deterministic; not fastest or globally shortest','headway_interpretation':'published nominal route-level weekday/weekend interval, not observed stop wait or lowfloor headway; file freshness is not guaranteed by download date','fleet_interpretation':'2025-04-25 fleet ratio reference only; NOT 2026 current route lowfloor share; ambiguous branch ratios left null','limits':['69 preselected routes only; no conclusion that other routes or rail alternatives do not exist','Euclidean endpoint distances are not verified pedestrian paths','Direction/turning check does not validate timetable continuity, service disruptions, accessibility or boarding','No actual field travel, passenger timing, wheelchair boarding or return appointment schedule verification','2026 nominal route snapshot is a case cross-check, not a replacement for the 2025 aggregate model'],'cases':results,'source_hashes':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [raw/'current_case_stops.json',raw/'노선정보_20261017.csv',raw/'topis_case_metadata.json']}}
 (out/'case_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');pd.DataFrame(rows).to_csv(out/'case_route_legs.csv',index=False,encoding='utf-8-sig')
 for x in results:print(x['dong'],x['direction'],'direct',x['captured_direct_examples'],'route',None if x['selected'] is None else [(l['route'],l['board'],l['board_seq'],l['alight'],l['alight_seq'],l['weekday_headway_minutes']) for l in x['selected']['legs']], 'walk',None if x['selected'] is None else [round(x['selected']['origin_straight_m']),round(x['selected']['destination_straight_m'])])
if __name__=='__main__':main()
