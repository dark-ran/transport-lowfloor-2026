from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,itertools,sys
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score,adjusted_rand_score
ROOT=Path(__file__).resolve().parent
SOURCE='https://data.seoul.go.kr/dataList/OA-22229/F/1/datasetView.do'
def allocate(n,l,b,mode,t=.5):
 a=np.zeros(len(n),dtype=int); cap=n-l
 if mode=='hybrid':
  ids=np.where(l==0)[0]
  for i in sorted(ids,key=lambda i:(n[i],i)):
   if b==0:break
   a[i]+=1;b-=1
  a+=allocate(n,l+a,b,'threshold',t)
 elif mode=='threshold':
  cost=np.maximum(0,np.ceil(t*n-1e-10).astype(int)-l)
  for i in sorted(range(len(n)),key=lambda i:(cost[i],i)):
   if cost[i]>0 and cost[i]<=b: a[i]=cost[i];b-=cost[i]
  # Remaining budget cannot complete another route: assign to smallest unfinished gap.
  for i in sorted(range(len(n)),key=lambda i:(max(0,cost[i]-a[i]) or 10**9,i)):
   k=min(int(cap[i]-a[i]),b);a[i]+=k;b-=k
   if b==0:break
 elif mode=='proportional':
  for _ in range(min(b,int(cap.sum()))):
   eligible=np.where(a<cap)[0]
   i=max(eligible,key=lambda i:(cap[i]/cap.sum()*(a.sum()+1)-a[i],-i));a[i]+=1
 elif mode=='lowest_ratio':
  for _ in range(min(b,int(cap.sum()))):
   ids=np.where(a<cap)[0];i=min(ids,key=lambda i:((l[i]+a[i])/n[i],-n[i],i));a[i]+=1
 assert (a>=0).all() and (a<=cap).all()
 return a

