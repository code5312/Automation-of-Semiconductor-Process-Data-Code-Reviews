# 진행 보고 (docs/progress.md)

CLAUDE.md 규정에 따라 각 Stage 종료 시 보고를 append한다. 설계서 이탈, 도메인 검증 필요 값도 여기 기록한다.

---

### Stage 0 보고

- 만든 것:
  - `pyproject.toml` (console script `fab-review`, deps: pandas/pyyaml/pydantic>=2, dev: pytest)
  - `fab_review/__init__.py`, `fab_review/__main__.py`, `fab_review/cli.py` (argparse 골격, `check` 서브커맨드는 아직 미구현 placeholder)
  - `tests/__init__.py`, `tests/test_cli.py`
  - 부록 A 디렉토리 골격: `contracts/`, `synth/`, `samples/`, `fab_review/{contract,analysis,checkers,report}/` (모두 빈 패키지, 동작 코드 없음)
  - `.gitignore`
  - `docs/progress.md` (본 파일)
- 검증:
  - `python -m pip install -e ".[dev]"` → 성공 (pandas 3.0.5, pyyaml 6.0.3, pydantic 2.13.4, pytest 9.0.3 모두 시스템에 이미 설치돼 있어 네트워크 다운로드 없이 완료)
  - `python -m fab_review --help` → 종료 코드 0, 사용법 출력 확인
  - `python -m pytest -q` → `3 passed` (test_help_exits_zero_via_run_function, test_check_subcommand_parses_required_args, test_module_entrypoint_help)
- 체크한 checklist 항목: 0절 — pandas/PyYAML/pydantic 설치, CLI 도구 결정(argparse), pytest+tests/ 구성, 저장소+디렉토리 구조. "Python 3.11+ 가상환경 구성"은 보류(아래 질문 참고).
- 설계서와 다르게 한 것 / 가정한 것:
  - **가상환경을 만들지 않았다.** 시스템 Python 3.14(요구사항 3.11+ 충족)에 필요한 패키지가 이미 전역 설치돼 있어 그대로 사용했다. 격리가 필요하면 이후 Stage에서 `venv` 생성으로 전환 가능.
  - `check` 서브커맨드는 인자 파싱만 구현하고 `[INFO] check 명령은 아직 구현되지 않았습니다`를 출력 후 종료 코드 0을 반환하는 placeholder로 두었다. 실제 로직은 Stage 1(계약)~5(리포트)에서 채운다.
  - `pyproject.toml`의 `[project.scripts]`는 `fab_review.cli:run`을 가리키며, `run()`은 int를 반환하고 pip이 생성한 wrapper가 `sys.exit()`으로 감싼다. `__main__.py`도 동일한 `run()`을 호출해 두 진입점이 같은 동작을 보장한다.
  - CLAUDE.md의 "PowerShell에서 파일을 utf-8로 다루기" 원칙을 CLI 콘솔 출력뿐 아니라 **subprocess로 CLI를 호출하는 테스트**에도 적용해야 함을 발견했다 (`subprocess.run(..., text=True)`가 기본적으로 cp949로 디코드해 한글 출력에서 `UnicodeDecodeError` 발생 → `encoding="utf-8"` 명시로 해결). 앞으로 subprocess 기반 테스트에는 항상 `encoding="utf-8"`을 명시한다.
- 도메인 검증 필요 값 (이번에 새로 추가된 것): 없음 (Stage 0은 스캐폴딩만, 도메인 값 없음)
- 다음 Stage 전에 결정이 필요한 질문:
  - 가상환경을 별도로 만들 것인지 (현재는 시스템 Python 그대로 사용 중). 계속 이대로 진행해도 괜찮은지 확인 필요.
  - Stage 1에서 계약을 확장할 두 가지 항목(사전 승인됨, 재확인차 기록): ① `sources`에 `sensor` 필드 + 최상위 `sensors:` 맵 추가(FAB-T001 판정용), ② `entities.metrology`에 `parent: wafer` 명시(FAB-J001 공통 조상 계산용).
- 제안 커밋 메시지: `Stage 0: fab-review CLI 스캐폴딩 및 pytest 골격 구성`

**해결**: 사용자가 가상환경 없이 진행 승인, Stage 0 커밋 완료 (`77849ab`).

---

### Stage 1 보고

- 만든 것:
  - `fab_review/contract/schema.py` (pydantic v2: `Parameter`, `Entity`, `Relationship`, `Source`, `SensorSpec`, `Contract` + 교차 참조 검증 + `Contract.ancestors()`/`Contract.common_ancestor()`)
  - `fab_review/contract/loader.py` (`load_contract()`, `ContractError`, 사람이 읽을 수 있는 메시지 포맷)
  - `fab_review/contract/matcher.py` (`match_any`, `match_source`, `match_parameter` — `fnmatch.fnmatchcase` + 소문자 정규화로 결정론 보장)
  - `contracts/contract.yaml` v0.1.0 (설계서 8.2절 구조 + 승인된 확장 2건 반영)
  - `tests/test_contract.py` (21건: 로더/스키마/교차참조/공통조상/매처)
