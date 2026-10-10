# app/chan/buy_sell.py
"""
缠论买卖点。

- B1/S1：MACD 背驰
- B2/S2：一买/一卖后回调确认
- B3/S3：三买/三卖（离开中枢后回踩）
- trigger_ts：信号**最近确认时间**（= 当前 K 线时间），用于过期过滤
- signal_ts：信号**原始形成时间**（背驰点/中枢突破点），仅用于展示
"""
from app.volume.macd import compute_macd


BUY_SELL_VERSION = "v2.1-trigger-ts"


MAX_AGE_BY_TF = {
    "1m": 60, "5m": 50, "15m": 40, "30m": 40,
    "1h": 30, "4h": 24, "1d": 20,
}
DEFAULT_MAX_AGE = 40

# 一买/一卖能有多老（K 线根数），超过就不再认为"新鲜"
B1_FRESH_MAX = 30

# 背驰最小力度
MIN_STRENGTH = 0.15


# ---------- 工具 ----------

def _bi_high(b):
    return b.get("high", max(b["start_price"], b["end_price"]))


def _bi_low(b):
    return b.get("low", min(b["start_price"], b["end_price"]))


def _post_bis(bis, center_end_idx):
    return [b for b in bis if b["start_idx"] > center_end_idx]


def _hist_area(hist, i1, i2):
    if i1 is None or i2 is None or i2 <= i1:
        return 0.0
    seg = hist[i1:i2 + 1]
    return float(sum(abs(float(x)) for x in seg))


# ---------- 一买 / 一卖 ----------

def _find_all_b1(candles, bis, min_strength=MIN_STRENGTH):
    if len(candles) < 40 or len(bis) < 4:
        return []
    macd = compute_macd([c.close for c in candles])
    if macd is None:
        return []
    hist = macd["hist"]

    downs = [(i, b) for i, b in enumerate(bis) if b.get("direction") == "down"]
    out = []
    for k in range(1, len(downs)):
        i_prev, prev = downs[k - 1]
        i_last, last = downs[k]
        if last["low"] >= prev["low"]:
            continue
        a_last = _hist_area(hist, last["start_idx"], last["end_idx"])
        a_prev = _hist_area(hist, prev["start_idx"], prev["end_idx"])
        if a_prev <= 0:
            continue
        if a_last >= a_prev * (1.0 - min_strength):
            continue
        out.append({
            "bi_idx": i_last,
            "end_idx": last["end_idx"],
            "price": last["low"],
            "strength": max(0.0, 1.0 - a_last / a_prev),
        })
    return out


def _find_all_s1(candles, bis, min_strength=MIN_STRENGTH):
    if len(candles) < 40 or len(bis) < 4:
        return []
    macd = compute_macd([c.close for c in candles])
    if macd is None:
        return []
    hist = macd["hist"]

    ups = [(i, b) for i, b in enumerate(bis) if b.get("direction") == "up"]
    out = []
    for k in range(1, len(ups)):
        i_prev, prev = ups[k - 1]
        i_last, last = ups[k]
        if last["high"] <= prev["high"]:
            continue
        a_last = _hist_area(hist, last["start_idx"], last["end_idx"])
        a_prev = _hist_area(hist, prev["start_idx"], prev["end_idx"])
        if a_prev <= 0:
            continue
        if a_last >= a_prev * (1.0 - min_strength):
            continue
        out.append({
            "bi_idx": i_last,
            "end_idx": last["end_idx"],
            "price": last["high"],
            "strength": max(0.0, 1.0 - a_last / a_prev),
        })
    return out


# ---------- 二买 / 二卖 ----------

def _detect_b2(bis, b1):
    i1 = b1["bi_idx"]
    after = bis[i1 + 1:]
    if len(after) < 2:
        return None
    if after[0]["direction"] != "up":
        return None
    if after[1]["direction"] != "down":
        return None

    pullback = after[1]
    pb_low = _bi_low(pullback)
    if pb_low <= b1["price"]:
        return None

    leave_high = _bi_high(after[0])
    rebound = leave_high - b1["price"]
    if rebound > 0:
        retrace = (leave_high - pb_low) / rebound
        if retrace > 0.7:
            return None
    else:
        retrace = 0.0

    score = 60
    if retrace < 0.5:
        score += 10
    if retrace < 0.382:
        score += 5
    if b1.get("strength", 0) > 0.3:
        score += 10
    if b1.get("strength", 0) > 0.5:
        score += 5
    score = min(score, 95)

    return {
        "signal": "B2",
        "score": score,
        "b1_price": b1["price"],
        "pullback_low": pb_low,
        "leave_high": leave_high,
        "retrace": round(retrace, 3),
        "strength": b1.get("strength"),
        "reason": "二买：一买后回调不破前低",
    }


