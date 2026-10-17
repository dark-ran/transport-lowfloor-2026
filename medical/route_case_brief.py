"""Concise evidence briefs for the best-documented allocated route examples.

This is a descriptive ordered-stop audit with straight-line endpoints; it is
neither an accessible pedestrian-route analysis nor a validated timed trip.
"""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parent


def format_leg(value):
    if pd.isna(value) or not value:
        return "확인 안 됨"
    x=json.loads(value)
    if not x:
        return "확인 안 됨"
    return (f"{x['board']} (순서 {x['board_seq']}) → "
            f"{x['alight']} (순서 {x['alight_seq']}); "
            f"양 끝 직선반경 {x['origin_straight_m']:.0f}m / "
            f"{x['destination_straight_m']:.0f}m")


def main():
    out=ROOT/"results"
    pilot=pd.read_csv(out/"cap5_route_pilot_candidates.csv",dtype={"route":str,"dong_code":str})
    marginal=pd.read_csv(out/"cap5_route_marginal_pairs.csv",dtype={"route":str,"dong_code":str,"hospital_id":str})
    if pilot.empty:
        (out/"route_case_brief.md").write_text(
            "# 추천 노선 제한적 정적 경로 점검\n\n기존 자료에서 분석 가능한 양방향 사례가 확인되지 않았다.\n",encoding="utf-8")
        return
    sums=marginal.groupby("route",as_index=False).population_weighted_pair_loss.sum()
    lookup=marginal.groupby(["route","dong_code","hospital_name"],as_index=False).agg(
        pair_weighted_loss=("population_weighted_pair_loss","sum"),
        pair_index_loss=("index_loss_without_route","max"))
    data=pilot.merge(lookup,left_on=["route","dong_code","hospital"],
                     right_on=["route","dong_code","hospital_name"],how="left")
    data["pair_weighted_loss"]=data.pair_weighted_loss.fillna(0)
    data["headway_numeric"]=pd.to_numeric(data.weekday_published_route_headway_min,errors="coerce")
    data=data[(data.both_directions==True)&data.headway_numeric.gt(0)].copy()
    data=data.sort_values(["pair_weighted_loss","route","dong_code"],ascending=[False,True,True])
    data=data.drop_duplicates("route").head(3)
    lines=[
        "# 추천 배분 노선의 의료시설 왕복 경로 — 기록 기반 사례",
        "",
        "분산형 5대 정책에서 지수에 실제로 기여하는 노선–동–병원 조합을 한 노선 제외 반사실 비교로 식별한 뒤,"
        " 보관된 2026-10-17 노선 스냅샷으로 양방향 정류장 순서가 확인된 사례를 선택했다.",
        "동마다 제공하는 두 정류장까지의 거리는 **직선거리**이므로 실제 보행 경로·경사·횡단·접근성을 의미하지 않는다.",
        "",
        "| 노선 | 출발 행정동 / 병원 | 가상 교체대수 | 보유율(기존→가상) | 2026 일반 평일 공시배차 |",
        "|---|---|---:|---:|---:|"
    ]
    for row in data.itertuples():
        lines.append(f"| {row.route} | {row.gu} {row.dong} / {row.hospital} | {row.added_in_model} | "
                     f"{row.static_lowfloor_ratio_before:.1%} → {row.static_lowfloor_ratio_after:.1%} | "
                     f"{row.headway_numeric:g}분 |")
    lines += ["","## 방향별 노선 순서와 모델 기여"]
    for row in data.itertuples():
        lines += [
            "",
            f"### {row.route}번 — {row.dong} / {row.hospital}",
            f"- 병원행: {format_leg(row.outbound_leg)}",
            f"- 귀가행: {format_leg(row.return_leg)}",
            f"- 이 노선의 가상 교체를 취소하고 다른 배분은 고정하면 해당 동–병원 쌍의 정적 지수가 "
            f"{row.pair_index_loss:.5f}만큼 감소한다. 다른 노선과 중첩될 수 있어 기여량을 합산하지 않는다.",
            f"- 노선 평일 공시 배차: {row.headway_numeric:g}분. **저상버스 전용 배차가 아니다.**"
        ]
    lines += [
        "", "## 해석의 한계",
        "- 2025-04-25 노선별 차량 구성과 2026-10-17 취득 일반 공시 배차를 섞은 정적 비교이며 동일 시점의 운행 실태가 아니다.",
        "- 정류장 방향 순서만 검증했다. 시간표 연속성, 실시간 운행, 차량별 저상버스 여부, 탑승 성공률은 확인하지 않았다.",
        "- 500m 직선반경은 보행로 길이, 휠체어 접근성, 횡단보도, 병원 출입문 또는 귀가 중 대기를 검증하지 않는다.",
        "- 선정 사례는 기존 69개 노선 조회 범위 내에 있다. 전체 서울시 추천 노선 중 대표 표본이라고 주장하지 않는다.",
        "- 이 결과로 실제 의료 접근시간 절감이나 사업 집행 가능성을 단정하지 않는다.",
        "", "자료: 서울시 2025 저상버스 보유율, 2026-10-17 취득 서울교통빅데이터플랫폼 노선정보·TOPIS 순서 스냅샷.",
    ]
    path=out/"route_case_brief.md"
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(path.name, "documented cases",len(data),", routes:",data.route.tolist())


if __name__=="__main__":
    main()
