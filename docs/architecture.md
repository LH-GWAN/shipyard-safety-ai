# YardGuard 아키텍처

## 1. 전체 구성

```
[브라우저]
   │  fetch (JSON / multipart)
   ▼
[Next.js App Router · frontend]
   app/            화면 라우팅 (대시보드, 작업 목록, 작업 등록, 분석 결과)
   features/       화면 단위 기능 컴포넌트
   components/     공통 표시 요소(제한 문구, 등급 배지, 상태 화면)
   lib/api.ts      백엔드 API 클라이언트, 오류 코드 변환
   types/domain.ts 백엔드와 공유하는 도메인 계약(enum, 응답 타입)
   │  HTTP  /api/...
   ▼
[FastAPI · backend]
   api/            라우터: 요청 파싱, 상태코드, OpenAPI 문서
   services/       응용 서비스: 검증, CSV 처리, 분석 실행, 일정 변경, LLM 구조화
   repositories/   SQLAlchemy 조회·저장
   domain/         순수 도메인: enum, 모델, 시간 중첩, 구역 그래프, 규칙 엔진, 시간 변경안
   llm/            LLMAdapter 인터페이스와 구현(mock / anthropic / openai)
   models/orm.py   DB 스키마
   │
   ▼
[SQLite 기본 · DATABASE_URL로 PostgreSQL 교체 가능]

[data/]        zones.json, work_items.csv, rules.json, expected_alerts.json (합성 데이터)
[evaluation/]  자연어 구조화 평가 체계 (합성 문장 36개, 모의/원격 러너)
[scripts/]     통합 스모크 테스트 (백엔드 + 프런트엔드 HTTP 점검)
```

## 2. 데이터 흐름

### 2.1 작업 등록 → 분석 → 경보 조회

1. 사용자가 화면(직접 입력 / CSV / 자연어)에서 작업계획을 등록한다.
2. `WorkItemService`가 표준시간대, 시간범위, 구역 존재, 작업명 공백을 검증하고 저장한다.
3. `POST /api/analysis/run`이 대상 작업을 조회한다(전체 / 날짜 / ID 목록).
4. `AnalysisService.partition()`이 분석 가능한 작업과 입력 오류 작업을 나눈다.
5. `RuleEvaluator.evaluate()`가 순수 도메인 계산으로 경보 목록을 만든다(정렬·중복 제거 포함).
6. 분석 결과와 경보를 `analyses` / `alerts` 테이블에 저장하고 `AnalysisResult`로 응답한다.
7. 화면은 요약, 타임라인, 경보 목록, 경보 상세(규칙·근거·권고)를 표시한다.

### 2.2 CSV 업로드

1. `POST /api/work-items/import-csv`는 기본값 `commit=false`(validate-only)이다.
2. 파일 크기(2MB), 행 수(1,000), 파일명·MIME, 텍스트 디코딩을 먼저 검사한다.
3. 헤더에 필수 열이 없으면 `INVALID_CSV_HEADER`(400)로 전체를 거절한다.
4. 행 단위 검증에서 오류가 나도 정상 행의 결과는 유지한다. 오류는 `row_number`(헤더=1행), `field`, `code`, `message`, `raw_value`로 반환한다.
5. `commit=true`일 때만 유효한 행을 저장하며, 기존 ID는 `overwrite=true`인 경우에만 갱신한다.

### 2.3 시간 변경안

1. `POST /api/schedule/preview-shift`가 원본을 변경하지 않고 변경 전후 값과 재분석 차이를 계산한다.
2. `preview_token`은 경보 ID, 이동 작업, 기준 작업, buffer, 두 작업의 현재 시각으로 만든 해시다.
3. `POST /api/schedule/apply-shift`는 **토큰을 필수로 요구한다.** 토큰이 없으면 422, 현재 상태와 다르면 409로 거절하며
   두 경우 모두 데이터를 변경하지 않는다. 검증을 통과한 경우에만 저장하고 전체 작업을 다시 분석한다.
4. 프런트엔드는 미리보기 결과가 있을 때만 적용 버튼을 노출하고, 이동 작업·buffer가 바뀌면 기존 미리보기와 토큰을 폐기한다.

### 2.4 자연어 구조화

1. `POST /api/work-items/parse-description`이 `LLMAdapter`를 통해 초안을 만든다.
2. `LLM_PROVIDER`와 `LLM_API_KEY`가 모두 있으면 실제 어댑터, 없으면 결정론적 모의 어댑터를 사용한다.
3. 어댑터 응답은 Pydantic(`ParsedWorkItemDraft`)으로 다시 검증하고, 허용 구역과 일치하지 않는 `zone_id`는 `null`로 되돌린 뒤 근거를 남긴다.
4. 초안은 저장하지 않는다. 사용자가 화면에서 확인·수정한 뒤 명시적으로 저장한다.
5. LLM은 위험 판정, 등급 결정, 승인에 관여하지 않는다. 경보 등급은 `data/rules.json`에 고정되어 있다.

