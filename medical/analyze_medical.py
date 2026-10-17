"""Static medical-route opportunity screening. Not a timetable or patient travel model."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from sklearn.neighbors import BallTree
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from shapely.geometry import shape
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
ROOT=Path(__file__).resolve().parent
EARTH=6371008.8

def distance(a,b):
 a=np.radians(a);b=np.radians(b);dy=a[:,None,0]-b[None,:,0];dx=a[:,None,1]-b[None,:,1]
 z=np.sin(dy/2)**2+np.cos(a[:,None,0])*np.cos(b[None,:,0])*np.sin(dx/2)**2
 return EARTH*2*np.arcsin(np.minimum(1,np.sqrt(z)))

def build(o,f,rs,h,radius=500,k=3,point='centroid',include_family=False,ordinary=False):
 use=np.ones(len(f),bool)
 if not include_family:use &= ~f.ambiguous_family.to_numpy(bool)
 if ordinary:use &= ~f.route.str.startswith(('8','N')).to_numpy()
 ff=f[use].reset_index(drop=True);ss=rs[rs.route.isin(ff.route)].copy()
 st=ss.groupby('stop_id',as_index=False).agg(lat=('lat','median'),lon=('lon','median'))
 tree=BallTree(np.radians(st[['lat','lon']].to_numpy()),metric='haversine')
 stop_routes={z:set(g.route) for z,g in ss.groupby('stop_id')};rid={z:i for i,z in enumerate(ff.route)}
 p=o[['lat','lon']].to_numpy() if point=='centroid' else o[['interior_lat','interior_lon']].to_numpy()
 dd=distance(p,h[['lat','lon']].to_numpy());nearest=np.argsort(dd,axis=1)[:,:k]
 nearO=tree.query_radius(np.radians(p),r=radius/EARTH);nearH=tree.query_radius(np.radians(h[['lat','lon']].to_numpy()),r=radius/EARTH)
 def routes(ids):
  ret=set()
  for j in ids:ret.update(stop_routes[st.stop_id.iloc[j]])
  return ret
 a=[routes(ids) for ids in nearO];b=[routes(ids) for ids in nearH]
 C=np.zeros((len(o)*k,len(ff)),bool);walk=np.zeros(len(o)*k,bool);pairs=[]
 for i in range(len(o)):
  for j,z in enumerate(nearest[i]):
   row=i*k+j;walk[row]=dd[i,z]<=radius
   for route in a[i]&b[z]:C[row,rid[route]]=True
   pairs.append({'dong_code':o.code.iloc[i],'hospital_id':h.hospital_id.iloc[z],'hospital_name':h.name.iloc[z],'rank':j+1,'straight_distance_m':float(dd[i,z]),'within_walk_radius':bool(walk[row]),'shared_routes':int(C[row].sum())})
 weights=np.repeat(o.seniors.to_numpy(float)/k,k);weights/=weights.sum()
 return {'f':ff,'C':C,'walk':walk,'weights':weights,'near_stop_counts':np.array([len(x) for x in nearO]),'pairs':pd.DataFrame(pairs),'k':k}

def scores(C,walk,ratio):
 result=np.max(np.where(C,ratio[None,:],0),axis=1);result[walk]=1
 return result

def proportional(n,l,budget):
 a=np.zeros(len(n),int);cap=n-l
 for _ in range(min(budget,int(cap.sum()))):
  ids=np.where(a<cap)[0];i=max(ids,key=lambda i:(cap[i]/cap.sum()*(a.sum()+1)-a[i],-i));a[i]+=1
 return a

def greedy_bundle(C,walk,w,n,l,budget):
 a=np.zeros(len(n),int);cur=scores(C,walk,l/n);steps=[];remaining=budget
 while remaining>0:
  best=None
  for j in np.where(a<n-l)[0]:
   mask=C[:,j]&~walk
   if not mask.any():continue
   ks=np.arange(1,min(int(n[j]-l[j]-a[j]),remaining)+1)
   benefits=(np.maximum(0,(l[j]+a[j]+ks[:,None])/n[j]-cur[mask][None,:])*w[mask]).sum(axis=1)
   v=int(np.argmax(benefits/ks));gain=float(benefits[v]);q=int(ks[v]);key=(gain/q,gain,-q,-j)
   if gain>1e-13 and (best is None or key>best[0]):best=(key,j,q,gain)
  if best is None:break
  _,j,q,gain=best;a[j]+=q;remaining-=q;cur=scores(C,walk,(l+a)/n);steps.append({'route_index':int(j),'added':q,'gain':gain,'spent_total':int(a.sum())})
 return a,steps

def evaluate(m,o,budget):
 f=m['f'];n=f.fleet.to_numpy(int);l=f.low.to_numpy(int);base=scores(m['C'],m['walk'],l/n);gr,steps=greedy_bundle(m['C'],m['walk'],m['weights'],n,l,budget)
 alloc={'현행':np.zeros(len(n),int),'잔여대수 비례':proportional(n,l,budget),'의료연결 우선':gr};rows=[];od={};aa=[]
 for name,a in alloc.items():
  s=scores(m['C'],m['walk'],(l+a)/n);bydong=s.reshape(len(o),m['k']).mean(axis=1);od[name]=bydong
  rows.append({'policy':name,'budget_limit':budget,'spent':int(a.sum()),'index':float(s@m['weights']),'delta_index':float((s-base)@m['weights']),'changed_dongs':int((bydong>od['현행']+1e-10).sum()),'changed_dong_seniors':int(o.loc[bydong>od['현행']+1e-10,'seniors'].sum()),'zero_index_dongs':int((bydong==0).sum())})
  for i in np.where(a>0)[0]:aa.append({'policy':name,'route':f.route.iloc[i],'fleet':int(n[i]),'low_before':int(l[i]),'added':int(a[i]),'ratio_after':float((l[i]+a[i])/n[i])})
 return pd.DataFrame(rows),od,pd.DataFrame(aa),steps

def main():
 out=ROOT/'results';out.mkdir(exist_ok=True)
 o=pd.read_csv(ROOT/'data'/'origins.csv',dtype={'code':str});f=pd.read_csv(ROOT/'data'/'fleets.csv',dtype={'route':str});rs=pd.read_csv(ROOT/'data'/'route_stops.csv',dtype={'route':str,'route_id':str,'stop_id':str});allh=pd.read_csv(ROOT/'data'/'hospitals.csv',dtype={'hospital_id':str});h=allh[allh.kind=='종합병원'].reset_index(drop=True)
 assert len(o)==426 and o.seniors.sum()==1873638 and o.code.is_unique
 assert f.route.is_unique and ((f.low>=0)&(f.low<=f.fleet)).all() and (f.fleet>0).all()
 assert rs[['lat','lon']].notna().all().all() and rs.lat.between(36,39).all() and rs.lon.between(125,129).all()
 assert h.hospital_id.is_unique and h.lat.between(37,38).all() and h.lon.between(126,128).all()
 m=build(o,f,rs,h,ordinary=True);res,od,aa,steps=evaluate(m,o,50);res.to_csv(out/'policy_50.csv',index=False,encoding='utf-8-sig');aa.to_csv(out/'allocation_50.csv',index=False,encoding='utf-8-sig');m['pairs'].to_csv(out/'origin_hospital_pairs.csv',index=False,encoding='utf-8-sig')
 z=o[['code','gu','dong','seniors','lon','lat','centroid_inside']].copy();z['score_before']=od['현행'];z['score_priority']=od['의료연결 우선'];z['score_proportional']=od['잔여대수 비례'];z['near_stop_count']=m['near_stop_counts'];con=(m['C'].any(axis=1)|m['walk']).reshape(len(o),3).mean(axis=1);z['hospital_connection_share']=con;z['gap_priority_weight']=z.seniors*(1-z.score_before)
 z['type']=np.select([z.near_stop_count==0,con==0,con<1,z.score_before<.8],['인근 정류소 없음','공유노선 연결 없음','일부 병원 연결 없음','연결노선 저상비율 낮음'],default='연결·공급 확보')
 X=StandardScaler().fit_transform(z[['hospital_connection_share','score_before','seniors']]);sil={};models={}
 for k in range(2,7):
  model=KMeans(n_clusters=k,random_state=42,n_init=30).fit(X);models[k]=model;sil[k]=float(silhouette_score(X,model.labels_))
 best=max(sil,key=sil.get);z['cluster']=models[best].labels_;z.to_csv(out/'dong_diagnosis.csv',index=False,encoding='utf-8-sig');z.sort_values('gap_priority_weight',ascending=False).head(20).to_csv(out/'priority_dongs.csv',index=False,encoding='utf-8-sig')
 ss=[]; robustness=[]
 configs=[('기본',500,3,'centroid',False,True,h),('반경300m',300,3,'centroid',False,True,h),('반경800m',800,3,'centroid',False,True,h),('최근접1곳',500,1,'centroid',False,True,h),('내부대표점',500,3,'interior',False,True,h),('분기집계군 포함',500,3,'centroid',True,True,h),('시간대제약 미반영',500,3,'centroid',False,False,h),('일반병원 포함',500,3,'centroid',False,True,allh[allh.kind.isin(['종합병원','병원'])].reset_index(drop=True))]
 for label,r,k,point,inc,ordinary,hh in configs:
  mm=m if label=='기본' else build(o,f,rs,hh,r,k,point,inc,ordinary)
  print('scenario',label,flush=True)
  rr,oo,_,_=evaluate(mm,o,50)
  robustness.append(pd.DataFrame({'code':o.code,'scenario':label,'score_before':oo['현행'],'near_stops':mm['near_stop_counts']}))
  for row in rr.to_dict('records'):row['scenario']=label;row['index_difference_vs_base']=float(row['index']-res[res.policy==row['policy']]['index'].iloc[0]);ss.append(row)
 pd.DataFrame(ss).to_csv(out/'sensitivity.csv',index=False,encoding='utf-8-sig')
 robust=pd.concat(robustness,ignore_index=True);robust.to_csv(out/'point_radius_diagnosis.csv',index=False,encoding='utf-8-sig')
 rr=robust[robust.scenario.isin(['기본','반경300m','반경800m','최근접1곳','내부대표점'])].groupby('code').agg(max_score=('score_before','max'),min_stops=('near_stops','min'))
 stable=z.merge(rr,on='code');stable=stable[(stable.min_stops>0)&stable.centroid_inside].copy();stable['robust_gap_weight']=stable.seniors*(1-stable.max_score);stable.sort_values('robust_gap_weight',ascending=False).to_csv(out/'robust_priority_dongs.csv',index=False,encoding='utf-8-sig')
 summary={'origins':len(o),'seniors':int(o.seniors.sum()),'fleet_families':len(f),'main_families':len(m['f']),'main_fleet_vehicles':int(m['f'].fleet.sum()),'general_hospitals':len(h),'all_active_coordinate_hospitals':len(allh),'coordinate_missing_active_hospitals':8,'centroids_outside':int((~o.centroid_inside).sum()),'population_weighted_connection_share':float(con@o.seniors/o.seniors.sum()),'types':z.groupby('type').agg(dongs=('code','count'),representative_seniors=('seniors','sum')).reset_index().to_dict('records'),'policy':res.to_dict('records'),'silhouette':sil,'selected_k':best,'greedy_steps':steps,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data').glob('*')},'interpretation':'Static shared-route supply opportunity; not actual direct travel, arrival probability, patient count, time savings or causal impact.'}
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':12})
 geo=json.loads((ROOT/'data'/'seoul_dongs.geojson').read_text(encoding='utf-8'));lookup=z.set_index('code');patches=[];vals=[]
 for feat in geo['features']:
  code=feat['properties']['adm_cd2'];geom=shape(feat['geometry']);polys=[geom] if geom.geom_type=='Polygon' else list(geom.geoms)
  for pp in polys:patches.append(Polygon(np.array(pp.exterior.coords)));vals.append(lookup.loc[code,'score_before'])
 fig,ax=plt.subplots(figsize=(10,8));coll=PatchCollection(patches,cmap='YlGnBu',edgecolor='#777',linewidth=.25);coll.set_array(np.array(vals));coll.set_clim(0,1);ax.add_collection(coll);ax.autoscale_view();ax.set_aspect(1/np.cos(np.radians(37.55)));fig.colorbar(coll,ax=ax,label='노선 연결·저상 공급지수 (0~1)',shrink=.7);ax.set(xlabel='경도',ylabel='위도',title='고령인구 동별 대표점에서 가까운 종합병원 3곳의 공급기회');fig.text(.02,.015,'동 중심점·직선반경 500m·정적 노선공유 기준. 실제 의료 접근시간·승차 가능성을 뜻하지 않음.',fontsize=10);fig.text(.02,.035,'경계: 통계청 SGIS / 가공: vuski/admdongkor, CC BY 4.0',fontsize=9);fig.tight_layout(rect=(0,.07,1,1));fig.savefig(out/'medical_map.png',dpi=180);plt.close(fig)
 top=stable.sort_values('robust_gap_weight',ascending=False).head(12).iloc[::-1];fig,ax=plt.subplots(figsize=(10,6));ax.barh(top.gu+' '+top.dong,top.robust_gap_weight,color='#2c7888');ax.set(xlabel='고령인구 × (1-조건별 최대 공급지수), 실제 미수혜 인원 아님',title='대표점·반경·병원 수를 바꿔도 부족이 남는 현장 점검 후보');fig.tight_layout();fig.savefig(out/'priority_dongs.png',dpi=180);plt.close(fig)
 q=res[res.policy!='현행'];fig,axs=plt.subplots(1,2,figsize=(10,4.6));axs[0].bar(q.policy,q.delta_index*100,color=['#9aa9bb','#247c8c']);axs[0].set(ylabel='공급지수 증가 (지수포인트 × 100)',title='50대 교체 상한의 모형상 증가');axs[1].bar(q.policy,q.changed_dongs,color=['#9aa9bb','#247c8c']);axs[1].set(ylabel='지수가 증가한 동 수',title='동별 변화의 범위');fig.text(.02,.01,'교체 가능성·동일 대당 비용을 가정. 전체 최적해·실제 주민 편익을 보장하지 않음.',fontsize=10);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(out/'medical_policy.png',dpi=180);plt.close(fig)
 ty=z.groupby('type').seniors.sum().sort_values();fig,ax=plt.subplots(figsize=(10,4.8));ax.barh(ty.index,ty.values/10000,color='#2c7888');ax.set(xlabel='해당 동의 고령인구 합계 (만 명, 전원 동일 접근성이라는 뜻 아님)',title='공급지수의 부족 원인을 나누어 다른 정책을 연결');fig.tight_layout();fig.savefig(out/'gap_types.png',dpi=180);plt.close(fig)
 print(json.dumps({k:v for k,v in summary.items() if k not in ['greedy_steps','source_hashes']},ensure_ascii=False,indent=2));print(z.sort_values('gap_priority_weight',ascending=False).head(12).to_string(index=False));print(pd.DataFrame(ss)[['scenario','policy','index','delta_index']].to_string(index=False))
if __name__=='__main__':main()
