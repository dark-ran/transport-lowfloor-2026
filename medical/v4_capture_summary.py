"""Create a public aggregate receipt; never publish private vehicle pseudonyms."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse,json
from v4_vehicle_snapshot import ROOT

def summarize(receipt,rows,requests,commit):
 failed={(x['route'],x['direction']) for x in receipt['failed_requests']}
 errors={(x['route'],x['direction']):x for x in receipt['failed_requests']}
 groups=[]
 for r in requests:
  selected=[x for x in rows if x['route']==r['route'] and x['direction']==r['direction']]
  types=Counter(x['vehicle_type'] for x in selected)
  groups.append({'route':r['route'],'direction':r['direction'],
   'query_scope':r.get('scope','section'),
   'status':'api_error_or_missing' if (r['route'],r['direction']) in failed else ('success_with_snapshots' if selected else 'success_empty'),
   'error':{k:errors[(r['route'],r['direction'])].get(k) for k in ['exception_type','http_status','provider_code']} if (r['route'],r['direction']) in errors else None,
   'snapshots':len(selected),'distinct_vehicle_pseudonyms_in_query':len({x['vehicle_pseudonym'] for x in selected}),
   'low_floor_snapshots':types['low_floor'],'ordinary_snapshots':types['ordinary'],'unknown_type_snapshots':types['unknown']})
 return {'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),
  'source_git_commit':commit,'query_scope':receipt.get('query_scope'),
  'api_requests_executed':receipt['requests'],
  'successful_requests':receipt['requests']-len(receipt['failed_requests']),
  'vehicle_snapshots':len(rows),'query_groups':groups,
  'verified_arrivals':0,'verified_boardings':0,'measured_lowfloor_headway_minutes':None,
  'interpretation':'One-shot vehicle-position snapshots only; empty/error is not evidence of no service. No boarding, waiting-time or arrival claim.',
  'private_rows_published':False,'official_source':'https://www.data.go.kr/data/15000332/openapi.do'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True);p.add_argument('--private-jsonl',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--commit',required=True);a=p.parse_args()
 receipt=json.loads(a.receipt.read_text(encoding='utf-8'));rows=[json.loads(x) for x in a.private_jsonl.read_text(encoding='utf-8').splitlines() if x.strip()];requests=receipt.get('request_manifest')
 if not isinstance(requests,list):raise ValueError('Capture receipt must contain actual request manifest')
 if receipt['requests']!=len(requests) or receipt['vehicle_snapshots']!=len(rows):raise ValueError('Capture receipt does not match manifest/rows')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(summarize(receipt,rows,requests,a.commit),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
