"""
批量回补：遍历 symbols.yaml 里的加密货币，下载多个周期。
用法：
    python -m scripts.backfill
"""
import asyncio
from datetime import datetime, timedelta, timezone
from app.config.settings import SYMBOLS
from app.data.adapters.binance import BinanceProvider


async def main():
    p = BinanceProvider()
    await p.connect()
    crypto = SYMBOLS.get("crypto", {})
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)

    for sym, cfg in crypto.items():
        binance_sym = cfg.get("binance_symbol", sym.replace("/", ""))
        for tf in ["15m", "1h", "4h", "1d"]:
            try:
                candles = await p.get_historical_klines(binance_sym, tf, start, end)
                print(f"{sym} {tf}: {len(candles)} 根")
            except Exception as e:
                print(f"{sym} {tf} 失败: {e}")
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())