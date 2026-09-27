# 반도체 공정 데이터 정합성 검증 — 프로토타입 구현 체크리스트

**기준 문서**: `GOAT_반도체_공정데이터_정합성검증_최종설계서.md` (최종안 v1.0)
**첫 데모 목표**: CLI에 분석 스크립트를 넣으면 공정 데이터 불변 조건 위반(단위·시간·입도)이 Markdown 리포트로 나온다 — LLM·서버·외부 연동 없이 로컬에서.

**범례**
- **[P]** 프로토타입 필수 (첫 데모까지)
- **[M]** 8주 MVP에서 추가
- **[R]** CI/CD 로드맵 (8주차 stretch 또는 MVP 이후)
- 담당은 설계서 14절 역할 분담 제안 기준이며, 팀 합의로 조정

---

## 0. 개발 환경

- [ ] [P] Python 3.11+ 가상환경 구성 (보류 — Stage 0 보고 참고)
- [x] [P] pandas 설치 (검사 대상 라이브러리 + 합성 데이터 생성)
- [x] [P] PyYAML 설치 (계약 로딩)
- [x] [P] pydantic 설치 (계약 스키마, Finding 모델, API 스키마)
- [x] [P] CLI 도구 결정: argparse(표준) 또는 typer → argparse 채택 (CLAUDE.md 지정)
- [x] [P] pytest 설치 및 `tests/` 디렉토리 구성
- [x] [P] 저장소 생성 + 부록 A 디렉토리 구조 반영 (llm/store/api 제외)
- [ ] [M] anthropic SDK 설치, `.env`로 API 키 관리 (`.gitignore`에 `.env` 추가)
- [ ] [M] FastAPI + uvicorn 설치
- [ ] [M] httpx 설치 (GitHub API, Slack webhook)
- [ ] [M] (선택) pint 설치
- [ ] [R] pre-commit, jupytext 설치

---

## 1. 공정 데이터 계약 [P]

담당(제안): 반도체 패키징·불량분석 경험자(계약 오너), 센서데이터 경험자(샘플링 주기 항목)

- [x] `contracts/contract.yaml` v0.1 작성 (설계서 8.2절 구조 + sensor/parent 확장)
  - [x] `unit_families`: 압력, 유량, 온도, 두께
  - [x] `parameters`: 공정 파라미터 ↔ family ↔ 이름 패턴
  - [x] `entities`: lot, wafer, step_event, fdc_trace, metrology (키, 입도, 커버리지, 시간 윈도우)
  - [x] `relationships`: lot:wafer = 1:N, wafer:metrology = 1:N(sampled)
  - [x] `sources`: 파일/테이블 이름 패턴 → 엔티티
- [x] 센서별 샘플링 주기 표 작성 (`fdc_trace`의 `per_sensor` 실제 값) — `sensors:` 맵, 예시 값(도메인 검증 필요)
- [ ] 계약 값의 출처 기록 (공개 자료 / 교재 / 팀원 경험 중 무엇인지) — 현재 값은 AI가 임시로 채운 예시일 뿐 출처 없음. 보류.
- [x] pydantic 계약 스키마 모델 작성
- [x] 계약 로더 작성 — 스키마 위반 시 로딩 단계에서 명확한 에러
- [x] 이름 패턴 매처 작성 (`fnmatch` 수준)
- [x] 계약 버전(`contract_version`)을 결과에 기록할 수 있게 노출
- [ ] [M] 도메인 팀원용 계약 작성 가이드 (1~2쪽)

**완료 기준**: 잘못된 계약 파일(키 누락, 알 수 없는 family)이 로딩 시 거부되는 테스트 통과

---

## 2. 합성 공정 데이터 & 데모 스크립트 [P]

담당(제안): 센서데이터 경험자(FDC trace), 반도체 배경 팀원(계측·로트 이력)

- [x] 합성 데이터 생성기 (`synth/`)
  - [x] 로트/웨이퍼 계층 (로트당 웨이퍼 수는 계약이 아니라 `synth/generate.py`의 상수로 관리 — 아래 보고 참고)
  - [x] 센서별로 샘플링 주기가 다른 FDC trace
  - [x] step 시작/종료 이벤트
  - [x] 일부 웨이퍼·사이트만 측정된 계측 데이터
  - [x] 장비별로 다른 단위로 기록된 파라미터 (예: 압력 mTorr / Pa)
- [x] 데모 스크립트 4개 (`samples/`)
  - [x] 단위 위반 스크립트 (FAB-U001 대상) — `bug_unit.py`
  - [x] 시간 정렬 위반 스크립트 (FAB-T001 대상) — `bug_time.py`
  - [x] 조인 입도 위반 스크립트 (FAB-J001, FAB-J002 대상) — `bug_join.py`
  - [x] 위반 없는 정상 스크립트 — `normal.py`
