# app/api/routes_market.py
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter(tags=["market"])


MAX_AGE_BY_TF = {
    "1m": 1, "5m": 2, "15m": 6, "30m": 12,
    "1h": 24, "4h": 36, "1d": 72,
}
DEFAULT_MAX_AGE = 24.0


def _clean(v):
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v


def _score_of(item):
    sc = item.get("score")
    if isinstance(sc, dict):
        return sc.get("total", 0) or 0
    if isinstance(sc, (int, float)):
        return sc
    return 0


def _parse_ts(ts):
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        sec = ts / 1000 if ts > 1e11 else ts
        try:
            return datetime.fromtimestamp(sec, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(ts, str):
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t
    return None


def _age_hours(ts):
    t = _parse_ts(ts)
    if t is None:
        return None
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600


def _max_age_for(tf):
    return MAX_AGE_BY_TF.get(tf, DEFAULT_MAX_AGE)


@router.get("/api/market/overview")
async def overview(request: Request):
    state = request.app.state.x1
    return {
        "ticks": list(state["ticks"].values()),
        "health": state["health"].status,
    }


@router.get("/api/market/health")
async def health(request: Request):
    state = request.app.state.x1
    return state["health"].status


@router.get("/api/market/debug/agg")
async def debug_agg(request: Request):
    state = request.app.state.x1
    agg = state["aggregator"]
    result = {}
    for symbol, tfs in agg.buffers.items():
        result[symbol] = {}
        for tf, buf in tfs.items():
            total = len(buf)
            closed = sum(1 for c in buf.values() if c.is_closed)
            result[symbol][tf] = {"total": total, "closed": closed}
    return result


@router.get("/api/market/debug/signals")
async def debug_signals(request: Request, raw: int = 0):
    from app.chan.buy_sell import BUY_SELL_VERSION

    state = request.app.state.x1
    signals = state.get("signals", {})

    if raw:
        return {"version": BUY_SELL_VERSION, "signals": signals}

    out = []
    for s in signals.values():
        if not s.get("signal"):
            continue
        tf = s.get("timeframe")
        age = _age_hours(s.get("trigger_ts"))
        out.append({
            "symbol": s.get("symbol"),
            "timeframe": tf,
            "signal": s.get("signal"),
            "score": _score_of(s),
            "trigger_ts": s.get("trigger_ts"),
            "age_hours": round(age, 2) if age is not None else None,
            "max_age": _max_age_for(tf),
            "expired": (age is not None and age > _max_age_for(tf)),
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return {"version": BUY_SELL_VERSION, "signals": out}


@router.get("/api/signals/active")
async def active_signals(
    request: Request,
    top_per_symbol: int = 1,
    min_score: int = 60,
    max_age_hours: float = -1.0,
):
    state = request.app.state.x1
    signals = state.get("signals", {})

    by_symbol = {}
    for s in signals.values():
        if not s.get("signal"):
            continue
        if _score_of(s) < min_score:
            continue

        tf = s.get("timeframe")
        age = _age_hours(s.get("trigger_ts"))

        if age is not None:
            limit = _max_age_for(tf) if max_age_hours < 0 else max_age_hours
            if age > limit:
                continue

        by_symbol.setdefault(s["symbol"], []).append(s)

    out = []
    for sym, lst in by_symbol.items():
        lst.sort(key=_score_of, reverse=True)
        out.extend(lst[:top_per_symbol])

    out.sort(key=_score_of, reverse=True)
    return _clean({"count": len(out), "signals": out})