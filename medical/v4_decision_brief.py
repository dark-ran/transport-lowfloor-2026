"""Build V4 judging brief from verified outputs, not manually copied claims."""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parent


def generate(out):
    caps=pd.read_csv(out/"cap_equity_summary.csv").set_index("policy")
    direction=json.loads((out/"v4_directional_metadata.json").read_text(encoding="utf-8"))
    gate=json.loads((out/"v4_implementation_metadata.json").read_text(encoding="utf-8"))
    v3=json.loads((out/"v3_denominator_metadata.json").read_text(encoding="utf-8"))
    n=direction["status_counts"]
    lines=[
        "# 저상버스 교체 50대: 의료 연결의 사전 검토와 실행 조건",
        "",
        "> **모형 분석 결과이며 실제 저상버스 탑승·대기·병원 접근성 개선의 실증 결과는 아니다.**",
        "",
        "## 1. 제한된 50대를 어디에 우선 검토할 것인가",
        "",
        "| 정책 | 노선당 상한 | 공급지수 증가 | 개선 동 | 지수 0.05 이상 개선 동 |",
        "|---|---:|---:|---:|---:|"
    ]
    for name,c in [("screened_cap_3",3),("screened_cap_5",5),("screened_cap_7",7)]:
        r=caps.loc[name]
        lines.append(f"| 분산형 | {c}대 | {r.base_delta_index:.6f} | {int(r.changed_dongs)} | {int(r.changed_dongs_ge_0p05)} |")
    lines+= [
        "",
        "50대는 구매 금액이 아니라 모형의 **가상 차량 교체 슬롯**이다. "
        "상한 3·5·7대 중 어느 대안이 현장에 적합한지는 차량별 차령·운수사·차고지·비용 검증이 필요하다.",
        "",
        "## 2. 교체로 완화될 수 있는 지역과 다른 정책이 필요한 지역",
        "",
        f"- 동–병원 모델 쌍: **{v3['input_model_pairs']:,}개**. "
        f"그중 정적 공유노선 없는 쌍: **{next(int(x['pairs']) for x in v3['pair_classes'] if x['class']=='no_shared_route')}개**.",
        f"- 모델 정의 내 가까운 종합병원 3곳 모두와 공유노선이 없는 행정동: "
        f"**{v3['all_three_nearest_hospital_pairs_without_shared_route_dongs']}개**.",
        "",
        "공유노선이 없는 모델 쌍은 노선의 차량 유형을 변경하는 것으로 지수가 개선되지 않는다. "
        "반대로 실제 교통망에서 철도·환승·다른 정류장·병원 선택을 이용할 수 있을 가능성은 남아 있다.",
        "",
        "## 3. 선택한 15개 노선의 증거 수준",
        "",
        f"- 공시 일반 평일 배차와 노선 일치: **{gate['published_nominal_headway_routes']}/{gate['allocated_routes']}개**.",
        f"- 과거 69개 노선 스냅샷에서 방향별 정류소 순서 분석 가능: "
        f"**{gate['snapshot_route_order_routes']}/{gate['allocated_routes']}개**.",
        f"- 최소 한 개 동–병원 쌍에서 병원행·귀가행 순서 확인: "
        f"**{gate['at_least_one_bidirectional_example_routes']}/{gate['allocated_routes']}개**.",
        f"- 전체 모형상 해당 노선에 기여하는 **{direction['model_attributable_pairs']}개 동–병원–노선 쌍** 중 "
        f"양방향 정적 순서 확인 {int(n.get('bidirectional',0))}개, "
        f"한쪽 방향만 {int(n.get('one_direction',0))}개, "
        f"기존 스냅샷에서 직접 경로 없음 {int(n.get('no_ordered_direct_in_snapshot',0))}개, "
        f"노선 자체가 스냅샷에 없음 {int(n.get('not_in_69_route_snapshot',0))}개.",
        "",
        f"- 현재 확인된 실제 차량별 교체 적격성·접근 보행로·가격·개별 저상버스의 양방향 통과 검증: "
        f"**{gate['field_verified_operational_approvals']}개 노선 승인**.",
        "",
        "결론: **15개 모두 후보 노선이며 즉시 집행 승인된 노선은 없다.** "
        "정류장 순서 검증은 시간표 연속성·휠체어 탑승·병원 진료시간 검증과 다르다.",
        "",
        "## 4. 실제 운행 확인을 위한 검증 가능한 수집 단계",
        "",
        "서울시 버스위치정보조회 서비스는 공개 명세에서 차량유형 `busType` "
        "(0=일반, 1=저상)을 안내한다. 서비스키가 있는 경우 `v4_vehicle_snapshot.py --capture`로 "
        "**실제 위치 조회 응답의 차량 유형**을 수집할 수 있다. "
        "기본 `python medical/v4_vehicle_snapshot.py`는 API 호출 없는 manifest 점검이다.",
        "",
        "중요하게도 차량 위치의 단일 스냅샷은 정류장 실제 도착, 이용자가 탑승할 수 있었는지, "
        "저상차량 운행간격·대기시간을 나타내지 않는다. 오류와 결측을 '버스가 없었다'로 해석하면 안 된다. "
        "차량 ID는 로컬 비밀값으로 가명처리하며 인증키와 원시 차량번호는 GitHub에 저장하지 않는다.",
        "",
        "## 5. 다음 현장 결정 게이트",
        "",
        "1. **데이터 확보:** 3개 대표노선 662·343·3413의 같은 날짜 병원행/귀가행 차량유형·운행시각 수집",
        "2. **접근성:** 실제 출발지–정류소–병원 출입문 간 단차·경사·횡단 및 휠체어 이동경로 확인",
        "3. **적격 차량:** 노선별 차령·차종·대폐차 일정과 공식 예외 여부 재확인",
        "4. **비용·운영:** 차량 및 유지비·운수사/차고지 운행제약 확인",
        "5. **정책 비교:** 3·5·7대 분산안 중 해당 자료를 충족하는 후보만 집행 가능한 대안으로 재평가",
        "",
        "## 6. 재현과 출처",
        "",
        "- `v4_directional_pairs.csv`: 모델상 기여가 있는 전체 후보 쌍의 방향별 검증 상태",
        "- `v4_implementation_gates.csv`: 15개 노선별 공식 예외·차량·운행·접근·비용·집행 적격성",
        "- `v4_capture_manifest.json`: 자료 수집 대상 명세. **실측 데이터가 아님**",
        "- `validation_v4_receipt.json`: 코드 재현·단위 테스트 이후 원자료 및 산출물 SHA 기록",
        "",
        "기초 자료 시점: 2025년 저상버스 차량·정류소·고령인구, 2026년 취득 노선정보·병원자료. "
        "명세 출처: https://www.data.go.kr/data/15000332/openapi.do.",
    ]
    (out/"v4_decision_brief.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("V4 decision brief produced",len(lines),"lines")


if __name__=="__main__":
    generate(ROOT/"results")
