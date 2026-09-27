"""Stage 2 테스트: 합성 데이터 생성기 + 데모 스크립트.

CLAUDE.md 절대 원칙 5의 예외("Stage 2에서 우리가 만든 데모 스크립트의 동작을
확인할 때")에 따라 여기서만 데모 스크립트를 실제로 실행한다.

완료 기준(docs/checklist.md 2절): 버그 스크립트 3개가 예외 없이 실행되고,
정상 스크립트 대비 결과 수치가 다름을 확인한다.
"""

from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from synth.generate import SEED, generate_all

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ["bug_unit.py", "bug_time.py", "bug_join.py", "normal.py"]


def test_generate_all_is_deterministic(tmp_path: Path):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    generate_all(out_a)
    generate_all(out_b)

    files_a = sorted(p.name for p in out_a.iterdir())
    files_b = sorted(p.name for p in out_b.iterdir())
    assert files_a == files_b

    for name in files_a:
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes()


def test_committed_fixture_matches_generator_output(tmp_path: Path):
    """samples/data/에 커밋된 CSV가 SEED로 재생성한 것과 동일한지 확인한다."""
    regenerated = tmp_path / "regenerated"
    generate_all(regenerated)

    committed_dir = REPO_ROOT / "samples" / "data"
    for path in regenerated.iterdir():
        committed = committed_dir / path.name
        assert committed.exists(), f"{path.name}이 samples/data/에 커밋돼 있지 않다"
        assert committed.read_bytes() == path.read_bytes()


@pytest.mark.parametrize("script_name", SAMPLES)
def test_sample_script_runs_without_exception(script_name: str):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "samples" / script_name)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr


def _run_and_get_globals(script_name: str) -> dict:
    script_path = REPO_ROOT / "samples" / script_name
    return runpy.run_path(str(script_path), run_name="not_main")


def test_bug_join_fans_out_rows_vs_normal():
    bug_globals = _run_and_get_globals("bug_join.py")
    normal_globals = _run_and_get_globals("normal.py")

    bug_rows = len(bug_globals["wafer_yield"])
    normal_rows = len(normal_globals["wafer_yield"])

    assert bug_rows == 1250  # 25 wafers x 10 sampled wafers x 5 sites
    assert normal_rows == 25  # wafer_yield 원본 행 수 그대로 보존 (left join)
    assert bug_rows != normal_rows


def test_bug_time_drops_rows_vs_normal():
    bug_globals = _run_and_get_globals("bug_time.py")
    normal_globals = _run_and_get_globals("normal.py")

    bug_rows = len(bug_globals["merged"])
    normal_rows = len(normal_globals["merged_traces"])

    assert bug_rows == 12  # 정확 일치하는 timestamp만 남음 (0,5,...,55)
    assert normal_rows == 60  # merge_asof는 rf_power 60행을 모두 보존
    assert bug_rows != normal_rows


def test_bug_unit_ucl_differs_from_normal():
    bug_globals = _run_and_get_globals("bug_unit.py")
    normal_globals = _run_and_get_globals("normal.py")

    bug_ucl = bug_globals["ucl"]
    normal_ucl = normal_globals["ucl"]

    assert bug_ucl != pytest.approx(normal_ucl)


def test_seed_is_fixed_constant():
    assert isinstance(SEED, int)
