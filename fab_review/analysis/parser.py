"""소스 파일을 ast로만 읽는다.

CLAUDE.md 절대 원칙 5: 분석 대상 코드를 실행·import하지 않는다. 텍스트를 읽어
``ast.parse``로만 다루고, 대상 코드는 신뢰할 수 없는 입력으로 취급한다.
"""

from __future__ import annotations

import ast
from pathlib import Path


class ParseError(Exception):
    """파싱 실패. 메시지는 사람이 바로 읽을 수 있게 작성한다."""


def parse_file(path: Path) -> ast.Module:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParseError(f"{path}: 파일을 읽을 수 없습니다 ({exc})") from exc
    except UnicodeDecodeError as exc:
        raise ParseError(f"{path}: UTF-8로 읽을 수 없습니다 ({exc})") from exc

    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise ParseError(f"{path}:{exc.lineno}: 구문 오류 ({exc.msg})") from exc
