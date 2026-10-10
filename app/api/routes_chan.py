from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/chan", tags=["chan"])


@router.get("/{symbol:path}/signal")
async def signal(symbol: str, request: Request, timeframe: str = "15m"):
    state = request.app.state.x1
    return state["signals"].get(f"{symbol}:{timeframe}", {})


@router.get("/{symbol:path}/all")
async def all_signals(symbol: str, request: Request):
    state = request.app.state.x1
    return {k: v for k, v in state["signals"].items() if k.startswith(symbol + ":")}