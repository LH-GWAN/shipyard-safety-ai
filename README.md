# YardGuard

조선소의 여러 **작업계획을 작업 시작 전에 비교**해 위험한 동시작업과 밀폐공간 안전조치 정보 누락을 사전에 찾아내는 웹 기반 안전 검토 보조 시스템.

> **안전 고지**
> YardGuard의 결과는 **합성 데이터와 사전 정의된 규칙에 기반한 검토 보조정보**입니다. 실제 현장 배포 전에는 회사별 작업허가 절차, 구역 관계, 안전규칙을 현장 안전담당자가 검증해야 합니다.
> 이 시스템은 작업허가 승인, 법적 적합성 판정, 작업중지 명령, 설비 제어 기능을 제공하지 않으며 작업자의 안전을 보증하지 않습니다.

[![CI](https://github.com/LH-GWAN/shipyard-safety-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/LH-GWAN/shipyard-safety-ai/actions/workflows/ci.yml)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 이름 | YardGuard |
| 한 줄 설명 | 조선소 작업계획의 시간·공간 충돌과 밀폐공간 안전조치 정보 누락을 작업 전에 탐지하는 검토 보조 도구 |
| 입력 | 웹 폼 직접 입력, CSV 업로드, 자연어 문장 |
| 출력 | 규칙 기반 경보 목록, 경보 근거, 규칙형 시간 변경안 |
| 데이터 | 저장소에 포함된 합성 데이터 (실제 작업허가서·공정표 없음) |
| 외부 의존 | 없음. LLM API 키가 없어도 전체 기능과 시연이 동작 |

## 2. 문제 정의

조선소에서는 같은 시간대에 같은 구역 또는 바로 옆 구역에서 서로 위험한 작업이 함께 계획되는 일이 발생합니다.

- 화기작업(용접·절단) 옆에서 도장이나 유기용제 작업이 진행되면 인화성 증기와 점화원이 같은 공간에 놓입니다.
- 밀폐공간 작업은 가스측정·환기·감시인 정보가 확인되지 않은 채 계획이 넘어가는 경우가 있습니다.

작업계획서를 한 건씩 보면 각각은 문제가 없어 보이기 때문에, **여러 계획을 함께 비교해야** 이런 조합이 드러납니다.
YardGuard는 그 비교를 자동화해 안전관리자가 확인해야 할 조합을 좁혀 줍니다.

## 3. 사용자

- **안전관리자**: 여러 작업계획을 사전 검토하고 확인이 필요한 조합을 골라냄
- **공정계획 담당자**: 일정 조정 전에 충돌 여부와 대안을 확인
- **작업허가 검토자**: 허가 검토 전 정보 누락 여부를 사전 점검

## 4. 핵심 기능

1. **작업계획 등록·수정·삭제** — 웹 폼, 필터·페이지네이션이 있는 목록
2. **CSV 업로드** — 기본 검증 전용, 행별 오류 표시 후 사용자가 저장을 확정
3. **자연어 구조화** — 문장에서 작업 정보를 초안으로 뽑아내고, 사용자가 확인·수정한 뒤 저장
4. **결정론적 규칙 검사** — 시간·공간 중첩 충돌 3종, 밀폐공간 정보 누락 3종
5. **경보 상세** — 적용 규칙과 근거 조문, 관련 작업, 구역 관계, 중첩시간, 입력 근거, 권고 확인사항
6. **규칙형 시간 변경안** — 미리보기 → 사용자 확인 → 적용 → 전체 재검사 (미리보기 없이 적용 불가)

## 5. LLM과 규칙 엔진의 역할 구분

| 구분 | LLM | 규칙 엔진 |
|---|---|---|
| 역할 | 자연어 문장 → 구조화된 입력값(초안) | 위험 판정과 경보 생성 |
| 위험 판정 | **하지 않음** | 수행 |
| 경보 등급 결정 | **하지 않음** (등급은 `data/rules.json`에 고정) | 규칙 정의를 그대로 사용 |
| 결정성 | 공급자에 따라 달라질 수 있음 | 동일 입력 → 항상 동일 결과 |
| 저장 | 사용자가 확인·수정한 뒤에만 저장 | 분석 결과를 DB에 저장 |
| 실패 시 | 모의 어댑터로 대체하거나 오류 안내 | 영향 없음 |

LLM 응답은 저장 전에 Pydantic으로 재검증하며, 허용 구역과 다른 `zone_id`는 `null`로 되돌리고 원문을 근거로 남깁니다.

## 6. 기술 스택

| 영역 | 스택 |
|---|---|
| 프런트엔드 | Next.js 16 (App Router), React 19, TypeScript 5, Tailwind CSS 4 |
| 백엔드 | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x |
| 데이터베이스 | SQLite 기본, `DATABASE_URL`로 PostgreSQL 교체 가능 |
| 테스트 | pytest (백엔드), Vitest + Testing Library (프런트엔드) |
| 품질 도구 | Ruff (lint/format), ESLint, TypeScript `--noEmit` |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |

## 7. 폴더 구조

```
.
├── backend/
│   ├── app/
│   │   ├── api/            FastAPI 라우터
│   │   ├── core/           설정, 오류 코드, 로깅, 시간 유틸, 데이터 로더
│   │   ├── db/             세션, 초기화(테이블 생성 + 구역 시드)
│   │   ├── domain/         enum, 모델, 시간 중첩, 구역 그래프, 규칙 엔진, 시간 변경안
│   │   ├── llm/            LLMAdapter, 모의 어댑터, 실제 공급자 어댑터
│   │   ├── models/         SQLAlchemy ORM
│   │   ├── repositories/   조회·저장
│   │   ├── schemas/        요청·응답 스키마
│   │   ├── services/       검증, CSV, 분석, 일정 변경, LLM 구조화
│   │   └── main.py
│   ├── scripts/            합성 데이터 적재 스크립트
│   └── tests/              단위 + 통합 + 스모크 테스트
├── frontend/
│   ├── app/                App Router 페이지
│   ├── components/         공통 컴포넌트
│   ├── features/           화면 기능 컴포넌트
│   ├── lib/                API 클라이언트, 포맷·라벨 유틸
│   ├── types/              백엔드와 공유하는 도메인 계약
│   └── tests/              Vitest 테스트
├── data/                   합성 데이터 (zones/work_items/rules/expected_alerts)
├── docs/                   아키텍처, 규칙 명세, 시연 대본, 작업허가서 확장 계획
├── evaluation/             자연어 구조화 평가 체계
├── scripts/                통합 스모크 테스트
├── .github/workflows/      CI
├── .env.example
└── run.sh
```

## 8. 요구 버전

- Python 3.12 이상 (개발·검증: 3.12)
- Node.js 20 이상 (개발·검증: Node 26, CI: Node 20)
- npm 10 이상

## 9. 설치 방법

```bash
git clone https://github.com/LH-GWAN/shipyard-safety-ai.git
cd shipyard-safety-ai

# 백엔드 가상환경
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements-dev.txt

# 프런트엔드 의존성
cd frontend && npm ci && cd ..
```

`uv`를 사용한다면 다음도 동일합니다.

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r backend/requirements-dev.txt
```

## 10. 환경변수 설정

```bash
cp .env.example .env                                  # 저장소 루트 (백엔드가 읽음)
cp frontend/.env.local.example frontend/.env.local    # 프런트엔드
```

두 파일 모두 **값을 비워 둔 채로도 그대로 동작합니다.** 빈 값은 미설정으로 처리되어 기본값이 적용됩니다.

| 변수 | 파일 | 기본값 | 설명 |
|---|---|---|---|
| `APP_NAME` | `.env` | `YardGuard API` | API 문서 제목 |
| `DATABASE_URL` | `.env` | 저장소 루트의 `yardguard.db` | PostgreSQL 등으로 교체 가능 |
| `DATA_DIR` | `.env` | 저장소 루트의 `data` | 합성 데이터 위치 |
| `CORS_ORIGINS` | `.env` | `http://localhost:3000,http://127.0.0.1:3000` | 허용 오리진 |
| `LLM_PROVIDER` | `.env` | 비어 있음 | `anthropic` 또는 `openai`. 비우면 모의 어댑터 |
| `LLM_API_KEY` | `.env` | 비어 있음 | **백엔드에서만** 읽음. 클라이언트 번들에 포함되지 않음 |
| `LLM_MODEL` | `.env` | `claude-sonnet-5` | 공급자별 모델 이름 |
| `LLM_TIMEOUT_SECONDS` | `.env` | `20` | 호출 시간초과(초) |
| `MAX_CSV_BYTES` | `.env` | `2097152` | CSV 업로드 크기 제한 |
| `MAX_CSV_ROWS` | `.env` | `1000` | CSV 행 수 제한 |
| `MAX_DESCRIPTION_LENGTH` | `.env` | `2000` | 설명 길이 제한 |
| `NEXT_PUBLIC_API_BASE_URL` | `frontend/.env.local` | `http://localhost:8000` | 백엔드 주소 |

실제 API 키는 `.env`에만 넣고 커밋하지 마십시오(`.gitignore`가 `.env`를 제외합니다).

## 11. 백엔드 실행

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

- API: <http://localhost:8000>
- OpenAPI 문서: <http://localhost:8000/docs>
- 상태 확인: <http://localhost:8000/health>

**데이터베이스 초기화**: 시작 시 테이블을 만들고 `data/zones.json`의 구역 12개를 반영합니다. 별도 마이그레이션이 필요 없습니다.
전체 초기화는 백엔드를 멈춘 뒤 `rm yardguard.db` 후 다시 실행합니다.

**합성 작업계획 40건 적재(선택)**:

```bash
cd backend
../.venv/bin/python -m scripts.load_sample_data              # 신규 적재
../.venv/bin/python -m scripts.load_sample_data --overwrite  # 기존 ID 덮어쓰기
```

## 12. 프런트엔드 실행

```bash
cd frontend
npm run dev      # http://localhost:3000
```

## 13. 통합 실행

```bash
./run.sh         # 백엔드(8000) + 프런트엔드(3000)
```

두 서버가 떠 있는 상태에서 시연 경로 전체를 자동 점검하려면:

```bash
.venv/bin/python scripts/smoke_full_stack.py
.venv/bin/python scripts/smoke_full_stack.py --skip-web   # 백엔드만
```

## 14. 테스트 방법

```bash
# 백엔드 (저장소 루트에서)
.venv/bin/python -m ruff check backend/app backend/tests
.venv/bin/python -m ruff format --check backend/app backend/tests
cd backend && ../.venv/bin/python -m pytest tests -q && cd ..

# 자연어 구조화 평가 (API 키 불필요)
.venv/bin/python evaluation/evaluate_mock.py

# 프런트엔드
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

모든 명령은 **API 키와 인터넷 연결 없이** 실행됩니다. 실제 LLM 공급자 어댑터는 HTTP 계층을 스텁으로 바꿔 검증하므로
테스트 중 외부 API를 호출하지 않습니다(`backend/tests/test_llm_remote_offline.py`).

## 15. 시연 순서

3분 대본은 [`docs/demo-script.md`](docs/demo-script.md)에 있습니다. 요약하면 다음과 같습니다.

1. 대시보드에서 문제와 제한 문구 소개
2. CSV 업로드 → **검증만 실행**(저장되지 않음 확인) → **유효 행 저장**(40건)
3. 분석 실행 → 경보 19건
4. `R001 · W001, W002` 경보에서 동일 구역 60분 중첩과 근거 확인
5. `R101 · W026`(미입력)과 `W027`(미실시 입력)의 메시지 차이 비교
6. 경보 상세에서 근거 조문과 "법 위반 판정 아님" 고지 확인
7. 시간 변경안 미리보기 → 해소/신규 경보 확인 → 적용 → 경보 18건
8. 자연어 입력 탭에서 모의 어댑터 구조화 결과 확인 후 저장

## 16. 합성 데이터 구성

| 파일 | 내용 |
|---|---|
| `data/zones.json` | 가상 구역 12개와 인접관계(단방향 선언도 양방향으로 정규화) |
| `data/work_items.csv` | 합성 작업계획 40건 (2026-03-16 ~ 03-18) |
| `data/rules.json` | 규칙 카탈로그 7개(경보 6 + 입력 검증 1)와 근거 조문 |
| `data/expected_alerts.json` | 기대 경보 19건과 음성 시나리오 7건 |

`work_items.csv`에는 동일·인접 구역 충돌, 경계시각 접촉, 시간만 겹치는 사례, 밀폐공간 필드별 `null`/`false`,
R001·R003 중복 억제 사례가 모두 들어 있습니다.

**CSV 형식**

필수 열: `id,title,work_type,zone_id,start_at,end_at`
선택 열: `description,uses_flammable_material,gas_measurement_completed,ventilation_confirmed,watcher_assigned,status`

```csv
id,title,work_type,zone_id,start_at,end_at,description,uses_flammable_material,gas_measurement_completed,ventilation_confirmed,watcher_assigned,status
W001,A블록 1구역 보강재 용접,HOT_WORK,A_BLOCK_1,2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,블록 보강재 맞대기 용접,,,,,REVIEWED
W026,탱크 B 내부 점검,CONFINED_SPACE,TANK_B,2026-03-18T08:00:00+09:00,2026-03-18T12:00:00+09:00,탱크 내부 육안 점검,,,true,true,DRAFT
```

- `work_type`: `HOT_WORK`, `PAINTING`, `SOLVENT_WORK`, `CONFINED_SPACE`, `OTHER` (대소문자까지 일치)
- 시각: ISO 8601 + **표준시간대 필수**(`+09:00`), 종료 > 시작
- 불리언 열: `true`/`false`, `TRUE`/`FALSE`, `1`/`0`. **빈 셀은 `null`(정보 미입력)** 이며 `false`(미실시로 입력)와 구분
- 제한: 2MB, 1,000행 초과 시 413

## 17. 구현된 규칙 목록

현재 구현은 **경보를 생성하는 규칙 6개 + 입력 검증 규칙 1개**입니다.

> 제출 계획서에 "안전규칙 10~15개"로 적혀 있다면 현재 구현과 다릅니다. 근거와 입력 필드가 확보된 규칙만 구현했으며,
> 숫자를 맞추기 위해 규칙을 임의로 추가하지 않았습니다. 나머지는 아래 "확장 후보"로만 기술합니다.

| 규칙 | 조건 | 등급 | 근거 조문(확인일 2026-09-06) |
|---|---|---|---|
| R001 | 화기작업 ↔ 도장작업, 시간 중첩 + 동일·인접 구역 | HIGH | 산업안전보건기준에 관한 규칙 제241조제2항제3호·제5호, 제232조제1항 |
| R002 | 화기작업 ↔ 유기용제 작업, 시간 중첩 + 동일·인접 구역 | HIGH | 같은 규칙 제232조제1항·제2항, 제241조제2항제5호 |
| R003 | 화기작업 ↔ 가연성 물질 사용 작업(같은 쌍에 R001/R002가 있으면 억제) | HIGH | 같은 규칙 제241조제2항제3호, 제241조의2제1항 |
| R101 | 밀폐공간 작업의 `gas_measurement_completed`가 true 아님 | HIGH | 같은 규칙 제619조의2제1항, 제619조제1항 |
| R102 | 밀폐공간 작업의 `ventilation_confirmed`가 true 아님 | HIGH | 같은 규칙 제620조제1항 |
| R103 | 밀폐공간 작업의 `watcher_assigned`가 true 아님 | HIGH | 같은 규칙 제623조제1항 |
| R104 | 시간정보 오류 → 저장·분석 입력 검증에서 차단 (**경보 생성 안 함**) | - | 내부 입력 검증 규칙(법령 근거 없음) |

- 조문 번호·제목·본문은 국가법령정보센터 공개 API로 **현행 법령(고용노동부령 제450호, 시행 2025-09-01)** 을 조회해 확인했습니다.
  재현 명령: `curl "https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST=273603&type=XML"`
- 인용 조문은 사업주의 안전조치 의무를 정한 것이며, **YardGuard의 경보는 법 위반 판정이 아닙니다.** 각 규칙에는
  `requires_site_validation` 표시가 있고 화면에도 같은 고지가 나옵니다.
- 규칙 상세와 테스트 대응은 [`docs/rule-specification.md`](docs/rule-specification.md)를 참고하십시오.

**확장 후보(현재 미구현, 입력 필드가 없어 구현하지 않음)**

- 고소작업과 상부·하부 동시작업 충돌
- 중량물 인양구역과 통행 작업 충돌
- 밀폐공간 작업시간 중 안전조치 재확인
- 동일 구역 내 복수 점화원 작업
- 작업허가 유효시간 초과
- 위험물 사용 작업의 안전조치 정보 누락

확장 후보를 구현하려면 입력 필드, 판정 조건, 경보 메시지, 권고 확인사항, 공식 근거, 양성·음성·경계값 테스트,
`expected_alerts.json` 반영이 모두 필요합니다.

## 18. 현재 제한사항

- 규칙은 6개이며, 회사별 작업허가 절차·설비 조건·작업 방법을 반영하지 않습니다.
- 구역 인접관계는 합성 그래프입니다. 실제 거리, 높이, 격벽, 환기 경로를 고려하지 않습니다.
- **완화조치(화재감시자 배치, 차단막 설치 등)를 입력할 수 없어**, 이미 통제된 조합도 경보로 표시됩니다.
- 시간 변경안은 두 작업만 고려하는 단순 규칙입니다. 공정 선후행, 자원 제약, 교대 시간은 계산하지 않습니다.
- 자연어 구조화는 초안 작성 보조입니다. 모의 어댑터는 사전 정의 키워드와 ISO 8601 시각만 인식하며,
  안전조치 표현("가스측정 완료")과 상대 날짜("내일 오전")를 해석하지 않습니다(측정값은 [`evaluation/README.md`](evaluation/README.md)).
- 실제 LLM 공급자의 **추출 품질은 아직 측정하지 않았습니다.** 어댑터의 동작·오류 처리·안전장치만 스텁으로 검증했습니다.
- 인증·권한 관리가 없으므로 로컬 또는 신뢰된 네트워크에서만 실행해야 합니다.
- 작업계획을 수정해도 자동 재분석하지 않습니다(시간 변경안 적용만 예외).
- 성능 목표(합성 40건 5초 이내)는 개발용 노트북 기준이며 현장 성능 주장이 아닙니다.
  측정 환경: Apple Silicon macOS, Python 3.12, SQLite. 실측값은 분석 응답의 `duration_ms`로 확인할 수 있습니다.

## 19. 실제 작업허가서 확보 시 확장 방법

현재는 실제 작업허가서를 사용하지 않습니다. 확보했을 때의 확장 경로(비식별화 절차, OCR, 서식 매핑,
LLM 구조화, 담당자 확인, 규칙 카탈로그 전환, 외부 일정 연동, 현장 적용 전 검증 단계)는
[`docs/work-permit-extension.md`](docs/work-permit-extension.md)에 정리했습니다.

요약: OCR·LLM 결과는 **절대 곧바로 판정에 쓰지 않고** 담당자가 원문 근거와 함께 확인·수정한 값만 `WorkItem`으로 변환합니다.
규칙 엔진은 그대로 두고 입력 경로만 추가하는 구조입니다.

## 20. 안전 및 윤리 고지

- YardGuard는 **검토 보조 도구**이며 안전관리자의 판단을 대체하지 않습니다.
- 작업허가 승인, 법적 적합성 판정, 작업중지 명령, 설비 제어를 수행하지 않습니다.
- 경보는 "확인이 필요한 조합"을 알리는 신호이며 법 위반 판정이 아닙니다.
- 모든 예제 데이터는 합성이며 실제 회사·선박·협력업체·개인을 식별하는 정보를 포함하지 않습니다.
- LLM은 위험 판정에 관여하지 않으며, 등급은 규칙 정의에 고정되어 있습니다.
- 자연어 원문 전체는 일반 오류 로그에 남기지 않고, LLM 요청에는 업무상 필요한 문장과 허용 구역 목록만 전달합니다.
- 측정하지 않은 정확도를 성능으로 제시하지 않습니다. 목표값과 측정값은 구분해 표기합니다.

## 21. 주요 API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 상태, 구역 수, LLM 활성 여부 |
| GET/POST | `/api/zones` | 구역 조회·등록 |
| GET | `/api/rules` | 규칙 카탈로그(경보 규칙/입력 검증 규칙 수 포함) |
| GET/POST | `/api/work-items` | 목록(필터·페이지네이션)·등록 |
| GET/PUT/DELETE | `/api/work-items/{id}` | 상세·수정·삭제 |
| POST | `/api/work-items/import-csv?commit=false&overwrite=false` | CSV 검증·저장 |
| POST | `/api/work-items/parse-description` | 자연어 구조화 초안(저장하지 않음) |
| POST | `/api/analysis/run` | 규칙 검사 실행 |
| GET | `/api/analysis/latest` | 최근 분석 결과 |
| GET | `/api/analysis/{id}` · `/api/analysis/{id}/alerts` | 분석 결과·경보 목록 |
| POST | `/api/schedule/preview-shift` | 시간 변경안 미리보기(원본 불변, 토큰 발급) |
| POST | `/api/schedule/apply-shift` | 미리보기 토큰이 있어야 적용, 적용 후 전체 재분석 |

오류 응답은 `{"error": {"code", "message", "details"}}` 형식이며 주요 코드는 `INVALID_TIME_RANGE`, `TIMEZONE_REQUIRED`,
`UNKNOWN_ZONE`, `DUPLICATE_WORK_ITEM_ID`, `INVALID_CSV_HEADER`, `INVALID_CSV_VALUE`, `CSV_LIMIT_EXCEEDED`,
`LLM_UNAVAILABLE`, `LLM_OUTPUT_INVALID`, `ANALYSIS_NOT_FOUND`, `ALERT_NOT_FOUND`, `STALE_SCHEDULE_PREVIEW`입니다.
