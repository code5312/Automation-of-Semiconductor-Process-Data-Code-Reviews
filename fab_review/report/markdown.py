"""Markdown 리포터.

설계서(docs/design.md) 9.5절의 PR 코멘트 형식을 따르되, CLAUDE.md 표기 규칙에 맞춰
이모지 없이 `[ERROR]`/`[INFO]`로만 등급을 표시한다.
"""

from __future__ import annotations

from fab_review.checkers.catalog import CATALOG
from fab_review.models import Finding

_SEVERITY_TAG = {"error": "[ERROR]", "warning": "[WARNING]", "info": "[INFO]"}


def render_markdown(findings: list[Finding], contract_version: str) -> str:
    error_count = sum(1 for f in findings if f.severity == "error")
    info_count = sum(1 for f in findings if f.severity == "info")

    lines: list[str] = [
        "# fab-review 리포트",
        "",
        f"계약 버전: `{contract_version}`  ",
        f"error {error_count}건, info {info_count}건",
        "",
    ]

    if not findings:
        lines.append("발견된 위반이 없습니다.")
        return "\n".join(lines) + "\n"

    for finding in findings:
        tag = _SEVERITY_TAG.get(finding.severity, finding.severity.upper())
        title = CATALOG[finding.rule_id].title if finding.rule_id in CATALOG else finding.rule_id
        lines.append(f"## {tag} {finding.rule_id} — {title} (규칙, contract {contract_version})")
        lines.append("")
        lines.append(f"`{finding.file}:{finding.line}`")
        lines.append("")
        lines.append(finding.message)
        lines.append("")
        lines.append(f"제안: {finding.suggestion}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