def _detect_s2(bis, s1):
    i1 = s1["bi_idx"]
    after = bis[i1 + 1:]
    if len(after) < 2:
        return None
    if after[0]["direction"] != "down":
        return None
    if after[1]["direction"] != "up":
        return None

    pullback = after[1]
    pb_high = _bi_high(pullback)
    if pb_high >= s1["price"]:
        return None

    leave_low = _bi_low(after[0])
    decline = s1["price"] - leave_low
    if decline > 0:
        retrace = (pb_high - leave_low) / decline
        if retrace > 0.7:
            return None
    else:
        retrace = 0.0

    score = 60
    if retrace < 0.5:
        score += 10
    if retrace < 0.382:
        score += 5
    if s1.get("strength", 0) > 0.3:
        score += 10
    if s1.get("strength", 0) > 0.5:
        score += 5
    score = min(score, 95)

    return {
        "signal": "S2",
        "score": score,
        "s1_price": s1["price"],
        "pullback_high": pb_high,
        "leave_low": leave_low,
        "retrace": round(retrace, 3),
        "strength": s1.get("strength"),
        "reason": "二卖：一卖后反抽不破前高",
    }


# ---------- 三买 / 三卖 ----------

def _detect_b3(candles, bis, center, tf):
    max_age = MAX_AGE_BY_TF.get(tf, DEFAULT_MAX_AGE)
    last_idx = len(candles) - 1
    last = candles[-1]

    age = last_idx - center["end_idx"]
    if age > max_age:
        return None

    post = _post_bis(bis, center["end_idx"])
    if len(post) < 2:
        return None

    leave_i = None
    for i, b in enumerate(post):
        if b["direction"] == "up" and _bi_high(b) > center["zg"]:
            leave_i = i
            break
    if leave_i is None:
        return None
    leave = post[leave_i]

    after = post[leave_i + 1:]
    if not after:
        return None
    pullback = after[0]
    if pullback["direction"] != "down":
        return None

    pb_low = _bi_low(pullback)
    if pb_low <= center["zg"]:
        return None

    pb_high = _bi_high(pullback)
    if last.close <= pb_high:
        return None

    score = 50
    if age < max_age // 2:
        score += 10
    leave_gain = _bi_high(leave) - center["zg"]
    pb_depth = _bi_high(pullback) - pb_low
    if leave_gain > 0 and pb_depth / leave_gain < 0.5:
        score += 10
    if last.close > _bi_high(leave):
        score += 10
    score = min(score, 95)

    return {
        "signal": "B3", "score": score,
        "center": {"zg": center["zg"], "zd": center["zd"]},
        "age_bars": age,
        "leave_high": _bi_high(leave),
        "pullback_low": pb_low,
        "signal_ts": last.timestamp,
    }


def _detect_s3(candles, bis, center, tf):
    max_age = MAX_AGE_BY_TF.get(tf, DEFAULT_MAX_AGE)
    last_idx = len(candles) - 1
    last = candles[-1]

    age = last_idx - center["end_idx"]
    if age > max_age:
        return None

    post = _post_bis(bis, center["end_idx"])
    if len(post) < 2:
        return None

    leave_i = None
    for i, b in enumerate(post):
        if b["direction"] == "down" and _bi_low(b) < center["zd"]:
            leave_i = i
            break
    if leave_i is None:
        return None
    leave = post[leave_i]

    after = post[leave_i + 1:]
    if not after:
        return None
    pullback = after[0]
    if pullback["direction"] != "up":
        return None

    pb_high = _bi_high(pullback)
    if pb_high >= center["zd"]:
        return None
    if last.close >= _bi_low(pullback):
        return None

    score = 50
    if age < max_age // 2:
        score += 10
    leave_drop = center["zd"] - _bi_low(leave)
    pb_depth = pb_high - _bi_low(pullback)
    if leave_drop > 0 and pb_depth / leave_drop < 0.5:
        score += 10
    if last.close < _bi_low(leave):
        score += 10
    score = min(score, 95)

    return {
        "signal": "S3", "score": score,
        "center": {"zg": center["zg"], "zd": center["zd"]},
        "age_bars": age,
        "leave_low": _bi_low(leave),
        "pullback_high": pb_high,
        "signal_ts": last.timestamp,
    }


