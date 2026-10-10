TF_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
}

ALL_TIMEFRAMES = list(TF_MS.keys())


def align_ts(ts_ms: int, tf: str) -> int:
    step = TF_MS[tf]
    return ts_ms - (ts_ms % step)