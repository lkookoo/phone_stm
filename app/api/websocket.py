from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    manager = ws.app.state.x1["alert_manager"]
    manager.register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.unregister(ws)
    except Exception:
        manager.unregister(ws)