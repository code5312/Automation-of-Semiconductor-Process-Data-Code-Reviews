"""Stage 1 테스트: 계약 스키마·로더·패턴 매처.

완료 기준(docs/checklist.md 1절): 키 누락·알 수 없는 family 등 잘못된 계약이
로딩 시 거부되는 테스트가 통과해야 한다.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from fab_review.contract.loader import ContractError, load_contract
from fab_review.contract.matcher import match_any, match_parameter, match_source
from fab_review.contract.schema import Contract

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_CONTRACT_PATH = REPO_ROOT / "contracts" / "contract.yaml"


def base_contract_dict() -> dict:
    """스키마 단위 테스트용 최소 유효 계약."""
    return {
        "contract_version": "0.1.0",
        "unit_families": {"pressure": ["mTorr", "Pa"]},
        "parameters": {
            "chamber_pressure": {"family": "pressure", "name_patterns": ["*pressure*"]}
        },
        "entities": {
            "lot": {"key": ["lot_id"], "grain": "lot"},
            "wafer": {"key": ["lot_id", "wafer_id"], "grain": "wafer", "parent": "lot"},
            "metrology": {
                "key": ["lot_id", "wafer_id", "site_id"],
                "grain": "site",
                "parent": "wafer",
                "coverage": "sampled",
            },
        },
        "relationships": [
            {"from": "lot", "to": "wafer", "cardinality": "1:N"},
            {"from": "wafer", "to": "metrology", "cardinality": "1:N", "coverage": "sampled"},
        ],
        "sources": [
            {"pattern": "*metrology*", "entity": "metrology"},
        ],
        "sensors": {},
    }


# ---------------------------------------------------------------------------
# 실제 계약 파일 로딩
# ---------------------------------------------------------------------------


def test_real_contract_loads_successfully():
    contract = load_contract(REAL_CONTRACT_PATH)
    assert contract.contract_version == "0.1.0"
    assert "fdc_trace" in contract.entities
    assert contract.sensors["rf_power"].sampling_period == "1s"


def test_missing_contract_file_raises_contract_error(tmp_path: Path):
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ContractError, match="찾을 수 없습니다"):
        load_contract(missing)


def test_empty_contract_file_raises_contract_error(tmp_path: Path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ContractError, match="비어 있습니다"):
        load_contract(empty)


def test_invalid_yaml_syntax_raises_contract_error(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("entities: [unclosed", encoding="utf-8")
    with pytest.raises(ContractError, match="파싱에 실패"):
        load_contract(bad)


def test_entity_missing_key_field_is_rejected(tmp_path: Path):
    data = base_contract_dict()
    del data["entities"]["wafer"]["key"]
    bad = tmp_path / "contract.yaml"
    _write_yaml(bad, data)
    with pytest.raises(ContractError):
        load_contract(bad)


def test_unknown_family_in_parameter_is_rejected(tmp_path: Path):
    data = base_contract_dict()
    data["parameters"]["chamber_pressure"]["family"] = "no_such_family"
    bad = tmp_path / "contract.yaml"
    _write_yaml(bad, data)
    with pytest.raises(ContractError, match="unit_families에 없다"):
        load_contract(bad)


def _write_yaml(path: Path, data: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# 스키마 단위 테스트 (pydantic 직접 검증)
# ---------------------------------------------------------------------------


def test_valid_minimal_contract_parses():
    contract = Contract.model_validate(base_contract_dict())
    assert contract.entities["wafer"].parent == "lot"


def test_entity_parent_referencing_unknown_entity_is_rejected():
    data = base_contract_dict()
    data["entities"]["wafer"]["parent"] = "no_such_entity"
    with pytest.raises(Exception, match="entities에 없다"):
        Contract.model_validate(data)


def test_entity_self_parent_is_rejected():
    data = base_contract_dict()
    data["entities"]["wafer"]["parent"] = "wafer"
    with pytest.raises(Exception, match="자기 자신을 참조"):
        Contract.model_validate(data)


def test_circular_parent_chain_is_rejected():
    data = base_contract_dict()
    data["entities"]["lot"]["parent"] = "metrology"  # lot -> metrology -> wafer -> lot 순환
    with pytest.raises(Exception, match="순환"):
        Contract.model_validate(data)


def test_relationship_referencing_unknown_entity_is_rejected():
    data = base_contract_dict()
    data["relationships"].append({"from": "wafer", "to": "no_such_entity", "cardinality": "1:N"})
    with pytest.raises(Exception, match="entities에 없다"):
        Contract.model_validate(data)


def test_source_referencing_unknown_entity_is_rejected():
    data = base_contract_dict()
    data["sources"].append({"pattern": "*x*", "entity": "no_such_entity"})
    with pytest.raises(Exception, match="entities에 없다"):
        Contract.model_validate(data)


def test_source_sensor_referencing_unknown_sensor_is_rejected():
    data = base_contract_dict()
    data["sources"].append({"pattern": "fdc_*", "entity": "wafer", "sensor": "no_such_sensor"})
    with pytest.raises(Exception, match="sensors에 없다"):
        Contract.model_validate(data)


def test_unknown_top_level_field_is_rejected():
    data = base_contract_dict()
    data["not_a_real_field"] = 123
    with pytest.raises(Exception):
        Contract.model_validate(data)


# ---------------------------------------------------------------------------
# 공통 조상 계산 (FAB-J001에서 재사용)
# ---------------------------------------------------------------------------


def test_common_ancestor_of_wafer_and_metrology_is_wafer():
    contract = Contract.model_validate(base_contract_dict())
    assert contract.common_ancestor("wafer", "metrology") == "wafer"


def test_common_ancestor_of_wafer_and_lot_is_lot():
    contract = Contract.model_validate(base_contract_dict())
    assert contract.common_ancestor("wafer", "lot") == "lot"


def test_common_ancestor_of_unrelated_entities_is_none():
    data = base_contract_dict()
    data["entities"]["fdc_trace"] = {
        "key": ["tool_id", "chamber_id", "timestamp"],
        "grain": "time",
    }
    contract = Contract.model_validate(data)
    assert contract.common_ancestor("fdc_trace", "lot") is None


# ---------------------------------------------------------------------------
# 패턴 매처
# ---------------------------------------------------------------------------


def test_match_source_finds_sensor_specific_pattern():
    contract = load_contract(REAL_CONTRACT_PATH)
    source = match_source(contract, "fdc_rf_power_20260101.csv")
    assert source is not None
    assert source.entity == "fdc_trace"
    assert source.sensor == "rf_power"


def test_match_source_returns_none_for_unmatched_filename():
    contract = load_contract(REAL_CONTRACT_PATH)
    assert match_source(contract, "unrelated_file.csv") is None


def test_match_parameter_finds_pressure_family():
    contract = load_contract(REAL_CONTRACT_PATH)
    result = match_parameter(contract, "chamber_pressure_mtorr")
    assert result is not None
    param_name, param = result
    assert param_name == "chamber_pressure"
    assert param.family == "pressure"


def test_match_any_is_case_insensitive_and_deterministic():
    assert match_any(["*Pressure*"], "chamber_PRESSURE_mtorr")
    assert not match_any(["*pressure*"], "gas_flow_sccm")
