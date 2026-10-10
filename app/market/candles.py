from collections import defaultdict
from app.data.base import Candle
from app.market.timeframe import align_ts, TF_MS, ALL_TIMEFRAMES


class CandleAggregator:
    def __init__(self):
        self.buffers = defaultdict(lambda: defaultdict(dict))

    def update(self, c: Candle):
        """
        更新聚合器。历史K线（来自 REST）直接标记为已收盘；
        实时K线根据时间戳判断是否收盘。
        """
        key = int(c.timestamp.timestamp() * 1000)
        for tf in ALL_TIMEFRAMES:
            open_ts = align_ts(key, tf)
            buf = self.buffers[c.symbol][tf]
            cur = buf.get(open_ts)
            if cur is None:
                buf[open_ts] = Candle(
                    symbol=c.symbol, timeframe=tf,
                    timestamp=c.timestamp,
                    open=c.open, high=c.high, low=c.low, close=c.close,
                    volume=c.volume, source=c.source,
                    # ★ 历史K线（来自 REST）在预加载时已经是完整的
                    is_closed=c.is_closed,
                )
            else:
                cur.high = max(cur.high, c.high)
                cur.low = min(cur.low, c.low)
                cur.close = c.close
                cur.volume += c.volume
                # ★ 实时K线：当收到下一周期的数据时才标记为 closed
                if c.is_closed:
                    cur.is_closed = True

    def get_closed(self, symbol, tf, limit=500):
        buf = self.buffers[symbol][tf]
        closed = [c for ts, c in sorted(buf.items()) if c.is_closed]
        return closed[-limit:]

    def get_all(self, symbol, tf, limit=500):
        buf = self.buffers[symbol][tf]
        rows = [c for ts, c in sorted(buf.items())]
        return rows[-limit:]