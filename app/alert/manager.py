class AlertManager:
    def __init__(self):
        self.subscribers = []
        self.history = []

    def register(self, ws):
        self.subscribers.append(ws)

    def unregister(self, ws):
        if ws in self.subscribers:
            self.subscribers.remove(ws)

    async def emit(self, alert: dict):
        self.history.append(alert)
        self.history = self.history[-500:]
        dead = []
        for ws in self.subscribers:
            try:
                await ws.send_json(alert)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister(ws)


alert_manager = AlertManager()