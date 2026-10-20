# 재현 명령과 입력 범위

저장소 루트에서 Python 3.12와 requirements.txt 의존성을 사용한다. 아래 명령은 실제 API를 호출하지 않는다. 출력은 medical/data와 medical/results에 다시 생성되므로 검토 시 별도 체크아웃에서 실행할 수 있다.

```sh
python -m pip install -r requirements.txt
python medical/reproduce_all.py
```

이 명령은 기초 정적 배분·사례·배차·민감도·V3·V4·V5 지도·V6, 교체가능성 검토, V10 조건부 대기시간, V11 정적 GIS, V13 보존 관측 검사, V14 역사 원자료 재계산, 전체 회귀시험과 검증 영수증을 실행한다. V14는 medical/raw/vehicle_history_20261018의 고정 원본을 검증한다. 최신 누적 observations를 과거 해시와 비교하지 않는다.

## 외부 월별 원본 CSV를 포함하는 재현

서울시 버스노선별 정류장별 시간대별 승하차 인원 정보의 2025년 5월·2026년 5월 원본 CP949 CSV가 필요하다. 배포되지 않은 파일을 이미 포함된 것으로 취급하지 않는다.

```sh
python medical/reproduce_all.py --may-2025 /absolute/path/202505.csv --may-2026 /absolute/path/202605.csv
```

이 옵션은 월별 수요·공간 비교, V5 시점 연결, V8 명칭 변형 민감도, V9 계보, V11 23개 노선 원본 승차량 재계산도 실행한다. 옵션이 없으면 이 경로는 SKIPPED로 표시한다. 주요 공간 비교만 확인하려면:

```sh
python medical/historical_policy_spatial_v3.py --may-2025 /absolute/path/202505.csv --may-2026 /absolute/path/202605.csv --output /absolute/path/audit
```

## 실행으로 대체할 수 없는 자료

V7 제출 문안과 V12 현장 기록 규칙은 새 관측을 생성하는 분석기가 아니다. V12 검증 함수와 V13 현장 등록 규칙은 전체 회귀시험에 포함된다. V12 새 GIS 취득 스크립트는 네트워크 작업이므로 오프라인 재현에 포함하지 않는다. 공개 API 관측 수집·암호화 보관은 별도의 GitHub 워크플로이며 위 명령에서 실행하지 않는다. 최신 관측의 정책 게이트 판정은 observations/policy_observed_evidence.csv에서 확인한다.

과거 배포 문안과 버전 기록은 development_history_through_v14.md에 보존한다. 현재 결론은 README와 current_evidence.md를 기준으로 읽는다.

## 공간 비교표와 V11 검산의 필드 계약

`boardings_geolinked_2026`은 해당 노선의 정적 정류장 ID에 연결된 승차량이며 병원 거리 제한이 없다. `general_hospital_800m_activity`는 병원 800m 내 승차+하차 합계다. V11이 검산하는 `general_hospital_800m_boardings`는 같은 거리 범위의 승차만 포함한다. 공간 비교 생성기가 이 마지막 필드를 별도로 출력하며 V11은 그것만 비교한다. 과거 오표기 열 이름을 새 ID 연결량으로 단순 치환하지 않는다. 명시적 승차 필드가 없으면 공간표 재생성을 요구하며 중단한다.

V6의 과거 오표기 비교는 `medical/raw/v3_legacy_spatial_evidence.csv`에 보존한 과거 표를 사용한다. 새 공간표가 생성된 뒤 재실행해도 역사 비교의 분모·의미가 바뀌지 않는다.
