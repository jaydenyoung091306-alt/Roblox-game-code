"""Helper for test_all.ClaudeTests: replays synthetic bars through the bot with
Claude switched on but a FAKE reviewer (no API call, no cost), then prints the
review store and scoreboard. Usage: python claude_e2e_helper.py <project dir> <out dir>"""
import sys, os, itertools, tempfile
sys.path.insert(0, sys.argv[1]); out = sys.argv[2]
import backtest
args = type("A", (), dict(equity=100000, slippage=0.01, quiet=True, set=None, signal_source=None,
                          warmup=6, start=None, end=None, out=out))()
nv, qq, daily = backtest.make_synthetic(14, seed=11)
calls = []
orig_load = backtest.load_bot
def load_bot(feed, broker, quiet):
    bot, events = orig_load(feed, broker, quiet)
    bot.CLAUDE_ENABLED = True                      # switch on, but with a fake reviewer — no API call
    flip = itertools.cycle(["take", "skip", "take"])
    def fake_review(snap, client=None):
        calls.append(snap)
        assert set(snap) >= {"setup", "context", "bars_5m_today"}
        return {"decision": next(flip), "confidence": 3, "reason": "test", "key_risks": [],
                "model": "fake", "latency_s": 0, "input_tokens": 3000, "output_tokens": 2000, "cost_usd": 0.052}
    bot.claude_review = fake_review
    return bot, events
backtest.load_bot = load_bot
work = tempfile.mkdtemp(); os.chdir(work)
bot, broker, closed, eq, events, first = backtest.run(nv, qq, daily, args)
import time; time.sleep(1)
recs = bot.claude_reviews_load()
print("bot trades closed:", len(closed), "| Claude calls:", len(calls), "| review records:", len(recs))
done = [r for r in recs if r.get("status") == "done"]
with_outcome = [r for r in done if r.get("pnl") is not None]
print("reviews done:", len(done), "| with real outcome:", len(with_outcome),
      "| errors:", sum(r.get("status") == "error" for r in recs))
by_id = {t["order_id"]: t for t in closed}
mismatch = [r for r in with_outcome if abs(by_id[r["order_id"]]["pnl"] - r["pnl"]) > 0.01]
print("pnl matches the bot's own trade record:", not mismatch)
st = bot.claude_stats(recs)
for k in ("bot_alone", "with_claude", "claude_skipped"):
    print(f"  {k:15s}", st[k])
print("  accuracy", st["claude_accuracy"], "| cost $", st["cost_usd"])
print("  verdict:", st["verdict"])
s0 = calls[0]["setup"]; c0 = calls[0]["context"]
print("sample snapshot:", s0["strategy"], s0["direction"], s0["entry"], "| ctx keys:", len(c0), "| bars:", calls[0]["bars_5m_today"].count("\n"))
