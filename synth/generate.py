"""합성 공정 데이터 생성기 (고정 시드).

CLAUDE.md 절대 원칙 2(결정론)를 지키기 위해 `random.Random(SEED)` 고정 시드만
쓴다. 여기 있는 수치 상수는 전부 예시 값이며 도메인 팀 검증이 필요하다
(docs/progress.md "도메인 검증 필요 값" 참고).

파일명은 `contracts/contract.yaml`의 `sources` 패턴과 대응한다:
- `wafer_yield_lot001.csv`   -> *wafer_yield* -> wafer
- `metrology_lot001.csv`    -> *metrology*   -> metrology
- `lot_hist_lot001.csv`     -> *lot_hist*    -> step_event
- `fdc_rf_power_lot001.csv` -> fdc_rf_*      -> fdc_trace (sensor: rf_power)
- `fdc_gas_flow_lot001.csv` -> fdc_gas_*     -> fdc_trace (sensor: gas_flow)
- `lot_master.csv`          -> *lot_master*  -> lot
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

SEED = 20260101  # 예시 값 — 도메인 팀 검증 필요 (재현성을 위한 고정 시드)

LOT_ID = "LOT001"
WAFERS_PER_LOT = 25  # 예시 값 — 도메인 팀 검증 필요 (FOUP 최대 적재량 기준 추정)
SITES_PER_WAFER = 5  # 예시 값 — 도메인 팀 검증 필요
SAMPLED_WAFER_RATIO = 0.4  # 예시 값 — 도메인 팀 검증 필요 (계측 커버리지)

TOOL_ID = "TOOL01"
CHAMBER_ID = "CH1"

RF_POWER_PERIOD_S = 1  # contracts/contract.yaml sensors.rf_power와 일치시켜야 함
GAS_FLOW_PERIOD_S = 5  # contracts/contract.yaml sensors.gas_flow와 일치시켜야 함
TRACE_DURATION_S = 60  # 예시 값 — 도메인 팀 검증 필요

STEP_DURATION_S = 300  # 예시 값 — 도메인 팀 검증 필요


def generate_lot_master() -> pd.DataFrame:
    return pd.DataFrame({"lot_id": [LOT_ID]})


def generate_wafer_yield(rng: random.Random) -> pd.DataFrame:
    rows = [
        {
            "lot_id": LOT_ID,
            "wafer_id": f"W{idx:02d}",
            "yield_pct": round(rng.uniform(90.0, 99.5), 2),
        }
        for idx in range(1, WAFERS_PER_LOT + 1)
    ]
    return pd.DataFrame(rows)


def generate_lot_hist() -> pd.DataFrame:
    rows = [
        {
            "lot_id": LOT_ID,
            "wafer_id": f"W{idx:02d}",
            "step_id": "STEP01",
            "step_start": idx * STEP_DURATION_S,
            "step_end": idx * STEP_DURATION_S + STEP_DURATION_S,
        }
        for idx in range(1, WAFERS_PER_LOT + 1)
    ]
    return pd.DataFrame(rows)


def generate_fdc_trace(
    period_s: int, value_column: str, rng: random.Random, base_value: float, jitter: float
) -> pd.DataFrame:
    timestamps = list(range(0, TRACE_DURATION_S, period_s))
    rows = [
        {
            "tool_id": TOOL_ID,
            "chamber_id": CHAMBER_ID,
            "timestamp": ts,
            value_column: round(base_value + rng.uniform(-jitter, jitter), 3),
        }
        for ts in timestamps
    ]
    return pd.DataFrame(rows)


def generate_metrology(rng: random.Random) -> pd.DataFrame:
    n_sampled = max(1, round(WAFERS_PER_LOT * SAMPLED_WAFER_RATIO))
    sampled_wafer_indices = sorted(rng.sample(range(1, WAFERS_PER_LOT + 1), n_sampled))
    rows = [
        {
            "lot_id": LOT_ID,
            "wafer_id": f"W{idx:02d}",
            "site_id": f"S{site_idx}",
            "thickness_nm": round(rng.uniform(48.0, 52.0), 3),
        }
        for idx in sampled_wafer_indices
        for site_idx in range(1, SITES_PER_WAFER + 1)
    ]
    return pd.DataFrame(rows)


def generate_pressure_logs(rng: random.Random) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = 20
    tool_a = pd.DataFrame(
        {
            "tool_id": ["TOOLA"] * n,
            "sample_idx": range(n),
            "chamber_pressure_mtorr": [round(rng.uniform(45.0, 55.0), 2) for _ in range(n)],
        }
    )
    tool_b = pd.DataFrame(
        {
            "tool_id": ["TOOLB"] * n,
            "sample_idx": range(n),
            # 1 mTorr ~= 0.133 Pa. 물리적으로 비슷한 범위지만 단위 토큰이 다르다.
            "chamber_pressure_pa": [round(rng.uniform(6.0, 7.3), 2) for _ in range(n)],
        }
    )
    return tool_a, tool_b


def generate_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    generate_lot_master().to_csv(out_dir / "lot_master.csv", index=False, encoding="utf-8")
    generate_wafer_yield(rng).to_csv(
        out_dir / "wafer_yield_lot001.csv", index=False, encoding="utf-8"
    )
    generate_lot_hist().to_csv(out_dir / "lot_hist_lot001.csv", index=False, encoding="utf-8")
    generate_metrology(rng).to_csv(out_dir / "metrology_lot001.csv", index=False, encoding="utf-8")

    generate_fdc_trace(RF_POWER_PERIOD_S, "rf_power", rng, base_value=500.0, jitter=5.0).to_csv(
        out_dir / "fdc_rf_power_lot001.csv", index=False, encoding="utf-8"
    )
    generate_fdc_trace(
        GAS_FLOW_PERIOD_S, "gas_flow_sccm", rng, base_value=120.0, jitter=2.0
    ).to_csv(out_dir / "fdc_gas_flow_lot001.csv", index=False, encoding="utf-8")

    tool_a, tool_b = generate_pressure_logs(rng)
    tool_a.to_csv(out_dir / "pressure_tool_a.csv", index=False, encoding="utf-8")
    tool_b.to_csv(out_dir / "pressure_tool_b.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    generate_all(Path(__file__).resolve().parent.parent / "samples" / "data")