- [x] 각 데모 스크립트가 합성 데이터로 **에러 없이 실행되는지** 확인 (조용히 틀린 숫자가 나오는 것이 이 프로젝트의 전제)

**완료 기준**: 버그 스크립트 3개 모두 예외 없이 실행되고, 정상 스크립트 대비 결과 수치가 달라지는 것을 확인

---

## 3. 분석 코어 [P]

담당(제안): Python·최적화 경험자

- [x] 입력 어댑터: 파일 / 디렉토리 → 소스 텍스트 (`fab_review/analysis/discovery.py`)
- [x] AST 파서 + 위치 정보 (파일, 줄, 컬럼) (`fab_review/analysis/parser.py`; 줄·컬럼은 ast 노드의 `lineno`/`col_offset`을 Stage 4 체커가 그대로 씀)
- [x] 공통 Finding 모델: `rule_id`, `severity`(error/warning/info), 위치, 메시지, 근거, 수정 제안, `contract_version`, 판정 출처(rule/llm) (`fab_review/models.py`)
- [x] **공정 데이터 흐름 추적기** (`fab_review/analysis/flow.py`)
  - [x] 로드 지점 탐지: `read_csv` / `read_parquet` / `read_sql`의 **문자열 리터럴** 인자 → `sources` 패턴 매칭
  - [x] 경로가 변수·f-string이면 `unknown` 엔티티로 표시
  - [x] 심볼 테이블: 변수명 → {엔티티, 입도 키, 알려진 컬럼}
  - [x] 입도 유지 전파: 단순 할당, 필터링(`df[mask]`), 컬럼 선택, `.copy()`
  - [x] 입도 변경 전파: `groupby(keys).agg(...)` → 입도 = keys
  - [x] `merge` 결과의 입도 계산
  - [x] 추적 실패 시 `info`(판정 불가)로 넘기는 경로 (`unknown_reason` — 실제 info 등급 부여는 Stage 4)
- [x] 컬럼 참조 추출: `df["col"]`, `df.col`, `df[["a", "b"]]`
- [x] merge 호출 해석기 (체커 공용) (`fab_review/analysis/merge_ir.py`)
  - [x] `pd.merge(a, b, ...)` / `a.merge(b, ...)` 두 형태
  - [x] `on` / `left_on`·`right_on`
  - [x] `on`이 문자열인 경우와 리스트인 경우
  - [x] `how` 생략 시 **inner**로 해석
  - [x] `df.join()`(인덱스 기준)은 MVP에서 `info` 처리 (감지만 하고, 등급 부여는 Stage 4)

**완료 기준**: 데모 스크립트 4개에서 각 DataFrame의 엔티티·입도가 기대대로 추적되는 단위 테스트 통과

---

## 4. 체커 3종 — 정적 규칙 [P]

- [x] 규칙 카탈로그 (`checkers/catalog.py`): 규칙 ID별 설명, 예시, 수정 제안 템플릿

### unit_checker (물리량 정합성) — 담당(제안): Python·최적화 경험자
- [x] 컬럼명·변수명 → (family, 단위) 추출기
  - [x] **접미사 위치** + **계약에 등록된 토큰만** 단위로 인정
  - [x] `_c`, `_k`, `_a` 같은 짧고 모호한 토큰은 unknown(info)으로 (LLM 후보는 [M], 스코프 밖)
- [x] FAB-U001: 같은 family·다른 단위 간 산술 / 비교 / concat 탐지
- [ ] [M] 단위가 이름에 없는 경우(`p1`, `val`) LLM 후보 생성
- [ ] [M] (선택) pint 기반 검증 시도

### timeseries_checker (시간 정합성) — 담당(제안): 센서데이터 경험자
- [x] FAB-T001: 샘플링 주기가 다른 `time` 입도 엔티티끼리 timestamp 정확 일치 merge 탐지
- [x] 수정 제안 템플릿: `merge_asof(direction, tolerance=계약 주기 기준)` 또는 공통 주기 resample
- [ ] [M] step 단위 집계에서 시간 윈도우 미사용 탐지
- [ ] [M] `merge_asof` tolerance·resample 주기 적절성 LLM 후보 생성

### join_checker (계보·입도 정합성) — 담당(제안): 챗봇·API 연동 경험자
- [x] FAB-J001: 두 엔티티 입도에 필요한 키가 조인 키에서 빠진 경우 탐지 (단, 같은 엔티티끼리의 병합은 제외 — 사용자 결정, Stage 3 참고)
- [x] FAB-J002: `coverage: sampled` 엔티티와 inner join(`how` 생략 포함) 탐지
- [x] 수정 제안 템플릿: 입도 맞춘 집계 → 전체 키 조인 + `validate` + `how="left"` + `indicator`
- [ ] [M] 계약에 없는 테이블 조합 → LLM 관계 추론 → 계약 추가 제안 생성

