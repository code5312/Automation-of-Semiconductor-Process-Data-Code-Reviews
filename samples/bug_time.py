"""FAB-T001 데모: 샘플링 주기가 다른 두 센서를 timestamp 정확 일치로 병합한다.

rf_power는 1초 주기, gas_flow는 5초 주기로 기록된다. `on=["tool_id", "timestamp"]`
정확 일치 merge는 두 시계열이 우연히 겹치는 시각만 남기고 나머지는 조용히 버린다.
"""

import sys

import pandas as pd

rf_power_df = pd.read_csv("samples/data/fdc_rf_power_lot001.csv")
gas_flow_df = pd.read_csv("samples/data/fdc_gas_flow_lot001.csv")

merged = rf_power_df.merge(gas_flow_df, on=["tool_id", "timestamp"])

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(
        f"[bug_time] 정확 일치 병합 결과 행 수 = {len(merged)} "
        f"(rf_power {len(rf_power_df)}행 중 대부분이 조용히 사라짐)"
    )
