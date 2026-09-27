"""규칙 카탈로그. 규칙 ID별 설명·예시·수정 제안 템플릿을 한곳에 모은다.

Stage 5의 리포터가 여기서 사람이 읽을 설명을 가져다 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    title: str
    invariant: str
    example: str
    suggestion_template: str


CATALOG: dict[str, RuleSpec] = {
    "FAB-U001": RuleSpec(
        rule_id="FAB-U001",
        title="단위 혼용 연산/결합",
        invariant=(
            "물리량 정합성 — 계약상 같은 물리량 family인데 단위 토큰이 다른 값끼리 "
            "산술·비교·concat하면 둘 다 float라 예외 없이 실행되지만 결과가 물리적으로 무의미하다."
        ),
        example='pd.concat([tool_a_df["chamber_pressure_mtorr"], tool_b_df["chamber_pressure_pa"]])',
        suggestion_template="한쪽 단위를 다른 쪽으로 변환한 뒤 연산/결합하세요 (예: mTorr <-> Pa).",
    ),
    "FAB-T001": RuleSpec(
        rule_id="FAB-T001",
        title="샘플링 주기가 다른 센서의 정확 일치 병합",
        invariant=(
            "시간 정합성 — 계약상 샘플링 주기가 다른 time 입도 엔티티끼리 timestamp를 "
            "정확 일치로 병합하면, 매칭되지 않은 행이 조용히 빠진다."
        ),
        example='rf_power_df.merge(gas_flow_df, on=["tool_id", "timestamp"])',
        suggestion_template=(
            "pd.merge_asof(..., on='timestamp', by=<tool/chamber 키>, direction='nearest', "
            "tolerance=<계약의 샘플링 주기 기준>)을 쓰거나 공통 주기로 resample한 뒤 병합하세요."
        ),
    ),
    "FAB-J001": RuleSpec(
        rule_id="FAB-J001",
        title="조인 입도 키 누락",
        invariant=(
            "계보·입도 정합성 — 조인 키가 두 엔티티의 공통 조상 입도의 키를 모두 포함하지 "
            "않으면, pandas merge는 다대다 조인을 기본 허용하므로 행이 곱해질 수 있다."
        ),
        example='yield_df.merge(metrology_df, on="lot_id")  # wafer_id 누락',
        suggestion_template=(
            "누락된 키를 조인 키에 추가하거나, 먼저 공통 조상 입도로 집계한 뒤 전체 키로 "
            "조인하세요 (필요하면 how='left'+validate+indicator 사용)."
        ),
    ),
    "FAB-J002": RuleSpec(
        rule_id="FAB-J002",
        title="표본 커버리지 엔티티의 암묵적 inner join",
        invariant=(
            "계보·입도 정합성 — coverage: sampled 엔티티와 how를 생략한(암묵적 inner) "
            "조인은 미측정 대상을 결과에서 조용히 뺀다."
        ),
        example="yield_df.merge(metrology_df, on=[...])  # how 생략, metrology는 표본 측정",
        suggestion_template='how="left"와 indicator=True를 명시해 미측정 대상을 보존/식별하세요.',
    ),
}
