"""Stage 3 테스트: Finding 모델."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fab_review.models import Finding


def _finding(**overrides) -> Finding:
    base = dict(
        rule_id="FAB-J001",
        severity="error",
        file="samples/bug_join.py",
        line=10,
        col=0,
        message="wafer 입도를 lot_id만으로 조인했습니다",
        suggestion="wafer_id를 조인 키에 추가하세요",
        contract_version="0.1.0",
    )
    base.update(overrides)
    return Finding(**base)


def test_finding_minimal_valid_defaults_source_to_rule():
    finding = _finding()
    assert finding.source == "rule"
    assert finding.evidence == {}


def test_finding_accepts_evidence_dict():
    finding = _finding(evidence={"entity": "wafer", "missing_key": ["wafer_id"]})
    assert finding.evidence["missing_key"] == ["wafer_id"]


def test_finding_rejects_unknown_severity():
    with pytest.raises(ValidationError):
        _finding(severity="warn")


def test_finding_rejects_unknown_extra_field():
    with pytest.raises(ValidationError):
        _finding(unexpected_field=123)


def test_finding_allows_warning_reserved_for_llm_layer():
    finding = _finding(severity="warning", source="llm")
    assert finding.severity == "warning"
