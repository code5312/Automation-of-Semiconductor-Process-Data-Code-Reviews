"""Finding 모델. 체커(unit/timeseries/join)가 만드는 판정 결과의 공통 형태.

CLAUDE.md 등급 규정: ``error`` | ``info`` (``warning``은 LLM 레이어를 위해
타입만 예약해두고 프로토타입에서는 만들지 않는다).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    severity: Literal["error", "warning", "info"]
    file: str
    line: int
    col: int
    message: str
    evidence: dict[str, Any] = {}
    suggestion: str
    contract_version: str
    source: Literal["rule", "llm"] = "rule"
