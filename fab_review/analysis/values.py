"""공정 데이터 흐름 추적에서 쓰는 값 타입.

- ``GrainInfo``: DataFrame 변수가 어떤 공정 엔티티를 어떤 입도(키)로 담고 있는지.
- ``SeriesInfo``: ``df["col"]``/``df.col``처럼 뽑아낸 컬럼(Series)이 어떤 엔티티의
  어떤 컬럼인지 (단위 판정에 쓴다).

둘 다 엔티티를 모르면(``entity is None``) ``unknown_reason``에 사유를 남긴다 —
CLAUDE.md 절대 원칙 3("모르면 통과가 아니라 info")을 만족시키기 위한 자리다.
"""

from __future__ import annotations

from dataclasses import dataclass

from fab_review.contract.schema import Contract


@dataclass(frozen=True)
class GrainInfo:
    entity: str | None
    current_key: tuple[str, ...] = ()
    sensor: str | None = None
    unknown_reason: str | None = None

    @classmethod
    def unknown(cls, reason: str) -> "GrainInfo":
        return cls(entity=None, current_key=(), sensor=None, unknown_reason=reason)

    @property
    def is_unknown(self) -> bool:
        return self.entity is None


@dataclass(frozen=True)
class SeriesInfo:
    entity: str | None
    column: str
    unknown_reason: str | None = None

    @property
    def is_unknown(self) -> bool:
        return self.entity is None


@dataclass
class FlowContext:
    contract: Contract
    pandas_alias: str
