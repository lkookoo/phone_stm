from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/candles", tags=["candles"])


@router.get("/{symbol:path}")
async def get_candles(symbol: str, request: Request,
                      timeframe: str = "15m", limit: int = 300):
    """
    返回指定 symbol + timeframe 的 K线列表。
    例：/api/candles/BTC/USDT?timeframe=15m&limit=200
    """
    state = request.app.state.x1
    agg = state["aggregator"]
    cs = agg.get_closed(symbol, timeframe, limit=limit)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(cs),
        "candles": [
            {
                "t": int(c.timestamp.timestamp()),   # 秒
                "o": c.open,
                "h": c.high,
                "l": c.low,
                "c": c.close,
                "v": c.volume,
            }
            for c in cs
        ],
    }


@router.get("/{symbol:path}/latest")
async def get_latest(symbol: str, request: Request, timeframe: str = "15m"):
    """只返回最新一根 K线"""
    state = request.app.state.x1
    agg = state["aggregator"]
    cs = agg.get_closed(symbol, timeframe, limit=1)
    if not cs:
        return {}
    c = cs[-1]
    return {
        "symbol": symbol, "timeframe": timeframe,
        "t": int(c.timestamp.timestamp()),
        "o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume,
    }