"""Synthetic, network-free privacy and movement regression tests."""
import tempfile,unittest,json
from pathlib import Path
from vehicle_evidence_storage import encrypt,decrypt,archive
KEY="fake-key-never-used-outside-unit-tests"
def rows(seq=3):
 return [{"route":"662","vehicle_pseudonym":"PSEUDONYM-UNIQUE","section_seq":str(seq),
          "vehicle_type":"low_floor","longitude":126.99,"latitude":37.55,
          "vehId":"RAW-VEH-ID","plainNo":"RAW-PLATE"}]
class VehicleHistoryTests(unittest.TestCase):
 def test_encryption_removes_raw_identifiers(self):
  p=encrypt(rows(),KEY);s=json.dumps(p)
  for secret in ["RAW-VEH-ID","RAW-PLATE","PSEUDONYM-UNIQUE"]:self.assertNotIn(secret,s)
  r=decrypt(p,KEY)
  self.assertEqual(r[0]["section_seq"],"3")
  self.assertNotIn("vehId",r[0]);self.assertNotIn("plainNo",r[0])
  with self.assertRaises(Exception):decrypt(p,KEY+"-wrong")
 def test_automatic_section_and_transition_summary(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);folder=root/"observations/vehicle_encrypted";folder.mkdir(parents=True)
   enc=root/"current.enc"
   enc.write_text(json.dumps(encrypt(rows(3),KEY)),encoding="utf-8")
   s={"vehicle_snapshots":1,"created_at_utc":"2026-10-19T01:00:00+00:00"}
   archive(enc,s,folder,KEY,"101")
   enc.write_text(json.dumps(encrypt(rows(6),KEY)),encoding="utf-8")
   archive(enc,{**s,"created_at_utc":"2026-10-19T01:05:00+00:00"},folder,KEY,"102")
   detail=(root/"observations/vehicle_encrypted/vehicle-102.enc").read_text()
   sections=(root/"observations/vehicle_section_timeseries.csv").read_text()
   moves=(root/"observations/vehicle_transitions.csv").read_text()
   self.assertNotIn("PSEUDONYM-UNIQUE",detail+sections+moves)
   self.assertIn("forward",moves);self.assertIn("102,",moves)
   self.assertIn("3,low_floor,1",sections)
   self.assertIn("6,low_floor,1",sections)
if __name__=="__main__":unittest.main()
