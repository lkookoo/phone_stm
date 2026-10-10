from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from pathlib import Path

from app.storage.models import Base, CandleModel, DataHealthModel
from app.data.base import Candle

# SQLite 数据库文件
DB_PATH = Path(__file__).resolve().parent.parent.parent / "x1_data.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DB_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """创建所有表"""
    print(f"[storage] 初始化数据库: {DB_PATH}")
    print(f"[storage] DB URL: {DB_URL}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        tables = list(Base.metadata.tables.keys())
        print(f"[storage] ✅ 表已创建: {tables}")
    except Exception as e:
        import traceback
        print(f"[storage] ❌ init_db 失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise

async def save_candles_bulk(candles: List[Candle], batch_size: int = 500):
    """
    批量保存 K 线（幂等：已存在则忽略）。
    ★ 分批插入，避免 SQLite 单条 INSERT 参数超限（默认上限 32766）。
    每批 500 行 × 10 字段 = 5000 参数，安全。
    """
    if not candles:
        return 0

    total_saved = 0
    async with SessionLocal() as session:
        for i in range(0, len(candles), batch_size):
            batch = candles[i:i + batch_size]
            rows = [{
                "symbol": c.symbol,
                "timeframe": c.timeframe,
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "source": c.source,
                "is_closed": c.is_closed,
            } for c in batch]

            stmt = sqlite_insert(CandleModel).values(rows)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["symbol", "timeframe", "timestamp"]
            )
            await session.execute(stmt)
            total_saved += len(rows)

        await session.commit()

    return total_saved

async def load_candles(symbol: str, timeframe: str,
                       start: Optional[datetime] = None,
                       end: Optional[datetime] = None,
                       limit: int = 5000) -> List[Candle]:
    """
    从数据库读 K 线。
    - start/end 不指定 → 读最近 limit 根
    - 指定 start/end → 读区间内的
    """
    async with SessionLocal() as session:
        stmt = select(CandleModel).where(
            CandleModel.symbol == symbol,
            CandleModel.timeframe == timeframe,
        )
        if start:
            stmt = stmt.where(CandleModel.timestamp >= start)
        if end:
            stmt = stmt.where(CandleModel.timestamp <= end)

        stmt = stmt.order_by(CandleModel.timestamp.desc()).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()

    # 转 Candle，按时间升序
    candles = [
        Candle(
            symbol=r.symbol,
            timeframe=r.timeframe,
            timestamp=r.timestamp,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
            source=r.source,
            is_closed=r.is_closed,
        )
        for r in reversed(rows)
    ]
    return candles


async def get_latest_timestamp(symbol: str, timeframe: str) -> Optional[datetime]:
    """查询某 symbol+timeframe 的最新 K 线时间戳（返回 timezone-aware UTC）"""
    async with SessionLocal() as session:
        stmt = (
            select(CandleModel.timestamp)
            .where(CandleModel.symbol == symbol, CandleModel.timeframe == timeframe)
            .order_by(CandleModel.timestamp.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None and row.tzinfo is None:
            row = row.replace(tzinfo=timezone.utc)
        return row

async def count_candles(symbol: str, timeframe: str) -> int:
    """统计 K 线数量"""
    from sqlalchemy import func
    async with SessionLocal() as session:
        stmt = select(func.count()).select_from(CandleModel).where(
            CandleModel.symbol == symbol,
            CandleModel.timeframe == timeframe,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() or 0


async def save_health(source: str, online: bool, latency_ms: int, score: float):
    async with SessionLocal() as session:
        session.add(DataHealthModel(
            source=source, online=online, latency_ms=latency_ms, score=score,
        ))
        await session.commit()