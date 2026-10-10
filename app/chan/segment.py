# app/chan/segment.py
"""
缠论线段（简化版：反向笔高低点破坏）。

- 向上线段：反向笔（向下）里出现"低点更低" → 线段结束
- 向下线段：反向笔（向上）里出现"高点更高" → 线段结束
"""
from typing import List


DEBUG = False   # 调试时改 True


def _make_segment(bis: List[dict], start_bi: int, end_bi: int, direction: str) -> dict:
    first = bis[start_bi]
    last = bis[end_bi]
    seg_bis = bis[start_bi:end_bi + 1]
    return {
        "start_idx":   first["start_idx"],
        "end_idx":     last["end_idx"],
        "start_ts":    first["start_ts"],
        "end_ts":      last["end_ts"],
        "start_price": first["start_price"],
        "end_price":   last["end_price"],
        "direction":   direction,
        "high":        max(b["high"] for b in seg_bis),
        "low":         min(b["low"]  for b in seg_bis),
        "bi_start":    start_bi,
        "bi_end":      end_bi,
        "bi_count":    end_bi - start_bi + 1,
    }


def build_segments(bis: List[dict]) -> List[dict]:
    if not bis or len(bis) < 3:
        return []

    segments: List[dict] = []
    n = len(bis)
    i = 0

    while i + 2 < n:
        seg_dir = bis[i]["direction"]

        # 找破坏点
        end_bi = None
        prev_feat = None
        for j in range(i + 1, n):
            if bis[j]["direction"] != seg_dir:
                if prev_feat is not None:
                    if seg_dir == "up":
                        if bis[j]["low"] < prev_feat["low"]:
                            end_bi = j - 1
                            break
                    else:
                        if bis[j]["high"] > prev_feat["high"]:
                            end_bi = j - 1
                            break
                prev_feat = bis[j]

        if end_bi is None:
            end_bi = n - 1

        if end_bi < i + 2:
            i += 1
            continue

        segments.append(_make_segment(bis, i, end_bi, seg_dir))
        i = end_bi + 1

    return segments