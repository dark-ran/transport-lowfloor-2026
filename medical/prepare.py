from pathlib import Path
import pandas as pd,numpy as np,json
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
out=Path(__file__).resolve().parent;raw=out/'raw';(out/'data').mkdir(parents=True,exist_ok=True)
f=pd.read_excel(raw/'서울시_저상버스_20250425.xlsx',dtype={0:str});f.columns=['route','fleet','low','rate'];f=f[f.fleet>0].copy();f['route']=f.route.str.strip()
s=pd.read_excel(raw/'노선정류소_20250513.xlsx',dtype={'ROUTE_ID':str,'노선명':str,'NODE_ID':str,'ARS_ID':str});s=s.rename(columns={'ROUTE_ID':'route_id','노선명':'route','순번':'seq','NODE_ID':'stop_id','정류소명':'stop_name','X좌표':'lon','Y좌표':'lat'});s['route']=s.route.str.strip();s['source_route']=s.route
alias={'110A고려대':'110','110B국민대':'110','5522A난곡':'5522','5522B호암':'5522','6640A':'6640','6640B':'6640','7013A':'7013','7013B':'7013','702A':'702','702B':'702','750A':'750','750B':'750','8553출근':'8553'}
s['route']=s.route.replace(alias)
f['ambiguous_family']=f.route.isin(['110','5522','6640','7013','702','750'])
print('routes',len(f),'match',f.route.isin(s.route).sum(),'unmatched',f[~f.route.isin(s.route)][['route','fleet','low']].to_dict('records'));print('sequence duplicates',s.duplicated(['route_id','seq']).sum())
f=f[f.route.isin(s.route)].copy();f['ambiguous_family']=f.route.isin(s.groupby('route').route_id.nunique().loc[lambda z:z>1].index);rs=s[s.route.isin(f.route)].copy();print('groups',rs.groupby('route').route_id.nunique().value_counts().to_dict())
f.to_csv(out/'data'/'fleets.csv',index=False);rs.to_csv(out/'data'/'route_stops.csv',index=False)
p=pd.read_csv(raw/'고령자현황_2025Q2.csv',header=None,dtype=str);p=p.iloc[4:].copy();p.columns=['city','gu','dong','total','men','women','seniors','sm','sw','sk','skm','skw','sf','sfm','sfw'];p['gu']=p.gu.str.replace(r'^\d+\s+','',regex=True);p['dong']=p.dong.str.replace(r'^\d+\s+','',regex=True)
city=p[p.gu=='소계'].seniors.iloc[0];p=p[p.dong!='소계'].copy();p['seniors']=pd.to_numeric(p.seniors);p['total']=pd.to_numeric(p.total);print('dong',len(p),'sum',p.seniors.sum(),'city',city)
g=json.loads((raw/'행정동경계_서울_20250401.geojson').read_text(encoding='utf-8'));g['features']=[x for x in g['features'] if x['properties']['sido']=='11'];print('boundaries',len(g['features']))
proj=Transformer.from_crs(4326,5179,always_xy=True).transform;rev=Transformer.from_crs(5179,4326,always_xy=True).transform;rows=[]
for feat in g['features']:
 a=feat['properties'];geom=shape(feat['geometry']);geomproj=transform(proj,geom);c=transform(rev,geomproj.centroid);q=transform(rev,geomproj.representative_point());rows.append({'code':a['adm_cd2'],'gu':a['sggnm'],'dong':a['adm_nm'].split(' ',2)[2],'lon':c.x,'lat':c.y,'interior_lon':q.x,'interior_lat':q.y,'centroid_inside':geom.covers(c)})
b=pd.DataFrame(rows);b['dong']=b.dong.str.replace('·','.',regex=False).replace({'상일제1동':'상일1동','상일제2동':'상일2동'});pop=p.merge(b,on=['gu','dong'],how='outer',indicator=True);print('join mismatch',pop[pop._merge!='both'][['gu','dong','_merge']].to_dict('records'));pop=pop[pop._merge=='both'].drop(columns='_merge');assert len(pop)==426 and pop.seniors.sum()==int(city);pop.to_csv(out/'data'/'origins.csv',index=False);(out/'data'/'seoul_dongs.geojson').write_text(json.dumps(g,ensure_ascii=False),encoding='utf-8')
h=pd.read_csv(raw/'병원_인허가_20261017.csv',encoding='cp949',dtype=str);print('status',h['영업상태명'].value_counts().to_dict());print('active types',h[h['영업상태코드']=='01']['업태구분명'].value_counts().to_dict())
h=h[h['영업상태코드']=='01'].copy();h['x']=pd.to_numeric(h['좌표정보(X)'],errors='coerce');h['y']=pd.to_numeric(h['좌표정보(Y)'],errors='coerce');print('missing_coords',h[['x','y']].isna().any(axis=1).sum());h=h.dropna(subset=['x','y']);tr=Transformer.from_crs(5174,4326,always_xy=True);h['lon'],h['lat']=tr.transform(h.x.to_numpy(),h.y.to_numpy());h=h.rename(columns={'관리번호':'hospital_id','사업장명':'name','업태구분명':'kind','도로명주소':'address','인허가일자':'approval_date'})
h[['hospital_id','name','kind','address','approval_date','lon','lat']].to_csv(out/'data'/'hospitals.csv',index=False);print('general hospitals',h[h.kind=='종합병원'][['name','lon','lat']].head().to_string(index=False))
