"""Collector-only regression tests; network responses are fixtures, not observations."""
import json,tempfile,unittest,shutil,io
from contextlib import redirect_stdout
import v4_vehicle_snapshot as collector
from pathlib import Path
from unittest.mock import patch,MagicMock
import urllib.parse
from v4_vehicle_snapshot import ROOT,collect,manifest
from v4_capture_summary import summarize
REQ={'route':'343','route_id':'107000002','direction':'outbound','boarding_seq':7,'startOrd':6,'endOrd':8}
SALT='fixture-local-salt-1234'
class CollectorTests(unittest.TestCase):
 def test_default_cli_makes_no_network_calls(self):
  with tempfile.TemporaryDirectory() as td,patch('urllib.request.urlopen') as net:
   root=Path(td);(root/'results').mkdir();shutil.copy2(ROOT/'results/cap5_route_pilot_candidates.csv',root/'results/cap5_route_pilot_candidates.csv')
   output=io.StringIO()
   with patch.object(collector,'ROOT',root),patch('sys.argv',['collector']),redirect_stdout(output):collector.main()
   result=json.loads(output.getvalue())
   self.assertEqual(result['queries_executed'],0)
   self.assertEqual(result['scope'],'full')
   self.assertEqual(len(result['requests']),3)
   self.assertTrue(all(r['direction']=='route_all' and 'startOrd' not in r and 'endOrd' not in r for r in result['requests']))
   net.assert_not_called()
 def test_section_scope_remains_available_in_dry_run(self):
  with tempfile.TemporaryDirectory() as td,patch('urllib.request.urlopen') as net:
   root=Path(td);(root/'results').mkdir();shutil.copy2(ROOT/'results/cap5_route_pilot_candidates.csv',root/'results/cap5_route_pilot_candidates.csv')
   output=io.StringIO()
   with patch.object(collector,'ROOT',root),patch('sys.argv',['collector','--scope','section']),redirect_stdout(output):collector.main()
   result=json.loads(output.getvalue())
   self.assertEqual(result['scope'],'section')
   self.assertEqual(len(result['requests']),6)
   self.assertTrue(all('startOrd' in r and 'endOrd' in r for r in result['requests']))
   net.assert_not_called()
 def test_full_route_uses_official_endpoint_and_no_section_params(self):
  req={'route':'343','route_id':'107000002','scope':'full','direction':'route_all'}
  payload=b'<ServiceResult><msgHeader><headerCd>0</headerCd></msgHeader><msgBody><itemList><vehId>fixture-private-id</vehId><busType>1</busType><sectOrd>11</sectOrd></itemList></msgBody></ServiceResult>'
  with tempfile.TemporaryDirectory() as td,patch('urllib.request.urlopen') as net:
   net.return_value.__enter__.return_value.read.return_value=payload
   output=Path(td)/'raw.jsonl'
   receipt=collect([req],'fixture-key',SALT,output)
   url=urllib.parse.urlparse(net.call_args.args[0])
   self.assertEqual(url.path,'/api/rest/buspos/getBusPosByRtid')
   params=urllib.parse.parse_qs(url.query)
   self.assertEqual(params['busRouteId'],['107000002'])
   self.assertNotIn('startOrd',params)
   self.assertNotIn('endOrd',params)
   self.assertEqual(receipt['request_manifest'],[req])
   rows=[json.loads(x) for x in output.read_text(encoding='utf-8').splitlines()]
   self.assertEqual(rows[0]['direction'],'route_all')
   self.assertIsNone(rows[0]['boarding_seq'])
   public=summarize(receipt,rows,receipt['request_manifest'],'fixture-commit')
   self.assertEqual(public['query_scope'],'full')
   self.assertEqual(public['query_groups'][0]['query_scope'],'full')
   self.assertEqual(public['vehicle_snapshots'],1)
   self.assertNotIn('fixture-private-id',json.dumps(public))
 def test_policy_cohort_matches_15_real_route_ids(self):
  import pandas as pd
  data=pd.read_csv(ROOT/'results/cap5_route_pilot_candidates.csv',dtype={'route':str})
  requests=manifest(data,scope='full',cohort='model15')
  self.assertEqual(len(requests),15)
  self.assertEqual(len({r['route_id'] for r in requests}),15)
  self.assertTrue(all(r['direction']=='route_all' for r in requests))
  self.assertTrue(all('startOrd' not in r and 'endOrd' not in r for r in requests))
  self.assertIn('662',{r['route'] for r in requests})
  self.assertIn('7211',{r['route'] for r in requests})
  with self.assertRaises(ValueError):
   manifest(data,scope='section',cohort='model15')
 def test_missing_key_makes_no_requests(self):
  with tempfile.TemporaryDirectory() as td,patch('urllib.request.urlopen') as net:
   with self.assertRaises(ValueError):collect([REQ],None,SALT,Path(td)/'raw.jsonl')
   net.assert_not_called()
 def test_repository_root_output_is_forbidden(self):
  with patch('urllib.request.urlopen') as net:
   with self.assertRaises(ValueError):collect([REQ],'fixture-key',SALT,ROOT.parent/'raw.jsonl')
   net.assert_not_called()
 def test_missing_provider_header_is_failure_not_empty_success(self):
  with tempfile.TemporaryDirectory() as td,patch('urllib.request.urlopen') as net:
   net.return_value.__enter__.return_value.read.return_value=b'<ServiceResult><msgBody/></ServiceResult>'
   receipt=collect([REQ],'fixture-key',SALT,Path(td)/'raw.jsonl')
   self.assertEqual(len(receipt['failed_requests']),1);self.assertEqual(receipt['vehicle_snapshots'],0)
 def test_encoded_key_used_once_and_raw_ids_removed(self):
  payload=b'<ServiceResult><msgHeader><headerCd>0</headerCd></msgHeader><msgBody><itemList><vehId>fixture-private-id</vehId><plainNo>fixture-plate</plainNo><busType>1</busType></itemList></msgBody></ServiceResult>'
  with tempfile.TemporaryDirectory() as td,patch('urllib.request.urlopen') as net:
   net.return_value.__enter__.return_value.read.return_value=payload
   out=Path(td)/'raw.jsonl';receipt=collect([REQ],'fixture%2Bkey%3D',SALT,out)
   self.assertTrue(net.call_args.args[0].startswith('http://ws.bus.go.kr/api/rest/buspos/getBusPosByRouteSt?'))
   self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(net.call_args.args[0]).query)['serviceKey'],['fixture+key='])
   rows=[json.loads(x) for x in out.read_text(encoding='utf-8').splitlines()];public=summarize(receipt,rows,[REQ],'fixture-commit')
   self.assertEqual(public['vehicle_snapshots'],1);self.assertEqual(public['verified_boardings'],0)
   for secret in ['fixture-private-id','fixture-plate',rows[0]['vehicle_pseudonym'],'serviceKey']:
    self.assertNotIn(secret,json.dumps(public))
 def test_empty_response_does_not_claim_no_service(self):
  p=summarize({'requests':1,'failed_requests':[]},[],[REQ],'fixture')
  self.assertEqual(p['query_groups'][0]['status'],'success_empty');self.assertIsNone(p['measured_lowfloor_headway_minutes'])
if __name__=='__main__':unittest.main()
