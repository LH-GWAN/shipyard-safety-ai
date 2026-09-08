# YardGuard 규칙 명세

이 문서는 `data/rules.json`과 `backend/app/domain/rules.py`에 구현된 규칙의 입력조건, 예외, 등급, evidence와 테스트 사례를 기록한다.
모든 규칙은 검토 보조 규칙이며, 법적 판정이나 작업허가 승인 기준이 아니다.

## 0. 규칙 구성과 근거

현재 구현은 **경보를 생성하는 규칙 6개(R001~R003, R101~R103)와 입력 검증 규칙 1개(R104)** 로 이루어져 있다.
`rule_type` 필드로 둘을 구분하며, `GET /api/rules`는 `alert_rule_count`와 `input_validation_rule_count`를 함께 반환한다.

> 제출 계획서에 "안전규칙 10~15개"라고 기재되어 있다면 현재 구현(경보 6 + 검증 1)과 다르다.
> 근거와 입력 필드가 확보된 규칙만 구현했으며, 숫자를 맞추기 위해 규칙을 추가하지 않았다. 나머지는 4절의 확장 후보로만 둔다.

근거 조문은 2026-09-06에 국가법령정보센터 공개 API로 현행 법령(산업안전보건기준에 관한 규칙,
고용노동부령 제450호, 시행 2025-09-01)의 조문 번호·제목·본문을 확인했다.

```bash
curl "https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST=273603&type=XML"
```

| 규칙 | 근거 조문 | 조문 제목 |
|---|---|---|
| R001 | 제241조제2항제3호·제5호, 제232조제1항 | 화재위험작업 시의 준수사항 / 폭발 또는 화재 등의 예방 |
| R002 | 제232조제1항·제2항, 제241조제2항제5호 | 폭발 또는 화재 등의 예방 / 화재위험작업 시의 준수사항 |
| R003 | 제241조제2항제3호, 제241조의2제1항 | 화재위험작업 시의 준수사항 / 화재감시자 |
| R101 | 제619조의2제1항, 제619조제1항 | 산소 및 유해가스 농도의 측정 / 밀폐공간 작업 프로그램의 수립·시행 |
| R102 | 제620조제1항 | 환기 등 |
| R103 | 제623조제1항 | 감시인의 배치 등 |
| R104 | 없음 | 내부 입력 검증 규칙 |

인용 조문은 사업주의 안전조치 의무를 정한 것이지만, **YardGuard의 경보는 법 위반 판정이 아니다.**
각 규칙에는 `requires_site_validation=true`가 표시되며, 현장 적용 전 회사 기준으로 재검증해야 한다.
검증은 `backend/tests/test_rules_catalog.py`가 수행한다.

## 1. 공통 계산 규칙

### 1.1 시간 중첩

```
overlaps(a, b) = a.start_at < b.end_at AND b.start_at < a.end_at
```

- 구간은 `[start_at, end_at)`로 처리한다. A의 종료시각과 B의 시작시각이 같으면 중첩이 아니다.
- 중첩 구간은 `max(start_at) ~ min(end_at)`이며, `overlap_minutes`는 내림한 분 단위 값이다.
- 구현: `backend/app/domain/overlap.py`

### 1.2 공간 관계

| 값 | 의미 | 공간 중첩 |
|---|---|---|
| `SAME` | 동일 구역 | 예 |
| `ADJACENT` | 인접 구역 | 예 |
| `UNRELATED` | 무관한 구역 | 아니오 |

- 인접관계는 항상 양방향으로 정규화한다. `data/zones.json`에서 A가 B를 인접구역으로 선언하면 B의 목록에 A가 없어도 인접으로 본다.
- 자기 자신을 인접구역으로 선언하거나, 존재하지 않는 구역 ID를 참조하면 시작 시점에 데이터 오류로 처리한다.
- 구현: `backend/app/domain/zones.py`

### 1.3 결정성

