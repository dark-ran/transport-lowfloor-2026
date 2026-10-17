"""Independent checks of the saved fixed allocations and reported outcomes."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from decision_stress import load_models
from analyze_medical import scores
ROOT=Path(__file__).resolve().parent

def main():
 out=ROOT/'results';a=pd.read_csv(out/'screened_allocations.csv',dtype={'route':str});r=pd.read_csv(out/'fixed_allocation_stress.csv');o,models=load_models();ban=set(json.loads((ROOT/'raw/exception_routes_2026.json').read_text(encoding='utf-8'))['routes']);checks=0
 for policy,g in a.groupby('policy'):
  assert g.added.sum()==50 and not g.route.duplicated().any() and (g.added>0).all() and (g.added<=g.fleet-g.low_before).all()
  if '예외제외' in policy:assert not (set(g.route)&ban)
  if '5대' in policy:assert g.added.max()<=5
  weights=g.set_index('route').added.to_dict()
  for scenario,m in models.items():
   f=m['f'];delta=np.array([weights.get(x,0) for x in f.route]);n=f.fleet.to_numpy();l=f.low.to_numpy();before=scores(m['C'],m['walk'],l/n);after=scores(m['C'],m['walk'],(l+delta)/n);calculated=float((after-before)@m['weights']);row=r[(r.policy==policy)&(r.scenario==scenario)].iloc[0];assert abs(calculated-row.delta_index)<1e-12;changed=int(((after-before).reshape(len(o),m['k']).mean(axis=1)>1e-10).sum());assert changed==row.changed_dongs;checks+=1
 orig=r[(r.policy=='의료연결 우선')&(r.scenario=='기본')].iloc[0];cap=r[(r.policy=='예외제외·노선당5대 의료우선')&(r.scenario=='기본')].iloc[0];assert orig.changed_dongs==60 and cap.changed_dongs==75
 manifest=json.loads((ROOT/'source_hashes.json').read_text(encoding='utf-8'));assert all(hashlib.sha256((ROOT/'raw'/k).read_bytes()).hexdigest()==v for k,v in manifest.items())
 receipt={'passed':True,'fixed_policy_scenario_checks':checks,'official_exception_routes':len(ban),'budget_slots_per_policy':50,'capped_max':5,'base_gain_retained_by_capped':float(cap.delta_index/orig.delta_index),'capped_changed_dongs':int(cap.changed_dongs),'observed_travel_outcomes':False,'certified_financial_costs':False,'scope':'saved allocations evaluated independently under all eight models; not global optimization or real-world impact verification'};(out/'decision_audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
