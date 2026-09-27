"""FAB-J001/J002 데모: wafer 입도 테이블을 lot_id만으로 site 입도 계측과 조인한다.

`yield_df`는 wafer 입도(웨이퍼당 1행), `metrology_df`는 site 입도(표본 웨이퍼의
사이트별 계측, `coverage: sampled`)다. `lot_id`만으로 조인하면 로트 내 웨이퍼 수 x
표본 웨이퍼의 site 수만큼 행이 곱해진다(FAB-J001). 또한 `how`를 생략해 암묵적
inner join이 되면서 미측정 웨이퍼가 결과에서 조용히 빠진다(FAB-J002).
"""

import sys

import pandas as pd

yield_df = pd.read_csv("samples/data/wafer_yield_lot001.csv")
metrology_df = pd.read_csv("samples/data/metrology_lot001.csv")

wafer_yield = yield_df.merge(metrology_df, on="lot_id")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(
        f"[bug_join] lot_id만으로 조인한 행 수 = {len(wafer_yield)} "
        f"(yield_df {len(yield_df)}행 x metrology 표본 웨이퍼 site 수만큼 곱해짐)"
    )
