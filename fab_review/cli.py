"""fab-review CLI 진입점.

Stage 0에서는 인자 구조만 만든다. `check` 서브커맨드의 실제 분석 로직은
Stage 1(계약 로딩)~5(리포트)에서 채운다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


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
    # Stage 1~5에서 계약 로딩, 분석 코어, 체커, 리포트로 채운다.
    print("[INFO] check 명령은 아직 구현되지 않았습니다 (Stage 0 스캐폴딩).")
    return 0


def run(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
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