def main():
 raw=ROOT/'data'/'서울시_저상버스_20250425.xlsx';out=ROOT/'results';out.mkdir(exist_ok=True)
 d=pd.read_excel(raw,dtype={0:str});d.columns=['route','fleet','low','published_rate'];d['route']=d.route.str.strip()
 assert len(d)==348 and not d.route.duplicated().any() and d.notna().all().all()
 assert ((d.low>=0)&(d.fleet>=d.low)).all();assert np.allclose(d.fleet,np.round(d.fleet)) and np.allclose(d.low,np.round(d.low))
 zero=d[d.fleet==0];v=d[d.fleet>0].copy().reset_index(drop=True);v['rate']=v.low/v.fleet;v['gap']=v.fleet-v.low
 assert np.allclose(v.rate,v.published_rate,atol=1e-8)
 n=v.fleet.to_numpy(int);l=v.low.to_numpy(int)
 stats={'source':SOURCE,'date':'2025-04-25','retrieved':'2026-10-17','sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'raw_rows':len(d),'valid_rows':len(v),'zero_fleet_rows':len(zero),'fleet':int(n.sum()),'low':int(l.sum()),'weighted_rate':float(l.sum()/n.sum()),'unweighted_rate':float(np.mean(l/n)),'zero_low_routes':int((l==0).sum()),'full_routes':int((l==n).sum()),'below50':int((l/n<.5).sum()),'zero_fleet_ids':zero.route.tolist()}
 rows=[];allocations=[]
 for scope in ['all','regular']:
  w=v if scope=='all' else v[~v.route.str.startswith(('8','N','서울'))].reset_index(drop=True)
  ns=w.fleet.to_numpy(int);ls=w.low.to_numpy(int)
  for t in [.25,.5,.75]:
   for b in [0,10,25,50,100,200]:
    for mode in ['proportional','lowest_ratio','threshold','hybrid']:
     a=allocate(ns,ls,b,mode,t);assert a.sum()==min(b,int((ns-ls).sum()))
     r=(ls+a)/ns
     rows.append({'scope':scope,'threshold':t,'budget':b,'policy':mode,'weighted_rate':(ls+a).sum()/ns.sum(),'below_threshold':int((r<t-1e-10).sum()),'zero_routes':int((r==0).sum()),'route_mean':r.mean(),'minimum_rate':r.min(),'supported_routes':int((a>0).sum()),'spent':int(a.sum())})
     if scope=='all' and t==.5 and b==50:
      allocations.extend({'route':w.route.iloc[i],'fleet':int(ns[i]),'low_before':int(ls[i]),'added':int(a[i]),'rate_after':float(r[i]),'policy':mode} for i in range(len(w)))
 x=StandardScaler().fit_transform(v[['fleet','rate']]);models={};scores={}
 for k in range(2,7):
  km=KMeans(n_clusters=k,random_state=42,n_init=30).fit(x);models[k]=km;scores[k]=float(silhouette_score(x,km.labels_))
 best=max(scores,key=scores.get);v['cluster']=models[best].labels_
 stability=[adjusted_rand_score(v.cluster,KMeans(n_clusters=best,random_state=s,n_init=30).fit_predict(x)) for s in [0,1,7,21,99]]
 stats.update(cluster_k=best,silhouette=scores,cluster_ari_min=float(min(stability)))
 summary=pd.DataFrame(rows);aa=pd.DataFrame(allocations)
 v.to_csv(out/'routes_validated.csv',index=False,encoding='utf-8-sig');zero.to_csv(out/'excluded_zero_fleet.csv',index=False,encoding='utf-8-sig');summary.to_csv(out/'policy_sensitivity.csv',index=False,encoding='utf-8-sig');aa.to_csv(out/'allocation_50.csv',index=False,encoding='utf-8-sig')
 clusters=v.groupby('cluster').agg(routes=('route','count'),fleet=('fleet','sum'),low=('low','sum'),mean_rate=('rate','mean'),min_fleet=('fleet','min'),max_fleet=('fleet','max'));clusters.to_csv(out/'clusters.csv',encoding='utf-8-sig')
 (out/'summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
 plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
 fig,ax=plt.subplots(figsize=(10,4.8)); bins=[int((v.rate==0).sum()),int(((v.rate>0)&(v.rate<.5)).sum()),int(((v.rate>=.5)&(v.rate<1)).sum()),int((v.rate==1).sum())];labels=['0%','0% 초과 ~ 50% 미만','50% 이상 ~ 100% 미만','100%'];ax.bar(labels,bins,color=['#c64545','#de9650','#559ba4','#1a5769']);ax.set_ylabel('노선 수');ax.set_title('전체 평균에 가려진 노선별 저상버스 공급 격차');[ax.text(i,b+2,str(b),ha='center') for i,b in enumerate(bins)];ax.set_ylim(0,max(bins)*1.2);fig.text(.02,.01,'서울시 원자료(2025.4.25), 인가대수 0인 행 제외. 실제 운행·도착확률 지표가 아님.',fontsize=9);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/'distribution.png',dpi=200);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(12,4.5));q=summary[(summary.scope=='all')&(summary.threshold==.5)&(summary.budget==50)]; names={'proportional':'잔여대수 비례','lowest_ratio':'최저비율 우선','threshold':'50% 도달노선 최대','hybrid':'0대 해소 후 문턱 도달'}
 for j,col in enumerate(['below_threshold','zero_routes']):
  axs[j].bar([names[z] for z in q.policy],q[col],color=['#8a9baf','#559ba4','#1a5769','#b87b45']);axs[j].set_title('50% 미만 노선 수' if j==0 else '저상버스 0대 노선 수');axs[j].tick_params(axis='x',rotation=15)
  for i,z in enumerate(q[col]):axs[j].text(i,z+.2,str(z),ha='center')
 fig.suptitle('같은 50대 교체, 정책 목표에 따라 달라지는 결과');fig.text(.02,.01,'모든 교체가 가능하고 대당 비용이 같다는 가정. 전체 보유율 증가는 정책 간 동일.',fontsize=9);fig.tight_layout(rect=(0,.05,1,.94));fig.savefig(out/'comparison.png',dpi=200);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,4.5))
 for mode,g in summary[(summary.scope=='all')&(summary.threshold==.5)].groupby('policy'):ax.plot(g.budget,g.below_threshold,'o-',label=names[mode])
 ax.set(xlabel='교체대수 가정',ylabel='50% 미만 노선 수',title='예산 민감도: 단일 평균 대신 취약노선 잔여량을 관리');ax.legend();fig.tight_layout();fig.savefig(out/'sensitivity.png',dpi=200);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,4.6));sc=ax.scatter(v.fleet,v.rate*100,c=v.cluster,cmap='tab10',alpha=.8);ax.set(xlabel='노선별 인가대수',ylabel='저상버스 보유율(%)',title=f'KMeans 탐색적 공급 유형화 (k={best})');ax.legend(*sc.legend_elements(),title='군집');fig.tight_layout();fig.savefig(out/'clusters.png',dpi=200);plt.close(fig)
 print(json.dumps(stats,ensure_ascii=False,indent=2));print(q.to_string(index=False));print(clusters.to_string())
if __name__=='__main__':main()

