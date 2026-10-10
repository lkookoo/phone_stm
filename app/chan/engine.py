# app/chan/engine.py
from app.chan.fractal import find_fractals
from app.chan.bi import build_bi
from app.chan.segment import build_segments
from app.chan.center import build_centers
from app.chan.buy_sell import detect_signals


CONFIRM_BARS = 2


# ---------- 工具 ----------

def _fractal_get(f, key, default=None):
    if isinstance(f, dict):
        return f.get(key, default)
    return getattr(f, key, default)


def _serialize_ts(ts):
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    if isinstance(ts, (int, float)):
        sec = ts / 1000 if ts > 1e11 else ts
        from datetime import datetime, timezone
        try:
            return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat()
        except Exception:
            return str(ts)
    try:
        return ts.isoformat()
    except AttributeError:
        return str(ts)


def _fractal_to_dict(f):
    return {
        "kind":  _fractal_get(f, "kind"),
        "idx":   _fractal_get(f, "idx"),
        "price": _fractal_get(f, "price"),
        "ts":    _serialize_ts(
            _fractal_get(f, "ts")
            or _fractal_get(f, "dt")
            or _fractal_get(f, "time")
        ),
    }


def _trim_confirmed_fractals(fractals, n_candles, confirm_bars):
    if not fractals:
        return []
    limit = n_candles - 1 - confirm_bars
    out = []
    for f in fractals:
        idx = _fractal_get(f, "idx")
        if idx is not None and idx <= limit:
            out.append(f)
    return out


def _classify_trend(bis, centers):
    if not bis:
        return "UNKNOWN"
    last_bi = bis[-1]
    end_price = last_bi.get("end_price")
    if end_price is None:
        return "UNKNOWN"
    if centers:
        c = centers[-1]
        if end_price > c["zg"]:
            return "UP"
        if end_price < c["zd"]:
            return "DOWN"
        return "RANGE"
    return "UP" if last_bi.get("direction") == "up" else "DOWN"


def _empty_result():
    return {
        "trend": "UNKNOWN",
        "fractals": [],
        "bi_count": 0,
        "last_bi": None,
        "segment_count": 0,
        "last_segment": None,
        "center_count": 0,
        "center": None,
        "segment_center_count": 0,
        "segment_center": None,
        "signal": None,
        "score": 0,
        "age_bars": None,
        "strength": None,
        "reason": None,
        "trigger_ts": None,
        "signal_ts": None,
        "signal_center": None,
    }


def _center_to_dict(c):
    if not c:
        return None
    return {
        "zg":        c.get("zg"),
        "zd":        c.get("zd"),
        "mid":       c.get("mid"),
        "start_idx": c.get("start_idx"),
        "end_idx":   c.get("end_idx"),
        "start_ts":  _serialize_ts(c.get("start_ts")),
        "end_ts":    _serialize_ts(c.get("end_ts")),
        "seg_count": c.get("seg_count"),
    }


# ---------- 引擎 ----------

class ChanEngine:
    def __init__(self, min_bi_gap: int = 4, confirm_bars: int = CONFIRM_BARS):
        self.min_bi_gap = min_bi_gap
        self.confirm_bars = confirm_bars

    def analyze(self, candles, tf: str = "15m"):
        result = _empty_result()

        if not candles or len(candles) < 20:
            result["error"] = "not enough candles"
            return result

        # 1. 分型
        try:
            raw_fractals = list(find_fractals(candles))
        except Exception as e:
            result["error"] = f"find_fractals: {type(e).__name__}: {e}"
            return result

        fractals = _trim_confirmed_fractals(
            raw_fractals, len(candles), self.confirm_bars
        )

        # 2. 笔
        try:
            bis = build_bi(fractals, min_gap=self.min_bi_gap) if fractals else []
        except Exception as e:
            result["error"] = f"build_bi: {type(e).__name__}: {e}"
            return result

        # 3. 线段
        try:
            segments = build_segments(bis) if len(bis) >= 3 else []
        except Exception as e:
            segments = []
            result["error"] = f"build_segments: {type(e).__name__}: {e}"

        # 4. 中枢（两套）
        try:
            centers = build_centers(bis) if len(bis) >= 3 else []
        except Exception as e:
            centers = []
            result["error"] = f"build_centers(bis): {type(e).__name__}: {e}"

        try:
            segment_centers = build_centers(segments) if len(segments) >= 3 else []
        except Exception:
            segment_centers = []

        # 5. 买卖点（继续用笔 + 笔中枢，保持现有逻辑）
        sig = {}
        try:
            sig = detect_signals(candles, bis, centers, tf=tf) or {}
        except Exception as e:
            result["error"] = f"detect_signals: {type(e).__name__}: {e}"

        # 6. 趋势
        trend = _classify_trend(bis, centers)

        # 7. 组装
        last_bi = bis[-1] if bis else None
        if last_bi:
            last_bi = {
                **last_bi,
                "start_ts": _serialize_ts(last_bi.get("start_ts")),
                "end_ts":   _serialize_ts(last_bi.get("end_ts")),
            }

        result.update({
            "trend":         trend,
            "fractals":      [_fractal_to_dict(f) for f in fractals[-10:]],
            "bi_count":      len(bis),
            "last_bi":       last_bi,
            "segment_count": len(segments),
            "last_segment":  segments[-1] if segments else None,
            "center_count":  len(centers),
            "center":        _center_to_dict(centers[-1]) if centers else None,
            "segment_center_count": len(segment_centers),
            "segment_center": _center_to_dict(segment_centers[-1]) if segment_centers else None,
            "signal":        sig.get("signal"),
            "score":         int(sig.get("score") or 0),
            "age_bars":      sig.get("age_bars"),
            "strength":      sig.get("strength"),
            "reason":        sig.get("reason"),
            "trigger_ts":    _serialize_ts(sig.get("trigger_ts")),
            "signal_ts":     _serialize_ts(sig.get("signal_ts")),
            "signal_center": sig.get("center"),
        })
        return result