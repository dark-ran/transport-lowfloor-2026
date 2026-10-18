"""Collector-only regression tests; network responses are fixtures, not observations."""
import json,tempfile,unittest,shutil,io
from contextlib import redirect_stdout
import v4_vehicle_snapshot as collector
from pathlib import Path
from unittest.mock import patch,MagicMock
import urllib.parse
from v4_vehicle_snapshot import ROOT,collect
from v4_capture_summary import summarize
REQ={'route':'343','route_id':'107000002','direction':'outbound','boarding_seq':7,'startOrd':6,'endOrd':8}
SALT='fixture-local-salt-1234'
class CollectorTests(unittest.TestCase):
 def test_default_cli_makes_no_network_calls(self):
  with tempfile.TemporaryDirectory() as td,patch('urllib.request.urlopen') as net:
   root=Path(td);(root/'results').mkdir();shutil.copy2(ROOT/'results/cap5_route_pilot_candidates.csv',root/'results/cap5_route_pilot_candidates.csv')
   output=io.StringIO()
   with patch.object(collector,'ROOT',root),patch('sys.argv',['collector']),redirect_stdout(output):collector.main()
   self.assertEqual(json.loads(output.getvalue())['queries_executed'],0);net.assert_not_called()
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
