# 자동 차량유형 관측 운영

GitHub Actions의 `Scheduled 15-route vehicle evidence`은 서울시 공식 버스위치 API를 사용해 `raw/vehicle_candidate_route_ids.json`의 15개 후보 **전체 노선**을 기본으로 각각 1회 조회한다. 반복 클릭하지 않아도 자동으로 실행된다.

## 기본 실행 일정 (Asia/Seoul, UTC+9)

- 평일(월~금) 08시·10시·14시·17시대의 00·05·10·15·20·25분
- 주말(토·일) 10시·16시대의 00·05·10·15·20·25분

실제 GitHub 스케줄러는 UTC를 사용하고 정시 보장 없이 지연·누락될 수 있다. 자동 실행은 `scope=full`; 필요하면 Actions → `Scheduled 15-route vehicle evidence` → `Run workflow`에서 `section`을 수동 선택해 구간별 관측을 추가할 수 있다. `SEOUL_BUS_API_KEY` Secret 미설정 시 API를 호출하지 않고 건너뛴다.

## 수집·보관 범위

- 한 번 실행 시 API 전체 노선 조회 15건, 예정대로 모두 실행될 때 평일 하루 360건, 주말 하루 180건(실패 시 재시도 없음). 사용자가 제시한 상세기능 호출 한도 1,000회/일보다 적다.
- GitHub Actions는 요청 당시 발급 인증키를 Secret으로 사용한다. 코드는 Secret 값이나 차량 ID를 Git에 추가하지 않는다.
- 각 실행의 **공개 가능한 집계치만** `observations/vehicle/aggregate-실행번호-시도번호.json`으로 보존한다. 원본 차량 ID·번호판·가명차량 ID·API 키는 포함하지 않는다. `observations/vehicle_timeseries.csv`는 이 파일들을 다시 읽어 누적 생성한다.
- GitHub 실행별 별도 집계 ZIP은 30일 보관 후 만료될 수 있지만, Git에 커밋한 공개 집계는 남는다. 저장소가 공개라면 이 집계도 공개된다.
- `successful_requests=0`이어도 워크플로가 성공 표시될 수 있으므로 반드시 데이터의 `status`를 확인한다. 실패·빈 응답은 운행 부재 증거가 아니다.

## 결과 해석

한 시점에 관측된 차량 유형 수는 실제 정류소 도착, 차량 탑승 성공, 대기시간, 평균 저상 배차간격의 직접 관측값이 아니다. 동일 차량이 여러 시점에 재관측될 수 있으므로 서로 다른 시점의 차량 수를 합산하여 고유 운행차량 대수라고 주장하지 않는다. 집계는 시간대별 **관측 구성 변화** 비교용이며 실제 저상버스 정책 효과 인과 추정으로 해석하지 않는다.

## 중단·변경

자동 수집은 `.github/workflows/vehicle-capture.yml`의 `schedule` 항목을 수정하거나 GitHub Actions 화면에서 `Disable workflow`를 선택해 중단할 수 있다. GitHub는 비활성 공개 저장소의 scheduled workflows를 장기간 활동이 없으면 자동 비활성화할 수 있다.
