"""FAB-U001 데모: 단위가 다른 챔버 압력 값을 그대로 섞어 관리한계를 계산한다.

tool_a는 mTorr, tool_b는 Pa로 로깅된 압력을 단위 변환 없이 concat 후 통계를 낸다.
둘 다 float이라 예외 없이 실행되지만, 관리한계(UCL) 값은 물리적으로 의미가 없다.
"""

import sys

import pandas as pd

tool_a_df = pd.read_csv("samples/data/pressure_tool_a.csv")
tool_b_df = pd.read_csv("samples/data/pressure_tool_b.csv")

pressure_a = tool_a_df["chamber_pressure_mtorr"]
pressure_b = tool_b_df["chamber_pressure_pa"]

combined = pd.concat([pressure_a, pressure_b])
ucl = combined.mean() + 3 * combined.std()

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"[bug_unit] 단위가 섞인 압력 UCL = {ucl:.3f} (mTorr/Pa 혼합, 물리적으로 무의미)")
