def score_signal(chan_result: dict, volume_result: dict, mtf: dict):
    """
    结构评分，不代表胜率。
    缠论结构 30 + 成交量 20 + 大周期 20 + 中周期 15 + 小周期 15
    """
    s_struct = 30 if chan_result.get("center") else 10
    s_vol = 20 if volume_result.get("status") == "放量" else \
            12 if volume_result.get("status") == "平量" else 6

    daily = mtf.get("1d", {}).get("trend")
    h4 = mtf.get("4h", {}).get("trend")
    h1 = mtf.get("1h", {}).get("trend")
    m15 = mtf.get("15m", {}).get("signal")

    s_big = 20 if daily == "UP" else 0
    s_mid = 15 if (h4 == "UP" and h1 == "UP") else 8 if h1 == "UP" else 0
    s_small = 15 if m15 in ("B3", "B2", "B1") else 0

    total = s_struct + s_vol + s_big + s_mid + s_small
    return {
        "total": total,
        "breakdown": {
            "chan_structure": s_struct,
            "volume": s_vol,
            "big_tf": s_big,
            "mid_tf": s_mid,
            "small_tf": s_small,
        },
        "disclaimer": "结构评分，不代表未来收益率或交易成功概率。",
    }