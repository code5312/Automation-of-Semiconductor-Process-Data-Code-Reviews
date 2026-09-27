"""fab-review CLI 진입점.

실행 예: ``fab-review check samples/ --contract contracts/contract.yaml --format md --out report.md``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fab_review.analysis.discovery import discover_python_files
from fab_review.analysis.parser import ParseError, parse_file
from fab_review.checkers import run_all
from fab_review.contract.loader import ContractError, load_contract
from fab_review.contract.schema import Contract
from fab_review.models import Finding
from fab_review.report import dedupe_and_sort
from fab_review.report.json_report import render_json
from fab_review.report.markdown import render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fab-review",
        description="공정 데이터 정합성 검증 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="지정한 경로의 파이썬 코드를 분석해 공정 데이터 정합성 위반을 찾는다",
    )
    check_parser.add_argument("path", type=Path, help="분석할 파일 또는 디렉토리")
    check_parser.add_argument(
        "--contract", type=Path, required=True, help="공정 데이터 계약 YAML 경로"
    )
    check_parser.add_argument(
        "--format", choices=["md", "json"], default="md", help="리포트 형식 (기본: md)"
    )
    check_parser.add_argument(
        "--out", type=Path, default=None, help="리포트 출력 경로 (생략 시 표준출력)"
    )
    check_parser.set_defaults(handler=_handle_check)

    return parser


def _handle_check(args: argparse.Namespace) -> int:
    try:
        contract = load_contract(args.contract)
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        files = discover_python_files(args.path)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for file_path in files:
        try:
            tree = parse_file(file_path)
        except ParseError as exc:
            findings.append(_parse_error_finding(file_path, contract, str(exc)))
            continue
        findings.extend(run_all(tree, file_path.as_posix(), contract))

    findings = dedupe_and_sort(findings)

    if args.format == "json":
        report_text = render_json(findings, contract.contract_version)
    else:
        report_text = render_markdown(findings, contract.contract_version)

    if args.out is not None:
        args.out.write_text(report_text, encoding="utf-8")
    else:
        print(report_text, end="")

    return 1 if any(f.severity == "error" for f in findings) else 0


def _parse_error_finding(file_path: Path, contract: Contract, message: str) -> Finding:
    return Finding(
        rule_id="FAB-PARSE",
        severity="info",
        file=file_path.as_posix(),
        line=1,
        col=0,
        message=f"파일을 분석할 수 없습니다: {message}",
        suggestion="파이썬 구문 오류를 수정한 뒤 다시 분석하세요.",
        contract_version=contract.contract_version,
    )


def run(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
