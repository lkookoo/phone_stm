from app.signal.scoring import score_signal


def test_score_signal():
    chan = {"center": {"zg": 100, "zd": 90}, "signal": "B3"}
    vol = {"status": "放量"}
    mtf = {"1d": {"trend": "UP"}, "4h": {"trend": "UP"},
           "1h": {"trend": "UP"}, "15m": {"signal": "B3"}}
    s = score_signal(chan, vol, mtf)
    assert s["total"] == 100
    assert "disclaimer" in s