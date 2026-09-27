"""Stage 4 테스트: 체커 3종(unit/timeseries/join).

완료 기준(docs/checklist.md 4절): 버그 스크립트 3개에서 해당 규칙 ID가 error로
1건 이상, 정상 스크립트에서 0건.
"""

from __future__ import annotations

import ast
from pathlib import Path

from fab_review.checkers import run_all
from fab_review.contract.loader import load_contract
from fab_review.analysis.parser import parse_file

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = load_contract(REPO_ROOT / "contracts" / "contract.yaml")
SAMPLES_DIR = REPO_ROOT / "samples"


def _findings_for_source(src: str) -> list:
    tree = ast.parse(src)
    return run_all(tree, "snippet.py", CONTRACT)


def _findings_for_sample(name: str) -> list:
    tree = parse_file(SAMPLES_DIR / name)
    return run_all(tree, name, CONTRACT)


def _rule_ids(findings, severity: str | None = None) -> set[str]:
    return {f.rule_id for f in findings if severity is None or f.severity == severity}


# ---------------------------------------------------------------------------
# 완료 기준: 데모 스크립트 4개
# ---------------------------------------------------------------------------


def test_bug_unit_triggers_u001_error():
    errors = _rule_ids(_findings_for_sample("bug_unit.py"), severity="error")
    assert "FAB-U001" in errors


def test_bug_time_triggers_t001_error():
    errors = _rule_ids(_findings_for_sample("bug_time.py"), severity="error")
    assert "FAB-T001" in errors


def test_bug_join_triggers_j001_and_j002_error():
    errors = _rule_ids(_findings_for_sample("bug_join.py"), severity="error")
    assert "FAB-J001" in errors
    assert "FAB-J002" in errors


def test_normal_script_has_zero_errors():
    findings = _findings_for_sample("normal.py")
    assert [f for f in findings if f.severity == "error"] == []


def test_all_findings_carry_contract_version():
    findings = _findings_for_sample("bug_join.py")
    assert findings
    assert all(f.contract_version == CONTRACT.contract_version for f in findings)


# ---------------------------------------------------------------------------
# unit_checker (FAB-U001) 양성/음성
# ---------------------------------------------------------------------------


def test_unit_checker_positive_concat_mixed_units():
    src = (
        "import pandas as pd\n"
        "a = pd.DataFrame({'chamber_pressure_mtorr': [1]})\n"
        "b = pd.DataFrame({'chamber_pressure_pa': [1]})\n"
        "pressure_a = a['chamber_pressure_mtorr']\n"
        "pressure_b = b['chamber_pressure_pa']\n"
        "combined = pd.concat([pressure_a, pressure_b])\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-U001"]
    assert any(f.severity == "error" for f in findings)


def test_unit_checker_negative_same_unit_no_finding():
    src = (
        "import pandas as pd\n"
        "a = pd.DataFrame({'chamber_pressure_mtorr': [1]})\n"
        "b = pd.DataFrame({'chamber_pressure_mtorr': [2]})\n"
        "pressure_a = a['chamber_pressure_mtorr']\n"
        "pressure_b = b['chamber_pressure_mtorr']\n"
        "combined = pd.concat([pressure_a, pressure_b])\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-U001"]
    assert findings == []


def test_unit_checker_ambiguous_short_token_is_info_not_error():
    src = (
        "import pandas as pd\n"
        "a = pd.DataFrame({'chamber_pressure_c': [1]})\n"
        "b = pd.DataFrame({'chamber_pressure_k': [1]})\n"
        "pressure_a = a['chamber_pressure_c']\n"
        "pressure_b = b['chamber_pressure_k']\n"
        "combined = pd.concat([pressure_a, pressure_b])\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-U001"]
    assert findings
    assert all(f.severity == "info" for f in findings)


# ---------------------------------------------------------------------------
# timeseries_checker (FAB-T001) 양성/음성
# ---------------------------------------------------------------------------


def test_timeseries_checker_positive_different_sensor_periods():
    src = (
        "import pandas as pd\n"
        "a = pd.read_csv('fdc_rf_power_x.csv')\n"
        "b = pd.read_csv('fdc_gas_flow_x.csv')\n"
        "merged = a.merge(b, on=['tool_id', 'timestamp'])\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-T001"]
    assert any(f.severity == "error" for f in findings)