**완료 기준**: 버그 스크립트 3개에서 해당 규칙 ID가 error로 1건 이상, 정상 스크립트에서 0건 — **충족** (`tests/test_checkers.py`로 고정)

---

## 5. 결과 처리·리포트·CLI [P]

담당(제안): 업무자동화·대시보드 경험자

- [ ] 중복 제거 및 등급 부여
- [ ] Markdown 리포터 (설계서 9.5절 PR 코멘트 형식)
- [ ] JSON 리포터
- [ ] CLI 엔트리포인트 (예: `fab-review check <경로> --contract <파일>`)
- [ ] CLI 종료 코드 규약: error 있으면 1, 없으면 0 (CI에서 그대로 재사용)
- [ ] [M] 억제 주석 파서: `# fab-review: ignore[FAB-U001] 사유: ...` (사유 누락 시 억제 무효)
- [ ] [M] 억제 건수 리포트 집계
- [ ] [R] SARIF 리포터

---

## ✅ 첫 데모 체크포인트

- [ ] 네트워크·LLM 없이 로컬에서 CLI 한 줄로 실행된다
- [ ] 버그 스크립트 3개 → 각각 기대 규칙 ID가 error로 출력된다
- [ ] 정상 스크립트 → error 0건
- [ ] 리포트에 계약 버전, 줄 번호, 수정 제안이 포함된다
- [ ] 같은 입력을 반복 실행하면 결과가 항상 동일하다

---

## 6. LLM 판단 레이어 [M]

담당(제안): 백엔드/보안 전공자(레이어), 챗봇·API 연동 경험자(프롬프트)

- [ ] 후보 → 프롬프트 빌더: 코드 스니펫(앞뒤 N줄) + 관련 계약 발췌 + 판단 질문
- [ ] 체커별 프롬프트 템플릿 + 프롬프트 버전 번호
- [ ] 구조화 응답(JSON: 확정/기각, 근거, 수정 제안) 스키마
- [ ] 응답 파싱 실패 시 `info`로 강등
- [ ] LLM 판정은 항상 `warning` 이하 등급으로만 출력 (error 불가)
- [ ] 캐시: (스니펫 해시, 계약 버전, 프롬프트 버전) 키
- [ ] LLM 끄기 스위치 (정적 전용 모드) — 끈 상태에서도 전체 파이프라인 동작 확인
- [ ] 호출 비용·지연 로깅 (11.3절 비교 실험용)
- [ ] (선택) 전송 전 식별자 마스킹

---

## 7. 저장소 — SQLite [M]

담당(제안): 백엔드/보안 전공자

- [ ] `runs`: 실행 ID, 시각, 대상, 계약 버전, 프롬프트 버전
- [ ] `findings`: 판정 결과, 처리 상태(open/resolved), 처리자
- [ ] `rule_proposals`: 계약 추가 제안 내용, 상태(proposed/approved/rejected), 승인자
- [ ] `llm_cache`
- [ ] 마이그레이션 또는 초기화 스크립트

---

## 8. API·연동 [M]

담당(제안): 백엔드/보안 전공자(API), 챗봇·API 연동 경험자(연동)

- [ ] `POST /review/analyze`
- [ ] `GET /review/findings/{id}`
- [ ] `PATCH /review/findings/{id}/resolve`
- [ ] `GET /contract`
- [ ] `POST /rules/propose`
- [ ] `PATCH /rules/{id}/approve` — 승인 시에만 계약 반영
- [ ] PR diff 입력: 변경 파일·줄 범위만 분석
- [ ] GitHub 토큰 준비 (PR 코멘트 쓰기 권한), 토큰은 환경변수로만 관리
- [ ] CLI에서 PR 코멘트 직접 게시 (webhook 서버 없이 시작)
- [ ] Slack incoming webhook 알림
- [ ] [M] 결과 대시보드 (업무자동화·대시보드 경험자)

---

## 9. 검증 자산·평가 [M]

담당(제안): 반도체 배경 팀원 전원(버그 주입), 챗봇·API 연동 경험자(baseline)

