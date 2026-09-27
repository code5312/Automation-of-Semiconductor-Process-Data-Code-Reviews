"""Stage 5 테스트: CLI 엔드투엔드 + 첫 데모 체크포인트(docs/checklist.md).

체크포인트 5개:
1. 네트워크·LLM 없이 로컬에서 CLI 한 줄로 실행된다
2. 버그 스크립트 3개 -> 각각 기대 규칙 ID가 error로 출력된다
3. 정상 스크립트 -> error 0건
4. 리포트에 계약 버전, 줄 번호, 수정 제안이 포함된다
5. 같은 입력을 반복 실행하면 결과가 항상 동일하다
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = REPO_ROOT / "contracts" / "contract.yaml"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "fab_review", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_check_samples_dir_exits_1_with_expected_rule_ids():
    result = _run_cli("check", "samples/", "--contract", str(CONTRACT), "--format", "json")
    assert result.returncode == 1, result.stderr

    payload = json.loads(result.stdout)
    assert payload["error_count"] == 4
    rule_ids = {f["rule_id"] for f in payload["findings"]}
    assert rule_ids == {"FAB-U001", "FAB-T001", "FAB-J001", "FAB-J002"}


def test_check_normal_script_exits_0_with_zero_errors():
    result = _run_cli("check", "samples/normal.py", "--contract", str(CONTRACT), "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["error_count"] == 0


def test_check_is_deterministic_across_runs():
    first = _run_cli("check", "samples/", "--contract", str(CONTRACT), "--format", "json")
    second = _run_cli("check", "samples/", "--contract", str(CONTRACT), "--format", "json")
    assert first.returncode == second.returncode
    assert first.stdout == second.stdout


def test_check_missing_contract_exits_2():
    result = _run_cli("check", "samples/", "--contract", "contracts/does_not_exist.yaml")
    assert result.returncode == 2


def test_check_missing_path_exits_2():
    result = _run_cli("check", "no_such_dir_xyz/", "--contract", str(CONTRACT))
    assert result.returncode == 2


def test_report_includes_contract_version_line_and_suggestion():
    result = _run_cli("check", "samples/bug_join.py", "--contract", str(CONTRACT), "--format", "md")
    assert result.returncode == 1
    assert "0.1.0" in result.stdout
    assert ":16" in result.stdout
    assert "제안" in result.stdout


def test_check_writes_report_to_out_file(tmp_path: Path):
    out_file = tmp_path / "out.md"
    result = _run_cli(
        "check",
        "samples/bug_unit.py",
        "--contract",
        str(CONTRACT),
        "--format",
        "md",
        "--out",
        str(out_file),
    )
    assert result.returncode == 1
    assert out_file.exists()
    assert "FAB-U001" in out_file.read_text(encoding="utf-8")
