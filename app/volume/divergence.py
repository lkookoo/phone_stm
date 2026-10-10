from .macd import compute_macd


def _hist_area(hist, i1, i2):
    """区间 [i1, i2] 内 MACD 柱的面积绝对值（红绿柱不区分方向）"""
    if i1 is None or i2 is None or i2 <= i1:
        return 0.0
    seg = hist[i1:i2 + 1]
    return float(sum(abs(float(x)) for x in seg))


def detect_divergence(candles, bis, direction: str = "bottom"):
    """
    direction="bottom": 底背驰（价新低，MACD 绿柱面积萎缩）→ 一买 B1
    direction="top":    顶背驰（价新高，MACD 红柱面积萎缩）→ 一卖 S1

    返回 dict 或 None
    """
    if len(candles) < 40 or len(bis) < 4:
        return None

    macd = compute_macd([c.close for c in candles])
    if macd is None:
        return None
    hist = macd["hist"]

    want_dir = "down" if direction == "bottom" else "up"
    same_dir = [b for b in bis if b.get("direction") == want_dir]
    if len(same_dir) < 2:
        return None

    last = same_dir[-1]
    prev = same_dir[-2]

    # 只处理"最近"的背驰：最后一段笔应该接近序列尾部
    if last.get("end_idx", 0) < len(candles) - 10:
        return None

    if direction == "bottom":
        if last.get("low", 0) >= prev.get("low", 0):
            return None
        a_last = _hist_area(hist, last.get("start_idx"), last.get("end_idx"))
        a_prev = _hist_area(hist, prev.get("start_idx"), prev.get("end_idx"))
        if a_prev <= 0 or a_last >= a_prev:
            return None
        strength = max(0.0, 1.0 - a_last / a_prev)
        return {
            "type": "B1",
            "signal": "B1",
            "price": last.get("end_price"),
            "prev_low":  prev.get("low"),
            "curr_low":  last.get("low"),
            "macd_area_prev": round(a_prev, 4),
            "macd_area_curr": round(a_last, 4),
            "strength": round(strength, 3),
            "trigger_ts": candles[last["end_idx"]].timestamp,
            "reason": "底背驰：价格新低，MACD 绿柱面积萎缩",
        }

    else:
        if last.get("high", 0) <= prev.get("high", 0):
            return None
        a_last = _hist_area(hist, last.get("start_idx"), last.get("end_idx"))
        a_prev = _hist_area(hist, prev.get("start_idx"), prev.get("end_idx"))
        if a_prev <= 0 or a_last >= a_prev:
            return None
        strength = max(0.0, 1.0 - a_last / a_prev)
        return {
            "type": "S1",
            "signal": "S1",
            "price": last.get("end_price"),
            "prev_high": prev.get("high"),
            "curr_high": last.get("high"),
            "macd_area_prev": round(a_prev, 4),
            "macd_area_curr": round(a_last, 4),
            "strength": round(strength, 3),
            "trigger_ts": candles[last["end_idx"]].timestamp,
            "reason": "顶背驰：价格新高，MACD 红柱面积萎缩",
        }