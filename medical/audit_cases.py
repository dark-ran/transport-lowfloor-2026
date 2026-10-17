from pathlib import Path
import json,hashlib,sys,pandas as pd
sys.stdout.reconfigure(encoding='utf-8');r=Path(__file__).resolve().parent;j=json.loads((r/'results/case_validation.json').read_text(encoding='utf-8'));sources={x['route_id']:x for x in json.loads((r/'raw/current_case_stops.json').read_text(encoding='utf-8'))};meta={x['routId']:x for x in json.loads((r/'raw/topis_case_metadata.json').read_text(encoding='utf-8'))};assert j['source_route_count']==69 and len(j['cases'])==6
for c in j['cases']:
 q=c['selected'];assert q and q['origin_straight_m']<=500 and q['destination_straight_m']<=500
 legs=q['legs'];assert len(legs)==q['transfers']+1
 for l in legs:
  a=sources[l['route_id']]['rows'];a=sorted(a,key=lambda x:x['stationOrd']);b=next(x for x in a if x['stationOrd']==l['board_seq']);e=next(x for x in a if x['stationOrd']==l['alight_seq']);assert b['arsId']==l['board_ars'] and e['arsId']==l['alight_ars'];assert b['stationOrd']<e['stationOrd'];assert not any(x['turnPlaceStationYn']=='Y' for x in a if b['stationOrd']<x['stationOrd']<e['stationOrd']);assert l['weekday_headway_minutes']==meta[l['route_id']]['norTerms'];assert int(l['weekday_headway_minutes'])>0
  if l['route'] in ['6640A','6640B','강남06']:assert l['fleet_ratio_2025'] is None
 if len(legs)==2:
  a=sources[legs[0]['route_id']]['rows'];b=sources[legs[1]['route_id']]['rows'];left=next(x for x in a if x['stationOrd']==legs[0]['alight_seq']);right=next(x for x in b if x['stationOrd']==legs[1]['board_seq']);assert left['stationId']==right['stationId']==q['transfer_platform']
 print(c['dong'],c['direction'],[(l['route'],l['board'],l['alight']) for l in legs])
manifest=json.loads((r/'source_hashes.json').read_text(encoding='utf-8'));assert all(hashlib.sha256((r/'raw'/n).read_bytes()).hexdigest()==v for n,v in manifest.items())
receipt={'passed':True,'checks':['six outward/return examples','endpoint Euclidean radius','raw station ID and order','no internal terminal passage','same-platform transfer','CSV/TOPIS headway consistency','unknown branch/village ratios retained null','all raw SHA256 manifest entries'],'source_route_count':69,'case_count':6,'actual_field_trip':False,'observed_waiting_time':False,'pedestrian_accessibility_verified':False}
(r/'results/case_audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS')