## 3. 계층 경계

| 계층 | 위치 | 의존 대상 | 금지 사항 |
|---|---|---|---|
| 도메인 | `app/domain/` | 표준 라이브러리만 | HTTP, DB, LLM, UI 의존 |
| 저장소 | `app/repositories/` | SQLAlchemy 세션 | 규칙 판단 |
| 서비스 | `app/services/` | 도메인 + 저장소 + 어댑터 | 응답 상태코드 결정 외 프레임워크 세부사항 |
| API | `app/api/` | 서비스 | 도메인 계산 직접 수행 |

규칙 엔진(`app/domain/rules.py`)은 `WorkItemData`, `ZoneGraph`, `RuleSpec`만 입력으로 받는다.
따라서 입력 경로가 늘어나도(수기 입력, CSV, 자연어, 향후 작업허가서) 규칙 계산 코드는 바뀌지 않는다.

## 4. 현재 구현과 향후 확장 지점

### 4.1 현재 코드에 존재하는 것

| 구성요소 | 위치 | 역할 |
|---|---|---|
| `LLMAdapter` | `app/llm/base.py` | 자연어 → 구조화 초안. `MockLLMAdapter`(기본), `AnthropicAdapter`, `OpenAIAdapter` 구현 |
| `RuleEvaluator` | `app/domain/rules.py` | 결정론적 규칙 판정 |
| `ZoneGraph` | `app/domain/zones.py` | 구역 인접관계 정규화와 공간 관계 계산 |
| `CsvImportService` | `app/services/csv_service.py` | CSV 입력 경로(현재의 대량 입력 어댑터) |
| `ScheduleService` | `app/services/schedule_service.py` | 규칙형 시간 변경안 |

### 4.2 향후 작업허가서 기반 기능을 위한 경계(문서상 설계, 코드 미구현)

MVP는 실제 작업허가서를 다루지 않는다. 다만 아래 책임 경계를 지금의 구조와 맞춰 두었으므로,
비식별 문서를 확보하면 규칙 엔진과 화면을 바꾸지 않고 입력 경로만 추가할 수 있다.

| 확장 지점 | 책임 | 현재 상태 | 붙일 위치 |
|---|---|---|---|
| `WorkItemInputAdapter` | 임의 입력원을 `WorkItemCreate` 목록으로 변환 | 웹 폼과 `CsvImportService`가 그 역할을 수행 | `app/services/` |
| `TemplateMapper` | 회사별 작업허가서 서식 → 공통 `PermitDocumentDraft` | 미구현 | `app/services/permits/` |
| 문서 텍스트화(OCR/문서 파서) | PDF·이미지 → 텍스트 | 미구현(MVP 범위 밖) | `app/services/permits/` |
| `LLMAdapter` 확장 | 허가서 텍스트 → 작업종류·구역·시간·물질·안전조치 구조화 | 인터페이스 존재, 허가서용 프롬프트 미구현 | `app/llm/` |
| `ExternalScheduleImporter` | 전자 작업허가/공정관리 시스템의 일정 변경 수신 후 재검사 | 미구현 | `app/services/` |
| `RuleEvaluator` 확장 | 설비 충돌, 선후행 위반 등 규칙 추가 | 규칙 추가만으로 확장 가능 | `app/domain/rules.py`, `data/rules.json` |

확장 시 유지해야 할 원칙은 두 가지다.

1. 새 입력 경로는 검증을 거쳐 `WorkItemData`로 수렴시키고, 규칙 엔진은 그대로 사용한다.
2. LLM 결과는 항상 Pydantic 재검증을 거치고, 사람이 확인·수정한 뒤에만 저장한다.

## 5. 오류와 로깅

- 모든 오류 응답은 `{"error": {"code", "message", "details"}}` 형식이다. 코드 목록은 `app/core/errors.py`의 `ErrorCode`에 있다.
- 내부 스택 추적은 응답에 노출하지 않는다.
- 요청 로그는 `request_id`, `endpoint`, `status_code`, `duration_ms`, `analysis_id`를 JSON 한 줄로 남긴다(`app/core/logging.py`).
- 자연어 원문 전체는 로그에 남기지 않고 길이만 기록한다. CSV 오류 응답도 `description` 값을 반환하지 않는다.
