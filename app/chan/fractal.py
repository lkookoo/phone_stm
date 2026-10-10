from dataclasses import dataclass
from typing import List
from app.data.base import Candle


@dataclass
class Fractal:
    idx: int
    ts: int
    kind: str      # "top" | "bottom"
    price: float


@dataclass
class MergedBar:
    high: float
    low: float
    last_idx: int   # 合并进来的最后一根原始 K 线索引
    direction: int  # 1 向上，-1 向下


def _merge_containing(candles: List[Candle]) -> List[MergedBar]:
    """
    缠论包含处理：
    - 相邻 K 线若一方完全包含另一方 → 按前一根的方向合并
    - 向上趋势：高取高、低取高
    - 向下趋势：高取低、低取低
    """
    if not candles:
        return []

    merged: List[MergedBar] = [
        MergedBar(
            high=candles[0].high,
            low=candles[0].low,
            last_idx=0,
            direction=1,
        )
    ]

    for i in range(1, len(candles)):
        c = candles[i]
        prev = merged[-1]

        # 判断是否包含
        contains = (
            (c.high <= prev.high and c.low >= prev.low) or
            (c.high >= prev.high and c.low <= prev.low)
        )

        if not contains:
            # 无包含：新 bar，方向由与前一根的高低决定
            direction = 1 if c.high > prev.high else -1
            merged.append(MergedBar(
                high=c.high, low=c.low,
                last_idx=i, direction=direction,
            ))
        else:
            # 包含：按 prev 的方向合并
            if prev.direction == 1:
                prev.high = max(prev.high, c.high)
                prev.low  = max(prev.low,  c.low)
            else:
                prev.high = min(prev.high, c.high)
                prev.low  = min(prev.low,  c.low)
            prev.last_idx = i   # 时间戳跟着最新那根走

    return merged


def find_fractals(candles: List[Candle]) -> List[Fractal]:
    """
    1. 先做包含处理
    2. 在合并后的 bar 序列上找顶/底分型
    3. idx / ts 都指向合并 bar 的最后一根原始 K 线，
       保证和 candles 索引严格对齐（bi / center 的坐标系一致）
    """
    if len(candles) < 3:
        return []

    merged = _merge_containing(candles)
    if len(merged) < 3:
        return []

    out: List[Fractal] = []
    for i in range(1, len(merged) - 1):
        a, b, c = merged[i - 1], merged[i], merged[i + 1]

        # 顶分型
        if b.high > a.high and b.high > c.high and \
           b.low  > a.low  and b.low  > c.low:
            idx = b.last_idx
            out.append(Fractal(
                idx=idx,
                ts=int(candles[idx].timestamp.timestamp() * 1000),
                kind="top",
                price=b.high,
            ))
        # 底分型
        elif b.low  < a.low  and b.low  < c.low and \
             b.high < a.high and b.high < c.high:
            idx = b.last_idx
            out.append(Fractal(
                idx=idx,
                ts=int(candles[idx].timestamp.timestamp() * 1000),
                kind="bottom",
                price=b.low,
            ))

    return out