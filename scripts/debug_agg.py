"""
诊断聚合器状态。必须让 uvicorn 在跑着。
用法：
    python -m scripts.debug_agg
"""
import asyncio
import httpx


async def main():
    async with httpx.AsyncClient(timeout=10) as c:
        # 直接调用内存里的 aggregator
        # 但这个是另一个进程，拿不到 → 用 REST 接口间接看
        print("=== /api/chan/BTC/USDT/all ===")
        r = await c.get("http://127.0.0.1:8000/api/chan/BTC/USDT/all")
        print(r.text[:300])

        print("\n=== /api/market/overview ===")
        r = await c.get("http://127.0.0.1:8000/api/market/overview")
        print(r.text[:300])


if __name__ == "__main__":
    asyncio.run(main())