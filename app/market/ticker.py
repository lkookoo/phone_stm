from collections import defaultdict


class TickerStore:
    def __init__(self):
        self.ticks = {}

    def update(self, tick):
        self.ticks[tick.symbol] = tick.to_dict()

    def all(self):
        return list(self.ticks.values())

    def get(self, symbol):
        return self.ticks.get(symbol)