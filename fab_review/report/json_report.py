"""JSON 리포터."""

from __future__ import annotations

import json

from fab_review.models import Finding


def render_json(findings: list[Finding], contract_version: str) -> str:
    payload = {
        "contract_version": contract_version,
        "error_count": sum(1 for f in findings if f.severity == "error"),
        "info_count": sum(1 for f in findings if f.severity == "info"),
        "findings": [f.model_dump() for f in findings],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
