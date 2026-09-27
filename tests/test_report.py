"""Stage 5 테스트: 리포트 공통(중복 제거·정렬), Markdown/JSON 리포터."""

from __future__ import annotations

import json

from fab_review.models import Finding
from fab_review.report import dedupe_and_sort
from fab_review.report.json_report import render_json
from fab_review.report.markdown import render_markdown


def _finding(**overrides) -> Finding:
    base = dict(
        rule_id="FAB-J001",
        severity="error",
        file="a.py",
        line=10,
        col=0,
        message="m",
        suggestion="s",
        contract_version="0.1.0",
    )
    base.update(overrides)
    return Finding(**base)


def test_dedupe_removes_exact_duplicates():
    result = dedupe_and_sort([_finding(), _finding()])
    assert len(result) == 1


def test_dedupe_keeps_distinct_rule_on_same_line():
    result = dedupe_and_sort([_finding(rule_id="FAB-J001"), _finding(rule_id="FAB-J002")])
    assert len(result) == 2


def test_sort_puts_error_before_info():
    info = _finding(severity="info", line=1)
    error = _finding(severity="error", line=99)
    result = dedupe_and_sort([info, error])
    assert [f.severity for f in result] == ["error", "info"]


def test_sort_is_stable_by_file_then_line():
    f1 = _finding(file="b.py", line=1)
    f2 = _finding(file="a.py", line=5)
    f3 = _finding(file="a.py", line=1)
    result = dedupe_and_sort([f1, f2, f3])
    assert [f.file for f in result] == ["a.py", "a.py", "b.py"]
    assert result[0].line == 1
    assert result[1].line == 5


def test_render_markdown_contains_key_fields():
    finding = _finding(message="테스트 메시지", suggestion="테스트 제안")
    text = render_markdown([finding], "0.1.0")
    assert "FAB-J001" in text
    assert "[ERROR]" in text
    assert "a.py:10" in text
    assert "0.1.0" in text
    assert "테스트 메시지" in text
    assert "테스트 제안" in text


def test_render_markdown_empty_findings_says_no_violations():
    text = render_markdown([], "0.1.0")
    assert "위반이 없습니다" in text


def test_render_markdown_uses_info_tag():
    finding = _finding(severity="info")
    text = render_markdown([finding], "0.1.0")
    assert "[INFO]" in text
    assert "[ERROR]" not in text


def test_render_json_round_trips():
    finding = _finding(evidence={"k": "v"})
    text = render_json([finding], "0.1.0")
    payload = json.loads(text)
    assert payload["contract_version"] == "0.1.0"
    assert payload["error_count"] == 1
    assert payload["findings"][0]["rule_id"] == "FAB-J001"
    assert payload["findings"][0]["evidence"] == {"k": "v"}
