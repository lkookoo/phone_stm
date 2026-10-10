def _seg_high(s):
    if "high" in s: return s["high"]
    return max(s["start_price"], s["end_price"])

def _seg_low(s):
    if "low" in s: return s["low"]
    return min(s["start_price"], s["end_price"])


def build_centers(segments):
    """
    三笔重叠成中枢 + 后续延伸 + 完全脱离结束。
    segments 是笔（或线段），每个元素必须有 start_idx / end_idx（K 线索引）。
    """
    centers = []
    n = len(segments)
    if n < 3:
        return centers

    i = 0
    while i + 2 < n:
        s1, s2, s3 = segments[i], segments[i+1], segments[i+2]
        zg = min(_seg_high(s1), _seg_high(s2), _seg_high(s3))
        zd = max(_seg_low(s1),  _seg_low(s2),  _seg_low(s3))
        if zg <= zd:
            i += 1
            continue

        j = i + 3
        while j < n:
            s = segments[j]
            if _seg_high(s) < zd or _seg_low(s) > zg:
                break
            j += 1

        seg_slice = segments[i:j]
        centers.append({
            "start_idx": seg_slice[0]["start_idx"],   # ★ K 线索引
            "end_idx":   seg_slice[-1]["end_idx"],    # ★ K 线索引
            "start_ts":  seg_slice[0].get("start_ts"),
            "end_ts":    seg_slice[-1].get("end_ts"),
            "zg": zg,
            "zd": zd,
            "mid": (zg + zd) / 2,
            "gg": max(_seg_high(s) for s in seg_slice),
            "dd": min(_seg_low(s)  for s in seg_slice),
            "seg_count": len(seg_slice),
        })
        i = j
    return centers