# NVDA AutoTrader (v4.98)

An algorithmic paper-trading bot for NVDA on Alpaca, with a browser control panel and a TradingView port.

| File | What it is |
|---|---|
| `build_dashboard.py` | **The app.** Control panel + dashboard. Starts/stops the bot and holds your keys. |
| `nvda_autotrader.py` | The trading bot (strategies, orders, exits). The panel runs it for you. |
| `nvda_strategy.pine` | TradingView Pine Script version of the strategies. |
| `nvda_settings.json` | Created by the Settings tab. Holds your keys, so **never commit or share it** (it's git-ignored). |

## Quick start

```bash
pip install alpaca-trade-api yfinance pandas numpy requests tzlocal
python build_dashboard.py
```

Your browser opens **http://127.0.0.1:8080**. Then:

1. **Settings** → pick *Paper trading*, paste your Alpaca **API key ID** and **secret key** (from app.alpaca.markets → API Keys), click **Test connection**, then **Save keys**.
2. Click **▶ Start Bot** (top right). Watch it boot in the **Console** tab.

When your keys change, paste the new ones in Settings, save, and click **Restart now**. You never edit code for keys.

### Run it every morning (Windows Task Scheduler)

Change your existing 8:20 AM task to run this instead of `nvda_autotrader.py`:

```
python build_dashboard.py --autostart --no-browser
```

The panel starts, launches the bot with your saved keys, and restarts it if it crashes (pauses after 5 crashes in 10 minutes). Open http://127.0.0.1:8080 any time to check on it.

> Only run one of the two. If an old task still starts `nvda_autotrader.py` directly, the dashboard says *"A bot started outside this panel is running"*.

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
5. Create Alert → Condition: *NVDA AutoTrader v4.98* → **Order fills only** → Webhook URL `https://<your-tunnel>/tv_webhook` → Message `{{strategy.order.alert_message}}`.

Every alert goes through the same checks as a dashboard trade: market hours, a fresh live price, stop/target on the correct sides of it, and size capped at `max_position_pct`. The bot holds one NVDA position at a time, so an entry alert is skipped while anything is open. Exact repeats within 30 s (TradingView retries) are dropped. Results show in the Console.

Alert JSON, if you write your own alerts:

```json
{"passphrase": "…", "ticker": "NVDA", "action": "buy", "strategy": "MY-SETUP", "stop": 178.40, "target": 182.10, "qty": 0}
```

`action` is `buy`, `sell` or `close`. `stop`/`target` are optional (default: 2×ATR stop, 1.5R target). `qty` 0 lets the bot size it from your equity.

## Security notes

- The panel and the bot only listen on `127.0.0.1`, so nothing else on your network can reach them. They refuse cross-site requests, so a web page you visit can't place orders through them. (Before v4.98 the bot's dashboard accepted trade requests from any device or website.)
- Your secret key is stored only in `nvda_settings.json` (owner-only permissions on macOS/Linux) and is never sent back to the browser.
- Anyone who has your tunnel URL **and** passphrase can place trades. Use the generated passphrase and stop the tunnel when you're not using it.
- **Shorts have no stop on Alpaca's side.** The bot watches them itself, so if the bot is stopped or offline, an open short is unprotected. The Stop button warns you about this.
