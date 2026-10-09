# NVDA AutoTrader (v5.00)

An algorithmic paper-trading bot for NVDA on Alpaca, with a browser control panel and a TradingView port.

| File | What it is |
|---|---|
| `Start NVDA AutoTrader.bat` | **Double-click this to start** (Windows). |
| `build_dashboard.py` | **Everything in one file:** the trading bot, the control panel and the dashboard. The only file you run. |
| `nvda_strategy.pine` | TradingView Pine Script version of the strategies (separate because TradingView only runs Pine). |
| `backtest.py` | Backtester: replays historical bars through the bot's real code. |
| `tests/` | Automated tests (no network, no real orders). |
| `nvda_settings.json` | Created by the Settings tab. Holds your keys, so **never commit or share it** (it's git-ignored). |

## Quick start

**Windows: double-click `Start NVDA AutoTrader.bat`.** It finds Python, installs the libraries on first run, and opens the dashboard. Keep its black window open while you trade; close it to quit. (Double-clicking `build_dashboard.py` itself just opens it as a text file — that's normal for Python files.)

No Python yet? Install it from https://www.python.org/downloads/ and tick **"Add python.exe to PATH"** on the first installer screen.

Or from a command prompt in this folder:

```bash
python -m pip install --only-binary=:all: yfinance pandas numpy requests tzlocal msgpack websockets websocket-client aiohttp pyyaml deprecation python-dateutil
python -m pip install --no-deps alpaca-trade-api==3.2.0
python build_dashboard.py
```

Why two install lines: `alpaca-trade-api` pins old `msgpack`/`PyYAML` versions that have no prebuilt download for current Python, so a plain `pip install alpaca-trade-api` fails with *"Failed building wheel"*. Installing its helpers first (current, prebuilt) and then it with `--no-deps` avoids compiling anything.

Your browser opens **http://127.0.0.1:8080**. Then:

1. **Settings** → pick *Paper trading*, paste your Alpaca **API key ID** and **secret key** (from app.alpaca.markets → API Keys), click **Test connection**, then **Save keys**.
2. Click **▶ Start Bot** (top right). Watch it boot in the **Console** tab.

When your keys change, paste the new ones in Settings, save, and click **Restart now**. You never edit code for keys.

**How the one file works:** `python build_dashboard.py` runs the dashboard. **Start Bot** launches the same file a second time with `--run-bot`, so the bot runs as its own process. That way Stop can always end it, and if the bot freezes, its watchdog restarts it without taking the dashboard down. You can also run the bot alone with `python build_dashboard.py --run-bot` (it serves a bot-only dashboard on http://127.0.0.1:8080).

### Run it every morning (Windows Task Scheduler)

Change your existing 8:20 AM task (it used to run `nvda_autotrader.py`, which no longer exists) to:

```
python build_dashboard.py --autostart --no-browser
```

The panel starts, launches the bot with your saved keys, and restarts it if it crashes (pauses after 5 crashes in 10 minutes). Open http://127.0.0.1:8080 any time to check on it.

> If an old copy of `nvda_autotrader.py` is still being started somewhere, delete it. The dashboard says *"A bot started outside this panel is running"* when it detects one.

## What's in the dashboard

- **Overview**: price chart (1H / Today / 5D / 1M / 6M) with VWAP and your trade's entry/stop/target lines, equity and P&L, ATR, trend/QQQ/multi-timeframe bias, kill-zone timeline, active trade with a stop→target progress bar, bot status, activity feed.
- **Trades**: open positions and the last close. **+ Manual trade** places a real Alpaca order with ATR-based or manual stop/target, a live price, and a risk/reward preview.
- **Signals**: every FVG/VWAP setup scored today.
- **Console**: everything the bot prints, filterable (also saved to `bot_console.log`).
- **Settings**: keys, Paper/Live (live needs you to type `LIVE`), where trades come from, auto-restart.
- **TradingView**: webhook setup and the Pine Script with Copy/Download buttons.

Light/dark toggle is top right. It also works on a phone-sized window.

## TradingView

TradingView can't run Python, and its strategies can't send orders to a broker by themselves. There are two parts:

### 1. Forward-test on TradingView (free)

Open NVDA on the **5-minute** chart → Pine Editor → paste `nvda_strategy.pine` → Save → *Add to chart*. The **Strategy Tester** shows TradingView's simulated fills on live bars. That's paper trading on TradingView itself.

Ported: SPIKE momentum, SPIKE 5-day extreme, VWAP bounce, FVG retrace, SWING-6M (SWING-3M off by default, like the bot), best-R:R selection, kill zones, risk sizing, end-of-day flatten, and SWING-6M overnight hold. **Not** ported: RANGE, multi-timeframe score adjustments, trailing stop / time stops. The header of the `.pine` file lists the differences.

### 2. TradingView alerts → Alpaca paper orders (needs a paid TradingView plan for webhooks)

1. Dashboard → **TradingView** tab → tick *Accept TradingView alerts* → **Generate** a passphrase → **Save**.
2. Settings → *Where trades come from* → **TradingView alerts** (or **Both**) → **Restart now**.
3. Expose the receiver: `ngrok http 8090` (or `cloudflared tunnel --url http://127.0.0.1:8090`). TradingView only calls public HTTPS URLs.
4. In the Pine script's inputs, paste the same passphrase.
5. Create Alert → Condition: *NVDA AutoTrader v5.00* → **Order fills only** → Webhook URL `https://<your-tunnel>/tv_webhook` → Message `{{strategy.order.alert_message}}`.

Every alert goes through the same checks as a dashboard trade: market hours, a fresh live price, stop/target on the correct sides of it, and size capped at `max_position_pct`. The bot holds one NVDA position at a time, so an entry alert is skipped while anything is open. Exact repeats within 30 s (TradingView retries) are dropped. Results show in the Console.

Alert JSON, if you write your own alerts:

```json
{"passphrase": "…", "ticker": "NVDA", "action": "buy", "strategy": "MY-SETUP", "stop": 178.40, "target": 182.10, "qty": 0}
```

`action` is `buy`, `sell` or `close`. `stop`/`target` are optional (default: 2×ATR stop, 1.5R target). `qty` 0 lets the bot size it from your equity.

## Backtesting

`backtest.py` replays historical 5-minute bars through the bot's **actual code**. The real `check_for_entry()`, `_place_trade()` and exit monitor run unchanged. Only the clock, the data feed and Alpaca are simulated. So the results include the bot's breakeven lock, trailing stop, FVG time stop, near-target lock, EOD close and SWING-6M overnight holds, exactly as coded.

```bash
python backtest.py --source alpaca --start 2026-04-01 --end 2026-09-30   # uses your saved keys, IEX feed (what the bot trades on)
python backtest.py --source yfinance                                     # last ~55 days, no keys needed
python backtest.py --source csv --csv nvda_5m.csv --qqq-csv qqq_5m.csv
python backtest.py --source alpaca --set '{"risk_reward": 2.0}'          # try a CONFIG change
```

It prints per-strategy stats (trades, win %, total and average $, average R, profit factor), net P&L, max drawdown and exit routes. It writes `backtest_results/trades.csv`, `equity.csv` and `summary.txt`. Every run also checks itself: P&L reconciles with the simulated broker, every bot trade matches a broker fill, entries happen only in kill zones, only SWING-6M is held overnight, position size stays within the cap, and only one position is open at a time. The backtest never touches your real `trade_logs/` or price history.

How exits are simulated: the bot polls every 15 s, so each 5-minute bar is replayed as 20 ticks along open → low → high → close (open → high → low → close on red bars). Market orders fill at the tick ± `--slippage` (default $0.01/share), and stops fill at the stop price unless price gapped through it. The real path inside a bar is unknown, so exits that depend on it are estimates.

`--source synthetic` runs on made-up random prices. It only proves the machinery works; its numbers mean nothing.

## Tests

```bash
python -m unittest discover -s tests -v
```

29 tests, about 50 s, no network and no real orders. They cover the control panel API and security guards, Start/Stop and auto-restart, the real bot booting from the same file, keys reaching the bot, manual trades and every TradingView webhook rule (through a simulated Alpaca account), the backtester's fill logic and data loaders, and a full backtest replay.

## Security notes

- The panel and the bot only listen on `127.0.0.1`, so nothing else on your network can reach them. They refuse cross-site requests, so a web page you visit can't place orders through them. (Before v4.98 the bot's dashboard accepted trade requests from any device or website.)
- Your secret key is stored only in `nvda_settings.json` (owner-only permissions on macOS/Linux) and is never sent back to the browser.
- Anyone who has your tunnel URL **and** passphrase can place trades. Use the generated passphrase and stop the tunnel when you're not using it.
- **Shorts have no stop on Alpaca's side.** The bot watches them itself, so if the bot is stopped or offline, an open short is unprotected. The Stop button warns you about this.
