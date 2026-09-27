"""FAB-T001: 시간 정합성(시계열 정렬) 검사기.

CLAUDE.md 규칙표:
- error: 샘플링 주기가 서로 다른 ``time`` 입도 엔티티끼리 timestamp 키를 포함해
  merge(정확 일치)
- info로 낮추는 경우: 한쪽의 센서·주기를 알 수 없음
"""

from __future__ import annotations

from fab_review.analysis.flow import FileFlowResult, MergeSighting
from fab_review.analysis.merge_ir import join_key_columns
from fab_review.checkers.catalog import CATALOG
from fab_review.contract.schema import Contract
from fab_review.models import Finding

RULE_ID = "FAB-T001"
TIME_KEY_COLUMN = "timestamp"


def _judge_sighting(sighting: MergeSighting, contract: Contract, file: str) -> Finding | None:
    if sighting.kind != "merge" or sighting.merge_call is None:
        return None

    left, right = sighting.left, sighting.right
    if left.entity is None or right.entity is None:
        return None  # 엔티티 자체를 모르면 T001 후보가 아니다 (join_checker가 별도로 info 처리)

    left_entity = contract.entities.get(left.entity)
    right_entity = contract.entities.get(right.entity)
    if left_entity is None or right_entity is None:
        return None
    if left_entity.grain != "time" or right_entity.grain != "time":
        return None  # 시간 입도 엔티티끼리의 병합이 아니면 T001 대상이 아니다

    join_keys = join_key_columns(sighting.merge_call)
    if join_keys is None or TIME_KEY_COLUMN not in join_keys:
        return None  # timestamp를 조인 키로 쓰지 않으면 대상이 아니다

    if left.sensor is None or right.sensor is None:
        return _info(sighting, file, contract, "한쪽 이상의 센서를 식별할 수 없습니다")

    left_sensor = contract.sensors.get(left.sensor)
    right_sensor = contract.sensors.get(right.sensor)
    if left_sensor is None or right_sensor is None:
        return _info(sighting, file, contract, "센서의 샘플링 주기가 계약에 정의돼 있지 않습니다")

    if left_sensor.sampling_period == right_sensor.sampling_period:
        return None  # 같은 주기면 정확 일치 병합이 위험하지 않다

    return Finding(
        rule_id=RULE_ID,
        severity="error",
        file=file,
        line=getattr(sighting.node, "lineno", 0),
        col=getattr(sighting.node, "col_offset", 0),
        message=(
            f"샘플링 주기가 다른 센서(`{left.sensor}`={left_sensor.sampling_period}, "
            f"`{right.sensor}`={right_sensor.sampling_period})를 timestamp 정확 일치로 "
            "병합했습니다. 두 시계열이 우연히 겹치는 시각만 남고 나머지 행은 조용히 사라집니다."
        ),
        evidence={
            "left_sensor": left.sensor,
            "right_sensor": right.sensor,
            "left_sampling_period": left_sensor.sampling_period,
            "right_sampling_period": right_sensor.sampling_period,
            "join_keys": sorted(join_keys),
        },
        suggestion=CATALOG[RULE_ID].suggestion_template,
        contract_version=contract.contract_version,
    )


def _info(sighting: MergeSighting, file: str, contract: Contract, reason: str) -> Finding:
    return Finding(
        rule_id=RULE_ID,
        severity="info",
        file=file,
        line=getattr(sighting.node, "lineno", 0),
        col=getattr(sighting.node, "col_offset", 0),
        message=f"timestamp 키로 병합했지만 {reason} — 샘플링 주기 불일치 여부를 판정할 수 없습니다.",
        evidence={"reason": reason},
        suggestion="센서/샘플링 주기를 계약에 보강하거나 사람이 직접 확인하세요.",
        contract_version=contract.contract_version,
    )


def check(flow_result: FileFlowResult, contract: Contract, file: str) -> list[Finding]:
    findings: list[Finding] = []
    for scope in (flow_result.module, *flow_result.functions.values()):
        for sighting in scope.merge_sightings:
            finding = _judge_sighting(sighting, contract, file)
            if finding:
                findings.append(finding)
    return findings
