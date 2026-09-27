"""체커 3종(unit/timeseries/join) 진입점."""

from __future__ import annotations

import ast

from fab_review.analysis.flow import analyze_file
from fab_review.checkers import join as join_checker
from fab_review.checkers import timeseries as timeseries_checker
from fab_review.checkers import unit as unit_checker
from fab_review.contract.schema import Contract
from fab_review.models import Finding


def run_all(tree: ast.Module, file: str, contract: Contract) -> list[Finding]:
    flow_result = analyze_file(tree, contract)
    findings: list[Finding] = []
    findings.extend(unit_checker.check(tree, flow_result, contract, file))
    findings.extend(timeseries_checker.check(flow_result, contract, file))
    findings.extend(join_checker.check(flow_result, contract, file))
    return findings