# ---------- 中枢 ----------

def _center_dict(centers):
    if not centers:
        return None
    c = centers[-1]
    return {"zg": c["zg"], "zd": c["zd"]}


# ---------- 入口 ----------

def detect_signals(candles, bis, centers, tf="15m"):
    if not candles or not bis:
        return {"signal": None, "score": 0, "center": None}

    last_idx = len(candles) - 1
    last_candle = candles[-1]
    cdict = _center_dict(centers)

    # ★ 所有信号的 trigger_ts 都用"当前 K 线时间"（最近确认时间）
    trigger_ts = last_candle.timestamp

    # -------- 1. 一买 / 二买 --------
    b1_list = _find_all_b1(candles, bis)
    if b1_list:
        b1_last = b1_list[-1]
        age = last_idx - b1_last["end_idx"]

        if age <= B1_FRESH_MAX:
            # ★ 有效期检查：当前价不能跌破一买低点
            if last_candle.close > b1_last["price"]:
                b2 = _detect_b2(bis, b1_last)
                if b2:
                    b2["center"] = cdict
                    b2["trigger_ts"] = trigger_ts
                    b2["signal_ts"] = candles[b1_last["end_idx"]].timestamp
                    b2["age_bars"] = last_idx - b1_last["end_idx"]
                    return b2

                return {
                    "signal": "B1",
                    "score": int(60 + b1_last["strength"] * 35),
                    "center": cdict,
                    "price": b1_last["price"],
                    "strength": round(b1_last["strength"], 3),
                    "age_bars": age,
                    "trigger_ts": trigger_ts,
                    "signal_ts": candles[b1_last["end_idx"]].timestamp,
                    "reason": "一买：底背驰（价格新低，MACD 绿柱面积萎缩）",
                }

    # -------- 2. 一卖 / 二卖 --------
    s1_list = _find_all_s1(candles, bis)
    if s1_list:
        s1_last = s1_list[-1]
        age = last_idx - s1_last["end_idx"]

        if age <= B1_FRESH_MAX:
            # ★ 有效期检查：当前价不能突破一卖高点
            if last_candle.close < s1_last["price"]:
                s2 = _detect_s2(bis, s1_last)
                if s2:
                    s2["center"] = cdict
                    s2["trigger_ts"] = trigger_ts
                    s2["signal_ts"] = candles[s1_last["end_idx"]].timestamp
                    s2["age_bars"] = last_idx - s1_last["end_idx"]
                    return s2

                return {
                    "signal": "S1",
                    "score": int(60 + s1_last["strength"] * 35),
                    "center": cdict,
                    "price": s1_last["price"],
                    "strength": round(s1_last["strength"], 3),
                    "age_bars": age,
                    "trigger_ts": trigger_ts,
                    "signal_ts": candles[s1_last["end_idx"]].timestamp,
                    "reason": "一卖：顶背驰（价格新高，MACD 红柱面积萎缩）",
                }

    # -------- 3. 三买 / 三卖 --------
    if centers:
        for center in reversed(centers):
            b3 = _detect_b3(candles, bis, center, tf)
            if b3:
                b3["trigger_ts"] = trigger_ts
                return b3
            s3 = _detect_s3(candles, bis, center, tf)
            if s3:
                s3["trigger_ts"] = trigger_ts
                return s3

    c = centers[-1] if centers else None
    return {
        "signal": None, "score": 0,
        "center": {"zg": c["zg"], "zd": c["zd"]} if c else None,
        "age_bars": (last_idx - c["end_idx"]) if c else None,
    }