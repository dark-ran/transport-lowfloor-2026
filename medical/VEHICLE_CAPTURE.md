# 실제 차량 위치 수집 — 노선 전체 기본, 구간 보조

수집 코드는 공개되어 있지만 API 키 미등록 상태에서는 실제 관측을 수행하지 않는다. 보고서·배분 분석·기존 0건 드라이런 결과를 실제 관측 결과로 바꾸지 않는다.

## GitHub에서 실행

1. [공식 API](https://www.data.go.kr/data/15000332/openapi.do)에 본인 계정으로 활용신청하고 서비스키를 발급받는다.
2. 저장소 Settings → Secrets and variables → Actions → New repository secret에 이름 `SEOUL_BUS_API_KEY`, 값은 본인 서비스키를 등록한다. 키를 코드·Issue·README·채팅에 쓰지 않는다.
3. Actions → **Manual real bus snapshot** → Run workflow에서 `scope=full`(기본) 또는 `scope=section`(보조)을 선택한다. API 미등록 시 호출하지 않고 정상 건너뛴다. 자동 일정은 [현재 자동 수집 안내](AUTOMATED_VEHICLE_OBSERVATIONS.md)를 따른다.
4. 성공 또는 API 오류 발생 시 실행 화면의 `bus-vehicle-aggregate-실행번호` 아티팩트에서 `vehicle_capture_summary.json`을 내려받는다. 제공기관 요청이 모두 실패해도 워크플로 상태는 성공일 수 있으므로 반드시 집계의 `successful_requests`를 확인한다. 오류 집계가 생성된 것을 관측 성공으로 취급하지 않는다.

기본 `scope=full`은 `raw/vehicle_candidate_route_ids.json`의 15개 후보 노선을 각각 1회, **총 15회 노선 전체** 질의한다(`getBusPosByRtid`). 정류소 구간 파라미터(`startOrd`, `endOrd`)는 전송하지 않는다. 이 관측은 병원행·귀가행 방향을 확인하지 않는다. 선택형 `scope=section`은 종전과 같이 병원행/귀가행 각 구간 **총 6회** 질의한다(`getBusPosByRouteSt`). 가명처리 salt는 실행마다 새로 생성한다. 차량 단위 JSONL은 임시 실행 환경 밖으로 올리지 않고, 차량 식별값·가명차량키가 없는 **구간별 유형 건수와 성공/빈 응답/오류 집계만** GitHub 아티팩트에 보관한다. 아티팩트 보관기간은 30일이다. 데이터와 배분 분석을 자동 수정·커밋하지 않는다.

## 로컬 실행

환경변수 `SEOUL_BUS_API_KEY`와 16자 이상의 무작위 `V4_VEHICLE_SALT`를 별도로 설정한 후 다음과 같이 실행한다.

```text
python medical/v4_vehicle_snapshot.py --scope full --capture --output <저장소 바깥의 비공개 경로>/vehicle_observations.jsonl
# 구간 보조 검사만 필요한 경우: --scope section
```

기본 명령은 기존대로 API를 호출하지 않는다. 수집 결과는 저장소의 어느 하위 경로에도 저장할 수 없다. 출력 JSONL에는 인증키·원시 차량ID·번호판을 저장하지 않는다. URL 인코딩된 키와 디코딩된 키 모두 지원한다.

## 해석과 검증 범위

- 성공한 위치 응답은 위치 스냅샷이다. 정류소 실제 도착·탑승 성공·저상차량 배차간격·실제 대기시간 증거가 아니다.
- 성공 빈 응답과 API 오류를 구분하며, 어느 쪽도 운행이 없다는 결론으로 바꾸지 않는다.
- 제공기관 성공 헤더가 없는 응답은 관측으로 수락하지 않는다.
- `test_vehicle_capture.py`는 기본 무호출·인증키 미설정·저장소 출력 금지·응답 헤더·키 인코딩·공개 집계의 식별자 제거를 모의 응답으로 검사한다. 모의 응답은 실제 관측 데이터가 아니다.

API 출처: 서울특별시 버스위치정보조회 서비스(공공저작물 출처표시 제1유형). 자세한 필드·이용조건은 위 공식 설명을 따른다.

연결 주소는 공식 안내의 `http://ws.bus.go.kr/api/rest/buspos/getBusPosByRouteSt` 를 사용한다. HTTPS로 임의 치환하지 않는다. HTTP에서는 키 전송이 암호화되지 않는다. 인증 URL·예외 메시지 전문 대신 오류 종류·HTTP 상태·제공기관 오류번호만 집계에 기록한다.

## 요청·응답 검증

공식 가이드(서울특별시_버스위치정보조회_서비스_활용가이드_20230530.docx): 노선 전체는 `http://ws.bus.go.kr/api/rest/buspos/getBusPosByRtid?ServiceKey=...&busRouteId=...`, 구간은 `getBusPosByRouteSt`에 `startOrd`·`endOrd`를 추가한다. API의 `headerCd=4`는 '노선을 찾을 수 없습니다'이며, 구간 지정 문제나 자료 시점 차이로 단정하지 않고 현재 노선 ID를 별도 확인한다. 노선 전체 관측의 `sectOrd`는 참고 필드이며 방향·정류소 탑승 입증자료가 아니다. 실제 실행 시 요청 계획은 capture receipt에 저장되어 요약기가 동일 실행의 계획을 이용한다. 오래된 체크인 드라이런 manifest를 참조하지 않는다.

주의: 공식 엔드포인트는 HTTP이고 요청 URL에 `serviceKey`가 포함되므로 전송 구간에서 키가 암호화되지 않는다. 요청 URL과 원문 예외 메시지는 저장하거나 로그에 출력하지 않는다. API 제공기관에 TLS 지원 여부를 확인하는 것이 바람직하다.
