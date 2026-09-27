"""AST 노드에서 리터럴 값을 뽑아내는 저수준 헬퍼. flow.py/merge_ir.py가 공용으로 쓴다."""

from __future__ import annotations

import ast


def is_name(node: ast.AST | None, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def string_constant(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def keyword_only(call: ast.Call, name: str) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def positional_or_keyword(call: ast.Call, index: int, keyword: str) -> ast.AST | None:
    if len(call.args) > index:
        return call.args[index]
    return keyword_only(call, keyword)


def extract_str_tuple(node: ast.AST | None) -> tuple[str, ...] | None:
    """단일 문자열 리터럴 또는 문자열 리터럴 리스트/튜플을 tuple[str, ...]로 정규화한다.

    CLAUDE.md 분석 규칙: `on`이 문자열이든 리스트든 같게 해석해야 한다.
    """
    if node is None:
        return None

    single = string_constant(node)
    if single is not None:
        return (single,)

    if isinstance(node, (ast.List, ast.Tuple)):
        values: list[str] = []
        for elt in node.elts:
            value = string_constant(elt)
            if value is None:
                return None  # 리스트 안에 비리터럴이 섞이면 전체를 알 수 없음으로 처리
            values.append(value)
        return tuple(values)

    return None
