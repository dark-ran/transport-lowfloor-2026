"""Synthetic policy evidence cases. Never treat them as measured bus data."""
import unittest
from datetime import datetime,timedelta,timezone
from observed_policy_review import review

KST=timezone(timedelta(hours=9))
GATES=[{"route":str(i),"2025_fleet":"20","2025_lowfloor":"12","proposed_replacements":"3"} for i in range(1,16)]
def row(route,dt,low=2,ordinary=8,status="success_with_snapshots",fresh=True,event="schedule"):
 total=low+ordinary
 return {"route":str(route),"event":event,"query_scope":"full","direction":"route_all",
    "observed_at_kst":dt.isoformat(),"status":status,
    "low_floor_snapshots":str(low),"ordinary_snapshots":str(ordinary),"unknown_type_snapshots":"0",
    "snapshots":str(total),
    "fresh_low_floor_snapshots":str(low if fresh else 0),
    "fresh_ordinary_snapshots":str(ordinary if fresh else 0)}
class PolicyReviewTests(unittest.TestCase):
 def test_missing_evidence_is_hold_not_zero(self):
  report=review(GATES,[])
  self.assertEqual(len(report),15)
  self.assertTrue(all(r["observed_weekday_lowfloor_share"] is None for r in report))
  self.assertTrue(all(r["policy_review_signal"]=="NO_POLICY_CHANGE_OR_RERANKING" for r in report))
 def test_multiple_valid_days_required_before_a_descriptive_gap(self):
  start=datetime(2026,10,19,8,0,tzinfo=KST)
  observations=[]
  for day in range(7):
   d=start+timedelta(days=day)
   if d.weekday()>4:continue
   for hour in (8,10,14):
    for minute in (0,5,10):
     observations.append(row(1,d.replace(hour=hour,minute=minute)))
  self.assertEqual(review(GATES,observations)[0]["evidence_status"],"HOLD_INSUFFICIENT_REPEATED_EVIDENCE")
  # Use seven explicit weekdays, three windows per day, three polls per window.
  observations=[]
  for offset in (0,1,2,3,4,7,8):
   d=start+timedelta(days=offset)
   for hour in (8,10,14):
    for minute in (0,5,10):
     observations.append(row(1,d.replace(hour=hour,minute=minute)))
  r=review(GATES,observations)[0]
  self.assertEqual(r["valid_weekdays"],7)
  self.assertEqual(r["evidence_status"],"READY_DESCRIPTIVE_ONLY")
  self.assertEqual(r["observed_weekday_lowfloor_share"],.2)
  self.assertEqual(r["policy_review_signal"],"REVIEW_LOWER_OBSERVED_SHARE")
  self.assertEqual(review(GATES,observations)[1]["evidence_status"],"HOLD_INSUFFICIENT_REPEATED_EVIDENCE")
 def test_stale_and_unscheduled_samples_do_not_manufacture_evidence(self):
  d=datetime(2026,10,19,8,0,tzinfo=KST)
  data=[row(1,d+timedelta(minutes=m),fresh=False) for m in (0,5,10)]
  data += [row(1,d+timedelta(minutes=m),event="workflow_dispatch") for m in (0,5,10)]
  data += [row(1,d+timedelta(minutes=m),status="api_error_or_missing") for m in (15,20,25)]
  r=review(GATES,data)[0]
  self.assertEqual(r["scheduled_polls"],6)
  self.assertEqual(r["successful_polls"],3)
  self.assertEqual(r["valid_windows"],0)
 def test_wrong_2025_fleet_fails(self):
  bad=[dict(x) for x in GATES];bad[0]["2025_lowfloor"]="25"
  with self.assertRaises(ValueError):review(bad,[])

if __name__=="__main__":unittest.main()
