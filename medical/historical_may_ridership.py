"""Reproduce 15-route May transit-card ridership comparison from two Seoul CSVs.

Usage: python medical/historical_may_ridership.py --may-2025 2025.csv --may-2026 2026.csv
Source: https://data.seoul.go.kr/dataList/OA-12913/F/1/datasetView.do
These are all-bus passenger counts, not low-floor, elderly, or wheelchair journeys.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

ROUTES = ('343','662','1124','1213','1222','3212','3319','3323','3413','5413','5611','6620','6629','6648','7211')
COLS = [(f'{hour:02d}' if hour == 0 else str(hour)) + f'시{kind}총승객수'
        for hour in range(24) for kind in ('승차','하차')]
FIELDS = ('route','proposed_replacements','2025_fleet','2025_lowfloor','2025_rows','2026_rows',
          '2025_boardings','2026_boardings','2025_common_stop_boardings','2026_common_stop_boardings',
          '2025_midday_boardings','2026_midday_boardings','comparison_warning')


def load(path, month):
    totals = {route: {'rows': 0, 'boarding': 0, 'midday': 0,
                      'stop_boarding': defaultdict(int)} for route in ROUTES}
    with open(path, newline='', encoding='cp949') as f:
        reader = csv.DictReader(f)
        if not {'사용년월','노선번호','표준버스정류장ID',*COLS}.issubset(reader.fieldnames):
            raise ValueError('CSV schema mismatch')
        for row in reader:
            if row['사용년월'] != month:
                raise ValueError('Incorrect month or mixed months')
            route = row['노선번호'].strip()
            if route not in totals:
                continue
            values = [int(row[k].replace(',', '')) for k in COLS]
            if min(values) < 0:
                raise ValueError('Negative passenger count')
            boarding = sum(values[::2])
            item = totals[route]
            item['rows'] += 1
            item['boarding'] += boarding
            item['midday'] += sum(values[2*h] for h in range(10,17))
            item['stop_boarding'][row['표준버스정류장ID']] += boarding
    if not all(item['rows'] for item in totals.values()):
        raise ValueError('At least one of the 15 target routes is absent')
    return totals


def digest(path):
    sha = hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def compute(a, b, gates):
    results = []
    for route in ROUTES:
        x,y = a[route],b[route]
        common = x['stop_boarding'].keys() & y['stop_boarding'].keys()
        xc = sum(x['stop_boarding'][s] for s in common)
        yc = sum(y['stop_boarding'][s] for s in common)
        d_all = (y['boarding']/x['boarding']-1)*100
        d_common = (yc/xc-1)*100
        flags=[]
        if abs(y['rows']-x['rows'])/x['rows'] >= .2:
            flags.append('ROW_COUNT_SHIFT_GE_20PCT')
        if abs(d_all-d_common) >= 5:
            flags.append('CHANGE_ESTIMATE_SENSITIVE_TO_STOP_SET_GE_5PP')
        if min(xc/x['boarding'],yc/y['boarding']) < .9:
            flags.append('COMMON_STOP_BOARDING_COVERAGE_LT_90PCT')
        g=gates[route]
        results.append((route,g['proposed_replacements'],g['2025_fleet'],g['2025_lowfloor'],
                        x['rows'],y['rows'],x['boarding'],y['boarding'],xc,yc,x['midday'],y['midday'],
                        ';'.join(flags) if flags else 'NONE'))
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--may-2025', required=True, type=Path)
    parser.add_argument('--may-2026', required=True, type=Path)
    parser.add_argument('--gates', type=Path, default=Path(__file__).resolve().parent/'results/v4_implementation_gates.csv')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent/'results/historical_ridership')
    args=parser.parse_args()
    with args.gates.open(encoding='utf-8-sig',newline='') as f:
        gates={r['route']:{k:int(r[k]) for k in ('proposed_replacements','2025_fleet','2025_lowfloor')}
               for r in csv.DictReader(f)}
    if set(gates) != set(ROUTES) or sum(x['proposed_replacements'] for x in gates.values()) != 50:
        raise ValueError('Expected unchanged V4 15 routes and 50 replacement slots')
    rows=compute(load(args.may_2025,'202505'),load(args.may_2026,'202605'),gates)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    with (args.output_dir/'may_route_simplified_reproduced.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(FIELDS);writer.writerows(rows)
    print(json.dumps({'status':'PASS','route_count':len(rows),'boarding_2025':sum(r[6] for r in rows),
                      'boarding_2026':sum(r[7] for r in rows),'sha256_2025':digest(args.may_2025),
                      'sha256_2026':digest(args.may_2026)},ensure_ascii=False))


if __name__ == '__main__': main()