- 검증:
  - `python -m pytest -q` → `24 passed` (Stage 0의 3건 포함)
  - 잘못된 계약(키 누락, 알 수 없는 family, 알 수 없는 parent/relationship/source 참조, parent 순환, 알 수 없는 sensor 참조, 알 수 없는 최상위 필드) 전부 로딩 거부 확인
  - 실제 `contracts/contract.yaml`이 정상 로딩되고 `contract_version`, `sensors["rf_power"].sampling_period` 접근 확인
- 체크한 checklist 항목: 1절 대부분 (`contract.yaml` 5개 하위 항목, 센서 샘플링 주기 표, pydantic 스키마, 로더, 패턴 매처, contract_version 노출). "계약 값의 출처 기록"은 보류(아래 참고), "[M] 도메인 팀원용 가이드"는 스코프 밖.
- 설계서와 다르게 한 것 / 가정한 것:
  - **승인된 확장 2건**을 실제로 적용: `sources[].sensor` + 최상위 `sensors:` 맵, `entities.metrology.parent: wafer`.
  - **추가 결정(재확인 필요)**: 같은 확장 방식을 `entities.step_event.parent: wafer`에도 동일하게 적용했다. 승인받은 것은 metrology뿐이었지만, FAB-J001 공통 조상 계산 메커니즘이 일관되게 동작하려면 부모가 있는 엔티티는 전부 `parent`를 명시해야 해서 같은 패턴을 확장했다. 별도 승인 안건으로 다시 확인받는다.
  - **`sources` 목록을 설계서 예시보다 늘렸다**: 설계서 예시엔 `wafer`/`lot` 자체를 가리키는 소스 패턴이 없어, Stage 2의 조인 위반 데모(`yield_df.merge(metrology_df, on="lot_id")` 같은 코드)가 로드 지점에서 엔티티를 식별할 수 없는 문제가 있었다. `*wafer_yield*` → `wafer`, `*lot_master*` → `lot` 패턴을 추가했다. 또한 기존 `fdc_*` 패턴을 `fdc_rf_*`/`fdc_gas_*`로 나눠 센서를 구분했다.
  - `Contract.common_ancestor()`를 스키마에 미리 만들어뒀다 — Stage 4 join_checker가 재사용할 순수 함수라 지금 만들어도 "동작 코드 금지" 원칙(LLM/M/R 기능)에 해당하지 않는다고 판단했다.
- 도메인 검증 필요 값 (이번에 새로 추가된 것):
  - `sensors.rf_power.sampling_period: "1s"`, `sensors.gas_flow.sampling_period: "5s"` — 출처 없음, AI가 FAB-T001 데모가 성립하도록 임의로 다르게 잡은 값. 도메인 팀 검증 필요.
- 다음 Stage 전에 결정이 필요한 질문:
  - `entities.step_event.parent: wafer` 추가를 승인하는지 (위 "설계서와 다르게 한 것" 참고).
  - `sources`에 추가한 `*wafer_yield*`, `*lot_master*` 패턴명이 실제 팀 파일명 규칙과 맞는지 (Stage 2 합성 데이터/데모 스크립트 파일명을 이 패턴에 맞춰 만들 예정이라, 지금 확정해두면 편함).
  - 계약 값 출처 기록(공개자료/교재/팀원경험) 항목은 실제 반도체 배경 팀원 입력이 필요해 보류함 — 이대로 두고 진행해도 괜찮은지.
- 제안 커밋 메시지: `Stage 1: 공정 데이터 계약 스키마·로더·패턴 매처 구현`

---

## 도메인 검증 필요 값 (누적 목록)

- `contracts/contract.yaml: sensors.rf_power.sampling_period = "1s"` — 출처 없음, Stage 1에서 임의 지정
- `contracts/contract.yaml: sensors.gas_flow.sampling_period = "5s"` — 출처 없음, Stage 1에서 임의 지정

## 설계서 대비 단순화/확장 기록 (누적 목록)

- **계약 확장 (Stage 1, 승인됨)**: `sources[].sensor` 필드 + 최상위 `sensors:` 맵 추가. 이유: FAB-T001이 "어떤 센서인지"를 알아야 샘플링 주기를 비교할 수 있는데 설계서 8.2절 예시엔 이 정보가 없었음.
- **계약 확장 (Stage 1, 승인됨)**: `entities.metrology.parent: wafer` 명시. 이유: FAB-J001의 "공통 조상 입도" 계산에 부모 관계가 필요.
- **계약 확장 (Stage 1, 재확인 필요)**: `entities.step_event.parent: wafer` 명시 — metrology와 같은 이유로 일관성을 위해 추가했으나 별도 승인은 못 받음.
- **sources 목록 보강 (Stage 1, 재확인 필요)**: `*wafer_yield*`→`wafer`, `*lot_master*`→`lot` 패턴 추가, `fdc_*`를 `fdc_rf_*`/`fdc_gas_*`로 분리. 설계서 예시에는 없던 항목.
- **FAB-J002 단순화 (CLAUDE.md에 이미 명시됨)**: 설계서 9.3절의 "inner join 결과가 수율 분모 계산에 쓰임"을 "coverage: sampled 엔티티와 how 생략 조인"으로 단순화. (아직 구현 전, Stage 4에서 실제로 반영 예정 — 기록은 미리 남겨둠)