def test_timeseries_checker_negative_same_sensor_no_finding():
    src = (
        "import pandas as pd\n"
        "a = pd.read_csv('fdc_rf_power_x.csv')\n"
        "b = pd.read_csv('fdc_rf_power_y.csv')\n"
        "merged = a.merge(b, on=['tool_id', 'timestamp'])\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-T001"]
    assert findings == []


# ---------------------------------------------------------------------------
# join_checker (FAB-J001) 양성/음성
# ---------------------------------------------------------------------------


def test_join_checker_j001_positive_missing_key():
    src = (
        "import pandas as pd\n"
        "yield_df = pd.read_csv('wafer_yield_x.csv')\n"
        "metrology_df = pd.read_csv('metrology_x.csv')\n"
        "wafer_yield = yield_df.merge(metrology_df, on='lot_id')\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-J001"]
    assert any(f.severity == "error" for f in findings)


def test_join_checker_j001_negative_full_key_no_finding():
    src = (
        "import pandas as pd\n"
        "yield_df = pd.read_csv('wafer_yield_x.csv')\n"
        "metrology_df = pd.read_csv('metrology_x.csv')\n"
        "wafer_metro = metrology_df.groupby(['lot_id', 'wafer_id'], as_index=False)['thickness_nm'].mean()\n"
        "wafer_yield = yield_df.merge(wafer_metro, on=['lot_id', 'wafer_id'], how='left')\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-J001"]
    assert findings == []


def test_join_checker_j001_same_entity_merge_is_excluded():
    src = (
        "import pandas as pd\n"
        "a = pd.read_csv('fdc_rf_power_x.csv')\n"
        "b = pd.read_csv('fdc_gas_flow_x.csv')\n"
        "merged = a.merge(b, on=['tool_id', 'timestamp'])\n"  # chamber_id 빠짐, 같은 엔티티
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-J001"]
    assert findings == []  # 사용자 결정: 같은 엔티티끼리 병합은 J001 대상 아님


def test_join_checker_j001_info_when_entity_unknown():
    src = (
        "import pandas as pd\n"
        "path = 'x.csv'\n"
        "a = pd.read_csv(path)\n"
        "b = pd.read_csv('metrology_x.csv')\n"
        "merged = a.merge(b, on='lot_id')\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-J001"]
    assert findings and all(f.severity == "info" for f in findings)


def test_join_checker_j001_info_for_join_method():
    src = (
        "import pandas as pd\n"
        "a = pd.read_csv('wafer_yield_x.csv')\n"
        "b = pd.read_csv('metrology_x.csv')\n"
        "joined = a.join(b)\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-J001"]
    assert findings and all(f.severity == "info" for f in findings)


# ---------------------------------------------------------------------------
# join_checker (FAB-J002) 양성/음성
# ---------------------------------------------------------------------------


def test_join_checker_j002_positive_implicit_inner_on_sampled_entity():
    src = (
        "import pandas as pd\n"
        "yield_df = pd.read_csv('wafer_yield_x.csv')\n"
        "metrology_df = pd.read_csv('metrology_x.csv')\n"
        "wafer_yield = yield_df.merge(metrology_df, on=['lot_id', 'wafer_id'])\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-J002"]
    assert any(f.severity == "error" for f in findings)


def test_join_checker_j002_negative_explicit_how_left():
    src = (
        "import pandas as pd\n"
        "yield_df = pd.read_csv('wafer_yield_x.csv')\n"
        "metrology_df = pd.read_csv('metrology_x.csv')\n"
        "wafer_yield = yield_df.merge(metrology_df, on=['lot_id', 'wafer_id'], how='left')\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-J002"]
    assert findings == []


def test_join_checker_j002_info_when_how_inner_explicit():
    src = (
        "import pandas as pd\n"
        "yield_df = pd.read_csv('wafer_yield_x.csv')\n"
        "metrology_df = pd.read_csv('metrology_x.csv')\n"
        "wafer_yield = yield_df.merge(metrology_df, on=['lot_id', 'wafer_id'], how='inner')\n"
    )
    findings = [f for f in _findings_for_source(src) if f.rule_id == "FAB-J002"]
    assert findings and all(f.severity == "info" for f in findings)
