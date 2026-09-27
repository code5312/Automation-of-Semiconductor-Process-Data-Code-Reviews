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

---

## 도메인 검증 필요 값 (누적 목록)

(아직 없음 — Stage 1부터 계약 값이 추가되면 여기 누적한다)

## 설계서 대비 단순화/확장 기록 (누적 목록)

(아직 없음 — Stage 1부터 계약 확장, FAB-J002 단순화 등을 여기 누적한다)
