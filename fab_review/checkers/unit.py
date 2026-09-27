"""FAB-U001: 물리량(단위) 정합성 검사기.

CLAUDE.md 분석 규칙:
- 컬럼명·변수명을 ``_``로 나눈 **마지막 토큰만** 단위 후보로 본다.
- 계약의 ``unit_families`` 토큰과 대소문자 무시로 일치할 때만 단위로 인정한다.
- 길이 1인 토큰(``c``, ``k``, ``a``)은 error 근거로 쓰지 않는다(모호로 취급).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from fab_review.analysis.ast_utils import is_name, string_constant
from fab_review.analysis.flow import FileFlowResult, TrackedValue, find_pandas_alias
from fab_review.analysis.values import SeriesInfo
from fab_review.checkers.catalog import CATALOG
from fab_review.contract.matcher import match_parameter
from fab_review.contract.schema import Contract
from fab_review.models import Finding

RULE_ID = "FAB-U001"

ARITH_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv)


@dataclass(frozen=True)
class _UnitInfo:
    family: str | None
    unit: str | None  # 계약에 등록된 표준 토큰(원래 대소문자). None이면 모호/없음.


def _name_for(node: ast.AST, symtab: dict[str, TrackedValue]) -> str | None:
    """산술/비교/concat 피연산자에서 단위 판정에 쓸 "이름"을 뽑는다.

    ``df["col"]``/``df.col``이면 컬럼명, 심볼 테이블에 Series로 추적된 변수면 그
    컬럼명, 그 외 변수면 변수명 자체를 쓴다.
    """
    if isinstance(node, ast.Subscript):
        return string_constant(node.slice)
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        value = symtab.get(node.id)
        if isinstance(value, SeriesInfo):
            return value.column
        return node.id
    return None


def _unit_info(name: str, contract: Contract) -> _UnitInfo:
    matched = match_parameter(contract, name)
    if matched is None:
        return _UnitInfo(family=None, unit=None)

    _, param = matched
    tokens = name.split("_")
    last = tokens[-1] if tokens else ""
    if len(last) <= 1:
        return _UnitInfo(family=param.family, unit=None)

    for token in contract.unit_families.get(param.family, []):
        if token.lower() == last.lower():
            return _UnitInfo(family=param.family, unit=token)
    return _UnitInfo(family=param.family, unit=None)


def _judge_pair(node: ast.AST, name_a: str, name_b: str, contract: Contract, file: str) -> Finding | None:
    info_a = _unit_info(name_a, contract)
    info_b = _unit_info(name_b, contract)

    if info_a.family is None or info_b.family is None or info_a.family != info_b.family:
        return None  # 물리량 family가 다르거나 확정 안 되면 U001 대상이 아님

    if info_a.unit is not None and info_b.unit is not None:
        if info_a.unit == info_b.unit:
            return None  # 같은 단위면 위반 아님
        severity = "error"
        message = (
            f"'{name_a}'({info_a.unit})와 '{name_b}'({info_b.unit})는 계약상 같은 "
            f"물리량({info_a.family})이지만 단위가 달라, 그대로 연산/결합하면 물리적으로 "
            "무의미한 값이 됩니다."
        )
        suggestion = CATALOG[RULE_ID].suggestion_template
    else:
        severity = "info"
        message = (
            f"'{name_a}'와 '{name_b}'는 계약상 같은 물리량({info_a.family})으로 보이지만 "
            "단위 토큰이 모호하거나 없어 위반 여부를 확정할 수 없습니다."
        )
        suggestion = "단위 토큰을 이름에 명확히 남기거나 사람이 직접 확인하세요."

    return Finding(
        rule_id=RULE_ID,
        severity=severity,
        file=file,
        line=getattr(node, "lineno", 0),
        col=getattr(node, "col_offset", 0),
        message=message,
        evidence={
            "operand_a": {"name": name_a, "family": info_a.family, "unit": info_a.unit},
            "operand_b": {"name": name_b, "family": info_b.family, "unit": info_b.unit},
        },
        suggestion=suggestion,
        contract_version=contract.contract_version,
    )


def _check_scope(
    stmts: list[ast.stmt],
    symtab: dict[str, TrackedValue],
    contract: Contract,
    file: str,
    pandas_alias: str,
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ARITH_OPS):
                name_a = _name_for(node.left, symtab)
                name_b = _name_for(node.right, symtab)
                if name_a and name_b:
                    finding = _judge_pair(node, name_a, name_b, contract, file)
                    if finding:
                        findings.append(finding)

            elif isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                names = [_name_for(operand, symtab) for operand in operands]
                for i in range(len(names) - 1):
                    if names[i] and names[i + 1]:
                        finding = _judge_pair(node, names[i], names[i + 1], contract, file)
                        if finding:
                            findings.append(finding)

            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "concat"
                and is_name(node.func.value, pandas_alias)
                and node.args
                and isinstance(node.args[0], (ast.List, ast.Tuple))
            ):
                names = [_name_for(elt, symtab) for elt in node.args[0].elts]
                for i in range(len(names)):
                    for j in range(i + 1, len(names)):
                        if names[i] and names[j]:
                            finding = _judge_pair(node, names[i], names[j], contract, file)
                            if finding:
                                findings.append(finding)
    return findings


def check(tree: ast.Module, flow_result: FileFlowResult, contract: Contract, file: str) -> list[Finding]:
    pandas_alias = find_pandas_alias(tree)
    module_stmts = [stmt for stmt in tree.body if not isinstance(stmt, ast.FunctionDef)]

    findings = _check_scope(module_stmts, flow_result.module.symtab, contract, file, pandas_alias)
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            findings.extend(
                _check_scope(
                    stmt.body, flow_result.functions[stmt.name].symtab, contract, file, pandas_alias
                )
            )
    return findings
