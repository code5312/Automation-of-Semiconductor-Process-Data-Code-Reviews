"""FAB-J001/FAB-J002: 계보·입도 정합성 검사기.

CLAUDE.md 규칙표:
- FAB-J001 error: 조인 키가 두 엔티티의 공통 조상 입도의 키를 모두 포함하지 않음
  info로 낮추는 경우: 한쪽 엔티티를 알 수 없음
- FAB-J002 error: `coverage: sampled` 엔티티와 `how`를 생략한 조인(암묵적 inner)
  info로 낮추는 경우: `how="inner"`를 명시함(의도가 드러난 것으로 보고 사람 확인 요청)

사용자 결정(Stage 3): 같은 엔티티끼리의 병합은 FAB-J001 대상에서 제외한다
(부모-자식 엔티티 사이의 계보 위반을 잡는 규칙이라, 같은 엔티티의 부분 키 병합은
대상이 아니라고 판단했다 — docs/progress.md 참고).
"""

from __future__ import annotations

from fab_review.analysis.flow import FileFlowResult, MergeSighting
from fab_review.analysis.merge_ir import effective_how, join_key_columns
from fab_review.checkers.catalog import CATALOG
from fab_review.contract.schema import Contract
from fab_review.models import Finding

RULE_ID_J001 = "FAB-J001"
RULE_ID_J002 = "FAB-J002"


def _j001_info(sighting: MergeSighting, file: str, contract: Contract, reason: str) -> Finding:
    return Finding(
        rule_id=RULE_ID_J001,
        severity="info",
        file=file,
        line=getattr(sighting.node, "lineno", 0),
        col=getattr(sighting.node, "col_offset", 0),
        message=f"조인 입도 위반 여부를 판정할 수 없습니다: {reason}.",
        evidence={"reason": reason},
        suggestion="엔티티/조인 키를 계약에 보강하거나 사람이 직접 확인하세요.",
        contract_version=contract.contract_version,
    )


def _judge_j001(sighting: MergeSighting, contract: Contract, file: str) -> Finding | None:
    if sighting.kind == "join":
        return _j001_info(sighting, file, contract, "df.join()은 인덱스 기준 조인이라 정적으로 판정할 수 없음")

    if sighting.kind != "merge" or sighting.merge_call is None:
        return None

    left, right = sighting.left, sighting.right
    if left.entity is None or right.entity is None:
        return _j001_info(sighting, file, contract, "한쪽 이상의 엔티티를 식별할 수 없음")

    if left.entity == right.entity:
        return None  # 같은 엔티티끼리의 병합은 대상이 아님(사용자 결정, Stage 3)

    ancestor = contract.common_ancestor(left.entity, right.entity)
    if ancestor is None:
        return _j001_info(sighting, file, contract, "두 엔티티의 관계가 계약에 정의돼 있지 않음")

    ancestor_key = set(contract.entities[ancestor].key)
    join_keys = join_key_columns(sighting.merge_call)
    if join_keys is None:
        return _j001_info(sighting, file, contract, "조인 키를 정적으로 알 수 없음")

    if join_keys.issuperset(ancestor_key):
        return None

    missing = sorted(ancestor_key - join_keys)
    return Finding(
        rule_id=RULE_ID_J001,
        severity="error",
        file=file,
        line=getattr(sighting.node, "lineno", 0),
        col=getattr(sighting.node, "col_offset", 0),
        message=(
            f"{left.entity} 입도와 {right.entity} 입도를 조인하는데, 공통 조상({ancestor}) "
            f"입도의 키 {sorted(ancestor_key)} 중 {missing}가 조인 키에서 빠졌습니다. "
            "행이 예상보다 곱해질 수 있습니다."
        ),
        evidence={
            "left_entity": left.entity,
            "right_entity": right.entity,
            "common_ancestor": ancestor,
            "ancestor_key": sorted(ancestor_key),
            "join_keys": sorted(join_keys),
            "missing_keys": missing,
        },
        suggestion=CATALOG[RULE_ID_J001].suggestion_template,
        contract_version=contract.contract_version,
    )


def _judge_j002(sighting: MergeSighting, contract: Contract, file: str) -> Finding | None:
    if sighting.kind != "merge" or sighting.merge_call is None:
        return None

    left, right = sighting.left, sighting.right
    call = sighting.merge_call

    sampled_entity: str | None = None
    for grain in (left, right):
        if grain.entity is None:
            continue
        entity = contract.entities.get(grain.entity)
        if entity is not None and entity.coverage == "sampled":
            sampled_entity = grain.entity
            break

    if sampled_entity is None:
        return None  # 표본 커버리지 엔티티가 관여하지 않으면 J002 대상이 아니다

    how = effective_how(call)
    if how is None:
        return _j002_finding(
            sighting, file, contract, sampled_entity, "info",
            "how를 정적으로 알 수 없어 암묵적 inner 여부를 판정할 수 없습니다",
        )

    if call.how_omitted and how == "inner":
        return _j002_finding(
            sighting, file, contract, sampled_entity, "error",
            "how를 생략해 암묵적 inner join이 되어, 표본 측정되지 않은 대상이 결과에서 조용히 빠집니다",
        )

    if not call.how_omitted and call.how_literal == "inner":
        return _j002_finding(
            sighting, file, contract, sampled_entity, "info",
            'how="inner"를 명시적으로 지정했습니다(의도가 드러난 것으로 보고 사람 확인을 요청합니다)',
        )

    return None  # how="left"/"right"/"outer" 등 명시적 안전 선택


def _j002_finding(
    sighting: MergeSighting, file: str, contract: Contract, sampled_entity: str, severity: str, reason: str
) -> Finding:
    return Finding(
        rule_id=RULE_ID_J002,
        severity=severity,
        file=file,
        line=getattr(sighting.node, "lineno", 0),
        col=getattr(sighting.node, "col_offset", 0),
        message=f"표본 커버리지 엔티티({sampled_entity})와의 조인: {reason}.",
        evidence={"sampled_entity": sampled_entity, "reason": reason},
        suggestion=CATALOG[RULE_ID_J002].suggestion_template,
        contract_version=contract.contract_version,
    )


def check(flow_result: FileFlowResult, contract: Contract, file: str) -> list[Finding]:
    findings: list[Finding] = []
    for scope in (flow_result.module, *flow_result.functions.values()):
        for sighting in scope.merge_sightings:
            j001 = _judge_j001(sighting, contract, file)
            if j001:
                findings.append(j001)
            j002 = _judge_j002(sighting, contract, file)
            if j002:
                findings.append(j002)
    return findings
