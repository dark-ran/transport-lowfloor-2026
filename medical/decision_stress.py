"""Evaluate ONE allocation across settings, and constrain route concentration.
All effects are model index changes, not measured travel benefits or costs.
"""
from pathlib import Path
import json
import numpy as np,pandas as pd
from analyze_medical import build,scores,greedy_bundle,proportional
ROOT=Path(__file__).resolve().parent

def load_models():
 o=pd.read_csv(ROOT/'data/origins.csv',dtype={'code':str});f=pd.read_csv(ROOT/'data/fleets.csv',dtype={'route':str});rs=pd.read_csv(ROOT/'data/route_stops.csv',dtype={'route':str,'route_id':str,'stop_id':str});allh=pd.read_csv(ROOT/'data/hospitals.csv',dtype={'hospital_id':str});h=allh[allh.kind=='종합병원'].reset_index(drop=True)
 configs=[('기본',500,3,'centroid',False,True,h),('반경300m',300,3,'centroid',False,True,h),('반경800m',800,3,'centroid',False,True,h),('최근접1곳',500,1,'centroid',False,True,h),('내부대표점',500,3,'interior',False,True,h),('분기집계군 포함',500,3,'centroid',True,True,h),('시간대제약 미반영',500,3,'centroid',False,False,h),('일반병원 포함',500,3,'centroid',False,True,allh[allh.kind.isin(['종합병원','병원'])].reset_index(drop=True))]
 models={name:build(o,f,rs,hh,r,k,pt,inc,day) for name,r,k,pt,inc,day,hh in configs};return o,models

def capped_greedy(models,budget,cap_per_route=5,robust=False):
 base=models[0];ff=base['f'];routes=ff.route.tolist();n=ff.fleet.to_numpy(int);low=ff.low.to_numpy(int);cap=np.minimum(n-low,cap_per_route);banned=set(json.loads((ROOT/'raw/exception_routes_2026.json').read_text(encoding='utf-8'))['routes']);cap[np.array([x in banned for x in routes])]=0;a=np.zeros(len(n),int)
 prepared=[]
 for m in models:
  pos=m['f'].set_index('route').index.get_indexer(routes);assert (pos>=0).all();mn=m['f'].fleet.to_numpy(float);ml=m['f'].low.to_numpy(float);C=m['C'][:,pos];s=scores(m['C'],m['walk'],ml/mn);gap=1-float(s@m['weights']);prepared.append((m,C,s.copy(),s.copy(),gap))
 cur_gain=np.zeros(len(prepared));steps=[]
 while a.sum()<budget:
  best=None
  for j in np.where(a<cap)[0]:
   ks=np.arange(1,min(int(cap[j]-a[j]),budget-int(a.sum()))+1);gains=np.zeros((len(prepared),len(ks)))
   for mi,(m,C,cur,initial,gap) in enumerate(prepared):
    mask=C[:,j]&~m['walk']
    if mask.any():gains[mi]=(np.maximum(0,(low[j]+a[j]+ks[:,None])/n[j]-cur[mask])*m['weights'][mask]).sum(axis=1)
   if robust:
    norm=(cur_gain[:,None]+gains)/np.array([z[4] for z in prepared])[:,None];now=cur_gain/np.array([z[4] for z in prepared]);primary=(norm.min(axis=0)-now.min())/ks;secondary=(norm.mean(axis=0)-now.mean())/ks
   else:primary=gains[0]/ks;secondary=primary
   for z,q in enumerate(ks):
    key=(float(primary[z]),float(secondary[z]),float(gains[:,z].sum()),-int(q),-j)
    if gains[:,z].sum()>1e-13 and (best is None or key>best[0]):best=(key,j,int(q),gains[:,z])
  if best is None:break
  _,j,q,gain=best;a[j]+=q;cur_gain+=gain
  for m,C,cur,initial,gap in prepared:cur[C[:,j]&~m['walk']]=np.maximum(cur[C[:,j]&~m['walk']],(low[j]+a[j])/n[j])
  steps.append({'route':routes[j],'added':q,'spent':int(a.sum()),'gains':cur_gain.tolist()})
 return a,steps

def measure(m,o,routes,a):
 ff=m['f'];n=ff.fleet.to_numpy(int);l=ff.low.to_numpy(int);mapping=dict(zip(routes,a));aa=np.array([mapping.get(x,0) for x in ff.route]);assert ((aa>=0)&(aa<=n-l)).all()
 b=scores(m['C'],m['walk'],l/n);s=scores(m['C'],m['walk'],(l+aa)/n);delta=float((s-b)@m['weights']);by=(s-b).reshape(len(o),m['k']).mean(axis=1);base=float(b@m['weights']);return {'index_before':base,'index_after':float(s@m['weights']),'delta_index':delta,'headroom_recovered':delta/(1-base),'changed_dongs':int((by>1e-10).sum()),'zero_after':int((s.reshape(len(o),m['k']).mean(axis=1)==0).sum())}

