"""공정 데이터 흐름 추적기.

CLAUDE.md 분석 범위: 단일 파일의 모듈 최상위와 함수 본문의 단순 할당 체인까지만
추적한다. 함수 인자·반환값으로 전달되는 값은 심볼 테이블에 없으므로 자연히
unknown으로 취급된다(``resolve_grain``이 ``symtab``에 없는 이름은 unknown을 반환).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from fab_review.analysis.ast_utils import (
    extract_str_tuple,
    is_name,
    positional_or_keyword,
    string_constant,
)
from fab_review.analysis.merge_ir import (
    MergeCall,
    compute_merge_result_grain,
    parse_merge_call,
)
from fab_review.analysis.values import FlowContext, GrainInfo, SeriesInfo
from fab_review.contract.matcher import match_source
from fab_review.contract.schema import Contract

TrackedValue = GrainInfo | SeriesInfo

LOAD_FUNCS = {"read_csv", "read_parquet", "read_sql"}

# groupby 뒤에 흔히 이어붙는 집계 메서드. base(=groupby 이후 입도)를 그대로 유지한다.
AGG_METHODS = {
    "mean",
    "sum",
    "count",
    "median",
    "std",
    "min",
    "max",
    "agg",
    "aggregate",
    "first",
    "last",
    "size",
    "var",
    "nunique",
}

# 컬럼이 아니라 pandas 자체 속성/메서드로 취급해 Series 추출 대상에서 제외한다.
NON_COLUMN_ATTRS = {
    "loc",
    "iloc",
    "at",
    "iat",
    "values",
    "index",
    "columns",
    "dtypes",
    "shape",
    "T",
    "empty",
    "size",
    "copy",
    "merge",
    "groupby",
    "join",
}


def find_pandas_alias(tree: ast.Module) -> str:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pandas":
                    return alias.asname or "pandas"
    return "pd"


def resolve_series(
    node: ast.AST, symtab: dict[str, TrackedValue], ctx: FlowContext
) -> SeriesInfo | None:
    """``df["col"]``/``df.col`` 형태면 SeriesInfo를, 아니면 None을 반환한다."""
    if isinstance(node, ast.Subscript):
        key = string_constant(node.slice)
        if key is None:
            return None
        base = resolve_grain(node.value, symtab, ctx)
        return SeriesInfo(entity=base.entity, column=key, unknown_reason=base.unknown_reason)

    if isinstance(node, ast.Attribute) and node.attr not in NON_COLUMN_ATTRS:
        base = resolve_grain(node.value, symtab, ctx)
        return SeriesInfo(entity=base.entity, column=node.attr, unknown_reason=base.unknown_reason)

    return None


def resolve_grain(node: ast.AST, symtab: dict[str, TrackedValue], ctx: FlowContext) -> GrainInfo:
    if isinstance(node, ast.Name):
        value = symtab.get(node.id)
        if value is None:
            return GrainInfo.unknown(f"추적되지 않는 변수: {node.id}")
        if isinstance(value, SeriesInfo):
            return GrainInfo.unknown(f"'{node.id}'는 Series이며 DataFrame이 아님")
        return value

    if isinstance(node, ast.Call):
        return _resolve_call_grain(node, symtab, ctx)

    if isinstance(node, ast.Subscript):
        # 컬럼 선택(리스트)이든 행 필터링(마스크)이든 입도는 유지된다.
        return resolve_grain(node.value, symtab, ctx)

    if isinstance(node, ast.Attribute):
        return GrainInfo.unknown(f"'{node.attr}' 속성 참조는 추적하지 않음")

    return GrainInfo.unknown("정적으로 추적할 수 없는 표현식")


def _resolve_call_grain(node: ast.Call, symtab: dict[str, TrackedValue], ctx: FlowContext) -> GrainInfo:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return GrainInfo.unknown("알 수 없는 형태의 호출")

    attr = func.attr

    if attr in LOAD_FUNCS and is_name(func.value, ctx.pandas_alias):
        return _resolve_load_point(node, ctx)

    if attr == "merge":
        call = parse_merge_call(node, ctx)
        if call is None:
            return GrainInfo.unknown("merge 호출을 해석할 수 없음")
        left_grain = resolve_grain(call.left_node, symtab, ctx)
        right_grain = resolve_grain(call.right_node, symtab, ctx)
        return compute_merge_result_grain(left_grain, right_grain, call, ctx.contract)

    if attr == "join":
        return GrainInfo.unknown("df.join()은 인덱스 기준 조인이라 정적으로 판정하지 않음")

    base = resolve_grain(func.value, symtab, ctx)

    if attr == "groupby":
        keys = extract_str_tuple(positional_or_keyword(node, 0, "by"))
        if keys is None:
            return GrainInfo.unknown("groupby 키를 정적으로 알 수 없음")
        return GrainInfo(
            entity=base.entity, current_key=keys, sensor=base.sensor, unknown_reason=base.unknown_reason
        )

    if attr == "copy":
        return base

    if attr in AGG_METHODS:
        return base

    return GrainInfo.unknown(f"'{attr}' 호출은 추적 대상이 아님")


def _resolve_load_point(node: ast.Call, ctx: FlowContext) -> GrainInfo:
    """read_csv/read_parquet/read_sql의 첫 인자가 문자열 리터럴일 때만 basename을
    계약의 sources 패턴과 대조한다. 변수/f-string이면 unknown."""
    literal = string_constant(node.args[0]) if node.args else None
    if literal is None:
        return GrainInfo.unknown("경로가 문자열 리터럴이 아님(변수/f-string)")

    basename = literal.replace("\\", "/").rsplit("/", 1)[-1]
    source = match_source(ctx.contract, basename)
    if source is None:
        return GrainInfo.unknown(f"'{basename}'이 계약의 sources 패턴과 매칭되지 않음")

    entity = ctx.contract.entities[source.entity]
    return GrainInfo(entity=source.entity, current_key=tuple(entity.key), sensor=source.sensor)


def build_scope_symtab(stmts: list[ast.stmt], ctx: FlowContext) -> dict[str, TrackedValue]:
    """단순 할당(``x = expr``, 단일 Name 타깃)만 순서대로 심볼 테이블에 반영한다."""
    symtab: dict[str, TrackedValue] = {}
    for stmt in stmts:
        if not (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
        ):
            continue
        name = stmt.targets[0].id
        series = resolve_series(stmt.value, symtab, ctx)
        symtab[name] = series if series is not None else resolve_grain(stmt.value, symtab, ctx)
    return symtab


@dataclass(frozen=True)
class MergeSighting:
    node: ast.Call
    kind: str  # "merge" | "join"
    left: GrainInfo
    right: GrainInfo
    merge_call: MergeCall | None


def collect_merge_sightings(
    stmts: list[ast.stmt], symtab: dict[str, TrackedValue], ctx: FlowContext
) -> list[MergeSighting]:
    """해당 스코프의 모든 문장을 훑어 merge/join 호출을 전부 찾아낸다.

    할당문의 RHS뿐 아니라 표현식 안에 임의로 중첩된 호출도 잡아야 해서
    ``ast.walk``로 순회한다 (체커가 재사용).
    """
    sightings: list[MergeSighting] = []
    for stmt in stmts:
        for node in ast.walk(stmt):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            attr = node.func.attr
            if attr == "merge":
                call = parse_merge_call(node, ctx)
                if call is None:
                    continue
                left = resolve_grain(call.left_node, symtab, ctx)
                right = resolve_grain(call.right_node, symtab, ctx)
                sightings.append(MergeSighting(node, "merge", left, right, call))
            elif attr == "join":
                left = resolve_grain(node.func.value, symtab, ctx)
                sightings.append(
                    MergeSighting(node, "join", left, GrainInfo.unknown("join() 대상 미추적"), None)
                )
    return sightings


@dataclass(frozen=True)
class ScopeFlowResult:
    symtab: dict[str, TrackedValue]
    merge_sightings: list[MergeSighting]


@dataclass(frozen=True)
class FileFlowResult:
    module: ScopeFlowResult
    functions: dict[str, ScopeFlowResult]


def analyze_file(tree: ast.Module, contract: Contract) -> FileFlowResult:
    """모듈 최상위와 각 최상위 함수 본문을 독립된 스코프로 각각 추적한다."""
    ctx = FlowContext(contract=contract, pandas_alias=find_pandas_alias(tree))

    module_stmts = [stmt for stmt in tree.body if not isinstance(stmt, ast.FunctionDef)]
    module_symtab = build_scope_symtab(module_stmts, ctx)
    module_sightings = collect_merge_sightings(module_stmts, module_symtab, ctx)

    functions: dict[str, ScopeFlowResult] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            local_symtab = build_scope_symtab(stmt.body, ctx)
            local_sightings = collect_merge_sightings(stmt.body, local_symtab, ctx)
            functions[stmt.name] = ScopeFlowResult(local_symtab, local_sightings)

    return FileFlowResult(ScopeFlowResult(module_symtab, module_sightings), functions)
