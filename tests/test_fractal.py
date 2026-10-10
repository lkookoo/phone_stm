from datetime import datetime, timezone, timedelta
from app.data.base import Candle
from app.chan.fractal import find_fractals
from app.chan.bi import build_bi


def make_candle(i, o, h, l, c):
    return Candle(
        symbol="BTC/USDT", timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * i),
        open=o, high=h, low=l, close=c, volume=100,
        source="test", is_closed=True,
    )


def test_fractal_basic():
    # 构造一个明显的顶分型
    candles = [
        make_candle(0, 10, 11, 9, 10),
        make_candle(1, 10, 12, 10, 11),
        make_candle(2, 11, 15, 11, 14),   # 顶
        make_candle(3, 14, 14, 12, 13),
        make_candle(4, 13, 13, 11, 12),
    ]
    fr = find_fractals(candles)
    assert len(fr) >= 1
    assert any(f.kind == "top" for f in fr)


def test_bi_basic():
    candles = [
        make_candle(0, 10, 11, 9, 10),
        make_candle(1, 10, 12, 10, 11),
        make_candle(2, 11, 15, 11, 14),
        make_candle(3, 14, 14, 12, 13),
        make_candle(4, 13, 13, 11, 12),
        make_candle(5, 12, 12, 8, 9),
        make_candle(6, 9, 10, 7, 8),
        make_candle(7, 8, 11, 8, 10),
        make_candle(8, 10, 13, 10, 12),
    ]
    fr = find_fractals(candles)
    bis = build_bi(fr, min_gap=2)
    assert isinstance(bis, list)