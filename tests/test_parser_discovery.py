"""Stage 3 테스트: 입력 어댑터(discovery)와 AST 파서."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from fab_review.analysis.discovery import discover_python_files
from fab_review.analysis.parser import ParseError, parse_file

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_parse_valid_file_returns_module_with_filename():
    tree = parse_file(REPO_ROOT / "samples" / "normal.py")
    assert isinstance(tree, ast.Module)


def test_parse_missing_file_raises_parse_error():
    with pytest.raises(ParseError):
        parse_file(REPO_ROOT / "samples" / "does_not_exist.py")


def test_parse_syntax_error_raises_parse_error_with_line(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text("def f(:\n    pass\n", encoding="utf-8")
    with pytest.raises(ParseError, match="구문 오류"):
        parse_file(bad)


def test_discover_single_file_returns_that_file():
    target = REPO_ROOT / "samples" / "normal.py"
    assert discover_python_files(target) == [target]


def test_discover_directory_is_sorted_and_recursive(tmp_path: Path):
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("x = 1\n", encoding="utf-8")

    result = discover_python_files(tmp_path)
    assert result == sorted(result)
    assert len(result) == 3


def test_discover_nonexistent_path_raises():
    with pytest.raises(FileNotFoundError):
        discover_python_files(REPO_ROOT / "no_such_dir_xyz")


def test_discover_non_python_file_raises(tmp_path: Path):
    txt = tmp_path / "x.txt"
    txt.write_text("hi", encoding="utf-8")
    with pytest.raises(ValueError):
        discover_python_files(txt)
