"""입력 어댑터: 파일/디렉토리 경로를 분석 대상 .py 파일 목록으로 바꾼다."""

from __future__ import annotations

from pathlib import Path


def discover_python_files(path: Path) -> list[Path]:
    """결정론(CLAUDE.md 절대 원칙 2)을 위해 항상 정렬된 목록을 반환한다."""
    if path.is_file():
        if path.suffix != ".py":
            raise ValueError(f"파이썬 파일이 아닙니다: {path}")
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.py"))
    raise FileNotFoundError(f"경로를 찾을 수 없습니다: {path}")
