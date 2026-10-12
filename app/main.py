# app/main.py
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config.settings import SYMBOLS, settings
from app.data.base import MarketTick, Candle
from app.data.adapters.binance import BinanceProvider
from app.data.adapters.coinbase import CoinbaseProvider
from app.data.adapters.kraken import KrakenProvider
from app.data.adapters.okx import OKXProvider
from app.data.adapters.us_market import YahooFinanceProvider, in_us_session
from app.data.adapters.sina_finance import SinaFinanceProvider
from app.data.health import DataHealthMonitor
from app.market.candles import CandleAggregator
from app.chan.engine import ChanEngine
from app.volume.engine import VolumeEngine
from app.signal.scoring import score_signal
from app.signal.multi_timeframe import MultiTimeframeEngine
from app.alert.manager import alert_manager
from app.cache import redis_client
from app.api import (
    routes_market, routes_chan, routes_candles,
    routes_chan_plot, websocket,
)


app = FastAPI(title="X1.0 Market Monitor")


# ============================================================
# ★ 屏蔽 Windows asyncio 已知噪音
# ============================================================

def _install_silent_exception_handler():
    """
    Windows ProactorEventLoop 在连接被强制重置时会抛出
    `AttributeError: 'ClientConnection' object has no attribute 'recv_messages'`，
    这是 websockets 库 + Windows asyncio 的已知问题，不影响功能。
    这里静默忽略它，其它异常走默认处理。
    """
    try:
        loop = asyncio.get_event_loop()
        orig = loop.get_exception_handler()

        def _handler(loop, context):
            exc = context.get("exception")
            if exc is not None and "recv_messages" in str(exc):
                return
            if orig is not None:
                orig(loop, context)
            else:
                loop.default_exception_handler(context)

        loop.set_exception_handler(_handler)
    except Exception:
        pass


# ============================================================
# 信号过滤规则
# ============================================================

MAX_AGE_BY_TF = {
    "1m": 1, "5m": 2, "15m": 6, "30m": 12,
    "1h": 24, "4h": 36, "1d": 72,
}
DEFAULT_MAX_AGE_HOURS = 24.0
MIN_SCORE = 60


