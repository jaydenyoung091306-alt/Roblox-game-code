"""
NVDA AutoTrader test suite (v4.99) — no network, no real orders.

    cd nvda-autotrader
    python -m unittest discover -s tests -v

Covers:
  PanelTests        control panel API, settings rules, secret never leaked,
                    security guards (Host / Origin / content type / CORS)
  BotProcessTests   Start/Stop, keys handed to the bot, exit codes,
                    auto-restart on crash, no restart on bad keys
  EndToEndTests     browser → panel → bot server → simulated Alpaca:
                    manual trade open/close, TradingView webhook rules
  BrokerSimTests    the backtester's simulated broker fills
  BacktestRunTest   a full backtest replay through the bot's real code,
                    all consistency checks must PASS
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
ET = ZoneInfo("America/New_York")
TMP = tempfile.mkdtemp(prefix="nvda_tests_")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


BOT_PORT, TV_PORT = free_port(), free_port()
PASS = "test-passphrase-123456"
# Everything the bot reads at import time — set before it is imported anywhere.
os.environ.update({
    "ALPACA_API_KEY": "PKTEST", "ALPACA_SECRET_KEY": "secret", "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
    "NVDA_BOT_HOST": "127.0.0.1", "NVDA_BOT_PORT": str(BOT_PORT),
    "NVDA_TV_ENABLED": "1", "NVDA_TV_PASSPHRASE": PASS, "NVDA_TV_PORT": str(TV_PORT),
    "NVDA_SIGNAL_SOURCE": "both",
})


def http(url, body=None, headers=None, method=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {"Content-Type": "application/json"} if data is not None else {}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode()
            code = r.status
    except urllib.error.HTTPError as e:
        txt, code = e.read().decode(), e.code
    try:
        return code, json.loads(txt)
    except ValueError:
        return code, txt


def wait_for(cond, timeout=20.0, step=0.1):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(step)
    return False


# ═══════════════════════════════════════════════════════════════
# Control panel
# ═══════════════════════════════════════════════════════════════

STUB = os.path.join(TMP, "stub_bot.py")
STUB_MODE = os.path.join(TMP, "stub_mode.txt")
with open(STUB, "w") as f:
    f.write(f'''import os, sys, time
print("stub bot started key=" + os.environ.get("ALPACA_API_KEY", "MISSING")
      + " url=" + os.environ.get("ALPACA_BASE_URL", "") + " src=" + os.environ.get("NVDA_SIGNAL_SOURCE", ""), flush=True)
mode = open({STUB_MODE!r}).read().strip()
if mode == "run":
    while True:
        time.sleep(0.2)
sys.exit(int(mode))
''')


def load_panel():
    import build_dashboard as bd
    bd.SETTINGS_FILE = os.path.join(TMP, "nvda_settings.json")
    bd.PRICE_HIST_FILE = os.path.join(TMP, "nvda_price_history.json")
    bd.CONSOLE_LOG = os.path.join(TMP, "bot_console.log")
    bd.BOT_SCRIPT = STUB
    return bd


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bd = load_panel()
        with open(cls.bd.PRICE_HIST_FILE, "w") as f:
            json.dump([{"t": "2026-10-01T10:00", "p": 180.5}], f)
        cls.srv = cls.bd.ThreadingHTTPServer(("127.0.0.1", 0), cls.bd.PanelHandler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        if os.path.exists(self.bd.SETTINGS_FILE):
            os.remove(self.bd.SETTINGS_FILE)
        s = dict(self.bd.DEFAULT_SETTINGS, bot_port=free_port())   # nothing listening there
        self.bd.save_settings(s)

    def test_dashboard_html(self):
        code, html = http(self.url + "/")
        self.assertEqual(code, 200)
        self.assertIn("NVDA AutoTrader", html)
        self.assertIn("standalone: false", html)

    def test_save_keys_and_secret_never_returned(self):
        code, r = http(self.url + "/api/settings", {"alpaca_api_key": "PKABCDEFGHIJKL1234", "alpaca_secret_key": "topsecretvalue"})
        self.assertEqual(code, 200, r)
        self.assertTrue(r["settings"]["has_secret"])
        code, s = http(self.url + "/api/settings")
        self.assertNotIn("topsecretvalue", json.dumps(s))
        self.assertEqual(s["api_key_masked"], "PKAB••••••1234")
        with open(self.bd.SETTINGS_FILE) as f:
            self.assertEqual(json.load(f)["alpaca_secret_key"], "topsecretvalue")
        # blank fields keep the saved keys
        http(self.url + "/api/settings", {"signal_source": "tradingview"})
        with open(self.bd.SETTINGS_FILE) as f:
            saved = json.load(f)
        self.assertEqual(saved["alpaca_secret_key"], "topsecretvalue")
        self.assertEqual(saved["signal_source"], "tradingview")
        code, _ = http(self.url + "/api/settings", {"clear_keys": True})
        self.assertFalse(http(self.url + "/api/settings")[1]["has_api_key"])

    def test_live_mode_requires_confirmation(self):
        code, r = http(self.url + "/api/settings", {"trading_mode": "live"})
        self.assertEqual(code, 400)
        self.assertEqual(http(self.url + "/api/settings")[1]["trading_mode"], "paper")
        code, r = http(self.url + "/api/settings", {"trading_mode": "live", "confirm_live": True})
        self.assertEqual(code, 200)
        self.assertEqual(r["settings"]["trading_mode"], "live")

    def test_webhook_settings_rules(self):
        self.assertEqual(http(self.url + "/api/settings", {"tv_enabled": True})[0], 400)       # no passphrase
        self.assertEqual(http(self.url + "/api/settings", {"tv_passphrase": "short"})[0], 400)
        self.assertEqual(http(self.url + "/api/settings", {"tv_port": 8080})[0], 400)
        code, r = http(self.url + "/api/generate_passphrase", {})
        self.assertGreaterEqual(len(r["passphrase"]), 24)
        code, r = http(self.url + "/api/settings", {"tv_enabled": True, "tv_passphrase": r["passphrase"], "tv_port": 8095})
        self.assertEqual(code, 200, r)

    def test_security_guards(self):
        self.assertEqual(http(self.url + "/api/settings", headers={"Host": "evil.example.com"})[0], 403)
        self.assertEqual(http(self.url + "/api/bot/start", raw=b"{}", headers={"Content-Type": "text/plain"})[0], 403)
        self.assertEqual(http(self.url + "/api/bot/start", {}, headers={"Origin": "https://evil.example.com"})[0], 403)
        self.assertEqual(http(self.url + "/manual_trade", method="OPTIONS")[0], 405)
        host = self.url.split("//")[1]
        self.assertEqual(http(self.url + "/api/generate_passphrase", {}, headers={"Origin": f"http://{host}"})[0], 200)

    def test_bot_offline_responses(self):
        code, r = http(self.url + "/data")
        self.assertEqual(code, 503)
        self.assertTrue(r["offline"])
        code, hist = http(self.url + "/history")
        self.assertEqual(code, 200)
        self.assertEqual(hist[0]["p"], 180.5)          # falls back to the saved file
        self.assertEqual(http(self.url + "/manual_trade", {"direction": "bullish", "qty": 1})[0], 503)

    def test_start_without_keys_is_refused(self):
        code, r = http(self.url + "/api/bot/start", {})
        self.assertEqual(code, 400)
        self.assertIn("keys", r["error"])

    def test_pine_served(self):
        code, txt = http(self.url + "/api/pine")
        self.assertEqual(code, 200)
        self.assertIn("//@version=6", txt)


class BotProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bd = load_panel()

    def setUp(self):
        self.bd.save_settings(dict(self.bd.DEFAULT_SETTINGS, alpaca_api_key="PKSTUBKEY", alpaca_secret_key="s",
                                   signal_source="both"))
        self.bp = self.bd.BotProcess()

    def tearDown(self):
        self.bp.stop()

    def _mode(self, m):
        with open(STUB_MODE, "w") as f:
            f.write(m)

    def test_keys_and_settings_reach_the_bot(self):
        self._mode("run")
        self.bp.start()
        self.assertTrue(wait_for(lambda: any("stub bot started" in l for _, l in self.bp.lines)))
        line = next(l for _, l in self.bp.lines if "stub bot started" in l)
        self.assertIn("key=PKSTUBKEY", line)
        self.assertIn("url=https://paper-api.alpaca.markets", line)
        self.assertIn("src=both", line)
        self.assertTrue(self.bp.status()["running"])
        self.bp.stop()
        self.assertFalse(self.bp.status()["running"])
        self.assertTrue(wait_for(lambda: self.bp.last_exit is not None))
        time.sleep(6)                              # a stop must never auto-restart
        self.assertFalse(self.bp.is_running())

    def test_bad_keys_exit_does_not_restart(self):
        self._mode("3")
        self.bp.start()
        self.assertTrue(wait_for(lambda: self.bp.last_exit == 3))
        time.sleep(6)
        self.assertFalse(self.bp.is_running())
        self.assertEqual(self.bp.restarts, 0)
        self.assertIn("keys", self.bp.status()["last_exit_note"])

    def test_crash_auto_restarts(self):
        self._mode("1")
        self.bp.start()
        self.assertTrue(wait_for(lambda: self.bp.restarts >= 1, timeout=15))
        self._mode("run")
        self.assertTrue(wait_for(self.bp.is_running, timeout=10))

    def test_clean_exit_does_not_restart(self):
        self._mode("0")
        self.bp.start()
        self.assertTrue(wait_for(lambda: self.bp.last_exit == 0))
        time.sleep(6)
        self.assertFalse(self.bp.is_running())
        self.assertFalse(self.bp.desired)


# ═══════════════════════════════════════════════════════════════
# End to end: panel → bot server → simulated Alpaca
# ═══════════════════════════════════════════════════════════════

class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backtest
        cls.broker = backtest.Broker(100_000, 0.0)
        cls.broker.px = 180.0
        cwd = os.getcwd()
        os.chdir(TMP)
        import nvda_autotrader as bot
        os.chdir(cwd)
        cls.bot = bot
        bot.get_alpaca = lambda: (cls.broker, 100_000.0)
        bot.is_market_open = lambda: True
        fixed = datetime.now(ET).replace(hour=10, minute=0)
        bot.now_et = lambda: fixed                   # inside place_order()'s 09:30-15:55 wall
        bot.save_state = lambda: None
        cls.events = []
        bot.log = lambda msg, level="INFO": cls.events.append((level, msg))
        bot.state.update(last_price=180.0, last_atr=0.6, last_vwap=179.5, status="test")
        bot.start_dashboard_server()
        bot.start_tradingview_webhook()
        cls.bd = load_panel()
        cls.bd.save_settings(dict(cls.bd.DEFAULT_SETTINGS, bot_port=BOT_PORT))
        cls.srv = cls.bd.ThreadingHTTPServer(("127.0.0.1", 0), cls.bd.PanelHandler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        assert wait_for(lambda: http(f"http://127.0.0.1:{BOT_PORT}/data")[0] == 200, 10)
        assert wait_for(lambda: http(f"http://127.0.0.1:{TV_PORT}/")[0] == 200, 10)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        self.events.clear()
        for t in list(self.bot.get_active_trades()):
            self.bot.remove_active_trade(t)
        if self.broker.qty:
            self.broker.close_position("NVDA")

    def hook(self, payload, raw=None):
        return http(f"http://127.0.0.1:{TV_PORT}/tv_webhook", payload, raw=raw)

    def test_data_through_panel_proxy(self):
        code, d = http(self.url + "/data")
        self.assertEqual(code, 200)
        self.assertEqual(d["last_price"], 180.0)

    def test_bot_server_guards(self):
        b = f"http://127.0.0.1:{BOT_PORT}"
        self.assertEqual(http(b + "/data", headers={"Host": "evil.com"})[0], 403)
        self.assertEqual(http(b + "/manual_trade", raw=b'{"direction":"bullish","qty":1}', headers={"Content-Type": "text/plain"})[0], 403)
        self.assertEqual(http(b + "/manual_trade", method="OPTIONS")[0], 405)
        self.assertIn("standalone: true", http(b + "/")[1])

    def test_manual_long_bracket_then_close(self):
        code, r = http(self.url + "/manual_trade", {"direction": "bullish", "qty": 5, "use_atr": True, "atr_mult": 1, "managed": True})
        self.assertEqual(code, 200, r)
        self.assertEqual((r["stop"], r["target"]), (179.4, 180.9))      # 1×ATR stop, 1.5R target
        self.assertEqual(self.broker.qty, 5)
        legs = sorted(o.type for o in self.broker.orders)
        self.assertEqual(legs, ["limit", "stop"])                          # bracket legs on Alpaca
        code, r = http(self.url + "/close_manual_trade", {})
        self.assertEqual(code, 200, r)
        self.assertEqual(self.broker.qty, 0)
        self.assertEqual(self.bot.get_active_trades(), [])

    def test_manual_trade_rejects_wrong_side_levels(self):
        code, r = http(self.url + "/manual_trade", {"direction": "bearish", "qty": 5, "stop": 179.0, "target": 181.0})
        self.assertEqual(code, 400)
        self.assertIn("bracket", r["error"])
        self.assertEqual(self.broker.qty, 0)

    def test_webhook_rejects_bad_requests(self):
        self.assertEqual(self.hook({"passphrase": "wrong", "action": "buy"})[0], 403)
        self.assertEqual(self.hook(None, raw=b"not json")[0], 400)
        self.assertEqual(self.hook({"passphrase": PASS, "ticker": "AAPL", "action": "buy"})[0], 200)
        self.assertTrue(wait_for(lambda: any("AAPL" in m for _, m in self.events)))
        self.assertEqual(self.broker.qty, 0)
        self.assertEqual(self.hook({"passphrase": PASS, "action": "teleport"})[0], 200)
        self.assertTrue(wait_for(lambda: any("Unknown action" in m for _, m in self.events)))

    def test_webhook_short_size_duplicate_block_and_close(self):
        alert = {"passphrase": PASS, "ticker": "NASDAQ:NVDA", "action": "sell", "strategy": "SPIKE",
                 "stop": 181.5, "target": 177.75, "qty": 0}
        self.assertEqual(self.hook(alert)[0], 200)
        self.assertTrue(wait_for(lambda: self.broker.qty != 0))
        self.assertEqual(self.broker.qty, -27)            # risk sizing capped by max_position_pct (5% / $180)
        code, r = self.hook(alert)
        self.assertTrue(r.get("duplicate"))                # TradingView retry dropped
        self.hook({"passphrase": PASS, "action": "buy", "strategy": "VWAP"})
        self.assertTrue(wait_for(lambda: any("already open" in m for _, m in self.events)))
        self.assertEqual(self.broker.qty, -27)
        t = self.bot.get_active_trades()[0]
        self.assertEqual((t["source"], t["stop"], t["target"]), ("tradingview", 181.5, 177.75))
        self.hook({"passphrase": PASS, "action": "close", "strategy": "SPIKE"})
        self.assertTrue(wait_for(lambda: self.broker.qty == 0 and not self.bot.get_active_trades()))

    def test_webhook_without_levels_uses_atr(self):
        self.hook({"passphrase": PASS, "action": "buy", "strategy": "X"})
        self.assertTrue(wait_for(lambda: bool(self.bot.get_active_trades())))
        t = self.bot.get_active_trades()[0]
        self.assertAlmostEqual(t["stop"], 180.0 - 2.0 * 0.6, places=2)           # stop_atr_mult × ATR
        self.assertAlmostEqual(t["target"], 180.0 + 2.0 * 0.6 * 1.5, places=2)   # × risk_reward


# ═══════════════════════════════════════════════════════════════
# Backtester
# ═══════════════════════════════════════════════════════════════

class BrokerSimTests(unittest.TestCase):
    def setUp(self):
        import backtest
        self.bt = backtest
        self.b = backtest.Broker(100_000, 0.01)
        self.b.px = 100.0

    def test_bracket_long_stop_leg(self):
        self.b.submit_order("NVDA", 10, "buy", "market", order_class="bracket",
                            stop_loss={"stop_price": 99.0}, take_profit={"limit_price": 102.0})
        self.assertEqual(self.b.qty, 10)
        self.assertAlmostEqual(self.b.avg, 100.01)
        self.b.tick(99.5, 100.0)
        self.assertEqual(self.b.qty, 10)
        self.b.tick(98.8, 99.5)                    # crossed 99 → fills at the stop, not 98.80
        self.assertEqual(self.b.qty, 0)
        self.assertAlmostEqual(self.b.round_trips[0]["exit"], 98.99)
        self.assertEqual(self.b.orders, [])        # take-profit leg cancelled
        self.assertAlmostEqual(self.b.cash_pnl, (98.99 - 100.01) * 10)

    def test_gap_through_stop_fills_at_market(self):
        self.b.submit_order("NVDA", 10, "sell", "market")
        self.b.submit_order("NVDA", 10, "buy", "stop", stop_price="101")
        self.b.tick(103.0, 103.0)                  # opened above the stop (gap)
        self.assertAlmostEqual(self.b.round_trips[0]["exit"], 103.01)

    def test_limit_and_day_expiry(self):
        self.b.submit_order("NVDA", 5, "buy", "market", order_class="bracket",
                            stop_loss={"stop_price": 98.0}, take_profit={"limit_price": 101.0})
        self.b.expire_day_orders()
        self.assertEqual(self.b.orders, [])        # "day" legs gone overnight, position remains
        self.assertEqual(self.b.qty, 5)
        self.b.submit_order("NVDA", 5, "sell", "limit", limit_price="101", time_in_force="gtc")
        self.b.tick(101.2, 100.5)
        self.assertEqual(self.b.qty, 0)
        self.assertAlmostEqual(self.b.round_trips[0]["exit"], 101.0)

    def test_position_404_like_alpaca(self):
        with self.assertRaises(Exception) as cm:
            self.b.get_position("NVDA")
        self.assertEqual(cm.exception.status_code, 404)

    def test_bar_path(self):
        p = self.bt.bar_path(10, 12, 9, 11)        # green bar: O → L → H → C
        self.assertEqual(len(p), self.bt.TICKS_PER_BAR)
        self.assertAlmostEqual(min(p), 9)
        self.assertAlmostEqual(max(p), 12)
        self.assertEqual(p[-1], 11)
        self.assertLess(p.index(min(p)), p.index(max(p)))


class LoaderTests(unittest.TestCase):
    """Each data source's parser, fed that source's real response format (no network)."""
    @classmethod
    def setUpClass(cls):
        import backtest
        cls.bt = backtest
        cls.nv, cls.qq, _ = backtest.make_synthetic(3, seed=1)

    def check(self, nv):
        self.assertGreater(len(nv), 100)
        self.assertEqual(str(nv.index.tz), "America/New_York")
        t = nv.index.hour * 60 + nv.index.minute
        self.assertTrue(((t >= 570) & (t <= 955)).all())                 # regular hours only
        self.assertEqual(list(nv.columns), ["Open", "High", "Low", "Close", "Volume"])

    def test_csv(self):
        path = os.path.join(TMP, "nv.csv")
        df = self.nv.copy()
        df.index = df.index.tz_convert("UTC")
        df.rename(columns=str.lower).rename_axis("timestamp").to_csv(path)
        nv, qq, daily = self.bt.load_csv(path, None)
        self.check(nv)
        self.assertEqual(len(daily), len(set(nv.index.date)))

    def test_alpaca(self):
        def to_bars(df):
            u = df.index.tz_convert("UTC")
            return [{"t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": r.Open, "h": r.High, "l": r.Low,
                     "c": r.Close, "v": int(r.Volume)} for ts, r in zip(u, df.itertuples())]
        nvb = to_bars(self.nv)
        pages = {}

        def fake_get(url, headers=None, params=None, timeout=None):
            self.assertEqual(headers["APCA-API-KEY-ID"], "PKTEST")
            self.assertEqual(params["feed"], "iex")
            sym = url.split("/stocks/")[1].split("/")[0]
            bars = nvb if sym == "NVDA" else to_bars(self.qq)
            if params["timeframe"] == "1Day":
                bars = bars[::78]
            half = len(bars) // 2                                        # force pagination
            tok = params.get("page_token")
            body = {"bars": bars[half:], "next_page_token": None} if tok else \
                   {"bars": bars[:half], "next_page_token": "p2"}
            pages[sym] = pages.get(sym, 0) + 1
            return types.SimpleNamespace(json=lambda: body, raise_for_status=lambda: None)
        import requests
        orig = requests.get
        requests.get = fake_get
        try:
            nv, qq, daily = self.bt.load_alpaca("2026-01-01", "2026-12-31", 6)
        finally:
            requests.get = orig
        self.check(nv)
        self.assertEqual(len(nv), len(self.nv))                          # both pages kept
        self.assertGreaterEqual(pages["NVDA"], 4)

    def test_yfinance(self):
        import yfinance as yf
        nv_y, qq_y = self.nv.copy(), self.qq.copy()

        class T:
            def __init__(s, sym): s.sym = sym
            def history(s, period=None, interval=None, auto_adjust=None):
                if interval == "1d":
                    d = self.bt._daily_from_intraday(nv_y)
                    d.index = d.index.tz_localize("America/New_York")
                    return d
                return nv_y if s.sym == "NVDA" else qq_y
        orig = yf.Ticker
        yf.Ticker = T
        try:
            nv, qq, daily = self.bt.load_yfinance()
        finally:
            yf.Ticker = orig
        self.check(nv)
        self.assertIsNone(daily.index.tz)


class BacktestRunTest(unittest.TestCase):
    def test_replay_through_real_bot_code(self):
        out = os.path.join(TMP, "bt")
        r = subprocess.run([sys.executable, os.path.join(HERE, "backtest.py"), "--source", "synthetic",
                            "--synthetic-days", "25", "--seed", "11", "--quiet", "--out", out],
                           capture_output=True, text=True, timeout=900, cwd=TMP)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        with open(os.path.join(out, "summary.txt"), encoding="utf-8") as f:
            summary = f.read()
        self.assertIn("PASS  every bot-closed trade matches", summary)
        self.assertNotIn("FAIL", summary, summary)
        self.assertIn("Bot ERROR/CRITICAL log lines during the run: 0", summary)
        self.assertFalse(os.path.exists(os.path.join(HERE, "trade_logs", "session_state.json"))
                         and os.path.getmtime(os.path.join(HERE, "trade_logs", "session_state.json")) > time.time() - 600,
                         "backtest must not write into the project's trade_logs")


if __name__ == "__main__":
    unittest.main(verbosity=2)
