"""공정 데이터 계약 로더.

로딩 실패(파일 없음, YAML 파싱 실패, 스키마 위반)는 모두 ContractError로 통일해
CLI가 사람이 읽을 수 있는 메시지를 출력하고 종료 코드 2를 반환하도록 한다.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from fab_review.contract.schema import Contract


class ContractError(Exception):
    """계약 로딩 실패. 메시지는 사람이 바로 읽을 수 있게 작성한다."""


def load_contract(path: Path) -> Contract:
    if not path.exists():
        raise ContractError(f"계약 파일을 찾을 수 없습니다: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ContractError(f"계약 YAML 파싱에 실패했습니다: {path}\n{exc}") from exc

    if raw is None:
        raise ContractError(f"계약 파일이 비어 있습니다: {path}")
    if not isinstance(raw, dict):
        raise ContractError(f"계약 파일의 최상위 구조가 매핑(mapping)이 아닙니다: {path}")

    try:
        return Contract.model_validate(raw)
    except ValidationError as exc:
        raise ContractError(_format_validation_error(path, exc)) from exc


def _format_validation_error(path: Path, exc: ValidationError) -> str:
    lines = [f"계약 파일이 스키마를 위반했습니다: {path}"]
    for error in exc.errors():
        location = ".".join(str(p) for p in error["loc"]) if error["loc"] else "(전체)"
        lines.append(f"  - {location}: {error['msg']}")
    return "\n".join(lines)