규칙 엔진은 현재시각, 무작위값, LLM 응답을 판정에 사용하지 않는다. 동일한 입력에는 항상 같은 경보와 같은 정렬 결과가 나온다.

## 2. 작업쌍 규칙

세 규칙 모두 **시간 중첩 = true**이고 **공간 관계가 SAME 또는 ADJACENT**인 경우에만 성립한다.

### R001 화기작업과 도장작업 충돌

- 입력조건: 한 작업이 `HOT_WORK`, 다른 작업이 `PAINTING`
- 등급: `HIGH`
- 예외: 두 작업이 모두 `HOT_WORK`이거나 공간 관계가 `UNRELATED`이면 생성하지 않는다.
- evidence: `work_items[]`(id, title, work_type, zone_id, zone_name, start_at, end_at, uses_flammable_material), `spatial_relation`, `overlap_start`, `overlap_end`, `overlap_minutes`
- 권고문: 시간 분리 또는 구역 분리 검토, 불가피한 경우 현장 안전관리자의 추가 통제조치 확인
- 테스트: `tests/test_rules_pair.py::test_r001_same_zone_positive`, `test_r001_adjacent_zone_positive`, `test_r001_negative_when_zones_unrelated`, `test_r001_negative_on_boundary_touch`

### R002 화기작업과 유기용제 작업 충돌

- 입력조건: 한 작업이 `HOT_WORK`, 다른 작업이 `SOLVENT_WORK`
- 등급: `HIGH`
- evidence/권고문: R001과 동일한 구조
- 테스트: `tests/test_rules_pair.py::test_r002_positive_and_negative`

### R003 화기작업과 가연성 물질 사용 작업 충돌

- 입력조건: 한 작업이 `HOT_WORK`이고 상대 작업의 `uses_flammable_material`가 `true`
- 등급: `HIGH`
- 예외 1: 상대 작업이 `PAINTING` 또는 `SOLVENT_WORK`여서 같은 작업쌍에 R001 또는 R002가 성립하면 R003은 생성하지 않는다(중복 억제).
- 예외 2: `uses_flammable_material`가 `null`(미입력) 또는 `false`(미사용으로 입력)이면 성립하지 않는다.
- evidence: R001의 필드에 더해 `flammable_work_item_id`
- 테스트: `tests/test_rules_pair.py::test_r003_positive_with_flammable_true`, `test_r003_negative_when_flammable_null_or_false`, `test_r003_suppressed_when_r001_applies`, `test_r003_suppressed_when_r002_applies`

## 3. 단일 작업 규칙(밀폐공간)

`work_type = CONFINED_SPACE`인 작업에만 적용하며, 각 규칙은 해당 필드가 `true`가 아닐 때 성립한다.
`null`(정보 미입력)과 `false`(미실시·미확인으로 입력)는 서로 다른 메시지를 사용한다.

| 규칙 | 필드 | null 메시지 | false 메시지 | 등급 |
|---|---|---|---|---|
| R101 | `gas_measurement_completed` | 가스측정 여부가 입력되지 않았습니다. | 가스측정 미실시로 입력되었습니다. | HIGH |
| R102 | `ventilation_confirmed` | 환기 확인 여부가 입력되지 않았습니다. | 환기 미확인으로 입력되었습니다. | HIGH |
| R103 | `watcher_assigned` | 감시인 배치 여부가 입력되지 않았습니다. | 감시인 미배치로 입력되었습니다. | HIGH |

- evidence: `work_item_id`, `title`, `work_type`, `zone_id`, `zone_name`, `start_at`, `end_at`, `field`, `value`, `value_state`(`MISSING` 또는 `DECLARED_FALSE`)
- 세 항목이 모두 미입력이면 R101, R102, R103 세 건이 각각 생성된다.
- 테스트: `tests/test_rules_confined.py`

### R104 밀폐공간 시간정보 오류

