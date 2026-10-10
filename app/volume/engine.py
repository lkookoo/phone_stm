import numpy as np
from app.data.base import Candle


class VolumeEngine:
    def analyze(self, candles, lookback: int = 20):
        if len(candles) < lookback + 1:
            return {"status": "unknown"}
        vols = np.array([c.volume for c in candles[-lookback - 1:-1]])
        cur = candles[-1].volume
        avg = vols.mean()
        ratio = cur / avg if avg > 0 else 0

        if ratio > 1.5:
            status = "放量"
        elif ratio < 0.7:
            status = "缩量"
        else:
            status = "平量"

        prices = np.array([c.close for c in candles[-lookback - 1:-1]])
        divergence = False
        if candles[-1].close > prices.max() and cur < vols.max():
            divergence = True

        return {
            "status": status,
            "ratio": round(ratio, 2),
            "avg_volume": round(float(avg), 2),
            "current_volume": round(float(cur), 2),
            "divergence": divergence,
        }