def _parse_ts(ts):
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        sec = ts / 1000 if ts > 1e11 else ts
        try:
            return datetime.fromtimestamp(sec, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(ts, str):
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t
    return None


def _score_of(item):
    sc = item.get("score")
    if isinstance(sc, dict):
        return sc.get("total", 0) or 0
    if isinstance(sc, (int, float)):
        return sc
    return 0


def _passes_filter(payload: dict) -> bool:
    if not payload.get("signal"):
        return False
    if _score_of(payload) < MIN_SCORE:
        return False
    tf = payload.get("timeframe")
    limit = MAX_AGE_BY_TF.get(tf, DEFAULT_MAX_AGE_HOURS)
    ts = _parse_ts(payload.get("trigger_ts"))
    if ts is not None:
        age = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age > limit:
            return False
    return True


# ============================================================
# symbol 统一映射
# ============================================================

def _build_raw_to_std():
    m = {}
    for std_sym, cfg in SYMBOLS.get("crypto", {}).items():
        for k, v in cfg.items():
            if not k.endswith("_symbol"):
                continue
            if not isinstance(v, str) or not v:
                continue
            m[v] = std_sym
            m[v.replace("-", "/")] = std_sym
            m[v.replace("-", "")]  = std_sym
            m[v.replace("/", "")]  = std_sym

    for std_sym in SYMBOLS.get("us_index", {}):
        m[std_sym] = std_sym

    return m


RAW_TO_STD = _build_raw_to_std()


def _to_std(candle: Candle) -> Candle:
    std = RAW_TO_STD.get(candle.symbol)
    if not std or std == candle.symbol:
        return candle
    return Candle(
        symbol=std,
        timeframe=candle.timeframe,
        timestamp=candle.timestamp,
        open=candle.open, high=candle.high,
        low=candle.low, close=candle.close,
        volume=candle.volume,
        source=candle.source,
        is_closed=candle.is_closed,
    )


# ============================================================
# 全局状态
# ============================================================

x1_state = {
    "ticks": {},
    "signals": {},
    "health": None,
    "alert_manager": alert_manager,
    "providers": {},
    "aggregator": None,
    "engines": {},
    "active_source": {},
}
app.state.x1 = x1_state


# ============================================================
# tick 回调
# ============================================================

async def on_tick(tick):
    std = RAW_TO_STD.get(tick.symbol)
    if std and std != tick.symbol:
        tick = MarketTick(
            symbol=std,
            asset_class=tick.asset_class,
            price=tick.price,
            volume=tick.volume,
            timestamp=tick.timestamp,
            source=tick.source,
        )

    x1_state["ticks"][tick.symbol] = tick.to_dict()
    await redis_client.set_ticker(tick.symbol, tick.to_dict())

    for ws in list(alert_manager.subscribers):
        try:
            await ws.send_json({"type": "ticker", **tick.to_dict()})
        except Exception:
            pass


# ============================================================
# K 线回调
# ============================================================

MTF_TFS = ["1d", "4h", "1h", "30m", "15m", "5m", "1m"]


async def on_kline(candle):
    try:
        candle = _to_std(candle)

        agg = x1_state["aggregator"]
        agg.update(candle)

        if not candle.is_closed:
            return

        try:
            from app.storage import repository as repo
            await repo.save_candles_bulk([candle])
        except Exception as e:
            print(f"[on_kline] save_candles failed: {type(e).__name__}: {e}")

        symbol = candle.symbol
        tf = candle.timeframe

        candles = agg.get_closed(symbol, tf, limit=500)
        if len(candles) < 30:
            return

        engines = x1_state["engines"]
        chan = engines["chan"]
        vol = engines["vol"]
        mtf = engines["mtf"]

        chan_res = chan.analyze(candles, tf=tf)
        vol_res = vol.analyze(candles)

        candles_by_tf = {}
        for t in MTF_TFS:
            cs = agg.get_closed(symbol, t, limit=300)
            if len(cs) >= 30:
                candles_by_tf[t] = cs

        mtf_res = mtf.analyze(candles_by_tf) if candles_by_tf else {}
        score = score_signal(chan_res, vol_res, mtf_res)

        payload = {
            "symbol": symbol,
            "timeframe": tf,
            "trend": chan_res.get("trend"),
            "signal": chan_res.get("signal"),
            "center": chan_res.get("center"),
            "volume": vol_res,
            "score": score,
            "source": candle.source,
            "trigger_ts": chan_res.get("trigger_ts"),
            "signal_ts": chan_res.get("signal_ts"),
            "reason": chan_res.get("reason"),
            "age_bars": chan_res.get("age_bars"),
            "price": candle.close,
        }

        key = f"{symbol}:{tf}"

        if chan_res.get("signal"):
            x1_state["signals"][key] = payload
        else:
            x1_state["signals"].pop(key, None)

        await redis_client.set_signal(symbol, tf, payload)

        if chan_res.get("signal") and _passes_filter(payload):
            alert = {
                "type": "chan_signal",
                "symbol": symbol,
                "timeframe": tf,
                "signal": chan_res["signal"],
                "score": score.get("total", chan_res.get("score", 0)),
                "price": candle.close,
                "volume_status": vol_res.get("status"),
                "trend": chan_res.get("trend"),
                "source": candle.source,
                "reason": chan_res.get("reason"),
                "trigger_ts": chan_res.get("trigger_ts"),
                "signal_ts": chan_res.get("signal_ts"),
                "center": chan_res.get("center"),
                "levels": {
                    "daily": mtf_res.get("1d", {}).get("trend"),
                    "h4":    mtf_res.get("4h", {}).get("trend"),
                    "h1":    mtf_res.get("1h", {}).get("trend"),
                    "m15":   mtf_res.get("15m", {}).get("trend"),
                },
                "disclaimer": score.get("disclaimer", ""),
            }
            await alert_manager.emit(alert)

    except Exception as e:
        import traceback
        print(f"[on_kline] ❌ {type(e).__name__}: {e}")
        traceback.print_exc()


# ============================================================
# REST 拉取（带重试）
# ============================================================

async def _fetch_klines_with_retry(provider, raw_sym, tf, start, end, retries=3):
    for i in range(retries):
        try:
            return await provider.get_historical_klines(raw_sym, tf, start, end)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            if i == retries - 1:
                raise
            print(f"[preload] {raw_sym} {tf} 第 {i+1} 次失败 ({type(e).__name__})，重试...")
            await asyncio.sleep(1.5 * (i + 1))


# ============================================================
# crypto failover 订阅
# ============================================================

async def subscribe_symbol_with_failover(sym: str, cfg: dict):
    """
    加密品种 failover。
    ★ 超时 30 秒：OKX 首次连接握手需要时间，前几秒可能收不到 tick。
    """
    providers = x1_state["providers"]
    candidates = [cfg["primary"]] + list(cfg.get("backup", []))
    candidates = [c for c in candidates if c in providers]

    for source_name in candidates:
        provider = providers[source_name]
        raw_sym = cfg.get(f"{source_name}_symbol")
        if not raw_sym:
            continue

        print(f"[failover] {sym}: 尝试源 {source_name} ({raw_sym})")
        got_data = asyncio.Event()
        bg_tasks = []

        async def on_tick_wrap(tick, _ev=got_data):
            _ev.set()
            await on_tick(tick)

        async def on_kline_wrap(c, _ev=got_data):
            _ev.set()
            await on_kline(c)

        try:
            await provider.connect()
            bg_tasks.append(asyncio.create_task(
                provider.subscribe_ticker(raw_sym, on_tick_wrap)
            ))
            for tf in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
                bg_tasks.append(asyncio.create_task(
                    provider.subscribe_kline(raw_sym, tf, on_kline_wrap)
                ))

            try:
                await asyncio.wait_for(got_data.wait(), timeout=30.0)
                print(f"[failover] {sym}: 源 {source_name} 工作正常 ✅")
                x1_state["active_source"][sym] = source_name
                return
            except asyncio.TimeoutError:
                print(f"[failover] {sym}: 源 {source_name} 30 秒无数据，切换下一个 ❌")
                for t in bg_tasks:
                    t.cancel()
                continue
        except Exception as e:
            print(f"[failover] {sym}: 源 {source_name} 异常 {type(e).__name__} {e}")
            for t in bg_tasks:
                t.cancel()
            continue

    print(f"[failover] {sym}: 所有源都失败 ⚠️")


# ============================================================
# 美股订阅（新浪主，Yahoo 备用）
# ============================================================

async def subscribe_us_symbol(sym: str, cfg: dict):
    """
    美股订阅。
    ★ 超时 25 秒：新浪每 15 秒轮询一次，第一次 tick 可能 15 秒后才到。
    """
    providers = x1_state["providers"]
    candidates = [cfg["primary"]] + list(cfg.get("backup", []))
    candidates = [c for c in candidates if c in providers]

    for source_name in candidates:
        provider = providers[source_name]
        print(f"[us] {sym}: 尝试源 {source_name}")

        got_data = asyncio.Event()
        bg_tasks = []

        async def on_tick_wrap(tick, _ev=got_data):
            _ev.set()
            await on_tick(tick)

        async def on_kline_wrap(c, _ev=got_data):
            _ev.set()
            await on_kline(c)

        try:
            await provider.connect()
            bg_tasks.append(asyncio.create_task(
                provider.subscribe_ticker(sym, on_tick_wrap)
            ))
            for tf in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
                bg_tasks.append(asyncio.create_task(
                    provider.subscribe_kline(sym, tf, on_kline_wrap)
                ))

            try:
                await asyncio.wait_for(got_data.wait(), timeout=25.0)
                print(f"[us] {sym}: 源 {source_name} 工作正常 ✅")
                x1_state["active_source"][sym] = source_name
                return
            except asyncio.TimeoutError:
                print(f"[us] {sym}: 源 {source_name} 25 秒无数据，切换下一个 ❌")
                for t in bg_tasks:
                    t.cancel()
                continue
        except Exception as e:
            print(f"[us] {sym}: 源 {source_name} 异常 {type(e).__name__} {e}")
            for t in bg_tasks:
                t.cancel()
            continue

    print(f"[us] {sym}: 所有源都失败 ⚠️")


# ============================================================
# 历史数据预加载（用 primary 源）
# ============================================================

async def _preload_crypto_history():
    from app.storage import repository as repo

    plan = {
        "1m":  timedelta(days=3),
        "5m":  timedelta(days=15),
        "15m": timedelta(days=30),
        "30m": timedelta(days=60),
        "1h":  timedelta(days=180),
        "4h":  timedelta(days=180),
        "1d":  timedelta(days=360),
    }

    crypto = SYMBOLS.get("crypto", {})
    print(f"[preload] 开始处理 {len(crypto)} 个币种")

    for sym, cfg in crypto.items():
        primary = cfg.get("primary", "okx")
        provider = x1_state["providers"].get(primary)
        raw_sym = cfg.get(f"{primary}_symbol", sym)

        if not provider:
            print(f"[preload] {sym}: ❌ 无 provider {primary}")
            continue

        agg = x1_state["aggregator"]
        print(f"[preload] {sym}: 用 {primary} ({raw_sym})")

        for tf, span in plan.items():
            try:
                end = datetime.now(timezone.utc)
                count = await repo.count_candles(sym, tf)
                latest_ts = await repo.get_latest_timestamp(sym, tf)

                if count >= 30 and latest_ts is not None:
                    if latest_ts.tzinfo is None:
                        latest_ts = latest_ts.replace(tzinfo=timezone.utc)
                    start = latest_ts - timedelta(minutes=5)
                    try:
                        candles_new = await _fetch_klines_with_retry(
                            provider, raw_sym, tf, start, end
                        )
                    except Exception as e:
                        print(f"[preload] {sym} {tf} 增量失败: {type(e).__name__}")
                        candles_new = []
                    if candles_new:
                        await repo.save_candles_bulk(candles_new)
                    candles = await repo.load_candles(sym, tf, limit=5000)
                    print(f"[preload] {sym} {tf}: 库 {count} + 增量 {len(candles_new)} → {len(candles)}")
                else:
                    start = end - span
                    try:
                        candles = await _fetch_klines_with_retry(
                            provider, raw_sym, tf, start, end
                        )
                    except Exception as e:
                        print(f"[preload] {sym} {tf} 首次失败: {type(e).__name__}")
                        candles = []
                    print(f"[preload] {sym} {tf}: 首次全量 {len(candles)}，写入数据库")
                    if candles:
                        await repo.save_candles_bulk(candles)

                for c in candles:
                    agg.update(c)

                cs = agg.get_closed(sym, tf, limit=500)
                if len(cs) >= 30:
                    await on_kline(cs[-1])

            except Exception as e:
                import traceback
                print(f"[preload] {sym} {tf} ❌ {type(e).__name__}: {e}")
                traceback.print_exc()


async def _preload_us_history():
    from app.storage import repository as repo

    providers = x1_state["providers"]
    plan = [("1d", timedelta(days=730))]

    agg = x1_state["aggregator"]
    us_index = SYMBOLS.get("us_index", {})
    print(f"[us-preload] 开始处理 {len(us_index)} 个指数（仅 1d）")

    for sym, cfg in us_index.items():
        candidates = [cfg.get("primary", "sina")] + list(cfg.get("backup", []))
        candidates = [c for c in candidates if c in providers]

        for tf, span in plan:
            try:
                count = await repo.count_candles(sym, tf)

                if count >= 30:
                    candles = await repo.load_candles(sym, tf, limit=5000)
                    print(f"[us-preload] {sym} {tf}: 库 {len(candles)} 根")
                else:
                    end = datetime.now(timezone.utc)
                    start = end - span
                    candles = []
                    for src in candidates:
                        provider = providers[src]
                        try:
                            candles = await provider.get_historical_klines(
                                sym, tf, start, end
                            )
                            if candles:
                                print(f"[us-preload] {sym} {tf}: {src} 拉到 {len(candles)} 根")
                                break
                        except Exception as e:
                            print(f"[us-preload] {sym} {tf} {src} 失败: {type(e).__name__}")

                    if candles:
                        await repo.save_candles_bulk(candles)

                for c in candles:
                    agg.update(c)

                cs = agg.get_closed(sym, tf, limit=500)
                if len(cs) >= 30:
                    await on_kline(cs[-1])

                await asyncio.sleep(3)

            except Exception as e:
                import traceback
                print(f"[us-preload] {sym} {tf} ❌ {type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)


async def preload_history():
    await _preload_crypto_history()
    await _preload_us_history()


# ============================================================
# ticker 兜底
# ============================================================

async def ticker_fallback_loop():
    PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None

    crypto = SYMBOLS.get("crypto", {})
    raw_list = [c.get("binance_symbol") for c in crypto.values()
                if c.get("binance_symbol")]
    if not raw_list:
        return

    fail_count = 0
    while True:
        try:
            async with httpx.AsyncClient(timeout=8, proxy=PROXY) as cli:
                r = await cli.get(
                    "https://api.binance.com/api/v3/ticker/price",
                    params={"symbols": "[" + ",".join(f'"{s}"' for s in raw_list) + "]"},
                )
            if r.status_code == 200:
                for item in r.json():
                    std = RAW_TO_STD.get(item["symbol"], item["symbol"])
                    tick = MarketTick(
                        symbol=std,
                        asset_class="crypto",
                        price=float(item["price"]),
                        volume=0.0,
                        timestamp=datetime.now(timezone.utc),
                        source="binance-rest",
                    )
                    await on_tick(tick)
                fail_count = 0
            else:
                fail_count += 1
                if fail_count <= 3 or fail_count % 30 == 0:
                    print(f"[ticker-fallback] HTTP {r.status_code} (累计失败 {fail_count})")
        except Exception as e:
            fail_count += 1
            if fail_count <= 3 or fail_count % 30 == 0:
                print(f"[ticker-fallback] {type(e).__name__}: {e} (累计失败 {fail_count})")
        await asyncio.sleep(10)


# ============================================================
# 健康检查
# ============================================================

async def health_loop():
    health = x1_state["health"]
    while True:
        for name, p in list(health.providers.items()):
            try:
                st = await p.health_check()
                health.status[name] = st
                await redis_client.set_health(name, st)
            except Exception as e:
                health.status[name] = {
                    "source": name, "online": False, "score": 0,
                    "latency_ms": 9999, "error": str(e),
                }
        await asyncio.sleep(settings.health_interval)


# ============================================================
# 启动订阅
# ============================================================

async def start_subscriptions():
    providers = x1_state["providers"]

    for sym, cfg in SYMBOLS.get("crypto", {}).items():
        asyncio.create_task(subscribe_symbol_with_failover(sym, cfg))

    for sym, cfg in SYMBOLS.get("us_index", {}).items():
        asyncio.create_task(subscribe_us_symbol(sym, cfg))

    await asyncio.sleep(2)
    asyncio.create_task(preload_history())


# ============================================================
# startup
# ============================================================

@app.on_event("startup")
async def startup():
    # ★ 静默 Windows asyncio 的 recv_messages 噪音
    _install_silent_exception_handler()

    print("=" * 60)
    print("[startup] 开始执行 startup()")
    print("=" * 60)

    try:
        from app.storage import repository as repo
        print("[startup] 导入 repo 成功")
        await repo.init_db()
        print("[startup] ✅ 数据库初始化完成")
    except Exception as e:
        import traceback
        print(f"[startup] ❌ 数据库初始化失败: {type(e).__name__}: {e}")
        traceback.print_exc()

    chan = ChanEngine()
    x1_state["engines"] = {
        "chan": chan,
        "vol":  VolumeEngine(),
        "mtf":  MultiTimeframeEngine(chan),
    }

    x1_state["aggregator"] = CandleAggregator()

    providers = {
        "binance":  BinanceProvider(),
        "okx":      OKXProvider(),
        "coinbase": CoinbaseProvider(),
        "kraken":   KrakenProvider(),
        "yahoo":    YahooFinanceProvider(),
        "sina":     SinaFinanceProvider(),
    }
    x1_state["providers"] = providers

    health = DataHealthMonitor()
    health.providers = providers
    x1_state["health"] = health

    asyncio.create_task(health_loop())
    asyncio.create_task(start_subscriptions())
    asyncio.create_task(ticker_fallback_loop())

    print("[startup] ✅ startup() 完成")
    print("=" * 60)


# ============================================================
# 路由 & 静态文件
# ============================================================

app.include_router(routes_market.router)
app.include_router(routes_chan.router)
app.include_router(routes_candles.router)
app.include_router(routes_chan_plot.router)
app.include_router(websocket.router)

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")