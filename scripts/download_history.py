"""
从 Binance 下载历史K线，写入 PostgreSQL。
用法：
    python -m scripts.download_history BTCUSDT 15m 500
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from app.data.adapters.binance import BinanceProvider


async def main(symbol: str, timeframe: str, limit: int):
    p = BinanceProvider()
    await p.connect()
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=limit * 60)
    candles = await p.get_historical_klines(symbol, timeframe, start, end)
    print(f"下载 {len(candles)} 根 K线")
    for c in candles[-3:]:
        print(c.to_dict())


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "15m"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    asyncio.run(main(symbol, timeframe, limit))