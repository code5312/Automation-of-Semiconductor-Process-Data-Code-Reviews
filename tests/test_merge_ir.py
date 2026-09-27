"""Stage 3 테스트: merge/join 호출 해석기 (부록 B 함정 다수 포함)."""

from __future__ import annotations

import ast
from pathlib import Path

from fab_review.analysis.merge_ir import (
    compute_merge_result_grain,
    effective_how,
    finer_entity,
    join_key_columns,
    parse_merge_call,
)
from fab_review.analysis.values import FlowContext, GrainInfo
from fab_review.contract.loader import load_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = load_contract(REPO_ROOT / "contracts" / "contract.yaml")


def _call(src: str) -> ast.Call:
    tree = ast.parse(src)
    stmt = tree.body[0]
    value = stmt.value if isinstance(stmt, (ast.Assign, ast.Expr)) else None
    assert isinstance(value, ast.Call)
    return value


def _ctx() -> FlowContext:
    return FlowContext(contract=CONTRACT, pandas_alias="pd")


def test_pd_merge_and_method_merge_resolve_same_operands():
    call1 = parse_merge_call(_call('pd.merge(a, b, on="lot_id")'), _ctx())
    call2 = parse_merge_call(_call('a.merge(b, on="lot_id")'), _ctx())

    assert isinstance(call1.left_node, ast.Name) and call1.left_node.id == "a"
    assert isinstance(call1.right_node, ast.Name) and call1.right_node.id == "b"
    assert isinstance(call2.left_node, ast.Name) and call2.left_node.id == "a"
    assert isinstance(call2.right_node, ast.Name) and call2.right_node.id == "b"
    assert call1.on == call2.on == ("lot_id",)


def test_on_string_and_list_are_equivalent():
    call_str = parse_merge_call(_call('a.merge(b, on="lot_id")'), _ctx())
    call_list = parse_merge_call(_call('a.merge(b, on=["lot_id"])'), _ctx())
    assert call_str.on == call_list.on == ("lot_id",)


def test_on_list_with_multiple_keys():
    call = parse_merge_call(_call('a.merge(b, on=["lot_id", "wafer_id"])'), _ctx())
    assert call.on == ("lot_id", "wafer_id")


def test_left_on_right_on_are_supported():
    call = parse_merge_call(
        _call('a.merge(b, left_on="wafer_num", right_on="wafer_id")'), _ctx()
    )
    assert call.left_on == ("wafer_num",)
    assert call.right_on == ("wafer_id",)
    assert join_key_columns(call) == frozenset({"wafer_num", "wafer_id"})


def test_how_omitted_resolves_to_inner():
    call = parse_merge_call(_call('a.merge(b, on="lot_id")'), _ctx())
    assert call.how_omitted is True
    assert effective_how(call) == "inner"


def test_how_explicit_literal_is_preserved():
    call = parse_merge_call(_call('a.merge(b, on="lot_id", how="left")'), _ctx())
    assert call.how_omitted is False
    assert effective_how(call) == "left"


def test_how_non_literal_cannot_be_resolved():
    call = parse_merge_call(_call('a.merge(b, on="lot_id", how=mode)'), _ctx())
    assert effective_how(call) is None


def test_join_method_call_is_not_parsed_as_merge():
    assert parse_merge_call(_call("a.join(b)"), _ctx()) is None


def test_unrelated_call_is_not_a_merge_call():
    assert parse_merge_call(_call("a.copy()"), _ctx()) is None


def test_finer_entity_prefers_descendant():
    assert finer_entity(CONTRACT, "wafer", "metrology") == "metrology"
    assert finer_entity(CONTRACT, "metrology", "wafer") == "metrology"
    assert finer_entity(CONTRACT, "lot", "wafer") == "wafer"


def test_finer_entity_same_entity():
    assert finer_entity(CONTRACT, "wafer", "wafer") == "wafer"


def test_finer_entity_unrelated_entities_is_none():
    assert finer_entity(CONTRACT, "fdc_trace", "lot") is None


def test_compute_merge_result_grain_missing_key_is_j001_unknown():
    call = parse_merge_call(_call('a.merge(b, on="lot_id")'), _ctx())
    left = GrainInfo(entity="wafer", current_key=("lot_id", "wafer_id"))
    right = GrainInfo(entity="metrology", current_key=("lot_id", "wafer_id", "site_id"))

    result = compute_merge_result_grain(left, right, call, CONTRACT)
    assert result.entity is None
    assert "FAB-J001" in result.unknown_reason


def test_compute_merge_result_grain_full_key_follows_equal_current_key():
    call = parse_merge_call(_call('a.merge(b, on=["lot_id", "wafer_id"])'), _ctx())
    left = GrainInfo(entity="wafer", current_key=("lot_id", "wafer_id"))
    right = GrainInfo(entity="metrology", current_key=("lot_id", "wafer_id"))  # 집계 후

    result = compute_merge_result_grain(left, right, call, CONTRACT)
    assert result.entity == "wafer"


def test_compute_merge_result_grain_raw_metrology_follows_finer_side():
    call = parse_merge_call(_call('a.merge(b, on=["lot_id", "wafer_id"])'), _ctx())
    left = GrainInfo(entity="wafer", current_key=("lot_id", "wafer_id"))
    right = GrainInfo(entity="metrology", current_key=("lot_id", "wafer_id", "site_id"))

    result = compute_merge_result_grain(left, right, call, CONTRACT)
    assert result.entity == "metrology"  # site 입도(더 세밀함)를 따름


def test_compute_merge_result_grain_same_entity_skips_ancestor_key_check():
    # tool_id+timestamp만 조인 키로 써서 fdc_trace의 계약 키(chamber_id 포함)를
    # 다 채우지 못하지만, 같은 엔티티끼리의 병합이라 FAB-J001 대상이 아니다.
    call = parse_merge_call(_call('a.merge(b, on=["tool_id", "timestamp"])'), _ctx())
    left = GrainInfo(
        entity="fdc_trace", current_key=("tool_id", "chamber_id", "timestamp"), sensor="rf_power"
    )
    right = GrainInfo(
        entity="fdc_trace", current_key=("tool_id", "chamber_id", "timestamp"), sensor="gas_flow"
    )

    result = compute_merge_result_grain(left, right, call, CONTRACT)
    assert result.entity == "fdc_trace"
    assert result.unknown_reason is None


def test_compute_merge_result_grain_same_entity_incomparable_keys_is_unknown_without_j001_label():
    call = parse_merge_call(_call('a.merge(b, on="x")'), _ctx())
    left = GrainInfo(entity="wafer", current_key=("lot_id", "wafer_id"))
    right = GrainInfo(entity="wafer", current_key=("lot_id", "step_id"))

    result = compute_merge_result_grain(left, right, call, CONTRACT)
    assert result.entity is None
    assert "FAB-J001" not in (result.unknown_reason or "")


def test_compute_merge_result_grain_unknown_entity_is_unknown():
    call = parse_merge_call(_call('a.merge(b, on="lot_id")'), _ctx())
    left = GrainInfo.unknown("추적 실패")
    right = GrainInfo(entity="metrology", current_key=("lot_id", "wafer_id", "site_id"))

    result = compute_merge_result_grain(left, right, call, CONTRACT)
    assert result.entity is None
