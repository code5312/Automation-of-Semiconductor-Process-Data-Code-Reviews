"""위반 없는 정상 스크립트.

세 가지 불변 조건을 모두 지킨다:
- 단위: 압력은 tool_a(mTorr)만 사용하고 다른 단위와 섞지 않는다.
- 시간: 샘플링 주기가 다른 두 센서는 `merge_asof` + `tolerance`로 병합한다.
- 계보: metrology를 wafer 입도로 먼저 집계한 뒤 전체 키로 조인하고,
  `coverage: sampled`이므로 `how="left"`로 미측정 웨이퍼를 보존한다.
"""

import sys

import pandas as pd

# --- 단위: 같은 단위만 사용 ---
tool_a_df = pd.read_csv("samples/data/pressure_tool_a.csv")
pressure_a = tool_a_df["chamber_pressure_mtorr"]
ucl = pressure_a.mean() + 3 * pressure_a.std()

# --- 시간: 주기가 다른 두 센서를 근사 병합 ---
rf_power_df = pd.read_csv("samples/data/fdc_rf_power_lot001.csv")
gas_flow_df = pd.read_csv("samples/data/fdc_gas_flow_lot001.csv")
merged_traces = pd.merge_asof(
    rf_power_df.sort_values("timestamp"),
    gas_flow_df.sort_values("timestamp"),
    on="timestamp",
    by="tool_id",
    direction="nearest",
    tolerance=5,
)

# --- 계보: wafer 입도로 집계 후 전체 키 + left join ---
yield_df = pd.read_csv("samples/data/wafer_yield_lot001.csv")
metrology_df = pd.read_csv("samples/data/metrology_lot001.csv")
wafer_metrology = metrology_df.groupby(["lot_id", "wafer_id"], as_index=False)[
    "thickness_nm"
].mean()
wafer_yield = yield_df.merge(
    wafer_metrology, on=["lot_id", "wafer_id"], how="left", validate="1:1"
)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(
        f"[normal] UCL={ucl:.3f}, "
        f"time-merge 행 수={len(merged_traces)}, "
        f"join 행 수={len(wafer_yield)} (wafer_yield {len(yield_df)}행 그대로 보존)"
    )
