"""merge/join 호출 해석기.

체커 공용(docs/checklist.md 3절)이라 flow.py의 입도 전파와 Stage 4의
join_checker/timeseries_checker가 이 모듈을 그대로 재사용한다.

CLAUDE.md 분석 규칙:
- ``pd.merge(a, b, ...)``와 ``a.merge(b, ...)``를 똑같이 처리한다.
- ``on``이 문자열이든 리스트든 같게 해석한다. ``left_on``/``right_on``도 지원한다.
- ``how``를 생략하면 inner로 해석한다.
- ``df.join()``은 info로 처리한다 (여기서는 감지만 하고, error/info 등급 판정은
  Stage 4 체커가 한다).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from fab_review.analysis.ast_utils import (
    extract_str_tuple,
    is_name,
    keyword_only,
    positional_or_keyword,
)
from fab_review.analysis.values import FlowContext, GrainInfo
from fab_review.contract.schema import Contract


@dataclass(frozen=True)
class MergeCall:
    node: ast.Call
    left_node: ast.AST
    right_node: ast.AST
    on: tuple[str, ...] | None
    left_on: tuple[str, ...] | None
    right_on: tuple[str, ...] | None
    how_literal: str | None
    how_omitted: bool


def parse_merge_call(node: ast.Call, ctx: FlowContext) -> MergeCall | None:
    """``pd.merge(a, b, ...)``와 ``a.merge(b, ...)`` 두 형태를 동일하게 해석한다."""
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "merge":
        return None

    func = node.func
    if is_name(func.value, ctx.pandas_alias):
        left_node = positional_or_keyword(node, 0, "left")
        right_node = positional_or_keyword(node, 1, "right")
    else:
        left_node = func.value
        right_node = positional_or_keyword(node, 0, "right")

    if left_node is None or right_node is None:
        return None

    on = extract_str_tuple(keyword_only(node, "on"))
    left_on = extract_str_tuple(keyword_only(node, "left_on"))
    right_on = extract_str_tuple(keyword_only(node, "right_on"))

    how_node = keyword_only(node, "how")
    if how_node is None:
        how_literal, how_omitted = None, True
    else:
        how_omitted = False
        how_literal = (
            how_node.value
            if isinstance(how_node, ast.Constant) and isinstance(how_node.value, str)
            else None
        )

    return MergeCall(node, left_node, right_node, on, left_on, right_on, how_literal, how_omitted)


def is_join_method_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "join"


def join_key_columns(call: MergeCall) -> frozenset[str] | None:
    """조인 키 컬럼 집합. ``on`` 우선, 없으면 ``left_on``∪``right_on``. 둘 다 없으면 None."""
    if call.on is not None:
        return frozenset(call.on)
    if call.left_on is not None or call.right_on is not None:
        cols = set(call.left_on or ()) | set(call.right_on or ())
        return frozenset(cols) if cols else None
    return None


def effective_how(call: MergeCall) -> str | None:
    """``how`` 생략 시 inner로 해석. 비리터럴이면 알 수 없음(None)."""
    if call.how_omitted:
        return "inner"
    return call.how_literal


def finer_entity(contract: Contract, entity_a: str, entity_b: str) -> str | None:
    """계약의 부모 체인 기준으로 어느 쪽이 더 세밀한(자식) 엔티티인지 판단한다.

    두 엔티티가 조상-자손 관계가 아니면(관계를 모르면) None.
    """
    if entity_a not in contract.entities or entity_b not in contract.entities:
        return None
    if entity_a == entity_b:
        return entity_a
    if entity_b in contract.ancestors(entity_a):
        return entity_a
    if entity_a in contract.ancestors(entity_b):
        return entity_b
    return None


def compute_merge_result_grain(
    left: GrainInfo, right: GrainInfo, call: MergeCall | None, contract: Contract
) -> GrainInfo:
    """merge 결과의 입도를 계산한다.

    CLAUDE.md 분석 규칙: "merge 결과는 더 세밀한 쪽 입도를 따른다. 단, FAB-J001
    위반이면 unknown이다." 세밀한 쪽은 계약상 엔티티 위치가 아니라 각 피연산자의
    *현재* 유효 키(``current_key``, groupby 등으로 이미 바뀌었을 수 있음)를 비교해
    판단한다 — 이래야 "metrology를 wafer 입도로 집계한 뒤 조인"한 경우에도 결과가
    올바르게 wafer 입도로 판정된다.
    """
    if left.entity is None or right.entity is None:
        return GrainInfo.unknown("병합 대상 중 하나 이상의 엔티티를 알 수 없음")

    ancestor = contract.common_ancestor(left.entity, right.entity)
    if ancestor is None:
        return GrainInfo.unknown("두 엔티티의 관계를 계약에서 알 수 없음")

    ancestor_key = set(contract.entities[ancestor].key)
    join_keys = join_key_columns(call) if call is not None else None
    if join_keys is None or not join_keys.issuperset(ancestor_key):
        return GrainInfo.unknown(
            "조인 키가 공통 조상 입도의 키를 포함하지 않거나(FAB-J001) 조인 키를 알 수 없음"
        )

    left_key = set(left.current_key)
    right_key = set(right.current_key)
    if left_key >= right_key:
        return left
    if right_key >= left_key:
        return right
    return GrainInfo.unknown("더 세밀한 쪽 입도를 판단할 수 없음")
