from datetime import datetime, timezone
from app.data.base import MarketTick, Candle
from app.data.normalizer import normalize_tick, normalize_candle


def test_normalize_tick():
    raw = {
        "symbol": "BTC/USDT",
        "asset_class": "crypto",
        "price": 108230.5,
        "volume": 12345,
        "timestamp": datetime.now(timezone.utc),
    }
    t = normalize_tick(raw, "binance")
    assert isinstance(t, MarketTick)
    assert t.symbol == "BTC/USDT"
    assert t.source == "binance"


def test_normalize_candle():
    raw = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "timestamp": datetime.now(timezone.utc),
        "open": 108000, "high": 108300, "low": 107900, "close": 108230,
        "volume": 1250,
    }
    c = normalize_candle(raw, "binance")
    assert isinstance(c, Candle)
    assert c.timeframe == "15m"
    assert c.is_closed is False