- 시작·종료시각이 없거나 `end_at <= start_at`인 입력은 저장 및 분석 입력 검증 단계에서 차단한다(`INVALID_TIME_RANGE`, `TIMEZONE_REQUIRED`).
- 분석 대상이 된 WorkItem에 대해서는 경보를 생성하지 않는다. 검증에서 걸러진 작업 수는 `AnalysisResult.invalid_work_items`로 보고한다.
- 테스트: `tests/test_api_work_items.py::test_invalid_time_range_is_rejected`, `test_naive_datetime_is_rejected`, `tests/test_api_csv.py::test_mixed_rows_keep_valid_results`

## 4. 중복 제거와 정렬

- 중복키: `rule_id` + 사전식으로 정렬된 `work_item_ids`
- 같은 중복키의 경보는 하나만 남긴다.
- 정렬: 등급(HIGH → MEDIUM → LOW) → 관련 작업 중 가장 이른 `start_at` → `rule_id` → `work_item_ids`
- `Alert.id`는 `analysis_id`와 중복키의 SHA-1 해시로 만들어 테스트에서 재현할 수 있다(`AL_` 접두사).
- 테스트: `tests/test_rules_ordering.py`

## 5. 시간 변경안(규칙형)

- 대상: 두 작업의 시간이 겹친 경보(`work_item_ids` 길이가 2)
- 입력: `alert_id`, `move_work_item_id`, `buffer_minutes`(기본 30, 허용 0~240)
- 계산: 새 `start_at` = 상대 작업 `end_at` + buffer, 새 `end_at` = 새 `start_at` + 기존 duration
- 미리보기는 원본을 변경하지 않고 변경 전후 값, 해소 경보, 신규 경보, 적용 전후 경보 수를 반환한다.
- 적용 시 `preview_token`은 **필수**다. 값이 없거나 빈 문자열이면 422로 거절하고, 현재 상태와 일치하지 않으면
  `STALE_SCHEDULE_PREVIEW`(409)로 거절한다. 두 경우 모두 데이터베이스를 변경하지 않는다.
- 토큰은 경보 ID, 이동 작업, 기준 작업, buffer, 두 작업의 현재 시각으로 만들기 때문에 어느 하나라도 바뀌면 만료된다.
- 이 기능은 단순 규칙 계산이며 일정 최적화나 AI 추천이 아니다.
- 테스트: `tests/test_domain_schedule.py`, `tests/test_api_schedule.py`, `tests/test_api_schedule_token.py`

## 5.1 확장 후보 (현재 미구현)

아래는 **구현되지 않은 확장 후보**다. 현재 입력 스키마에 필요한 필드가 없어 구현하지 않았고,
문서·화면 어디에서도 구현된 기능처럼 표시하지 않는다.

| 확장 후보 | 추가로 필요한 입력 | 상태 |
|---|---|---|
| 고소작업과 상부·하부 동시작업 충돌 | 작업 높이/층 정보 | 미구현 |
| 중량물 인양구역과 통행 작업 충돌 | 인양 반경, 통행 경로 | 미구현 |
| 밀폐공간 작업시간 중 안전조치 재확인 | 측정·환기 시각 이력 | 미구현 |
| 동일 구역 내 복수 점화원 작업 | 점화원 유형·수량 | 미구현 |
| 작업허가 유효시간 초과 | 허가 발행·만료 시각 | 미구현 |
| 위험물 사용 작업의 안전조치 정보 누락 | 위험물 종류, 취급 안전조치 필드 | 미구현 |

새 규칙을 구현하려면 다음을 모두 갖춰야 한다: 입력 필드 정의, 판정 조건, 경보 메시지, 권고 확인사항,
공식 또는 공개 안전자료 근거, 양성·음성·경계값 테스트, `data/expected_alerts.json` 반영.

## 6. 합성 데이터 기대 결과

`data/expected_alerts.json`에는 19건의 기대 경보와 7건의 음성 시나리오가 기록되어 있다.
`tests/test_expected_alerts_dataset.py`와 `tests/test_api_analysis.py::test_full_dataset_analysis_matches_expected_alerts`가
누락 경보 0건, 예상하지 않은 추가 경보 0건임을 검증한다.
