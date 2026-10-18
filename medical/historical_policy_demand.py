"""Reproduce 3/5/7-route-cap transit-card demand screening (not causal impact).

Input: official Seoul May 2025/May 2026 CP949 CSV downloads.
Usage: python medical/historical_policy_demand.py --may-2025 A.csv --may-2026 B.csv
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

POLICIES=('screened_cap_3','screened_cap_5','screened_cap_7')
HOURS=range(24)
BOARD=[f'{h:02d}' if h==0 else str(h) for h in HOURS]
BOARD=[h+'시승차총승객수' for h in BOARD]
ALIGHT=[f'{h:02d}' if h==0 else str(h) for h in HOURS]
ALIGHT=[h+'시하차총승객수' for h in ALIGHT]


def allocation(path):
    policies={p:{} for p in POLICIES}
    with open(path,encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['policy'] not in policies:continue
            p=r['policy'];route=r['route']
            added,fleet,low=(int(r[k]) for k in ('added','fleet','low_before'))
            if route in policies[p] or not(0<=low<fleet and 1<=added<=fleet-low):
                raise ValueError('Invalid allocation '+str(r))
            policies[p][route]=(added,fleet)
    if [len(policies[p]) for p in POLICIES]!=[22,15,12] or any(sum(n for n,f in v.values())!=50 for v in policies.values()):
        raise ValueError('Expected original 22/15/12 routes and 50 slots each')
    return policies


def extract(path,year,routes):
    data={r:dict(board=0,mid=0,hosp=0,hosp_mid=0,stops=defaultdict(int),rows=0,hosp_stops=set()) for r in routes}
    with open(path,encoding='cp949',newline='') as f:
        reader=csv.DictReader(f)
        if not {'사용년월','노선번호','표준버스정류장ID','역명',*BOARD,*ALIGHT}.issubset(reader.fieldnames):
            raise ValueError('Invalid CSV schema')
        for row in reader:
            if row['사용년월']!=str(year)+'05':raise ValueError('Wrong year/month')
            route=row['노선번호'].strip()
            if route not in data:continue
            b=[int(row[k]) for k in BOARD];a=[int(row[k]) for k in ALIGHT]
            if min(b+a)<0:raise ValueError('Negative count')
            d=data[route];board=sum(b);mid=sum(b[10:17]);stop=row['표준버스정류장ID']
            hospital='병원' in row['역명'] and '동물병원' not in row['역명']
            d['board']+=board;d['mid']+=mid;d['rows']+=1;d['stops'][stop]+=board
            if hospital:
                d['hosp']+=board+sum(a)
                d['hosp_mid']+=sum(b[10:17])+sum(a[10:17]);d['hosp_stops'].add(stop)
    if any(not v['rows'] for v in data.values()):raise ValueError('A policy route is missing from CSV')
    return data


def build(policy,a,b):
    universe=set().union(*(v.keys() for v in policy.values()))
    denom={k:sum(v[k] for v in b.values()) for k in ('board','mid','hosp','hosp_mid')}
    denom25=sum(x['board'] for x in a.values())
    common={r:sum(b[r]['stops'][sid] for sid in a[r]['stops'].keys()&b[r]['stops'].keys()) for r in universe}
    common_total=sum(common.values())
    if not(denom['board'] and denom['mid'] and denom25 and common_total and denom['hosp'] and denom['hosp_mid']):
        raise ValueError('Empty fixed denominator')
    result=[]
    for name in POLICIES:
        r=policy[name]
        weighted=lambda getter:sum(getter(route)*added/fleet for route,(added,fleet) in r.items())
        row={
            'policy':name,'allocated_routes':len(r),'replacements':sum(added for added,fleet in r.values()),
            'selected_route_boardings_2026':sum(b[route]['board'] for route in r),
            'fixed_universe_boardings_2025':denom25,'fixed_universe_boardings_2026':denom['board'],
            'route_demand_coverage_pct':sum(b[route]['board'] for route in r)/denom['board']*100,
            'demand_weighted_gain_pp':weighted(lambda x:b[x]['board'])/denom['board']*100,
            'demand_weighted_gain_2025_pp':weighted(lambda x:a[x]['board'])/denom25*100,
            'midday_demand_weighted_gain_pp':weighted(lambda x:b[x]['mid'])/denom['mid']*100,
            'hospital_name_stop_activity_weighted_gain_pp':weighted(lambda x:b[x]['hosp'])/denom['hosp']*100,
            'hospital_name_stop_midday_weighted_gain_pp':weighted(lambda x:b[x]['hosp_mid'])/denom['hosp_mid']*100,
            'same_stop_2026_demand_weighted_gain_pp':weighted(lambda x:common[x])/common_total*100,
            'selected_routes_with_named_hospital_stop':sum(bool(b[route]['hosp_stops']) for route in r),
            'data_quality_notes':'SEE_METHOD_LIMITS'
        }
        result.append(row)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--may-2025',type=Path,required=True)
    p.add_argument('--may-2026',type=Path,required=True)
    p.add_argument('--allocations',type=Path,default=Path(__file__).resolve().parent/'results/cap_allocations.csv')
    p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'results/historical_ridership')
    args=p.parse_args()
    policies=allocation(args.allocations)
    union=set().union(*(x.keys() for x in policies.values()))
    a=extract(args.may_2025,2025,union);b=extract(args.may_2026,2026,union)
    result=build(policies,a,b)
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'may_policy_demand_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
