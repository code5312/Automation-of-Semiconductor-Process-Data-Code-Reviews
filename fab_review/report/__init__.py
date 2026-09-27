"""리포트 공통: 중복 제거 및 정렬(등급 부여는 체커가 이미 끝냈다).

CLAUDE.md 절대 원칙 2(결정론)를 지키기 위해 항상 같은 순서로 정렬한다.
"""

from __future__ import annotations

from fab_review.models import Finding

_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}


def dedupe_and_sort(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (
            finding.rule_id,
            finding.severity,
            finding.file,
            finding.line,
            finding.col,
            finding.message,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)

    return sorted(
        unique,
        key=lambda f: (_SEVERITY_RANK.get(f.severity, 99), f.file, f.line, f.col, f.rule_id),
    )
