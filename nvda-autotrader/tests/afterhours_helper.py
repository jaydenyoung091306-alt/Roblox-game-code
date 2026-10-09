"""Helper for test_all.AfterHoursTests: runs the REAL run_bot() main loop on a
simulated clock from 15:58 ET through the night to 10:00 ET the next day,
against a simulated broker, and prints what happened as JSON.

    python afterhours_helper.py <project dir> <managed|standalone> <open|flat>
"""
import contextlib
import io
import json
import os
import socket
import sys
import tempfile
import types
from datetime import datetime
from zoneinfo import ZoneInfo

proj, mode, position = sys.argv[1], sys.argv[2], sys.argv[3]
sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
os.environ.update(ALPACA_API_KEY="x", ALPACA_SECRET_KEY="y", NVDA_TV_ENABLED="0", NVDA_CLAUDE_ENABLED="0",
                  NVDA_BOT_PORT=str(port), NVDA_MANAGED="1" if mode == "managed" else "0")
os.chdir(tempfile.mkdtemp())
sys.path.insert(0, proj)
import backtest  # noqa: E402  (Clock, SimDatetime, Broker)
with contextlib.redirect_stdout(io.StringIO()):
    import build_dashboard as bot  # noqa: E402

ET = ZoneInfo("America/New_York")
START = datetime(2026, 10, 8, 15, 58, tzinfo=ET)      # Thursday
END = datetime(2026, 10, 9, 10, 0, tzinfo=ET)         # Friday morning
backtest.Clock.now = START
broker = backtest.Broker(100_000, 0.0)
broker.px = 180.0

out = {"max_heartbeat_gap_s": 0, "summary_saves_evening": 0, "scans_next_morning": 0,
       "monitor_calls_night": 0, "monitor_calls_morning": 0, "exit": None, "errors": [],
       "closed_at_reset": False}


def fake_sleep(sec):
    hb = bot.state.get("_last_heartbeat") or START.timestamp()
    # the watchdog sees the heartbeat's age at any moment during this sleep
    out["max_heartbeat_gap_s"] = max(out["max_heartbeat_gap_s"],
                                     backtest.Clock.now.timestamp() + sec - hb)
    backtest.Clock.now = datetime.fromtimestamp(backtest.Clock.now.timestamp() + sec, ET)
    if backtest.Clock.now >= END:
        raise KeyboardInterrupt


def phase():
    n = backtest.Clock.now
    if n.date() == START.date() and n.hour >= 16:
        return "evening"
    if n.date() == END.date() and (n.hour, n.minute) >= (9, 30):
        return "morning"
    return "night"


def count(key_by_phase):
    def f(*a, **k):
        p = phase()
        k2 = key_by_phase.get(p)
        if k2:
            out[k2] += 1
    return f


bot.datetime = backtest.SimDatetime
bot.time = types.SimpleNamespace(sleep=fake_sleep, time=lambda: backtest.Clock.now.timestamp())
bot.get_alpaca = lambda: (broker, 100_000.0)
bot._watchdog_loop = lambda: None                 # gaps are measured above instead
bot.shutil = types.SimpleNamespace(copy2=lambda *a, **k: None)
bot.save_state = lambda: None
bot.save_daily_summary = count({"evening": "summary_saves_evening"})
bot.check_for_entry = count({"morning": "scans_next_morning"})
bot.monitor_trade = count({"night": "monitor_calls_night", "morning": "monitor_calls_morning"})
bot._fetch_alpaca = lambda *a, **k: None
bot.fetch_candles = lambda *a, **k: None
bot.print = lambda *a, **k: None


def log(msg, level="INFO"):
    if level in ("ERROR", "CRITICAL") or msg.startswith("Unexpected error"):
        out["errors"].append(msg[:200])
    if "closing any open positions" in msg:
        out["closed_at_reset"] = True
bot.log = log

if position == "open":
    t = {"order_id": "o1", "strategy": "SWING-6M", "fvg_type": "bearish", "entry": 180.0, "stop": 182.0,
         "target": 175.0, "qty": 10,
         # bot.datetime is the simulated-clock class; build with it so the bot's
         # isinstance(opened_at, datetime) exemption check sees a real datetime
         "opened_at": bot.datetime(2026, 10, 8, 14, 30, tzinfo=ET)}
    bot.add_active_trade(t)

try:
    bot.run_bot()
    out["exit"] = "returned"
except SystemExit as e:
    out["exit"] = f"sys.exit({e.code}) at {backtest.Clock.now:%Y-%m-%d %H:%M} ET"
print(json.dumps(out))
