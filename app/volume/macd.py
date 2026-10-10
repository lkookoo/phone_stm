import numpy as np


def _ema(arr, n):
    k = 2.0 / (n + 1)
    out = np.zeros_like(arr, dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = arr[i] * k + out[i - 1] * (1 - k)
    return out


def compute_macd(closes, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    返回 dict: {"dif": np.ndarray, "dea": np.ndarray, "hist": np.ndarray}
    hist 采用 (dif - dea) * 2，与国内看盘软件一致。
    """
    closes = np.asarray(closes, dtype=float)
    if len(closes) < slow + signal:
        return None

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal)
    hist = (dif - dea) * 2.0
    return {"dif": dif, "dea": dea, "hist": hist}