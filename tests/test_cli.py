"""Stage 0 스캐폴딩 테스트: CLI 골격이 정상적으로 뜨는지만 확인한다."""

import subprocess
import sys

import pytest

from fab_review.cli import build_parser, run


def test_help_exits_zero_via_run_function():
    with pytest.raises(SystemExit) as exc_info:
        run(["--help"])
    assert exc_info.value.code == 0


def test_check_subcommand_parses_required_args():
    parser = build_parser()
    args = parser.parse_args(
        ["check", "samples/", "--contract", "contracts/contract.yaml"]
    )
    assert args.command == "check"
    assert args.format == "md"


def test_module_entrypoint_help(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "fab_review", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert "fab-review" in result.stdout