def main():
 out=ROOT/'results';o,models=load_models();m=models['기본'];routes=m['f'].route.tolist();n=m['f'].fleet.to_numpy(int);l=m['f'].low.to_numpy(int);old=pd.read_csv(out/'allocation_50.csv',dtype={'route':str});alloc={}
 for label in ['잔여대수 비례','의료연결 우선']:
  z=old[old.policy==label].set_index('route').added.to_dict();alloc[label]=np.array([z.get(x,0) for x in routes],int);assert alloc[label].sum()==50
 eligible=np.array([x not in set(json.loads((ROOT/'raw/exception_routes_2026.json').read_text(encoding='utf-8'))['routes']) for x in routes]);ap=np.zeros(len(n),int);ap[eligible]=proportional(n[eligible],l[eligible],50);alloc['예외제외 비례']=ap
 core=list(models.values())[:5];alloc['예외제외·노선당5대 의료우선'],_=capped_greedy([m],50,5);alloc['예외제외·5조건 강건5대'],steps=capped_greedy(core,50,5,True)
 rows=[];aa=[]
 for label,a in alloc.items():
  assert a.sum()==50 and (a<=n-l).all()
  for scenario,mm in models.items():rows.append({'policy':label,'scenario':scenario,'spent':int(a.sum()),'route_count':int((a>0).sum()),'largest_route_addition':int(a.max()),**measure(mm,o,routes,a)})
  for i in np.where(a>0)[0]:aa.append({'policy':label,'route':routes[i],'fleet':int(n[i]),'low_before':int(l[i]),'added':int(a[i])})
 result=pd.DataFrame(rows);result.to_csv(out/'fixed_allocation_stress.csv',index=False,encoding='utf-8-sig');pd.DataFrame(aa).to_csv(out/'screened_allocations.csv',index=False,encoding='utf-8-sig')
 # No re-optimization when one selected route cannot be replaced: leave its slots unused.
 failure=[]
 for label,a in alloc.items():
  for j in np.where(a>0)[0]:
   removed=a.copy();removed[j]=0;effects=[measure(mm,o,routes,removed) for mm in models.values()];failure.append({'policy':label,'blocked_route':routes[j],'unspent_slots':int(a[j]),'base_delta':effects[0]['delta_index'],'min_normalized_gain':min(x['headroom_recovered'] for x in effects),'min_delta_across_settings':min(x['delta_index'] for x in effects)})
 pd.DataFrame(failure).to_csv(out/'route_unavailable_stress.csv',index=False,encoding='utf-8-sig')
 curve=[]
 for budget in [10,25,50,100]:
  for label,a in [('잔여대수 비례',proportional(n,l,budget)),('의료연결 우선',greedy_bundle(m['C'],m['walk'],m['weights'],n,l,budget)[0]),('예외제외·노선당5대 의료우선',capped_greedy([m],budget,5)[0])]:curve.append({'budget':budget,'policy':label,'spent':int(a.sum()),'max_added':int(a.max()),**measure(m,o,routes,a)})
 pd.DataFrame(curve).to_csv(out/'budget_curve.csv',index=False,encoding='utf-8-sig')
 summary={'all_policies_fixed_across_8_settings':True,'robust_training_settings':list(models)[:5],'additional_scope_checks':list(models)[5:],'per_route_cap_5':'illustrative concentration/implementation constraint, not actual depot capacity','robust_objective':'greedy lexicographic increase in minimum headroom-recovered gain over five settings, then mean; not global optimum','exception_screen':'25 official 2026 approved-exception routes excluded from new capped/robust and screened-proportional allocations; original allocation retained as comparison','budget_units':'vehicle replacement slots, not verified financial costs','failure_rule':'one allocated route unavailable; its slots remain unspent; allocation to other routes unchanged','no_observed_travel_benefit':True,'fixed_table':result.to_dict('records'),'robust_steps':steps,'failure_summary':pd.DataFrame(failure).groupby('policy').agg(worst_base_delta=('base_delta','min'),worst_min_normalized=('min_normalized_gain','min'),max_unused=('unspent_slots','max')).reset_index().to_dict('records')};(out/'decision_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(result[['policy','scenario','delta_index','changed_dongs','largest_route_addition']].to_string(index=False));print(pd.DataFrame(summary['failure_summary']).to_string(index=False))
if __name__=='__main__':main()
