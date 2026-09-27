"""이름 패턴 매처. 계약의 sources/parameters 패턴을 fnmatch 수준으로 매칭한다.

결정론(CLAUDE.md 절대 원칙 2)을 지키기 위해 대소문자를 소문자로 정규화한 뒤
``fnmatch.fnmatchcase``를 써서 OS별 대소문자 처리 차이에 흔들리지 않게 한다.
"""

from __future__ import annotations

import fnmatch

from fab_review.contract.schema import Contract, Parameter, Source


def match_any(patterns: list[str], name: str) -> bool:
    lowered = name.lower()
    return any(fnmatch.fnmatchcase(lowered, pattern.lower()) for pattern in patterns)


def match_source(contract: Contract, filename: str) -> Source | None:
    """파일 basename을 sources 패턴과 대조해 첫 번째로 일치하는 Source를 반환한다."""
    for source in contract.sources:
        if fnmatch.fnmatchcase(filename.lower(), source.pattern.lower()):
            return source
    return None


def match_parameter(contract: Contract, name: str) -> tuple[str, Parameter] | None:
    """변수/컬럼명을 parameters의 name_patterns와 대조해 (파라미터 이름, Parameter)를 반환한다."""
    for param_name, param in contract.parameters.items():
        if match_any(param.name_patterns, name):
            return param_name, param
    return None