- [ ] 1주차: 팀원별 실증 사례 1건 이상 수집·기록
- [ ] 기본형 분석 스크립트 세트: SPC 관리도 / FDC 룰 / 수율 리포트
- [ ] 버그 주입 케이스 (유형별 20건 내외, 1주차 합의로 확정)
- [ ] 정답 라벨: 케이스별 기대 규칙 ID, 줄 번호
- [ ] 음성 대조군 (버그 없는 정상 코드)
- [ ] 블라인드 원칙: 버그 작성자 ≠ 해당 체커 담당자
- [ ] 평가 하네스: 테스트셋 일괄 실행 → 탐지율, 오탐률, 반복 일관성, 비용, 지연 산출
- [ ] LLM-only baseline 러너: 같은 케이스 + 일반 프롬프트, 응답을 라벨과 대조
- [ ] (선택) 범용 도구(SonarQube 등) 비교 실행
- [ ] 리뷰 시간 측정 기록지 (도구 없이 vs 도구와 함께)
- [ ] 테스트셋을 도구 자체의 회귀 테스트로 등록 (설계서 12.6절)

---

## ✅ MVP 완료 체크포인트

- [ ] 3개 체커 + LLM 레이어 + 리포트가 PR 코멘트·Slack까지 연결된다
- [ ] 계약 제안이 사람 승인 없이는 반영되지 않는다
- [ ] 평가 하네스로 하이브리드 / LLM-only / 범용 도구 결과표가 나온다
- [ ] error 등급 오탐률이 음성 대조군 기준으로 측정되어 있다 (Phase 2 진입 판단 근거)
- [ ] 정적 전용 모드로도 데모 가능하다

---

## 10. CI/CD [R]

담당(제안): 백엔드/보안 전공자

### 8주차 stretch
- [ ] GitHub Actions workflow: 정적 규칙만 실행, non-blocking
- [ ] PR diff 기반으로 변경 파일만 분석

### Phase 2
- [ ] Phase 2 진입 기준(error 오탐률 허용치) 팀 합의
- [ ] error 등급을 required status check로 설정
- [ ] 계약 기반 fixture 테스트 러너 (행 수·키 유일성·커버리지)
- [ ] SARIF 업로드 (저장소 플랜에서 지원되는 경우)
- [ ] 계약 변경 PR의 스키마 검증 CI
- [ ] `/rules/propose` → 계약 저장소 PR 생성 방식으로 전환
- [ ] LLM API 키를 CI secrets로 관리

### Phase 3
- [ ] pre-commit hook (정적 규칙만, 로컬)
- [ ] Jupyter 노트북 지원 (jupytext 등으로 변환 후 분석)

---

## 부록 A. 디렉토리 구조

```
fab-review/
├─ contracts/contract.yaml
├─ fab_review/
│  ├─ contract/     # 스키마, 로더, 패턴 매처
│  ├─ analysis/     # AST 파서, 흐름 추적기, merge 호출 해석기
│  ├─ checkers/     # unit.py, timeseries.py, join.py, catalog.py
│  ├─ llm/          # 프롬프트, 클라이언트, 캐시        [M]
│  ├─ report/       # markdown, json, (sarif)
│  ├─ store/        # sqlite                          [M]
│  ├─ api/          # FastAPI                         [M]
│  └─ cli.py
├─ synth/           # 합성 공정 데이터 생성기
├─ samples/         # 데모 스크립트 (버그/정상)
├─ eval/            # 테스트셋, 라벨, 평가 하네스, baseline 러너 [M]
├─ tests/
└─ .github/workflows/                                 [R]
```

---

## 부록 B. 구현 함정 — 테스트로 고정해둘 것

- [ ] `merge`에서 `how` 생략 → inner로 해석하는 테스트
- [ ] `pd.merge(a, b)`와 `a.merge(b)`가 같은 결과를 내는 테스트
- [ ] `on="lot_id"`(문자열)와 `on=["lot_id"]`(리스트)가 같게 해석되는 테스트
- [ ] `left_on`·`right_on` 조인 해석 테스트
- [ ] 모호한 단위 토큰(`_c`, `_k`, `_a`)이 error로 확정되지 않는 테스트
- [ ] 경로가 변수·f-string인 로드가 unknown으로 표시되고 조용히 통과되지 않는 테스트
- [ ] `groupby` 후 입도가 groupby 키로 바뀌는 테스트
- [ ] LLM 판정이 error 등급으로 나오지 않는 테스트

---

## 부록 C. 설계서 매핑

| 체크리스트 | 설계서 |
|---|---|
| 1. 공정 데이터 계약 | 8절 |
| 3. 분석 코어 (흐름 추적) | 9.2절 |
| 4. 체커 3종 | 7.2절, 9.3절 |
| 5. 리포트 | 9.4절, 9.5절 |
| 6. LLM 판단 레이어 | 5.2절, 9.1절 |
| 7~8. 저장소·API | 10절 |
| 9. 검증 자산·평가 | 11절 |
| 10. CI/CD | 12절 |