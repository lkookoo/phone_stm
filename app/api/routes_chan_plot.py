# app/api/routes_chan_plot.py
from fastapi import APIRouter, Request

from app.chan.fractal import find_fractals
from app.chan.bi import build_bi
from app.chan.segment import build_segments
from app.chan.center import build_centers
from app.chan.buy_sell import detect_signals


router = APIRouter(prefix="/api/chan", tags=["chan-plot"])


def _to_ms(v):
    if v is None:
        return None
    try:
        v = int(v)
    except Exception:
        return None
    if v < 10_000_000_000:
        v *= 1000
    return v


def _ts_to_sec(v):
    ms = _to_ms(v)
    return int(ms / 1000) if ms else None


def _bi_to_line(item):
    return {
        "start_time":  _ts_to_sec(item.get("start_ts")),
        "start_price": item.get("start_price"),
        "end_time":    _ts_to_sec(item.get("end_ts")),
        "end_price":   item.get("end_price"),
        "direction":   item.get("direction"),
    }


def _seg_to_line(item):
    return {
        "start_time":  _ts_to_sec(item.get("start_ts")),
        "end_time":    _ts_to_sec(item.get("end_ts")),
        "start_price": item.get("start_price"),
        "end_price":   item.get("end_price"),
        "direction":   item.get("direction"),
        "high":        item.get("high"),
        "low":         item.get("low"),
        "bi_start":    item.get("bi_start"),
        "bi_end":      item.get("bi_end"),
        "bi_count":    item.get("bi_count"),
    }


def _center_to_rect(item):
    return {
        "start_time": _ts_to_sec(item.get("start_ts")),
        "end_time":   _ts_to_sec(item.get("end_ts")),
        "zg":         item.get("zg"),
        "zd":         item.get("zd"),
        "mid":        item.get("mid"),
        "seg_count":  item.get("seg_count"),
    }


def _do_plot(request: Request, symbol: str, timeframe: str, limit: int):
    state = request.app.state.x1
    agg = state["aggregator"]
    candles = agg.get_closed(symbol, timeframe, limit=limit)
    if len(candles) < 10:
        return {"error": "not enough candles"}

    fractals = find_fractals(candles)
    bis = build_bi(fractals)
    segments = build_segments(bis) if len(bis) >= 3 else []
    centers = build_centers(bis) if len(bis) >= 3 else []
    segment_centers = build_centers(segments) if len(segments) >= 3 else []
    sig = detect_signals(candles, bis, centers, tf=timeframe)

    def f_to_pt(f):
        c = candles[f.idx] if 0 <= f.idx < len(candles) else None
        if not c:
            return None
        return {
            "time":  int(c.timestamp.timestamp()),
            "price": f.price,
            "kind":  f.kind,
        }

    signal_info = None
    if sig.get("signal"):
        last = candles[-1]
        signal_info = {
            "type":  sig["signal"],
            "time":  int(last.timestamp.timestamp()),
            "price": last.close,
            "score": sig.get("score", 0),
            "reason": sig.get("reason"),
        }

    return {
        "symbol":    symbol,
        "timeframe": timeframe,
        "fractals":  [p for p in (f_to_pt(f) for f in fractals) if p],
        "bis":       [_bi_to_line(b) for b in bis],
        "segments":  [_seg_to_line(s) for s in segments],
        "centers":   [_center_to_rect(c) for c in centers],
        "segment_centers": [_center_to_rect(c) for c in segment_centers],
        "signal":    signal_info,
        "trend": "UP" if segments and segments[-1]["direction"] == "up" else
                 "DOWN" if segments else "UNKNOWN",
    }


@router.get("/plot")
async def chan_plot_query(request: Request,
                          symbol: str,
                          timeframe: str = "15m",
                          limit: int = 300):
    return _do_plot(request, symbol, timeframe, limit)


@router.get("/{symbol:path}/plot")
async def chan_plot_path(symbol: str, request: Request,
                         timeframe: str = "15m", limit: int = 300):
    return _do_plot(request, symbol, timeframe, limit)