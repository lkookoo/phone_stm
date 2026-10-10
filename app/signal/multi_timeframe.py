class MultiTimeframeEngine:
    def __init__(self, chan_engine):
        self.chan = chan_engine

    def analyze(self, candles_by_tf: dict):
        result = {}
        for tf, candles in candles_by_tf.items():
            result[tf] = self.chan.analyze(candles)
        return result