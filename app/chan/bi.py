from typing import List
from app.chan.fractal import Fractal


def build_bi(fractals: List[Fractal], min_gap: int = 4) -> List[dict]:
    if not fractals:
        return []
    bis = []
    last = fractals[0]
    for f in fractals[1:]:
        if f.kind == last.kind:
            if (f.kind == "top" and f.price > last.price) or \
               (f.kind == "bottom" and f.price < last.price):
                last = f
            continue
        if abs(f.idx - last.idx) < min_gap:
            continue

        sp, ep = last.price, f.price
        bis.append({
            "start_idx": last.idx,          # ★ K 线索引
            "end_idx":   f.idx,             # ★ K 线索引
            "start_ts":  last.ts,
            "end_ts":    f.ts,
            "start_price": sp,
            "end_price":   ep,
            "high": max(sp, ep),            # ★
            "low":  min(sp, ep),            # ★
            "direction": "up" if f.kind == "top" else "down",
        })
        last = f
    return bis