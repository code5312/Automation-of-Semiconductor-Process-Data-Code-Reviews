"""Stage 3 테스트: 공정 데이터 흐름 추적기.

완료 기준(docs/checklist.md 3절): 데모 스크립트 4개에서 각 DataFrame의
엔티티·입도가 기대대로 추적되는지 확인한다.
"""

from __future__ import annotations

import ast
from pathlib import Path

from fab_review.analysis.flow import analyze_file
from fab_review.analysis.parser import parse_file
from fab_review.analysis.values import SeriesInfo
from fab_review.contract.loader import load_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = load_contract(REPO_ROOT / "contracts" / "contract.yaml")
SAMPLES_DIR = REPO_ROOT / "samples"


def _analyze_file(script_name: str):
    tree = parse_file(SAMPLES_DIR / script_name)
    return analyze_file(tree, CONTRACT)


def _analyze_source(src: str):
    tree = ast.parse(src)
    return analyze_file(tree, CONTRACT)


# ---------------------------------------------------------------------------
# 데모 스크립트 4개 (완료 기준)
# ---------------------------------------------------------------------------


def test_bug_unit_pressure_files_unknown_but_columns_tracked():
    result = _analyze_file("bug_unit.py")
    symtab = result.module.symtab

    # pressure_tool_*.csv는 contract.yaml의 sources 패턴에 없다 (의도된 설계, Stage 1 보고 참고)
    assert symtab["tool_a_df"].entity is None
    assert symtab["tool_b_df"].entity is None

    pressure_a = symtab["pressure_a"]
    pressure_b = symtab["pressure_b"]
    assert isinstance(pressure_a, SeriesInfo) and pressure_a.column == "chamber_pressure_mtorr"
    assert isinstance(pressure_b, SeriesInfo) and pressure_b.column == "chamber_pressure_pa"


def test_bug_time_sensors_identified_and_differ():
    result = _analyze_file("bug_time.py")
    symtab = result.module.symtab

    rf = symtab["rf_power_df"]
    gas = symtab["gas_flow_df"]
    assert rf.entity == "fdc_trace"
    assert gas.entity == "fdc_trace"
    assert rf.sensor == "rf_power"
    assert gas.sensor == "gas_flow"
    assert rf.sensor != gas.sensor

    sightings = result.module.merge_sightings
    assert len(sightings) == 1
    assert sightings[0].kind == "merge"
    assert sightings[0].merge_call.on == ("tool_id", "timestamp")


def test_bug_join_entities_tracked_and_result_is_j001_unknown():
    result = _analyze_file("bug_join.py")
    symtab = result.module.symtab

    assert symtab["yield_df"].entity == "wafer"
    assert symtab["metrology_df"].entity == "metrology"

    wafer_yield = symtab["wafer_yield"]
    assert wafer_yield.entity is None
    assert "FAB-J001" in wafer_yield.unknown_reason

    sightings = result.module.merge_sightings
    assert len(sightings) == 1
    assert sightings[0].merge_call.on == ("lot_id",)


def test_normal_script_grain_propagates_correctly():
    result = _analyze_file("normal.py")
    symtab = result.module.symtab

    assert symtab["yield_df"].entity == "wafer"
    assert symtab["metrology_df"].entity == "metrology"

    wafer_metrology = symtab["wafer_metrology"]
    assert wafer_metrology.entity == "metrology"
    assert set(wafer_metrology.current_key) == {"lot_id", "wafer_id"}  # groupby로 입도 변경

    wafer_yield = symtab["wafer_yield"]
    assert wafer_yield.entity == "wafer"
    assert set(wafer_yield.current_key) == {"lot_id", "wafer_id"}


# ---------------------------------------------------------------------------
# 개별 전파 규칙 (부록 B 및 CLAUDE.md 분석 규칙)
# ---------------------------------------------------------------------------


def test_variable_path_load_is_unknown_not_silent():
    result = _analyze_source(
        "import pandas as pd\n"
        "path = 'metrology_lot001.csv'\n"
        "df = pd.read_csv(path)\n"
    )
    grain = result.module.symtab["df"]
    assert grain.entity is None
    assert grain.unknown_reason is not None and "리터럴" in grain.unknown_reason


def test_fstring_path_load_is_unknown():
    result = _analyze_source(
        "import pandas as pd\n"
        "lot = 'lot001'\n"
        "df = pd.read_csv(f'metrology_{lot}.csv')\n"
    )
    assert result.module.symtab["df"].entity is None


def test_literal_load_point_matches_source_pattern():
    result = _analyze_source(
        "import pandas as pd\ndf = pd.read_csv('metrology_lot001.csv')\n"
    )
    grain = result.module.symtab["df"]
    assert grain.entity == "metrology"
    assert set(grain.current_key) == {"lot_id", "wafer_id", "site_id"}


def test_filter_selection_and_copy_preserve_grain():
    result = _analyze_source(
        "import pandas as pd\n"
        "df = pd.read_csv('metrology_lot001.csv')\n"
        "filtered = df[df['site_id'] == 'S1']\n"
        "selected = df[['lot_id', 'wafer_id']]\n"
        "copied = df.copy()\n"
    )
    symtab = result.module.symtab
    assert symtab["filtered"].entity == "metrology"
    assert symtab["selected"].entity == "metrology"
    assert symtab["copied"].entity == "metrology"


def test_groupby_changes_grain_to_keys():
    result = _analyze_source(
        "import pandas as pd\n"
        "df = pd.read_csv('metrology_lot001.csv')\n"
        "agg = df.groupby(['lot_id', 'wafer_id'], as_index=False)['thickness_nm'].mean()\n"
    )
    grain = result.module.symtab["agg"]
    assert grain.entity == "metrology"
    assert set(grain.current_key) == {"lot_id", "wafer_id"}


def test_groupby_with_non_literal_keys_is_unknown():
    result = _analyze_source(
        "import pandas as pd\n"
        "keys = ['lot_id']\n"
        "df = pd.read_csv('metrology_lot001.csv')\n"
        "agg = df.groupby(keys).mean()\n"
    )
    assert result.module.symtab["agg"].entity is None


def test_join_method_call_is_unknown():
    result = _analyze_source(
        "import pandas as pd\n"
        "a = pd.read_csv('metrology_lot001.csv')\n"
        "b = pd.read_csv('wafer_yield_lot001.csv')\n"
        "joined = a.join(b)\n"
    )
    assert result.module.symtab["joined"].entity is None


def test_function_body_is_independent_scope_params_are_unknown():
    result = _analyze_source(
        "import pandas as pd\n"
        "def process(df):\n"
        "    filtered = df[df['x'] > 0]\n"
        "    return filtered\n"
    )
    local_symtab = result.functions["process"].symtab
    assert local_symtab["filtered"].entity is None  # df는 함수 인자라 추적되지 않음
