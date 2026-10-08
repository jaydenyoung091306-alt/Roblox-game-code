"""
NVDA DUAL-STRATEGY AUTO TRADER v4.98
======================================================

CLAUDE AI CONTEXT — READ THIS FIRST IF STARTING A NEW CHAT
============================================================
This is a two-file algorithmic paper trading system for NVDA stock.
The companion file is build_dashboard.py — always keep versions in sync.

FILES (all in the same project folder):
  nvda_autotrader.py        — This file (current version: v4.98)
  build_dashboard.py        — Control panel + dashboard UI (v4.98). Starts/stops
                              this bot and holds the API keys.
  nvda_strategy.pine        — TradingView Pine Script port of the strategies
  nvda_settings.json        — Keys + settings saved by the control panel
                              (local only — never commit or share it)
  nvda_price_history.json   — Rolling 2000-point price history {"t":ts,"p":price}
  nvda_bot_state.json       — Persisted session state
  trade_logs/               — Daily .txt summaries + master_trade_log.csv

HOW TO RUN (v4.98):
  Start:   cd %USERPROFILE%\\Downloads\\NVDA && python build_dashboard.py
           → opens http://127.0.0.1:8080. Enter keys in Settings, click Start Bot.
  Headless (Task Scheduler at 8:20 AM): python build_dashboard.py --autostart --no-browser
  This file can still be run on its own (python nvda_autotrader.py) — it reads
  the keys saved by the control panel and serves the same UI on 127.0.0.1:8080.
  After 4 PM ET: bot stays alive serving dashboard until midnight (no trading).

BROKER & DATA:
  Alpaca paper trading. Keys come from the control panel (env vars or
  nvda_settings.json) — see the API KEYS section below. Paper/live is a
  Settings toggle, not a code edit.
  Data: Alpaca IEX free feed. YFinance fallback for QQQ/MTF.
  Live switch: change ALPACA_BASE_URL to api.alpaca.markets + live keys.

FIVE STRATEGIES (all run in parallel):
  1. FVG Retrace     — Fair Value Gap, waits for retrace into gap zone
  2. VWAP Bounce     — Price vs VWAP ±1×ATR bands, enters on bounce
  3. Spike Reversal  — Sharp spike ≥2.5×ATR + ≥1.5×ATR from VWAP + rejection candle
  4. Range Extreme   — Price at 5-day high/low + reversal candle (added v4.17)
  5. Swing Reversion — Price near 3mo/6mo high/low + confirmed trend turn (added v4.84,
                        SWING-3M/SWING-6M variants, fades stalled multi-month extremes)
  FVG vs VWAP chosen at kill zone open via scoring. Spike+RangeExtreme always run.
  Spike checked first; Range Extreme is fallback if no spike fires. All five compete
  every scan via "parallel strategy evaluation" (best R:R wins) in check_for_entry().

KILL ZONES (ET): 09:30-11:00 | 12:00-13:00 | 14:00-15:55

MULTI-TRADE ARCHITECTURE:
  state["active_trades"]  — list of ALL open trades (bot + manual)
  state["active_trade"]   — legacy alias → first non-MANUAL bot trade or None
  get_bot_trade()         — returns first non-MANUAL bot trade or None
  add_active_trade(t)     — appends + syncs alias
  remove_active_trade(t)  — removes + syncs alias
  Manual trades fire real Alpaca orders.
  Longs: bracket order (stop_loss + take_profit legs).
  Shorts: plain market sell — IEX free tier doesn't support short brackets.
  Bot monitors shorts via price polling in _monitor_bot_trade().

ORDER / EXIT LOGIC:
  _monitor_bot_trade()    — monitors single Alpaca bot trade, returns True if closed
  _monitor_manual_trade() — monitors manual trade via Alpaca position check
  monitor_trade()         — loops all active trades, calls appropriate helper
  Fixed target check added in _monitor_bot_trade for active positions (v4.16 bug fix)
  5-min cooldown after any spike/extreme attempt (state["_spike_cooldown_until"])

DASHBOARD (build_dashboard.py):
  The control panel (build_dashboard.py) serves the UI on 127.0.0.1:8080 and
  proxies to this bot's server on 127.0.0.1:8081 (8080 when run standalone).
  IMPORTANT: bind to '127.0.0.1' (not 'localhost', Windows IPv6/IPv4 issue;
  not '' — that exposes order placement to the whole network). Open the
  dashboard as http://127.0.0.1:8080.
  ATR multiplier selector: 0.5× 1× 1.5× 2× 2.5× with live preview.
  Manual trade modal sends atr_mult to bot; bot uses it in calculation.
  After editing build_dashboard.py, run: python build_dashboard.py

IMPORTANT RULES FOR CLAUDE:
  - ALWAYS bump VERSION in both files when making any change
  - ALWAYS syntax-check before presenting: python3 -c "import ast; ast.parse(open('f').read())"
  - HTTP servers bind to '127.0.0.1' (never '' or 'localhost'), no CORS headers
  - Never put API keys in code — they live in nvda_settings.json via the dashboard
  - Short bracket orders are NOT supported on IEX free tier — use plain market sell
  - _check_spike_reversal and _check_range_extreme both return:
    ("bullish"/"bearish", entry, stop, target, risk, reason) or None
  - Manual ATR calc: stop_dist = atr_mult * ATR, tgt_dist = stop_dist * CONFIG["risk_reward"]
  - PDT protection: pdt_protection=False for paper, True for live sub-$25k
  - price_history format: list of {"t": iso_timestamp, "p": float}

ACCOUNT (as of 2026-06-04):
  Starting equity (May 26): $100,366.41
  Current equity:           $100,637.63
  Paper trading — Alpaca paper account

KEY CONFIG (see CONFIG dict below):
  risk_reward:            1.5   target = 1.5× stop distance
  stop_atr_mult:          2.0   bot stop = 2× ATR
  pdt_protection:         False set True for live sub-$25k
  spike_atr_mult:         2.5   spike must be ≥2.5×ATR
  spike_vwap_mult:        1.5   price must be ≥1.5×ATR from VWAP
  spike_lookback:         3     candles to measure spike over
  extreme_lookback_days:  5     days back for range high/low
  extreme_proximity_mult: 0.5   within 0.5×ATR of extreme to trigger

CHANGELOG:
  v4.98 — Control panel, keys out of the code, TradingView, dashboard lockdown:
             1) build_dashboard.py is now the app: `python build_dashboard.py`
                serves a redesigned dashboard on 127.0.0.1:8080 with Start /
                Stop / auto-restart for this bot, a live console, and a
                Settings tab for Alpaca keys + paper/live. Keys are saved to
                nvda_settings.json and handed to this process as environment
                variables; ALPACA_API_KEY etc. are no longer edited in code.
             2) Security: the dashboard server bound to every interface and
                sent "Access-Control-Allow-Origin: *" with unauthenticated
                POST /manual_trade — any device on the wifi, or any website
                open in the browser, could place orders. Now loopback-only
                by default (NVDA_BOT_HOST), no CORS, Host checked against
                DNS rebinding, and POSTs must be same-origin JSON.
             3) TradingView: new webhook receiver (start_tradingview_webhook)
                turns TradingView alert JSON into Alpaca orders through the
                same checks as a dashboard manual trade. Passphrase-protected,
                off unless enabled in Settings. SIGNAL_SOURCE picks whether
                trades come from the bot's strategies, TradingView, or both.
                nvda_strategy.pine ports the strategies to Pine Script.
             4) Refactor: /manual_trade and /close_manual_trade logic moved
                into open_manual_trade() / close_manual_trade() (shared with
                the webhook), serialized by _TRADE_ACTION_LOCK because the
                dashboard server is now ThreadingHTTPServer — a slow request
                (see v4.83) no longer freezes every other dashboard poll.
             5) Exit codes: missing keys → 2, Alpaca connect failure → 3 (was
                0) so the control panel can tell "fix your keys" apart from a
                crash worth auto-restarting.
  v4.97 — Three compounding bugs, all surfaced by the v4.96 watchdog doing
           its job and force-restarting mid-SWING-6M-hold on 2026-10-02,
           which then exposed each of these in turn (caught live by the
           user noticing an open position mislabeled "RESTORED" instead of
           "SWING-6M" the next morning, with a price gap that obviously
           looked like a swing trade):
             1) reset_daily_state()'s "new day detected — closing any open
                positions" logic predates SWING-6M's overnight-carry (v4.94)
                and unconditionally tried to close ANY open trade at every
                midnight crossing — including a legitimately-still-open,
                under-its-hold-cap SWING-6M position. When the market was
                closed the order just sat pending rather than failing, which
                is almost certainly the source of the repeated "a closing
                market order is already pending" messages — a stale order
                from a prior midnight sitting in Alpaca's queue, capable of
                filling unexpectedly at a LATER market open independent of
                the trade's real stop/target. Fixed: this block now skips
                the close attempt entirely when every currently-active trade
                is an exempt, under-cap SWING-6M position.
             2) save_daily_summary()'s CSV row writer used
                t.get("outcome", "OPEN") — dict.get()'s default only applies
                when the key is MISSING, not when it's explicitly None, and
                an open trade has "outcome": None explicitly set. This wrote
                a blank CSV cell instead of the literal string "OPEN",
                silently breaking _find_open_trade_in_recent_logs()'s
                recovery lookup (which searches for outcome == "OPEN") for
                exactly the trades it exists to rescue — a still-open
                position carried past an EOD summary. Same fix applied to
                the dashboard's _fmt_trade() for consistency. Together with
                bug #1's dangling order risk, this is what let the watchdog
                force-restart turn into the real incident: the ALPACA SYNC
                reconnect found a real position Alpaca but couldn't recover
                its SWING-6M identity, fell back to a generic "RESTORED"
                label with crude guessed stop/target, and from that point
                on bug #1 kept trying (and failing, all weekend) to close a
                trade that should have been left alone.
             3) monitor_trade()'s status-line builder used
                t.get('pnl', 0) — same None-vs-missing gotcha — producing
                "unsupported format string passed to NoneType.__format__"
                every single poll cycle a RESTORED/reconnected trade (pnl
                still None) was being monitored. Harmless on its own (caught
                by main()'s outer handler, retried in 60s) but added
                constant log noise and wasted cycles on top of bug #1's
                futile close attempts.
           Net effect before this fix: a real, profitable SWING-6M position
           could get incorrectly force-closed the next time the market
           opened, for reasons entirely unrelated to its actual stop/target.
  v4.96 — Added a main-loop watchdog. Confirmed live 2026-10-02: the main
           loop froze silently for ~60 minutes immediately after closing a
           trade — almost certainly an unbounded network call inside the
           resumed check_for_entry() scan, given that week's repeated SSL/
           DNS/timeout errors. The dashboard's HTTP server runs in its own
           thread and kept responding the whole time with stale last-known
           state, which is exactly what made it look deceptively fine —
           nothing in bot_console.log hinted anything was wrong, and the
           only visible symptom was the price chart not accumulating new
           points (caught by the user noticing that, not by any alert).
           Fix: state["_last_heartbeat"] is now updated at the top of every
           main-loop iteration; a separate daemon thread (_watchdog_loop())
           checks it every 10s, and if it's gone stale past
           CONFIG["watchdog_timeout_sec"] (300s — comfortably longer than
           any single iteration's worst-case retry/backoff math), force-
           exits the whole process via os._exit() so Task Scheduler's
           restart (3 attempts, 1 min apart) brings it back clean instead
           of sitting frozen indefinitely. os._exit() rather than sys.exit()
           deliberately — sys.exit() would only terminate the watchdog's own
           thread, leaving the actually-hung main thread untouched.
  v4.95 — Two changes, both per explicit user request after watching a live
           SWING-3M trade block the bot from evaluating anything else for
           1.5+ hours:
             1) SWING-3M same-day trading disabled — shadow-only, not a
                full kill. Still detected and logged every scan (research
                data keeps flowing) via new CONFIG["swing_3m_trading_enabled"]
                = False, but never added to check_for_entry()'s candidates,
                so it can never win the R:R competition or actually open a
                position. Chosen over a full kill because it costs nothing
                extra: the opportunity-cost problem comes from a REAL
                position consuming the bot's one trade slot (which stops
                check_for_entry() from running at all — confirmed live,
                zero candidate scans happen while any bot trade is open),
                not from evaluation itself. SWING-6M and every other
                strategy are unaffected — separate from the master
                swing_trading_enabled switch.
             2) Fixed a real bug found while closing a stale SWING-3M
                position to test this: the generic "position found gone on
                Alpaca" reconciliation path in _monitor_bot_trade() (used
                whenever a position is closed externally — e.g. this
                session's own manual close_all() calls, or the "new day"
                safety check) logged the trade closed and P&L'd correctly
                via _finalize_trade_close(), but never called
                remove_active_trade() — unlike every other close path in
                this file (EOD close, FVG time-stop). The trade stayed
                stuck in state["active_trades"] forever, looking like a
                phantom still-open position. This was mistaken for network
                flakiness and hand-patched via session_state.json surgery
                twice this week (2026-09-29, 2026-09-30) before the actual
                root cause was found here.
  v4.94 — SWING-6M is now exempted from the same-day EOD force-close that
           every other strategy still uses. Per explicit user request,
           following a backtest showing SWING-6M's real target (2.5R off a
           6-month price extreme, an inherently multi-day thesis) was only
           reached ~11% of the time under same-day forcing vs ~30% when
           actually allowed to resolve — total R across the 2020-2026
           backtest window flips from -16.21 to +31.50 uncapped. Bounded
           by new CONFIG["swing_max_hold_days"] (10) so it can't become an
           unbounded hold — a cap sweep (see validate_swing6m_overnight.py)
           showed 10 trading days captures nearly all the benefit (+29.03
           total R) vs the uncapped 35-day tail, with only ~2% of trades
           ever actually hitting the cap. _monitor_bot_trade() now pauses
           entirely (no stop/target check) outside market hours for an
           exempt SWING-6M trade rather than checking stale off-hours
           price data — that's exactly the class of bug the v4.88 EOD fix
           eliminated, so it must not be reintroduced here. SWING-3M and
           every other strategy's EOD behavior is completely unchanged —
           user explicitly compared SWING-3M's and SWING-6M's numbers
           (with and without same-day forcing) before choosing 6M only.
           Dashboard now shows a "(Nd open)" badge and a dated timestamp
           instead of a bare HH:MM for any trade held past today.
  v4.93 — Startup Alpaca connection no longer gives up after one failed
           attempt. Prompted by repeated mornings where Task Scheduler's
           8:20 AM launch hit the machine's wifi not being connected yet —
           the bot printed "Could not connect to Alpaca" and exited
           immediately, relying entirely on Task Scheduler's own 3-retries/
           1-min-apart config to cover the gap, which usually wasn't enough
           runway and needed a manual restart once wifi came up. Now, on a
           failed initial connection, waits once until a fixed local time
           (CONFIG["startup_retry_at_local"], default "09:10") and makes
           exactly one more attempt before actually giving up — not a
           retry loop, one deliberate second try. Skips the wait if that
           time has already passed. Set startup_retry_at_local to None to
           disable and restore the old immediate-fail behavior.
  v4.92 — Fixed a latent crash-and-skip bug in _evaluate_fvg_strategy()'s
           distance-filter fallback, also found while porting strategies for
           the historical backtest. state["all_fvgs_today"] is shared
           between FVG's own candidates and VWAP's fvg_compat dicts (both
           append there for cross-strategy dedup-by-key), but only real FVG
           dicts carry "top"/"bottom". The fallback that searches for a
           closer-than-best FVG when the best one's entry zone is too far
           from price only filtered on score/entry_zone, so it could select
           a VWAP dict as the new "best FVG" — a few lines later the bearish
           branch does fvg["top"] unconditionally, KeyError. This was caught
           by main()'s top-level exception handler, so it never crashed the
           bot outright — just silently skipped that scan and retried 60s
           later, no visible symptom besides an "Unexpected error" log line.
           Fixed by requiring "top" in f and "bottom" in f in the fallback's
           filter, so a VWAP entry can no longer be selected there.
  v4.91 — CRITICAL fix, found while porting these strategies for a
           historical backtest (reproducing live's exact behavior was the
           only way to match a real logged "MTF: bearish" reading that
           should have been bullish): get_daily_closes() and get_mtf_bias()'s
           opening-gap fetch both requested a `limit` smaller than the true
           bar count in their query window, and Alpaca fills `limit` from
           the OLDEST bars in range first — so both have been silently
           returning STALE data instead of the most recent, every single
           trading day since this code went live. get_daily_closes(n_days=65)
           was confirmed live returning closes ~5 weeks stale; the opening
           gap fetch (bars=5) was confirmed pulling a bar from 2 calendar
           days earlier instead of today's actual open. This fed the
           weekly/monthly MTF trend, daily_momentum, and gap direction —
           which in turn feed get_effective_score_threshold() (FVG/VWAP
           counter-trend gating) and detect_range()'s hard trend filter —
           from wrong data for as long as the bot has been trading. Fixed
           by requesting a generous limit (1000 for daily bars, 300 for the
           5-min gap fetch) so neither request truncates before reaching
           the recent end; the existing trailing-slice logic in both
           functions was already correct, it just never had the right data
           to slice from. Does not affect any trade currently open — this
           only changes what NEW scans see once the bot restarts.
  v4.90 — Trade log now captures longer-horizon trend context at entry,
           not just the short intraday `trend` field: monthly_trend (60-day
           slope), daily_momentum (5-day up/down-day read), and swing_pos_6m
           (near_6m_high / near_6m_low / mid_range, from the same extremes
           SWING-3M/6M uses). Prompted by being asked to compare how
           predictive 5-day vs monthly vs 6-month trend reads are of trade
           outcomes — that analysis wasn't possible because none of those
           three were ever written to master_trade_log.csv (only the
           intraday `trend` was), and SWING-3M/6M itself has 0 trades since
           going live in v4.84, so there's nothing yet to compare. This is
           purely additive logging (new CSV columns, default "" for
           historical rows) — no strategy, sizing, or order-placement logic
           changed. Revisit once enough trades have accumulated (~50/strategy,
           per the standing sample-size rule).
  v4.89 — Strategy-tuning pass per explicit user request: the goal shifted
           from protecting equity to maximizing real trade volume for
           setup-quality research ("I don't really care about making or
           losing paper money, but rather identifying good and bad
           setups"). Changed, all in CONFIG unless noted:
             - risk_per_trade: 0.01 → 0.002 and max_position_pct: 0.20 →
               0.05 — much smaller size per trade, same volatility-aware
               sizing formula otherwise.
             - perf_scale_enabled: True → False — stops scaling size UP
               after a strategy's been winning, which would otherwise
               produce inconsistent, harder-to-compare trade sizes across
               the research dataset.
             - fvg_trading_enabled / spike_momentum_enabled: False → True
               — both were shadow-only after underperforming historically;
               re-enabled so real (small-size) trade data gets collected
               on every setup type, not just the four that were already
               live.
             - min_score_qqq_neutral: 4 → 2 (now matches
               min_score_qqq_aligned) — removed the extra caution bar for
               days QQQ isn't clearly confirming direction.
             - get_effective_score_threshold(): the MTF counter-trend bars
               (previously hardcoded 5/9 and 6/9) lowered to 3/9 and 4/9.
               Found while investigating why days could pass with zero
               qualifying setups even at a low baseline threshold — MTF
               bias reads directional (not neutral) most days in this
               bot's actual history, so THESE bars, not
               min_score_to_trade, were likely the real bottleneck.
             - max_trades_day: left at 1, but documented as dead config —
               grepped the whole file, it's never read anywhere. There is,
               and never was, a real daily trade cap; check_for_entry()
               only blocks while a trade is currently open plus a short
               wash-trade cooldown. A second qualifying setup can already
               trade the same day once the first one closes.
  v4.88 — CRITICAL fix, full root-cause pass: a RANGE long (entry $218.57,
           stop $217.90) opened Friday 2026-09-11, was never actually closed
           by the bot's own mechanisms all weekend, and finally settled
           Monday pre-market at $209.88 — ~$8/share past its stop, a real
           ~$800 loss. Traced and fixed the ENTIRE chain, not just the
           symptom:
           (1) close_all()'s "a closing order is already pending, leave it"
           check matched ANY open order with the right side/qty — including
           a resting take-profit LIMIT order that was never going to fill at
           that price. Every close_all() call for this trade (EOD retries
           Friday, and the false stop-hit below) saw that limit order,
           concluded a close was already in flight, and left it at that —
           while an EARLIER call's "cancel other orders" step had already
           cancelled the position's actual protective stop as collateral
           damage. The position ended up with nothing real protecting or
           closing it. Fixed: only a genuine MARKET order counts as "already
           closing" now — a resting limit or stop order gets cancelled like
           anything else.
           (2) _monitor_bot_trade()'s EOD-force-close gate compared bare
           times-of-day (`now_et().time() >= 15:55`) with no date attached —
           correct for the rest of a trading day, but the instant the clock
           crossed midnight it silently stopped applying, since 00:00 < 15:55.
           Execution fell through into the live tick-based stop/target check,
           never meant to run outside real market hours. At that exact
           moment "Alpaca returned no bars for NVDA" and "YF rate limited"
           both fired — the price data was bad — and cur_px tripped the stop
           check, producing a false STOP HIT that removed the trade from
           active_trades and stopped monitoring it entirely, while the real
           position stayed open on Alpaca. Fixed: added `or not
           is_market_open()` — date/weekday-aware every call, doesn't reset
           at midnight — so the safe, confirmation-gated EOD path can never
           be skipped this way again.
           (3) Even without (2), a false trigger could still have finalized
           the trade wrongly: TARGET HIT / STOP HIT (both directions) and
           TRAILING STOP HIT (both directions) each waited up to N seconds
           for get_position() to confirm the close, then finalized
           UNCONDITIONALLY regardless of whether that confirmation actually
           succeeded — only the near-target-lock branch had this gated
           correctly. All six call sites had their own near-identical copy
           of "wait, then finalize" with the same gap. Replaced all of them
           (target/stop hit x2 directions, trailing stop hit x2 directions,
           near-target-lock) with one shared _confirm_and_finalize_close()
           that only finalizes once get_position() actually confirms flat —
           one implementation instead of six that can't silently drift out
           of sync again.
           (4) Added a direct sanity check rejecting cur_px <= 0 before it
           can reach any target/stop comparison at all — defense-in-depth on
           top of (2), independent of why a bad price might ever show up.
           (5) The chart's price_history buffer had no market-hours guard on
           its append inside _monitor_bot_trade() — with the v4.86 fix now
           correctly keeping a still-open position monitored through nights
           and weekends, this happily logged Alpaca's frozen "last known"
           price every ~30s all weekend, timestamped with the real (weekend)
           wall-clock time. Confirmed live: chart points dated a Sunday
           afternoon. Added `and is_market_open()`.
           (6) _refresh_market_clock() (caches the scheduled close time, e.g.
           for half-days) only ever ran once at process startup — harmless
           when the bot restarted fresh every morning, but the v4.86 fix
           means a single process can now legitimately run for days without
           restarting, so this could go stale. Now also refreshed once per
           genuine new day inside reset_daily_state().
           (7) monitor_trade()'s "no active trades" branch never actually
           touched state["status"] — once a trade closed, the last
           "TRADES OPEN: ..." string just sat there, since this function
           returns immediately on every later call once active_trades is
           empty. Confirmed live: the dashboard was still showing "TRADES
           OPEN: RANGE LONG $-25.51" a full trading day later with nothing
           actually open. Now explicitly clears it.
           Also removed ~1,900 weekend-mislabeled points from the local
           price_history chart cache as a one-time cleanup (dashboard
           display only — not trading data, not account data; rebuilds
           naturally over the next couple weeks).
  v4.87 — CRITICAL fix: found while checking in on the bot after the v4.86
           restart — the dashboard's daily P&L and last-closed-trade display
           went completely empty mid-day even though two real wins had
           already happened (+$242.79, +$625.76). Root cause: save_state()
           never persisted bod_date, bod_equity, daily_pnl, or closed_trade,
           and load_state() never restored state["last_date"] at all. Two
           consequences, both confirmed live: (1) get_daily_pnl()'s "already
           set bod_equity for today, don't reset it" check (added specifically
           to survive intraday restarts) could never find a prior save to
           compare against, so every restart reset the P&L baseline to
           CURRENT equity — silently erasing whatever had already been won or
           lost that day from the dashboard, even though the trades were
           still real and still recorded in Alpaca. (2) state["last_date"]
           being unrestorable meant reset_daily_state()'s main gate
           (`state["last_date"] != today`) was always true on a fresh
           process, so its full new-day reset block fired on every intraday
           restart too — wiping traded_today, closed_trade, best_fvg_today,
           and mtf/weekly/monthly trend state along with it. active_trades
           was already separately protected by its own bod_date-based check
           (v4.53) — everything else in that block wasn't. Fixed by
           persisting bod_date/bod_equity/daily_pnl/closed_trade in
           save_state(), restoring them in load_state(), and setting
           state["last_date"] there too so reset_daily_state() correctly
           recognizes a same-day restart across the board, not just for the
           one field that already had its own protection.
           Caught a follow-on bug testing this same fix live: the BOD-equity
           block used to live INSIDE the `if state["last_date"] != today`
           gate — harmless before, since that gate used to fire on every
           restart anyway, but now that it correctly stays closed on a
           same-day restart, bod_equity would never get a chance to be set
           if it was still missing (e.g. the very first restart after this
           fix, reading an old-format state file). Pulled the BOD check out
           to its own top-level guard in reset_daily_state() — a cheap
           string compare on every call, only hitting Alpaca when bod_date
           genuinely isn't set for today. Also dropped the "Starting equity"
           line from the new-session console banner, since that value is
           now set later than where the banner prints — session_start_equity
           is still tracked, just no longer echoed at that exact moment.
  v4.86 — CRITICAL fix: found and fixed the real reason a position stays open
           overnight even after the v4.79/v4.80/v4.81 fix chain — confirmed
           live 2026-09-10 -> 09-11. A SPIKE long was still open at 4pm ET.
           The v4.79 after-hours idle loop worked exactly as designed —
           698+ logged retries calling monitor_trade() every 30s all evening,
           correctly finding a closing order already pending and leaving it
           alone. But at midnight ET, that loop hit `sys.exit(0)` completely
           UNCONDITIONALLY — it never checked whether a trade was still open
           before killing the process. bot_console.log confirms the process
           died at exactly 00:00 ET with the position still open; Task
           Scheduler's next trigger wasn't until 8:20 AM — an 8+ hour window
           where the bot process didn't exist at all, so nothing could
           monitor the position, manage its stop, or retry closing it. Two
           more of the exact same shape were found nearby: the weekend-detected
           exit a few lines up also didn't check for an open trade (would
           abandon a position for the entire weekend, not just overnight),
           and the pre-market "waiting for open" branch never called
           monitor_trade() at all while idling toward 9:30 ET. Fixed all
           three in main(): compute get_active_trades() once per check,
           call monitor_trade() whenever it's true, and gate every
           sys.exit(0) in this section on NOT having an open trade — the bot
           now only shuts down for its scheduled restart once it has
           confirmed it's actually flat, and otherwise keeps monitoring
           right through midnight and through the weekend until it is.
           Second bug found while verifying this fix on restart the same
           morning: reset_daily_state()'s "new day" branch called
           close_all() then unconditionally wiped state["active_trades"]
           to [], assuming close_all() returning True meant the position
           was flat — but close_all() can return True having only
           confirmed a closing order is already pending (exactly this
           case: a "day, market" order queued pre-market, can't fill
           until 9:30 ET). This wiped the bot's own tracking of a
           position that was still genuinely open on Alpaca, orphaning
           it — get_active_trades() then reported empty, so even with
           the main() fix above, monitor_trade() had nothing to act on.
           Fixed by checking get_position() after close_all() and only
           clearing active_trades once actual flatness is confirmed;
           otherwise the trade stays tracked and monitored.
  v4.85 — Fixed a real bug found while scoping remote/phone dashboard access
           for a second user: every fetch() call in the dashboard's JS
           (build_dashboard.py) hardcoded the literal string
           "http://localhost:8080" instead of a relative path. A browser
           resolves "localhost" against whatever device it's running on —
           so the initial HTML page would load fine from any device (the
           server itself binds to all interfaces), but every live update,
           manual trade, and the 6-month chart fetch would silently try to
           reach the VIEWING device's own loopback and fail. This was never
           caught before because the dashboard had only ever been opened
           from the same PC running the bot. Fixed by switching all 7
           fetch() calls to relative paths (e.g. '/data' instead of
           'http://localhost:8080/data') — these resolve correctly against
           whatever origin the page was actually loaded from (localhost,
           a LAN IP, or a Tailscale IP), with no code change needed per
           deployment. [build_dashboard.py] Required for any remote/phone
           access to work at all — not specific to one instance or user.
  v4.84 — Added a fifth strategy, Swing Reversion (SWING-3M / SWING-6M),
           per user request after noticing the bot took no trades on a day
           with a clear intraday downtrend, plus a separate observation
           using the new 6-month chart that price looked stretched from a
           recent high. Root cause: all four existing strategies (FVG,
           VWAP, Spike, Range) are short-lookback retest triggers — none
           of them reference where price sits relative to its multi-month
           range, so a trending day with no retest into a gap/band zone
           produced zero candidates despite trend/QQQ/MTF all reading
           bearish. detect_swing_reversion() fades price when it's within
           swing_extreme_pct (3%) of a 3-month or 6-month daily high/low
           AND the intraday trend has already confirmed the turn (same
           "won't fade a live breakout" guard RANGE already uses) — stop
           sits beyond the extreme itself (new-extreme-made is the real
           invalidation), target is risk × swing_risk_reward (2.5, wider
           than the 1.5 scalp default). Extended _fetch_daily_bars_for_chart()
           (built for the 6-month chart) to also return daily h/l, and added
           get_swing_extremes() to cache both windows' highs/lows once per
           day off a single Alpaca call, same guard pattern as
           mtf_fetched_today. Both variants plug into check_for_entry()'s
           existing "parallel strategy evaluation, best R:R wins" candidate
           list — no changes needed to order placement, sizing, monitoring,
           or close_all(); the dashboard already renders active_strategy
           generically so SWING-3M/SWING-6M show up with zero UI changes.
  v4.83 — Fixed a real performance bug found while testing v4.82 live in a
           browser, not just reading the code: GET /daily_history took
           14.6s end to end. Cause: _fetch_daily_bars_for_chart() called
           get_alpaca() first, which does its own full account-info round
           trip before this function's OWN bars request even starts —
           double the network cost for no reason (_fetch_alpaca(), the
           intraday candle fetcher, never had this problem since it never
           called get_alpaca() either). Worse than just a slow chart tab:
           the dashboard's HTTPServer is single-threaded (not
           ThreadingHTTPServer), so that 14.6s call stalled the ENTIRE
           dashboard — including the regular 5s /data poll driving the live
           price/status — for the whole time, for anyone with the 6 Month
           tab open, not just that tab. Fixed by dropping the get_alpaca()
           call and going straight to the raw request with the module-level
           keys, matching _fetch_alpaca()'s existing pattern. Also raised
           the client-side fetch timeout 8s → 20s as a safety margin, since
           this is a one-time cached-per-session fetch, not a repeated poll.
  v4.82 — Added a 6 Month tab to the dashboard price chart per user request.
           Investigated first rather than just wiring up a button: the
           rolling price_history buffer (state["price_history"] /
           nvda_price_history.json, 2000-point cap) only actually retains
           ~1-2 weeks of data in practice (~300-390 points/day at current
           polling) — nowhere near enough range, and this means even the
           existing "1 Month" tab has likely been running on less than a
           full month whenever the buffer hadn't been filling long enough.
           A 6-month view needed a genuinely different data source, not a
           bigger buffer. Added _fetch_daily_bars_for_chart() (real daily
           bars from Alpaca, ~200 days, date + close only) and a new GET
           /daily_history endpoint serving it. [build_dashboard.py] Added
           the tab, a lazy-loaded/cached sixMonthHistory fetch (only hits
           Alpaca the first time the tab is opened, not on every poll), and
           month-boundary x-axis labels (Jan, Feb, Mar...) — y-axis was
           already price, unchanged.
  v4.81 — CRITICAL fix to the v4.80 fix. Checked on the v4.79 RANGE position
           the next time I looked and found it had gone through 600+ cancel/
           resubmit cycles overnight (8/20→8/21) without closing — v4.80's
           blanket "cancel all open orders before resubmitting" made things
           worse, not better. Real mechanism: a plain "day, market" close
           order submitted after 4pm ET just sits queued — it physically
           cannot fill until the market reopens, no matter how many times
           it's resubmitted. But v4.80 cancelled that queued order on every
           single retry (~every 40s, all night) and replaced it with a fresh
           one, so a legitimately-pending order that would have filled right
           at next market open never survived long enough to do so. Full
           order history for that trade confirmed it: dozens of "canceled,
           filled_qty=0" market sells every ~40-80s through the night, then
           finally one FILLED at 8/21 9:20-9:32 ET — the next regular
           session, and only by the luck of which retry's timing happened to
           land after market open before the next cancel could tear it down.
           Fixed: close_all() now checks whether an order is already open
           that would fully close the position (same side, sufficient qty)
           and leaves it alone if so — only cancels OTHER open orders (the
           stray protective stop v4.80 was actually meant to clear) before
           submitting a new closing order. A queued after-hours order can
           now actually survive to fill at the next open instead of being
           destroyed by its own retry logic.
  v4.80 — CRITICAL, root cause of the v4.79 incident (and the older v4.68
           "11 failed attempts... strongly suggesting a network hiccup, but
           not provable" mystery from 2026-07-30 — same bug, unprovable back
           then only because close_all() didn't log the real exception yet).
           The "insufficient qty available for order (requested: N,
           available: 0)" rejection wasn't an external order and wasn't
           Alpaca or a network issue — it was this bot's own hybrid-trail
           BREAKEVEN LOCK, which submits a real broker-side protective stop
           order (api.submit_order(..., type="stop", ...)) once a trade
           reaches 1R profit. close_all() never cancelled that order before
           trying to flatten the position, so Alpaca correctly rejected the
           close — the shares were already reserved by the bot's own pending
           stop order. Two of the bot's own safety mechanisms were fighting
           each other. Fixed close_all() to cancel any open orders for the
           ticker first, mirroring the pattern place_order() already uses
           before a new entry. Combined with the v4.79 after-hours retry
           fix, a trade that reaches breakeven and later needs to be closed
           (target, near-target lock, FVG time-stop, or EOD) should no
           longer get stuck fighting its own protective stop.
  v4.79 — CRITICAL: a VWAP short (order 1378bc3b, opened 8/19 14:40 ET)
           stayed open all night and into the next trading day — user caught
           it near target and closed it manually for a profit, but it was
           pure luck the price didn't move against it. Full trace from real
           Alpaca order history + bot_console.log:
             - EOD force-close (inside _monitor_bot_trade, caps at 15:55 ET)
               triggered correctly and retried 11 times in the ~5 minute
               window before 16:00 ET, but close_all() was rejected every
               time: "APIError: insufficient qty available for order
               (requested: 92, available: 0)". A separate stop order
               (buy_to_close, 92 shares) had been submitted around 15:45 ET
               reserving those same shares — not from this bot (shorts only
               ever get a plain market sell, no bracket/stop order — see
               place_order()) and not logged anywhere in bot_console.log, so
               it was placed directly through Alpaca outside this system.
               That order expired unfilled at end of day.
             - Once the clock passed 16:00 ET, main()'s after-hours branches
               (both the "hour>=16" gate and the idle-until-midnight loop)
               stopped calling monitor_trade() ENTIRELY — no further close
               attempts, no stop/target checks, nothing — until the process
               exited at midnight and reconnected the following morning.
               The EOD mechanism's retry design is sound; it just never got
               another chance to run once market hours ended, even though
               the conflicting order that blocked it had already expired by
               then and a later attempt would likely have succeeded.
           This is the real fix for "trades should have a time limit on how
           long they stay open" — that mechanism (EOD force-close) already
           existed, it just wasn't being invoked reliably after hours. Added
           `if get_active_trades(): monitor_trade()` to both after-hours
           branches so retries continue for as long as the process runs
           (idle loop polls every 30s until midnight, ~8 hours of retry
           attempts instead of ~5 minutes) instead of abandoning any
           still-open position the moment the clock passes 4pm ET.
  v4.78 — CORRECTION to v4.77: that diagnosis was wrong. User clarified the
           dashboard was showing $227.70 as the live price — only the
           rejection error said $226.32. Not a case of manually-typed
           stop/target on the wrong side of a genuinely current price.
           Real root cause: the modal's displayed "live" price came from
           state["last_price"], which the background refresh loop sets from
           a 5-MINUTE CANDLE CLOSE (see the "Always refresh price + ATR
           every poll" block in main()) — that can legitimately lag the true
           price by minutes. /manual_trade's validation has always used a
           fresh api.get_latest_trade() tick instead (the v4.63 fix), which
           is more accurate but is a DIFFERENT source than what the modal
           displayed — so "live" on screen and "live" in the rejection could
           genuinely disagree by $1+, exactly as reported. Not a display
           glitch or a user mistake — two different data sources that both
           looked authoritative.
           Fix: added GET /live_price — calls api.get_latest_trade() fresh,
           same call the order validation makes. [build_dashboard.py] The
           modal no longer shows state["last_price"] at all — openModal()
           starts a dedicated poll (fetchLivePriceForModal(), every 4s via
           startLivePricePolling()/stopLivePricePolling()) against
           /live_price for as long as the modal is open, so the number shown
           to the user is now the exact same number the order will be
           validated against, not a second, slower-moving feed that happens
           to also be labeled "live."
  v4.77 — User hit the manual-trade bracket rejection ("stop/target don't
           bracket it correctly for a SHORT") and asked why, since the
           displayed live price looked current. Investigated: confirmed via
           the actual JS that when "Auto-calculate from ATR" is checked, the
           server computes stop/target itself from a fresh entry+ATR at
           submit time, so the rejection is mathematically impossible there.
           This was a manual (ATR unchecked) entry — the typed target was
           above the live price, which is backwards for a SHORT (target must
           be below price; it's the reverse of a LONG). The price hadn't
           actually moved — the form just never told the user which side of
           price each field needed to be on for the direction picked.
           [build_dashboard.py] Added a live hint under the Stop/Target
           fields showing the actual requirement for the selected direction
           and current price, updating in real time and turning red once
           both fields are filled if they don't bracket correctly. Added the
           same bracket check client-side in submitManualTrade() (mirrors
           the server's rule exactly) so this is caught instantly instead of
           round-tripping to find out — the server check stays authoritative
           since price can still move in the gap before it re-verifies.
           [nvda_autotrader.py] This rejection was never logged — raised and
           returned straight to the browser as a 400, invisible in
           bot_console.log. Added a WARN log line before each raise. Also
           softened the error message, which previously asserted "the price
           likely moved" as if that were the only possible cause; it now
           covers both moved-price and wrong-side-of-price without asserting
           which one happened.
  v4.76 — [build_dashboard.py] Fixed "screen fit" bug per user report: the
           price chart rendered tiny (canvas locked at 300x260px) inside its
           ~575px+ wide card, instead of filling it. Root cause: Chart.js can
           measure its container before the CSS grid (.main-grid) finishes
           its layout pass on first load, and — confirmed through direct
           testing — neither a window resize event, nor chart.resize(), nor
           even chart.resize(width, height) with explicit correct numbers
           corrects an already-stuck instance; only destroying and
           recreating the chart does. Added fixChartSizeIfStuck(), run once
           ~500ms after load and also on window resize (there was no resize
           handling at all before), which destroys/recreates the chart only
           when its canvas size doesn't actually match its container —
           no-op in the common case where sizing was already correct.
           Also found while actually running `python build_dashboard.py` to
           verify this fix: the same class of bug fixed in nvda_autotrader.py's
           log() at v4.73 (bare print() + a non-ASCII character crashing under
           cp1252 outside PYTHONIOENCODING=utf-8) existed here too — three
           print() status lines used an em-dash/arrow/checkmark and crashed
           the build outright (UnicodeEncodeError) rather than just a log
           call. Replaced with ASCII (-, ->, plain text).
  v4.75 — CRITICAL: manual trade showed WIN on the dashboard while still
           genuinely open on Alpaca. Root cause: _monitor_manual_trade()'s
           "pos is None → treat as closed" branch had no grace period before
           trusting Alpaca's positions endpoint, unlike its bot-trade sibling
           (_monitor_bot_trade() has waited up to 30s for this exact
           propagation lag since an earlier fix). Confirmed live: a manual
           trade placed 09:59:34 CDT was polled again at 09:59:35 — one
           second later — got pos=None because the fill genuinely hadn't
           propagated yet, got marked "auto-closed WIN, PnL $+0.00", and was
           then NEVER removed from active_trades (remove_active_trade() was
           missing from this branch entirely) — so it stayed in the active
           list indefinitely with a permanently stale WIN label while the
           real position (100sh short, unrealized +$13 at time of fix) kept
           trading underneath it on Alpaca, untouched. Added the same 30s
           grace-period guard as the bot-trade path, and added the missing
           remove_active_trade() call for when this branch is legitimately
           reached. Manually repaired the live-corrupted trade in
           session_state.json: outcome reset OPEN, exit_px/closed_at/
           duration_min cleared, and the bogus entry removed from
           closed_trades_today so it doesn't get written to the permanent
           CSV log at EOD.
  v4.74 — Full silent-error audit per user request: read every `except`
           block in the file (~90) looking for the pattern that caused two
           real bugs already this session (v4.67's swallowed AttributeError,
           v4.73's swallowed UnicodeEncodeError in get_performance_scale) —
           a broad except that returns a plausible-looking "safe" default
           with zero logging, indistinguishable from a genuinely normal
           result. Most of the ~90 are legitimate (confirmation-wait loops
           that intentionally `break` and let the surrounding retry logic
           handle "not confirmed"; documented non-critical fallbacks like
           dashboard history baking). Five were real risks, all fixed by
           adding a log line on the exception path without changing any
           return values (no behavior change, purely visibility):
             - get_position(): caught ANY exception and returned None,
               identical to "genuinely flat." Confirmed via a live test that
               Alpaca raises a distinct 404 (status_code=404, "position does
               not exist") when truly flat — everything else (timeout, auth
               failure, rate limit) looked exactly the same to every caller,
               all of which treat None as closed. This exact confusion (API
               failure mistaken for flat) was the root mechanism behind the
               worst incident of the whole session (v4.67 — a real position
               went untracked overnight). Now only the expected 404 stays
               silent; anything else logs a WARN.
             - get_trend(): silently returned "neutral" on any exception —
               a real, consequential signal (feeds RANGE's hard trend
               filter, MTF score thresholds), not just a "no data" marker.
             - get_qqq_direction(): same pattern, feeds QQQ-alignment
               scoring.
             - get_mtf_bias()'s opening-price fetch: silently fell back to
               cur_px=0, which analyse_opening_gap() would turn into a
               roughly -100% gap written into state as if real.
             - calculate_atr(): lower risk (callers already branch on None
               explicitly) but added a log line for consistency/trace.
  v4.73 — Raised qty for proven strategies per user request, using the
           performance-scale system that already existed for exactly this
           (get_performance_scale() — 1.5x risk_per_trade when a strategy's
           win rate over its last N trades clears 50%) but had been dormant
           ALL SESSION: perf_scale_lookback was 10, and neither SPIKE (9
           trades) nor RANGE (6 trades) ever reached it, so this never once
           fired despite both being consistently profitable. Lowered lookback
           10 → 5: SPIKE 100% (5/5), RANGE 80% (4/5) over their most recent 5
           — both clear the 50% bar with real margin. Re-evaluated every kill
           zone open, so it's not a permanent bump — it can de-scale just as
           automatically if performance drops.
           CRITICAL bug found while verifying this actually engaged: log()
           did a bare print() with no encoding safety net. Several log
           messages in this file use non-ASCII characters (arrows, stars,
           checkmarks) — get_performance_scale()'s own success-path log line
           ("-> scaling qty") is one of them. Outside run_bot.bat's
           PYTHONIOENCODING=utf-8, that print() raises UnicodeEncodeError,
           which propagated straight out of log() and was silently swallowed
           by get_performance_scale()'s own try/except, which then returned
           its "safe" no-scale default (1.0x) — meaning the very feature just
           re-enabled above would have silently never worked outside that one
           specific launch path, with no visible error anywhere. Fixed log()
           to catch UnicodeEncodeError and fall back to an ASCII-safe encode
           instead of ever letting a log line crash its caller — protects
           every log() call in the file, not just this one. Verified fixed:
           get_performance_scale() now correctly returns 1.5x for both SPIKE
           and RANGE even with PYTHONIOENCODING unset.
  v4.72 — Split "SPIKE" into its two real sub-triggers after data review:
           _check_range_extreme() (5-day high/low + rejection) is carrying
           ALL of SPIKE's real profit (7-for-8, +$899.44); _check_spike_
           reversal() (sharp momentum extension + rejection) has fired once,
           ever, and lost (-$57.74). One trade isn't enough to call it broken
           the way FVG was (0-for-5), so instead of cutting it outright, gave
           it the same shadow treatment as FVG: CONFIG["spike_momentum_
           enabled"] = False excludes it from the live candidate list, but
           _check_spike_reversal() still runs every scan for detection.
           Previously momentum was tried FIRST and range-extreme only got
           evaluated `if _spike is None` — a real behavior fix, not just a
           disable: range-extreme (the profitable trigger) no longer gets
           silently skipped on scans where momentum also happened to fire.
           Generalized the FVG shadow-check machinery (was FVG-specific) into
           _run_shadow_check(trade, shadow_key, label, csv_name), reused for
           both FVG (trade_logs/fvg_shadow_log.csv) and momentum-spike
           (trade_logs/spike_shadow_log.csv) — whenever a real trade closes
           as a LOSS, any disabled sub-strategy that also had a valid signal
           at that same scan gets replayed against real historical bars to
           see if IT would have won. No strategy-name exclusion on the
           momentum check: a real range-extreme SPIKE loss still gets
           checked against the momentum shadow, since they're different
           triggers sharing one label — that comparison is the whole point.
  v4.71 — Disabled FVG from live trading (CONFIG["fvg_trading_enabled"] =
           False) after data review: 0-for-5 real trades, -$662.09, and every
           individual loss came back "worked exactly as designed, still lost"
           when investigated — no misfire to fix. detect_fvgs() only ever
           fires WITH the prevailing (fast, 25-candle) trend by construction,
           and account-wide, "with-trend" trades have been the single worst
           cohort (20% win rate, -$403.82), almost entirely FVG's own losses
           — the opposite of SPIKE/RANGE, which trade against extremes and
           have been consistently profitable. Rather than guess-tune 5 data
           points, FVG detection/scoring still runs every scan (unchanged)
           but is no longer appended to check_for_entry()'s live candidate
           list, so it can never be selected/traded — VWAP/SPIKE/RANGE now
           get those kill-zone slots instead.
           Added an FVG "shadow" check per user request, so disabling it
           isn't just a guess either: whenever check_for_entry() picks a
           DIFFERENT strategy this scan, if FVG also had a valid signal at
           that exact moment it's stashed on the trade as trade["_fvg_shadow"]
           (plain floats/strings only — no datetime, to stay safe through
           save_state()'s JSON serialization). If that trade later closes as
           a LOSS, _run_fvg_shadow_check() replays real historical 1-min bars
           from the trade's entry forward and checks whether FVG's own stop
           or target would have hit first — i.e. would FVG have won where the
           strategy that was actually live lost. Result logged to
           trade_logs/fvg_shadow_log.csv, building a real (simulated,
           zero-risk) track record over time to inform whether FVG is ever
           worth re-enabling.
  v4.70 — Fixed a permanent-record data-loss bug found while analyzing
           strategy performance: state["closed_trade"] is a single slot,
           overwritten on every trade close. save_daily_summary() (writes
           trade_logs/{date}_trades.csv and master_trade_log.csv) only ever
           read that one slot, so whenever MORE THAN ONE trade closed on the
           same day, every close except the last silently never reached the
           CSV — daily_pnl/trades_today still counted it correctly in memory,
           but the permanent record lost it forever. Confirmed live: two real
           wins vanished this way once v4.69's near-target lock started
           producing multiple real closes per day (8/5 10:57 CDT +$178.36,
           8/6 09:15 CDT ~+$125 — neither ever reached the CSV). Added
           _finalize_trade_close(trade) — sets state["closed_trade"] (dashboard
           display, unchanged) AND appends to new state["closed_trades_today"]
           list — and routed all 16 real close sites (bot target/stop/trail/
           time-stop/near-target-lock/EOD closes, manual trade closes, EOD
           manual-trade close, Ctrl+C shutdown close) through it instead of
           overwriting the slot directly. save_daily_summary() now builds
           today's CSV rows from the full list. Also persisted the list
           through save_state()/load_state() (mirroring how active_trades
           already survives a restart) so a same-day restart doesn't lose
           trades closed earlier in that same session either.
  v4.69 — Added near-target time lock (CONFIG["near_target_lock_min"/"_pct"],
           applied in _monitor_bot_trade for ALL bot strategies). Motivated by
           a live SPIKE/range-extreme short (2026-08-05) that sat ~18 cents
           from target for over an hour without closing. Root cause: that
           trade's target distance ($2.91) was smaller than its stop distance
           ($3.24), i.e. reward < 1R — the existing hybrid trail (breakeven at
           1R, trailing stop at 2R) structurally can never engage on a trade
           like that, since price would have to move further than the target
           itself before either threshold trips. FVG already had an analogous
           time-stop (fvg_time_stop_min/pct) but it only fires when a trade is
           UNDERPERFORMING and only for strategy=="FVG". This is the mirror
           case — a trade that's mostly WON and stalled — generalized to every
           strategy: once open >= near_target_lock_min (20) minutes AND price
           has covered >= near_target_lock_pct (80%) of the move to target,
           close immediately and bank it rather than risk giving it back
           waiting for the exact tick. Mirrors the FVG time-stop's confirm/
           retry-close pattern (close_all() + 20x1s confirmation poll, retry
           counter, ERROR escalation after 8 unconfirmed attempts).
  v4.68 — Investigated the 2026-07-30 EOD close failure (11 retries over ~5
           min, all "API error", zero orders ever reaching Alpaca per the
           broker's own order history). close_all() swallowed the exception
           entirely, so the true cause couldn't be confirmed — the retry
           spacing (27-46s) closely matches the 20s API timeout plus the
           confirmation-wait loop, strongly suggesting a network connectivity
           hiccup rather than a broker-side rejection, but that remains an
           inference, not a proven fact. Fixed close_all() to log the actual
           exception type/message so a repeat is diagnosable with certainty
           instead of requiring after-the-fact detective work.
  v4.67 — CRITICAL, most severe bug found this session: a real open position
           (short 104 sh, opened 2026-07-30) carried across a genuine midnight
           boundary into 2026-07-31 was left COMPLETELY UNTRACKED all morning
           — the bot scanned for brand-new setups as if flat while the real
           position sat open, unmonitored, and losing money (loss grew from
           confirmed to -$293+ before being caught). Two compounding bugs:
           1) load_state() used to `return` directly from inside its try
              block for the "state file is from a previous day" case (and
              the "no state file" case) — this exited the ENTIRE function,
              skipping the Alpaca-sync reconnection block written
              unconditionally below it. Every prior same-day restart this
              session happened to keep the file's date matching today, so
              this never got exercised until a position genuinely crossed
              midnight. Restructured so the stale/missing-file cases skip
              only the restore-from-file step, not the whole function —
              execution now always reaches the Alpaca sync block.
           2) check_for_entry()'s pre-scan Alpaca check had a ternary that
              evaluated `hasattr(_closed_t.get("closed_at"), ...)` — calling
              .get() on _closed_t before checking it's non-None. Since
              state["closed_trade"] is None on every fresh process until a
              trade closes that session, this raised AttributeError on every
              single call, silently swallowed as a generic "Pre-scan Alpaca
              check failed" WARN — which meant the reconnection logic a few
              lines below (meant to catch exactly this scenario) never ran
              either. Fixed with an explicit None guard before touching
              _closed_t.
  v4.66 — RANGE hard trend filter, added per user request after a -$608.88 day
           (2026-07-27): 5 of 6 real trades were RANGE longs buying a "floor"
           while state["last_trend"] read bearish the entire time — NVDA hit a
           monthly low and kept dropping, and the strategy kept buying dips
           that weren't floors. detect_range() previously only gave a small
           scoring bonus (+1) for trend alignment via MTF bias — it never
           blocked a setup that fought the trend outright. Now hard-rejects:
           no floor-bounce longs when trend is bearish, no ceiling-bounce
           shorts when trend is bullish. Only blocks on a definite counter-
           trend reading — "neutral" trend still passes through unaffected.
           Would have prevented all but one of that day's losing entries.
  v4.65 — CRITICAL: found live — dashboard showed a RANGE short as
           "Status: WIN | P&L: -$50.78" (user separately reported the same
           pattern at -$113.49 on a different instance). Root cause: entry-
           sync (both _monitor_bot_trade and _monitor_manual_trade) updates
           trade["entry"] to the real Alpaca fill price but left stop/target
           at their original ABSOLUTE price levels. Large slippage — which
           the RANGE strategy hits often, re-entering every ~2 minutes in a
           tight band — could push the synced entry past the original
           target, making the setup directionally invalid (a SHORT's target
           ending up ABOVE the new entry). The target/stop-hit checks only
           compare cur_px against trade["target"]/["stop"], with no check
           that target/stop are still on the correct side of entry, so this
           produced an immediate false "target hit" and a WIN label despite
           a negative real P&L (confirmed against Alpaca's actual fills:
           real loss ≈ -$8.10 on the trade that displayed as -$50.78 "WIN").
           Fixed in both entry-sync paths: stop/target are now recomputed
           from the new entry, preserving the ORIGINAL risk/reward
           distances, so the setup stays directionally sane regardless of
           slippage magnitude.
  v4.64 — Bot can now trade alongside an open manual trade, per user request.
           main()'s top-level dispatch used to gate on get_active_trades()
           (ANY trade, including manual) before ever reaching
           check_for_entry() — so a manual trade sitting open silently
           blocked the bot from placing its own trade all day, contradicting
           the multi-trade architecture this file already documents
           (get_bot_trade() specifically means "the bot's own trade";
           check_for_entry() itself already guards on get_bot_trade() is not
           None, not on any-trade, so it was already safe to call — just
           never reached). Restructured: monitor_trade() now runs whenever
           anything is open, independent of kill-zone timing; check_for_entry()
           now depends only on whether the BOT has a trade open. This also
           fixes the "orphan trade" per-trade monitoring loops in the
           between-KZ / all-KZ-passed branches, which had been unreachable
           dead code — they only ran when get_active_trades() was empty,
           since a non-empty list used to route to monitor_trade() instead
           and never fall through to them.
           Caveat worth knowing: Alpaca tracks one position per symbol, so a
           concurrent bot trade in the same direction as an open manual trade
           blends into one combined position (shared avg entry price) even
           though the bot and dashboard track them as separate trade objects
           with independent stop/target. Also, _place_trade()'s position
           sizing (max_position_pct=20%) sizes off total account equity, not
           equity minus what a manual trade already committed — so combined
           exposure across both could exceed 20% if both are open at once.
  v4.63 — Manual trade entry price is no longer client-trusted, per user
           request after a stale-target mistake caused an instant-loss trade
           (v4.62 changelog). Two changes:
           1) Dashboard: the Entry Price field in the manual trade modal is
              now read-only, auto-filled from the live price on modal open
              AND continuously refreshed every ~5s while the modal stays
              open (piggybacking on the existing /data poll) — it can no
              longer go stale from sitting open or from a typo.
           2) /manual_trade (authoritative — this is what actually matters):
              entry is no longer read from the request body at all. The
              handler now fetches a fresh quote directly via
              api.get_latest_trade() right before submitting, and uses THAT
              as entry regardless of what the dashboard sent. Then sanity-
              checks stop/target against it — bullish requires
              stop < price < target, bearish requires target < price < stop
              — and rejects with a clear error before ever placing the order
              if the live price has moved enough that the levels no longer
              make sense. This is what actually prevents "stale data →
              automatic loss": even a stale/manipulated client request can no
              longer place a mis-calibrated trade.
  v4.62 — Manual trades now call save_state() immediately on creation
           (previously relied only on the periodic every-10-scans counter
           during kill-zone scanning, or a later close, to ever persist a
           manual trade — a restart in that window found nothing on disk
           for it and had to reconnect from Alpaca with fabricated generic
           stop/target instead of the real ones). Closes the gap that
           contributed to both the v4.60 entry-price and v4.61 duplicate-
           tracking incidents.
  v4.61 — CRITICAL: duplicate trade tracking on restart. Found live: I had
           directly restored a still-open MANUAL trade into session_state.json
           to correct its entry price (see v4.60), then restarted. load_state()
           correctly restored that MANUAL trade — but the ALPACA SYNC fallback
           right after checked `get_bot_trade() is None`, which only asks "is
           there a non-MANUAL trade tracked?" and ignores MANUAL trades
           entirely. Since the only tracked trade was MANUAL, this fallback
           still fired and added a SECOND "RESTORED" copy of the exact same
           Alpaca position with different (generic) stop/target. Both then
           got monitored independently: the RESTORED copy hit its own
           generic stop first and closed the real position; moments later
           the MANUAL copy polled, found the position gone, and recorded its
           own (fabricated) close too. Net effect: one real trade produced
           two contradictory log entries (-$56.20 and +$1.30) and double-
           credited/debited state["daily_pnl"] — though the dashboard's
           user-facing daily P&L was unaffected, since that's computed
           straight from Alpaca's account equity (get_daily_pnl()), not the
           internal per-trade accumulator. Real outcome per Alpaca's own
           fills: entry $209.73 → exit $210.00 (target hit) → +$2.70.
           Fixed: the sync fallback now checks `not get_active_trades()` —
           any tracked trade of any strategy means this position is already
           accounted for, so no reconnect is attempted.
  v4.60 — Manual trade entry-sync race condition fix. Found live: a 10-share
           manual LONG showed entry $206.65 (the price typed into the modal)
           while Alpaca's real fill was $209.73, inflating displayed P&L by
           over $30. _monitor_manual_trade's entry-sync searched
           list_orders(after=trade["opened_at"]) for the fill — but
           opened_at is stamped AFTER place_order() returns, and a market
           order can already be filled (Alpaca's paper engine fills near-
           instantly) before that stamp happens. The "after" filter excluded
           the exact fill it needed, and the fallthrough silently marked
           _entry_synced=True anyway — permanently giving up without ever
           correcting entry. Fixed by fetching the order directly via
           api.get_order(trade["order_id"]) instead of fuzzy timestamp/side
           matching — no ambiguity possible about which order this is. If
           not filled yet, _entry_synced stays False so it retries next poll
           instead of giving up for good.
  v4.59 — P&L accuracy fix for overnight-carried trades + daily loss limit
           removed per user request:
           1) User reported a manual short (700 sh, entry $212.618371) left
              open overnight and manually closed the next day for a real
              +$2,000.86 profit (verified directly from Alpaca's own order
              fills), while the dashboard showed it as a -$861 loss.
              Root cause: load_state() correctly refuses to reuse a state
              file from a prior day, but that meant the ALPACA SYNC reconnect
              fallback discarded the trade's real stop/target/strategy and
              reset opened_at to the reconnect moment, fabricating generic
              placeholder stop/target instead. Combined with a silent
              fallback to a possibly-stale candle close when the real-fill
              lookup in _monitor_bot_trade doesn't find a match (never
              logged before — see #2), this could produce a badly wrong P&L
              with no visible sign anything was estimated. Fixed: added
              _find_open_trade_in_recent_logs() — the ALPACA SYNC reconnect
              now searches recent daily trade CSVs for a matching still-OPEN
              row (same qty + side) and reuses its real stop/target/strategy/
              opened_at when found, instead of fabricating values.
           2) _monitor_bot_trade's actual-fill-price lookup fell through
              silently to the stale-candle fallback when no matching closed
              order was found — zero log trace that an estimate was used.
              Now logs an ERROR making that fallback (and its risk) visible.
           3) daily_loss_limit_enabled set to False per user request — no
              more daily loss cutoff. CONFIG["daily_loss_limit"] left in
              place (unused while disabled) in case it's wanted again later.
  v4.58 — CRITICAL: crashed the whole bot process. save_daily_summary()
           reconstructs trade dicts from master_trade_log.csv for trades
           closed in an earlier session today (multi-restart day), storing
           opened_at as the plain CSV string — but then unconditionally
           called .strftime() on it, raising "'str' object has no attribute
           'strftime'". This is only reachable once a restart happens after
           at least one trade has already closed today, which is common on
           a day with multiple restarts. The crash hit the outer exception
           handler's after-market-close branch, which calls sys.exit(0) —
           so the bot silently exited instead of staying up for the
           after-hours dashboard. Fixed with a hasattr('strftime') guard,
           same pattern used elsewhere in this file for opened_at fields
           that may be either a datetime or a restored string. Also hardened
           the dashboard payload's equivalent line defensively.
  v4.57 — Dashboard chart flat-plateau fix (diagnosed via user + separate
           Claude session, confirmed and scoped here): last_price freezes
           whenever the bar-date guard (v4.52) rejects a stale candle bar,
           which happens for the whole window IEX hasn't yet published a
           bar for today — showing as dead-flat plateaus in the dashboard
           chart. Added a fallback in both the background price refresh loop
           and check_for_entry(): when the guard rejects the candle bar,
           call api.get_latest_trade() instead of leaving last_price frozen
           — it asks for just the single most recent trade print, no full
           bar required, so it's available well before IEX finishes
           aggregating today's first bar. Reuses the same call pattern
           place_order() already relies on for live-price checks. Narrowly
           scoped to the last_price fallback only — ATR/VWAP/FVG/trend
           detection still require actual OHLC bars and are unaffected.
  v4.56 — CRITICAL: found live with a real open manual trade unmonitored for
           ~2 hours. _monitor_manual_trade() bailed out immediately whenever
           cached state["last_price"] was 0 — which is the case on every
           restart (last_price isn't persisted) and stays 0 indefinitely once
           a trade is active, because the background refresh that would
           normally populate it is deliberately skipped while any trade is
           open. Net effect: a manual trade opened before last_price had a
           chance to populate (e.g. right after a restart) got zero
           monitoring — no entry-fill sync, no target/stop checks, no P&L —
           until the bot was later restarted while flat. Manual shorts have
           no broker-side stop order (IEX limitation), so this silently
           removed the only thing protecting the position; the position kept
           moving against the stop with nothing watching it. Fixed:
           cur_px<=0 no longer bails before attempting to pull a live price
           straight from the Alpaca position; the early-return now only
           fires as a last resort if Alpaca itself is unreachable AND
           there's no cached price at all. Also fixed the pos-is-None (auto-
           closed) branch to fall back to entry instead of a bogus $0 exit
           price when cur_px was never populated.
  v4.55 — Found live via user report ("ATR not available yet" on manual trade):
           main()'s outer exception handler had `now_et = datetime.now(MARKET_TZ)`
           — a LOCAL variable named the same as the module-level now_et()
           function. Python scopes a name as local to the whole function if
           it's assigned anywhere inside it, so every call to now_et() earlier
           in main() — including the background price/ATR/VWAP refresh's
           `now_et().date()` — raised "cannot access local variable 'now_et'"
           on every single call, always, not intermittently. That block's bare
           `except Exception: pass` swallowed it silently, so last_atr/
           last_vwap/last_scan_time stayed stuck at 0/empty the entire time the
           bot was between kill zones (or before the first kill zone of a
           session) — exactly when the dashboard's manual-trade ATR auto-calc
           needs them. check_for_entry() (a separate function) was unaffected,
           so this only broke ATR availability outside active kill zones.
           Fixed by renaming the local to _err_now_et. Also replaced the bare
           except with a one-time-per-distinct-error log (state["_last_bg_refresh_err"]
           dedup) so a failure here is never silently invisible again.
  v4.54 — Same-day restart false-positive fix (found live, same session as v4.53):
           Restarting the bot shortly after the day's first trade opened — before
           any trade CSV existed to set bod_date — made reset_daily_state()'s
           _is_same_day_restart check evaluate False, so it treated a genuine
           same-day restart as a new day and force-closed the just-restored open
           position (then the next scan immediately opened a near-identical new
           one). Fixed by also tracking state["_state_file_date"] — the date
           session_state.json was actually saved with, set on every load_state()
           call regardless of whether a CSV exists yet — and treating a match
           against today as same-day too.
  v4.53 — Full audit pass: fixed two real state-desync bugs found across the
           restart and manual-trade paths, plus extended the v4.52 close-
           confirmation pattern to manual trades:
           1) reset_daily_state() was wiping state["active_trades"]/
              ["active_trade"] unconditionally right after logging "Same-day
              restart detected — preserving open positions (not closing)" —
              the log message was a lie; the just-restored trade was
              discarded from memory a moment later. Any midday restart with
              an open position left the bot blind to it while Alpaca still
              held it open. Fixed: the wipe now only runs on a genuine
              new-day reset; same-day restarts leave active_trades untouched.
           2) end_of_day_check()'s MANUAL trade branch marked trades
              EOD_CLOSE from an estimated price WITHOUT ever calling
              close_all() — the real Alpaca position was never told to
              close and could sit open indefinitely past 16:00 ET while the
              bot believed it was done. Fixed to mirror the bot-trade path:
              close_all() + confirmation wait, only booking closed once
              Alpaca confirms the position is gone (retries + ERROR
              escalation after 8 attempts, same as v4.52).
           3) Extended the v4.52 "don't mark closed until Alpaca confirms"
              fix to the two manual-trade close paths that didn't have it:
              _monitor_manual_trade's target/stop-hit close, and the
              /close_manual_trade HTTP handler (used by the dashboard's
              Close Trade button) — both now wait for confirmation before
              marking the trade closed instead of assuming close_all()
              worked.
           4) /close_manual_trade was silently discarding the "Realized
              P&L" value typed into the dashboard's Close modal and always
              recalculating from cached last_price. Now uses the typed
              value when provided (non-zero) and only falls back to the
              cached-price estimate when it's omitted.
           5) build_dashboard.py VERSION was still v4.22 and hardcoded kill
              zone 3 as ending 15:00 in the KZ status bar (docstring, HTML
              labels, and JS active/passed logic) — stale since v4.42
              extended KZ3 to 15:55. Synced to v4.53 / 15:55 throughout.
  v4.52 — EOD/FVG-time-stop close confirmation bug + phantom price fix:
           1) EOD force-close (_monitor_bot_trade) and FVG time-stop close
              were marking trades "closed" in state (daily_pnl, active_trades,
              trade log) the instant the confirmation wait timed out, even if
              Alpaca never actually confirmed the position was gone. This
              caused a real desync on 2026-07-20 (EOD close submitted, never
              confirmed, bot moved on, position stayed open — required manual
              close). Fixed: both paths now return False and leave the trade
              in active_trades when unconfirmed, so the normal poll loop
              (monitor_trade / between-KZ / post-KZ) retries the close
              automatically every ~15s. Escalates to an ERROR log after 8
              unconfirmed attempts (~2 min) so it's loudly visible instead of
              silently retrying forever. Also now checks close_all()'s return
              value instead of ignoring API-level failures.
           2) Phantom price jump fix: last_price inside _monitor_bot_trade's
              candle fetch was being set from fetch_candles() without checking
              the bar's date. fetch_candles()/_fetch_alpaca() can return stale
              IEX bars from a prior day on no-bar days (e.g. Fridays), which
              was overwriting last_price and creating fake jumps on the
              dashboard chart. Now only updates last_price when the bar is
              from today — same guard already in place at the main scan
              (check_for_entry) and background price-refresh sites.
  v4.51 — EOD close always fires regardless of position check:
           get_position() returning None (network hiccup) was silently
           skipping close_all(), marking trade EOD_CLOSE in state, then
           leaving Alpaca position open. Now always calls close_all()
           unconditionally with 10s confirmation wait and fallback retry.
           Also uses actual position current_price for exit_px when available.
  v4.50 — Ghost trade loop fix:
           DUPLICATE PREVENTED now checks closed_trade state before
           reconnecting monitor. If the position matches a recently
           closed trade (same entry/qty, within 5 min), force-closes
           on Alpaca and skips reconnect. Prevents infinite loop where
           bot marks trade closed but Alpaca position hasn't settled.
  v4.49 — Manual trade P&L fix + daily P&L baseline:
           (1) Manual trade entry price now synced to actual Alpaca fill
               on first monitor call — previously used typed entry price
               causing large P&L discrepancies when slippage occurred.
           (2) get_daily_pnl() uses bod_equity as baseline instead of
               Alpaca last_equity — immune to overnight position accounting
               corruption that caused false loss limit triggers.
  v4.48 — EOD close + time-stop strategy fix:
           (1) Between-KZ orphan monitor now covers bot trades — previously
               only monitored MANUAL trades, so bot trades open at 15:55 ET
               fell into idle loop and never got EOD-closed via monitor.
           (2) Post-KZ "all done" path now monitors open trades — after all
               kill zones pass, the bot kept scanning/sleeping without
               calling _monitor_bot_trade, missing EOD close entirely.
           (3) FVG time-stop strategy default changed from "FVG" to "UNKNOWN"
               — prevented RANGE/RESTORED trades from being falsely flagged
               as FVG and closed by the 45-min time-stop.
           (4) RANGE stop widened 1.5×ATR → 2×ATR — gives more room to
               survive normal range oscillation wicks before reversal.
  v4.47 — Authoritative daily P&L from Alpaca:
           get_daily_pnl() reads account.equity - account.last_equity
           directly from Alpaca on every dashboard poll and EOD summary.
           Replaces state["daily_pnl"] accumulation which was corrupted
           by restarts, fake wins from stale bars, and reversed orders.
           Dashboard Day P&L, daily loss limit, and EOD summary all now
           use Alpaca's figure. Falls back to state["daily_pnl"] if
           Alpaca is unreachable.
  v4.46 — FVG time-stop + audit fixes:
           (1) FVG time-stop: FVG trades open > 45 min without reaching
               70% of target move are closed at market to capture partial
               profit rather than risking full reversal to stop.
               CONFIG: fvg_time_stop_min=45, fvg_time_stop_pct=0.70
           (2) Stale bar checks (_bar_high/_bar_low) removed from
               _monitor_manual_trade — LONG target, LONG stop, SHORT stop
               were still using stale candle bars for close detection.
           (3) RANGE activity check loosened: 20 points (was 10),
               20% threshold (was 30%) — prevents blocking valid entries
               when price just arrived at range extreme after full swing.
           (4) RANGE debug logging added — logs exact reason when
               detect_range() rejects a setup (mid-range, drift, etc).
  v4.45 — Trail stop + close fixes:
           (1) Trailing stop for SHORT capped below target — trail was
               overshooting target, triggering before target was reached
               and leaving Alpaca position open while bot marked WIN
           (2) Trailing stop for LONG capped above target — symmetric fix
           (3) Close confirmation extended 8s → 20s with explicit warning
               if position not confirmed gone — prevents ghost trades
           (4) remove_active_trade moved after close confirmation
           (5) Breakeven disabled for RANGE strategy — range oscillation
               means price bouncing near entry is normal, not a reversal
           (6) Midday restart now preserves open positions (same-day check
               via bod_date vs new day detection)
           (7) EOD force-close inside _monitor_bot_trade with hard 15:55
               cap — ensures positions close before EOD summary fires
  v4.44 — Major trade execution fixes:
           (1) hybrid_trail and trail_atr_mult were MISSING from CONFIG —
               trailing stop/breakeven logic never executed. Added both with
               correct values (hybrid_trail=True, trail_atr_mult=2.0).
           (2) Removed _bar_high/_bar_low from ALL target/stop/trail checks —
               stale IEX fallback bars were triggering false closes across
               fixed target, fixed stop, trailing stop, and manual monitor.
               All checks now use cur_px only (live position price).
           (3) 30-second position propagation guard — prevents premature close
               detection when Alpaca's /positions endpoint lags after short fill.
           (4) Stale order cancellation extended to 15s with abort safety —
               reversed order timestamps (buy-before-sell) caused wrong
               position direction. Bot now aborts entry if stale orders
               won't clear within 15 seconds.
           (5) Actual Alpaca fill price used for P&L (not theoretical target/stop).
               Order query scoped to post-trade-open fills to avoid matching
               prior trade's cover order.
           (6) Range activity/drift check — last 10 price points must show
               ≥30% of range amplitude to confirm active oscillation. Prevents
               entry when range has already broken into a trend.
           (7) Hard market hours wall in place_order() — no orders outside
               09:30–15:55 ET regardless of main loop state.
           (8) Range minimum bounces raised 2→3 (tier 1 and tier 2 both now 3).
           (9) Dominant level detection uses cluster-based algorithm instead
               of median — correctly identifies $194/$202 range boundaries
               even when intermediate chop prices dominate the median.
           (10) Full day price_history used for range detection (not 45-min
                rolling window) — early session floor/ceiling touches stay
                visible throughout the day.
  v4.43 — Range strategy refinements (anti-noise fixes):
           (1) Tier 2 minimum swing raised $1.00 → $1.50 — $1 micro-chop
               was generating repeated near-zero trades inside larger ranges
           (2) Dominant range filter: detected range must represent ≥40% of
               total price swing in lookback window — prevents bot from trading
               sub-ranges inside larger trending moves
           (3) Minimum R:R filter (2.0): won't enter if risk/reward < 2:1
               regardless of how well-formed the range appears
           (4) Lookback extended 30 → 45 minutes for better range structure
               visibility on volatile sessions
           (5) end_equity in EOD summary now calculated from state["daily_pnl"]
               instead of Alpaca portfolio_value — fixes recurring paper trading
               accounting bug where rapid short sequences corrupted P&L display
  v4.42 — Major architecture overhaul + new RANGE strategy:
           PARALLEL STRATEGY EVALUATION: all 4 strategies (FVG, VWAP, SPIKE,
           RANGE) evaluate every 15s scan simultaneously; best R:R wins.
           Replaces rigid "pick one at KZ open" selection.
           NEW RANGE STRATEGY (detect_range): detects intraday oscillating
           ranges from price_history. Tier 1: $2+ swing, 2 bounces, $0.60
           tolerance. Tier 2: $1.50-$1.99 swing, 3 bounces, $0.30 tolerance,
           2x qty. Entry at range extreme (aggressive), stop 0.5×ATR beyond
           extreme, target at opposite boundary.
           MTF bias changed from hard veto (return 99) to scoring weight:
           strong_bullish/bearish → threshold 6/9; moderate → 5/9.
           KZ3 extended 15:00 → 15:55 ET.
           SPIKE elevated to equal strategy selection footing.
           detect_fvgs() now accepts mtf_bias parameter.
           _evaluate_fvg_strategy() and _evaluate_vwap_strategy() wrappers
           added — return candidates without placing trades.
           Performance-based scaling: get_performance_scale() reads
           master_trade_log.csv; boosts risk_per_trade 1.5x when strategy
           win rate >50% over last 10 trades.
           Tiered range qty: tier 2 ranges get 2x shares to offset lower
           per-share profit potential.
           Dashboard server auto-restart loop added.
           Alpaca 10s hard timeout via _alpaca_session_with_timeout().
           Half-day detection: _refresh_market_clock() + get_scheduled_close().
           IEX fallback to prior day bars when today has no data yet.
           Unconditional price_history recording (decoupled from trade guard).
           Orphan trade between-KZ monitor added.
  v4.41 — Audit pass on v4.40. Three real fixes:
           (1) Price history dedup block had wrong indentation (escaped
               the `if 50 < _px_bg < 2000:` guard) — history points could
               be appended at any price. Fixed to correct indent level.
           (2) live_equity and _equity_poll_count not reset in
               reset_daily_state — new day would show stale equity until
               first refresh poll. Now both reset to 0 at daily reset.
           (3) Confirmed false alarms: global _yf_rate_limited_until is
               covered by multi-name global declaration; traded_today=False
               in monitor_trade is intentional (not a re-entry gate);
               all bare except passes are non-critical; close paths are
               correct (outer monitor_trade loop calls remove_active_trade).
  v4.40 — Live equity tracking fix. Dashboard was showing BOD equity
           (session_start_equity snapshot) instead of current portfolio value.
           Fix: background loop now refreshes state["live_equity"] from Alpaca
           every ~5 min (~20 polls at 15s). Dashboard serves live_equity with
           fallback to session_start_equity. Also added bod_equity to dashboard
           payload so JS can compute and display live day P&L (equity - BOD).
  v4.39 — Full audit pass. Fixes:
           (1) Moved inline imports (numpy, csv, re, shutil, socket) to top-level
           (2) Removed dead ternary in position-gone PnL path (always evaluated
               to same branch, result was correct but code was confusing)
           (3) Removed duplicate last_candle_count_prev = 0 in reset_daily_state
           (4) stale_scan_count now resets on each new kill zone open (was
               bleeding stale count from KZ1 into KZ2)
           (5) daily_momentum reset to neutral in reset_daily_state (new day)
           False alarms confirmed safe: global _yf_rate_limited_until (already
           declared via multi-name global), manual close path (outer loop handles
           remove_active_trade), division by zero (all guarded upstream).
  v4.38 — Daily momentum detection. Computed in get_mtf_bias using already-
           fetched daily closes. BULLISH: 4 of last 5 closes higher + price
           in lower 40% of 20d range (rising off lows). BEARISH: 4 of last 5
           closes lower + price in upper 40% of 20d range (falling from highs).
           Effects: +2 bonus to aligned FVG scores; overrides strong MTF hard
           block (strong_bullish no longer blocks shorts if momentum=bearish,
           and vice versa). Logs MOMENTUM BULLISH/BEARISH at kill zone open.
  v4.37 — CRITICAL: manual trade breakeven firing immediately on entry.
           orig_stop was never stored in the manual trade dict, so
           risk = abs(entry - orig_stop) fell back to abs(entry - stop)
           which after _entry_synced set stop=entry = 0. Any profit
           satisfied profit >= 0 → breakeven fired on first monitor call.
           Fix: orig_stop now stored at manual trade creation AND preserved
           in the _entry_synced block before entry is updated.
  v4.36 — Stale data force-refresh spam fix. When IEX candle count is stuck
           and YF keeps returning empty, the force-refresh was firing and
           logging every single scan after scan 20. Now only attempts refresh
           every 5 scans and only logs at scan 20 (not 21, 22, 23...).
  v4.35 — YF hard timeout: yf.history() wrapped in 8s daemon thread — prevents
           bot freeze when YF hangs on rate limit (was blocking monitor loop for
           19+ min). Timeout treated as rate limit, returns cached data if
           available. Manual trade close now cancels all open bracket orders
           before closing position — prevents ghost positions from unfilled
           stop/target legs triggering fills and being reconnected as new trades.
  v4.34 — Price history deduplication fix. All 3 write locations (background
           refresh, scan append, monitor append) upgraded from single-entry
           dedup (only checked hist[-1]) to 4-entry window dedup (checks last
           4 entries for current minute). Also updates price of existing minute
           entry rather than discarding the newer tick. Fixes 649/2000 (32%)
           wasted slots from 4 polls/min all writing the same timestamp.
           monitor append cap corrected from 5000 to 2000. Cleaned
           nvda_price_history.json: 2000 → 1351 unique entries.
  v4.33 — BOD equity guard: reset_daily_state was unconditionally overwriting
           bod_equity each time it fired (including late-session and after-hours
           restarts), replacing the true morning baseline with degraded equity.
           Now only sets bod_equity when bod_date != today or value is unset.
           Logs "BOD equity preserved" vs "BOD equity set" for diagnostics.
  v4.32 — Cross-session P&L tracking. BOD (beginning-of-day) equity now
           persisted in state on new-day reset and restored on same-day
           restart — day P&L is always measured from market open, not last
           restart. EOD summary now reads master_trade_log.csv to include
           trades from all earlier sessions today. EOD console shows
           "equity: $X → $Y" and total trades including prior sessions.
  v4.31 — Bullish range extreme min_bounce fix (v4.30 only patched bearish).
           Fill price sync: trade["entry"] updated to actual Alpaca fill on
           first monitor call — prevents breakeven firing too early when
           fill differs from requested price. Stress zone logging: position
           logs every poll (not once/min) when price within 20% of stop
           distance, with ⚠ NEAR STOP marker.
  v4.30 — Range extreme min bounce requirement. Bullish extreme now requires
           price >= 0.1×ATR above the low before entry (confirms reversal
           has started, not still falling). Same for bearish extreme (must be
           0.1×ATR below the high). Prevents buying/selling exactly at the
           extreme level where one bad tick stops the trade out immediately.
           Note: v4.29 unrealized PnL was correct — $1.00 reflected actual
           fill at $201.15 vs requested $201.55 (normal market order slip).
  v4.29 — YF rate limit data blackout fix. Three bugs combined to kill all
           data after a rate limit: (1) cache was wiped to None on rate limit
           hit — now preserved so stale-but-valid bars still serve during
           backoff; (2) fetch_candles with 1-4 IEX bars returned None cache
           indefinitely — now retries YF once backoff window expires;
           (3) check_stale_data force-refresh cleared last_fetch timestamp
           but not rate_limited_until timer — now clears both if window passed.
  v4.28 — Ghost trade loop fix (log showed TARGET HIT firing 5x on same trade).
           All 6 bot close paths: replaced sleep(2) with position verify loop
           (polls up to 8s until Alpaca confirms position gone). Pre-scan
           DUPLICATE PREVENTED: skips reconnect if trade already tracked OR
           within 10s of a close (settling guard). Uses last_atr for restored
           stop/target estimates. Cancel-before-entry: replaced sleep(0.5s)
           with cancel verify loop (polls until orders cleared). Bracket
           stop_price error: re-fetches live price before submitting and
           adjusts stop/target if market moved since calculation.
  v4.27 — Full audit. Manual trade fixes: SHORT target/stop now calls close_all
           (was never closing Alpaca position — ghost trade every time).
           Wick detection (bar high/low) added to _monitor_manual_trade
           matching _monitor_bot_trade. All 7 state keys used but missing
           from initial state dict added (prevents KeyError on first access).
           yfinance moved to top-level import (was duplicated inline 2x).
  v4.26 — CRITICAL: all 6 bot trade close paths were missing
           remove_active_trade(trade) and 2 were also missing close_all(api).
           Trades stayed in active_trades after closing → next scan's
           duplicate check found settling Alpaca position → ghost trade.
           All paths now: close_all → remove_active_trade → sleep(2) →
           state updates. 2s sleep lets Alpaca settle before next poll.
  v4.25 — Cancel stale open orders before bracket submission. Fixes "bracket
           orders must be entry orders" — bracket child legs from a previous
           trade can persist on Alpaca briefly after the parent fills; submitting
           a new bracket while any open order exists causes the rejection.
  v4.24 — Post-trade cooldown (90s) added to prevent Alpaca wash-trade rejections.
           Cooldown stamped in remove_active_trade() so all close paths covered.
           Configurable via post_trade_cooldown_sec in CONFIG.
  v4.23 — Smarter IEX/YF data source logic at market open. fetch_candles now:
           uses IEX if >= 5 bars (full scan ready); serves stale YF cache if
           IEX has 1-4 bars (warming up, avoids new YF fetch + rate limits);
           suppresses YF entirely if IEX has 0 bars < 10 min after KZ open;
           only fetches fresh YF if IEX still empty after 10 min (genuine issue).
           Eliminates YF rate limits at open and IEX/YF flip-flop mid-session.
  v4.22 — No changes (dashboard-only release)
  v4.21 — Log analysis fixes: YF fallback suppressed during first 10 min of
           kill zone open (IEX delay was triggering YF rate limit every session
           at 9:30). STALE DATA warning now fires once per stuck episode (was
           repeating every scan after scan 8, flooding the log). Best FVG
           score "waiting" message now only logs when score or threshold changes
           (was logging every scan while best_fvg_today was set).
  v4.20 — Wick-detection for SHORT target/stop monitoring. _monitor_bot_trade
           now fetches latest candle and checks candle High/Low alongside cur_px
           for all target and stop checks (LONG target, LONG stop, SHORT target,
           SHORT stop, LONG trail, SHORT trail). Fixes missed closes when price
           wicks through target/stop and bounces back within the 15s poll window.
           Single fetch reused across all 6 checks to avoid extra API calls.
  v4.19 — Full audit fixes: reset_daily_state now closes open Alpaca positions
           before wiping state on new day (orphan trade prevention). end_of_day_check
           moved from 15:00→16:00 ET (was killing the 14:00–15:00 kill zone).
           _yf_rate_limited_until duplicate module-level declaration removed.
           Duplicate imports (warnings 3x, traceback 3x, sys 3x, timedelta 4x)
           consolidated to top-level. sys+traceback added to top-level imports.
           Background refresh: unused _atr_vwap var renamed to _. Dashboard:
           VERSION constant now wired into logo HTML automatically. atrMult
           resets to 1x on every modal open.
  v4.18 — JS syntax fix (stray }} broke all dashboard JS). Manual trade handler:
           undefined `mode` var fixed; real Alpaca error now propagates to dashboard
           instead of generic message; market-hours guard added. KeyboardInterrupt
           handler: undefined `to_remove`/`trade` fixed. place_order re-raises on
           failure. ATR auto-calc: clear error when ATR not ready. Background price
           + ATR refresh now runs every poll cycle unconditionally (not just between
           kill zones) so dashboard and manual modal stay live at all times.
  v4.17 — Range extreme detection (_check_range_extreme). Runs as fallback
           after spike check. 5D range logged every scan. Dashboard HTTP
           server wrapped in try/except with full traceback. Server binds
           to '' (all interfaces). do_GET/do_POST wrapped in try/except.
           After-hours: bot stays alive in low-power loop until midnight.
           ATR multiplier selector (0.5-2.5×) in manual trade modal.
  v4.16 — PDT protection framework (off by default). Fixed target check
           for active bot positions (_monitor_bot_trade). Manual trade
           ATR auto-calc uses CONFIG["risk_reward"] not hardcoded 4×.
           early_shutdown_et config key.
  v4.15 — Short bracket order fix (plain market sell for shorts). Spike
           5-min cooldown. Spike failures don't block FVG/VWAP.
  v4.14 — Spike/mean-reversion strategy parallel to FVG/VWAP. ATR fix
           (min 3 candles). YF timestamp-based cache (60-min minimum).
  v4.13 — Multi-trade architecture. Real Alpaca manual orders.
           _monitor_manual_trade detects Alpaca auto-closes.
  v4.12 — Critical bug fixes: VWAP direction key, FVG stop ATR calc,
           MTF gap price, breakeven order cancellation.
======================================================
"""

import time
import json
import sys
import traceback
import threading
import numpy as np
import csv
import re
import shutil
import socket
import requests
import pandas as pd
import os
import warnings
import statistics
import yfinance as yf
from datetime import datetime, timedelta, time as dtime

# Suppress yfinance/pandas deprecation warnings
# Using simplefilter for aggressive suppression of all FutureWarning noise
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*utcnow.*")
warnings.filterwarnings("ignore", message=".*Timestamp.utcnow.*")

# Also suppress at the yfinance module level via environment
import os as _os
_os.environ.setdefault("PYTHONWARNINGS", "ignore::FutureWarning,ignore::DeprecationWarning")
from zoneinfo import ZoneInfo

# ═══════════════════════════════════════════════════════════════
# ─────────────── API KEYS — SET FROM THE DASHBOARD ───────────
# ═══════════════════════════════════════════════════════════════
# v4.98: keys are no longer edited into this file. They come from (first
# match wins):
#   1. Environment variables ALPACA_API_KEY / ALPACA_SECRET_KEY /
#      ALPACA_BASE_URL — this is how the control panel (build_dashboard.py)
#      passes them when you click Start Bot.
#   2. nvda_settings.json next to this file — written by the control panel's
#      Settings tab, so running this file directly (e.g. from Task Scheduler)
#      picks up the same keys.
# Change keys in the dashboard's Settings tab; never commit nvda_settings.json.

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nvda_settings.json")
PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL  = "https://api.alpaca.markets"


def _load_settings_file():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as _f:
            _s = json.load(_f)
            return _s if isinstance(_s, dict) else {}
    except (OSError, ValueError):
        return {}


_SETTINGS = _load_settings_file()

ALPACA_API_KEY    = os.environ.get("ALPACA_API_KEY")    or _SETTINGS.get("alpaca_api_key", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY") or _SETTINGS.get("alpaca_secret_key", "")
ALPACA_BASE_URL   = (os.environ.get("ALPACA_BASE_URL")
                     or (LIVE_BASE_URL if _SETTINGS.get("trading_mode") == "live" else PAPER_BASE_URL))
ALPACA_DATA_URL   = "https://data.alpaca.markets"
IS_PAPER          = "paper-api" in ALPACA_BASE_URL

# Where trade signals come from: "bot" (this file's own strategies),
# "tradingview" (only TradingView webhook alerts open trades), or "both".
SIGNAL_SOURCE = (os.environ.get("NVDA_SIGNAL_SOURCE") or _SETTINGS.get("signal_source") or "bot").lower()

# TradingView webhook receiver — disabled unless a passphrase is set.
TV_WEBHOOK_PASSPHRASE = os.environ.get("NVDA_TV_PASSPHRASE") or _SETTINGS.get("tv_passphrase", "")
TV_WEBHOOK_PORT       = int(os.environ.get("NVDA_TV_PORT") or _SETTINGS.get("tv_port") or 8090)
TV_WEBHOOK_ENABLED    = bool(TV_WEBHOOK_PASSPHRASE) and (
    os.environ.get("NVDA_TV_ENABLED", "1" if _SETTINGS.get("tv_enabled") else "0") == "1")

# ═══════════════════════════════════════════════════════════════
# IMPORTS (continued)
# ═══════════════════════════════════════════════════════════════
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
import hmac
import hashlib
warnings.filterwarnings('ignore')

STATE_FILE = os.path.join("trade_logs", "session_state.json")

try:
    import alpaca_trade_api as tradeapi
except ImportError:
    print("ERROR: Run: pip install alpaca-trade-api")
    exit(1)

try:
    import tzlocal
    LOCAL_TZ = tzlocal.get_localzone()
except Exception:
    LOCAL_TZ = ZoneInfo("America/Chicago")

MARKET_TZ = ZoneInfo("America/New_York")

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

CONFIG = {
    "ticker":             "NVDA",
    "qqq_ticker":         "QQQ",
    "min_fvg_size":       0.20,
    "max_fvg_size":       2.00,
    "min_body_ratio":     0.40,
    "max_fvg_age_min":    999,
    "trend_lookback":     25,   # v4.3: increased from 10 for stability
    "trend_threshold":    0.15,
    "kill_zones_et": [
        ("09:30", "11:00"),
        ("12:00", "13:00"),
        ("14:00", "15:55"),  # v4.42: extended from 15:00 — high-scoring setups were
                              # firing at 15:40/15:55 and being missed by the old window
    ],
    "score_weights": {
        "morning_window":  3,
        "fvg_ideal_size":  2,
        "qqq_aligned":     2,
        "high_body_ratio": 1,
        "large_volume":    1,
    },
    "entry_at_fvg_pct":   0.50,
    "stop_buffer":        0.50,
    "risk_reward":        1.5,    # target = risk_reward × stop distance (1.5 = scalp, 2.0 = standard)
    # v4.89: dropped from 0.01 (1%) to 0.002 (0.2%) per user request — the
    # goal shifted from protecting equity to maximizing the number of real
    # trades for setup-quality research ("I don't care about making or
    # losing paper money, but rather identifying good and bad setups").
    # Smaller dollar risk per trade so a string of losses collecting that
    # data doesn't require touching anything else about how trades are
    # detected or sized relative to stop distance — qty still scales with
    # volatility exactly as before, just at 1/5th the dollar risk.
    "risk_per_trade":     0.002,
    # ── Performance-based position scaling ────────────────────────────────
    # v4.89: disabled — this scales qty UP after a strategy's been winning,
    # which directly fights the research goal above (want consistent,
    # comparable trade sizes across the dataset, not bigger bets riding a
    # hot streak).
    "perf_scale_enabled": False,  # scale up qty when strategy win rate > 50% over last 10 trades
    # ── FVG time-stop (explicit — also readable via CONFIG.get with defaults) ────
    "fvg_time_stop_min":   45,    # minutes before time-stop closes stalled FVG trade
    "fvg_time_stop_pct":   0.70,  # close if price hasn't reached 70% of target move
    # ── Near-target time lock (v4.69, all strategies) ─────────────────────────────
    # Tight-target strategies (SPIKE/RANGE) often have reward < risk, so the
    # R-multiple hybrid trail below (breakeven at 1R, trail at 2R) can require
    # more move than the target itself and never engages. This closes early once
    # a trade has been open a while AND is most of the way to target, banking the
    # near-full profit instead of risking a round-trip back toward stop while
    # waiting for the exact target tick.
    "near_target_lock_min": 20,   # minutes open before the lock is eligible to fire
    "near_target_lock_pct": 0.80, # close if price has covered >= 80% of the move to target
    # ── Daily loss limit override ─────────────────────────────────────────────────
    "daily_loss_limit_enabled": False,  # v4.59: disabled per user request — no daily loss cutoff
    # v4.71: FVG disabled from live trading — 0-for-5 real trades (-$662.09),
    # every loss individually verified as "worked as designed, still lost."
    # FVG trades WITH the (fast, twitchy 25-candle) trend by construction —
    # exactly the cohort that's performed worst account-wide (20% win rate).
    # Detection/scoring still runs every scan (kept for shadow comparison
    # below) — it just never gets appended to the live candidate list.
    # v4.89: re-enabled per user request — the goal is now maximizing real
    # trade data across every setup type for research ("identifying good
    # and bad setups"), not protecting equity. A strategy with a known-poor
    # track record is exactly the kind of thing worth generating more real
    # (small-size) data on rather than only ever shadow-replaying it.
    "fvg_trading_enabled": True,
    # v4.72: same treatment for the momentum-spike sub-trigger inside "SPIKE"
    # (_check_spike_reversal — sharp move + rejection). Split from the
    # range-extreme sub-trigger (_check_range_extreme — 5-day high/low +
    # rejection) which is carrying ALL of SPIKE's real profit (7-for-8,
    # +$899.44); momentum has fired once, ever, and lost. One trade isn't
    # enough to call it broken like FVG, so it's shadow-tracked instead of
    # cut outright — still evaluated every scan, just never live.
    # v4.89: re-enabled — same research-data reasoning as fvg_trading_enabled
    # above.
    "spike_momentum_enabled": True,
    # v4.73: lowered 10 → 5 per user request to raise qty on proven
    # strategies now, not once 10 trades exist. get_performance_scale() has
    # been dormant the whole session — SPIKE (9 trades) and RANGE (6 trades)
    # never reached the old lookback=10 gate, so this mechanism never once
    # fired despite both being consistently profitable. At lookback=5: SPIKE
    # 100% (5/5), RANGE 80% (4/5) — both clear the 50% threshold with real
    # margin, not a knife-edge. Acknowledged tradeoff: 5 trades is a genuinely
    # small window and will re-evaluate (and can de-scale) every kill zone
    # open as new trades roll in — it is not a permanent bump.
    "perf_scale_lookback": 5,     # number of recent trades per strategy to evaluate
    "perf_scale_threshold": 0.50, # win rate threshold to trigger scaling
    "perf_scale_mult":    1.5,    # multiply risk_per_trade by this when threshold is met
    "daily_loss_limit":   -500.0,  # v4.11: calculated from bod_equity, not last_equity
    # hybrid_trail and trail_atr_mult defined below with corrected values
    # v4.89: lowered 0.20 → 0.05 alongside risk_per_trade above — a secondary
    # cap on position value itself (not just risk-per-share), same research-
    # mode sizing goal.
    "max_position_pct":   0.05,
    # v4.89 finding: this key is never actually read anywhere in the code —
    # grepped the whole file, only this definition exists. There is, and
    # never was, a real 1-trade-per-day cap; check_for_entry() only blocks
    # while a trade is currently OPEN (get_bot_trade() is not None) plus a
    # short wash-trade cooldown — nothing stops a second qualifying setup
    # from trading the same day once the first one closes. Left as-is
    # (harmless, but also pointless to "raise" — it wouldn't do anything).
    "max_trades_day":     1,
    # ── PDT (Pattern Day Trader) protection ──────────────────────
    # Set pdt_protection = True when using a live account under $25,000.
    # Limits to pdt_max_trades round-trips per rolling 5-business-day window.
    # Each completed buy+sell counts as 1 day trade.
    # Set to False for paper trading or accounts over $25,000.
    "pdt_protection":     False,   # enable for live accounts under $25k
    "pdt_max_trades":     3,       # max day trades per 5-business-day window
    "min_score_to_trade": 2,       # baseline minimum score
    # v4.89: lowered 4 → 2 (now matches min_score_qqq_aligned) — this was an
    # extra caution layer requiring a much stronger setup on days QQQ isn't
    # clearly confirming direction. Per the same research-data goal, removed
    # so a day with a neutral QQQ read doesn't disproportionately go
    # trade-less.
    "min_score_qqq_neutral": 2,    # v4.7: higher bar when QQQ gives no confirmation
    "min_score_qqq_aligned": 2,    # v4.7: standard bar when QQQ confirms direction
    "poll_seconds":       15,
    "fetch_timeout":      30,
    "watchdog_timeout_sec": 300,  # v4.96: main loop watchdog — if the top of the
                                   # while-True loop hasn't been reached in this
                                   # many seconds, the process force-exits so Task
                                   # Scheduler's restart (3 attempts, 1 min apart)
                                   # brings it back clean. Confirmed live 2026-10-02:
                                   # the main loop froze silently for ~60 minutes
                                   # right after closing a trade (almost certainly
                                   # an unbounded network call inside the resumed
                                   # check_for_entry() scan, given the network
                                   # instability that week) while the dashboard's
                                   # separate HTTP thread stayed up and masked it —
                                   # nothing in bot_console.log hinted anything was
                                   # wrong. 300s is comfortably longer than any
                                   # single iteration's worst-case retry/backoff
                                   # math (fetch_timeout × fetch_retries + sleeps is
                                   # nowhere near this), short enough to recover in
                                   # minutes instead of silently going dark for an
                                   # hour-plus.
    "post_trade_cooldown_sec":  90,     # v4.24: seconds to wait after close before re-entry (wash-trade prevention)
    "fetch_retries":      3,
    "startup_retry_at_local": "09:10",  # v4.93: if the initial Alpaca connect fails
                                         # (e.g. wifi not up yet at Task Scheduler's
                                         # 8:20 AM launch), wait until this LOCAL time
                                         # and try exactly once more instead of giving
                                         # up immediately. None disables this.
    "dashboard_port":     8080,
    "early_shutdown_et":  None,    # Optional early exit e.g. "12:00" — None = normal 16:00 ET shutdown
    # ── Spike / mean-reversion strategy (v4.13) ──────────────────
    "spike_atr_mult":     2.5,    # candle range must be >= this × ATR to qualify as spike
    # ── Range oscillation strategy (v4.42) ────────────────────────────────
    "range_min_swing":    2.0,    # minimum $ swing amplitude to qualify as a tradeable range (tier 1)
    "range_tolerance":    0.60,   # how close price must return to the level to count as a bounce (tier 1)
    "range_lookback_min": 45,     # minutes of price history — longer window captures dominant range, not micro-chop
    "range_min_bounces":  3,      # confirmed bounces required before entry (tier 1) — raised from 2, third touch confirms range holds
    # ── Range tier 2 — tighter oscillations ($1.00–$1.99), higher confidence required
    "range_t2_min_swing": 1.50,   # minimum $ swing for tier 2 (raised from $1.00 — too noisy)
    "range_t2_max_swing": 1.99,   # maximum $ swing for tier 2 (above this = tier 1)
    "range_t2_tolerance": 0.30,   # tighter tolerance — price must return 75%+ of the way back
    "range_t2_min_bounces": 3,    # extra bounce required to compensate for lower R:R
    "range_t2_qty_mult":  2.0,    # 2x shares to offset lower per-share profit potential
    "spike_vwap_mult":    1.5,    # price must be >= this × ATR away from VWAP
    "spike_lookback":     3,      # number of candles to measure the move over
    "spike_stop_mult":    1.5,    # stop = spike_stop_mult × ATR beyond spike extreme
    # ── Trailing stop config ──────────────────────────────────────────────
    "hybrid_trail":       True,   # enable breakeven + trailing stop once trade moves in favour
    "trail_atr_mult":     2.0,    # trailing stop distance = trail_atr_mult × ATR
                                   # 2.0 gives ~$1.40 trail on today's ATR ($0.70) — enough
                                   # room to not get shaken out on normal retracements (widened from 0.5 — IEX ask spikes trigger stops)
    "spike_target_mult":  1.5,    # target = spike_target_mult × ATR toward VWAP
    # ── Range extreme / multi-day level detection ─────────────────
    "extreme_lookback_days":   5,    # how many days back to find range high/low
    "extreme_proximity_mult":  0.5,  # price must be within this × ATR of the extreme

    # ── VWAP strategy settings ────────────────────────────────
    # How many candles to look back for ATR calculation
    "vwap_atr_lookback":     14,
    # Band multiplier: entry triggers when price within N*ATR of VWAP
    "vwap_band_mult":        1.0,
    # Minimum momentum: bounce candle body must be >= this % of its range
    "vwap_min_body_ratio":   0.50,
    # Minimum candles of data before VWAP trades are allowed
    "vwap_min_candles":      20,

    # ── Strategy selector thresholds ─────────────────────────
    # Range (High-Low of day) above this = wide = favors FVG
    "wide_range_threshold":  3.00,
    # Trend strength pct above this = strong trend = favors FVG
    "strong_trend_pct":      0.40,
    # Volume spike multiplier that triggers mid-window re-evaluation
    "volume_spike_mult":     3.0,

    # ── v4.3 fixes ───────────────────────────────────────────
    # Max % distance from current price to FVG entry zone
    # FVGs further away than this are deprioritized (logged but not traded)
    "max_fvg_entry_distance_pct": 2.0,
    # Stop width as ATR multiple (replaces fixed stop_buffer)
    "stop_atr_mult":              2.0,   # v4.4: widened from 1.5x to reduce noise stopouts
    # ATR lookback for dynamic stop sizing
    "stop_atr_lookback":          14,

    # ── Swing reversion strategy (v4.84) ──────────────────────────
    # Fades price when it's near a 3-month or 6-month high/low AND the
    # intraday trend has already confirmed a turn (not just proximity —
    # same "won't fade a live breakout" philosophy as RANGE's trend filter).
    "swing_lookback_days_3m": 63,    # ~1 trading quarter of daily bars
    "swing_lookback_days_6m": 126,   # ~6 trading months of daily bars
    "swing_extreme_pct":      3.0,   # must be within this % of the window's extreme
    "swing_stop_atr_mult":    1.0,   # stop = extreme ± this × ATR
    "swing_risk_reward":      2.5,   # wider target than the 1.5 scalp default
    "swing_trading_enabled":  True,  # kill-switch, same convention as fvg_trading_enabled
    "swing_max_hold_days":    10,    # v4.94: SWING-6M only — trading days it may carry
                                      # past same-day EOD before being force-closed
                                      # regardless of stop/target. Backtest sweep showed
                                      # 10 captures nearly all the benefit of letting it
                                      # run (total R +29.03 vs +31.50 uncapped) while
                                      # bounding worst-case hold to ~2 trading weeks
                                      # instead of the uncapped 35-day tail.
    "swing_3m_trading_enabled": False,  # v4.95: SWING-3M disabled live per explicit
                                      # user request — same-day-forced backtest was the
                                      # worst-performing strategy of all six tested
                                      # (total R -18.95), and every minute it holds a
                                      # real position blocks check_for_entry() from
                                      # evaluating ANY other strategy at all (confirmed
                                      # live: zero candidate scans for 1.5+ hours while
                                      # one was open). Shadow-only, not a full kill —
                                      # still evaluated and logged every scan so research
                                      # data keeps accumulating, just never added to
                                      # check_for_entry()'s candidates so it can never
                                      # actually be selected or opened. Separate from
                                      # swing_trading_enabled (the master switch for the
                                      # whole SWING family, still gates SWING-6M too).
}

# ═══════════════════════════════════════════════════════════════
# BOT STATE
# ═══════════════════════════════════════════════════════════════

state = {
    "traded_today":         False,      # used for duplicate detection only
    "trades_today":         0,          # count of trades taken today
    "daily_pnl":            0.0,        # v4.10: running P&L for today
    "pdt_trades_window":    [],         # list of ISO date strings for rolling 5-day PDT count
    "trail_activated":      False,      # v4.10: trailing stop engaged (legacy, per-trade now)
    "trail_peak":           0.0,        # v4.10: best price seen since trail activated
    "trail_stop":           0.0,        # v4.10: current trailing stop price
    "price_history":        [],         # rolling price buffer for dashboard chart
    "scan_count_since_save": 0,         # counter for periodic save_state() every 10 scans
    "mtf_bias":             "neutral",  # v4.10: combined weekly+monthly bias
    "weekly_trend":         "neutral",  # v4.10: last 20 daily closes
    "monthly_trend":        "neutral",  # v4.10: last 60 daily closes
    "gap_direction":        "neutral",  # v4.10: today open vs yesterday close
    "gap_pct":              0.0,        # v4.10: gap size in %
    "prev_close":           0.0,        # v4.10: yesterday closing price
    "mtf_fetched_today":    False,      # v4.10: prevents re-fetching MTF each session
    "swing_extremes_fetched_today": False,  # v4.84: prevents re-fetching swing highs/lows each session
    "swing_high_3m":        0.0,        # v4.84: cached 3-month daily high
    "swing_low_3m":         0.0,        # v4.84: cached 3-month daily low
    "swing_high_6m":        0.0,        # v4.84: cached 6-month daily high
    "swing_low_6m":         0.0,        # v4.84: cached 6-month daily low
    "order_failed_today":   False,
    "active_trades":        [],         # v4.12: list of all open trades (bot + manual)
    "active_trade":         None,       # v4.12: legacy alias → points to first bot trade or None
    "closed_trade":         None,       # most recently closed trade (for dashboard)
    "closed_trades_today":  [],         # v4.70: EVERY trade closed today (for save_daily_summary)
    "best_fvg_today":       None,
    "best_score_today":     0,
    "all_fvgs_today":       [],
    "daily_events":         [],
    "last_date":            None,
    "session_start_equity": 0,
    "bod_equity":           0,      # Beginning-of-day equity — survives same-day restarts
    "daily_momentum":       "neutral",  # bullish/bearish/neutral from 4-of-5 daily close rule
    "live_equity":           0,          # refreshed from Alpaca every ~5 min (dashboard display)
    "_equity_poll_count":    0,          # counter to throttle equity refresh calls
    "bod_date":             "",     # Date string matching bod_equity
    "fetch_errors_today":   0,
    "last_price":           0,
    "last_trend":           "neutral",
    "last_qqq":             "neutral",
    "last_scan_time":       "",
    "last_candle_count":    0,
    "status":               "Starting...",
    "_spike_cooldown_until":      "",
    "last_trade_close_time":      None,
    "_last_cooldown_log":          None,
    "_last_kz_logged":             None,
    "_last_order_fail_log":        None,
    "_last_wait_log_key":          None,
    "last_kz":                     None,
    # ── Strategy selector state ───────────────────────────────
    "active_strategy":      "FVG",       # "FVG" or "VWAP"
    "strategy_reason":      "",          # why this strategy was chosen
    "kz_strategy_set":      None,        # which kill zone the strategy was set in
    "last_vwap":            0,           # current VWAP level
    "last_vwap_upper":      0,           # VWAP + 1 ATR
    "last_vwap_lower":      0,           # VWAP - 1 ATR
    "last_atr":             0,           # current ATR
    "vwap_setups_today":    [],          # VWAP bounce setups seen today
    # ── Network / stale data tracking ────────────────────────
    "last_candle_count_prev": 0,
    "stale_scan_count":       0,
    "network_ok":             True,
    "fvg_skipped_distance":   0,    # FVGs skipped today due to distance filter
    "trade_complete_logged":  False, # suppress repetitive "Trade complete" log spam
}

def get_bot_trade():
    """Return the first non-MANUAL trade, or None."""
    for t in state.get("active_trades", []):
        if t.get("strategy") != "MANUAL":
            return t
    return None

def get_active_trades():
    """Return list of all active trades."""
    return state.get("active_trades", [])

def add_active_trade(trade):
    """Add a trade to active_trades and sync legacy active_trade alias."""
    if "active_trades" not in state:
        state["active_trades"] = []
    state["active_trades"].append(trade)
    # Keep legacy alias pointing to first bot trade (for backward compat)
    state["active_trade"] = get_bot_trade()

def remove_active_trade(trade):
    """Remove a trade from active_trades and sync legacy alias.
    Stamps a post-trade cooldown to prevent wash-trade rejections from Alpaca."""
    trades = state.get("active_trades", [])
    state["active_trades"] = [t for t in trades if t is not trade]
    state["active_trade"] = get_bot_trade()
    # Stamp cooldown — Alpaca flags wash trades when same ticker is re-entered too quickly
    state["last_trade_close_time"] = datetime.now(MARKET_TZ)

def _run_shadow_check(trade, shadow_key, label, csv_name):
    """v4.71 (FVG) / v4.72 (generalized for SPIKE momentum): a disabled
    sub-strategy is still evaluated every scan for detection/scoring, but
    excluded from the live candidate list (see CONFIG["fvg_trading_enabled"]
    / ["spike_momentum_enabled"]). Whenever a DIFFERENT strategy's real trade
    closes as a LOSS, if the disabled sub-strategy also had a valid signal at
    that same scan moment (stashed on the trade as trade[shadow_key] in
    check_for_entry()), replay real historical 1-min bars forward from the
    trade's entry to see whether ITS stop or target would have hit first —
    i.e. would it have won where the strategy that was actually live lost.
    Logged to trade_logs/{csv_name} so this builds a real (simulated,
    zero-risk) track record over time instead of leaving the question
    unanswered. label is the human-readable name used in log lines
    ("FVG", "SPIKE MOMENTUM").
    """
    shadow = trade.get(shadow_key)
    if not shadow:
        return
    opened_at = trade.get("opened_at")
    if not hasattr(opened_at, "astimezone"):
        return
    try:
        api_result = get_alpaca()
        api = api_result[0] if api_result[0] else None
        if api is None:
            return
        open_et = opened_at.astimezone(MARKET_TZ)
        eod_et  = open_et.replace(hour=15, minute=55, second=0, microsecond=0)
        end_et  = min(open_et + timedelta(hours=4), eod_et)
        if end_et <= open_et:
            end_et = open_et + timedelta(minutes=30)
        bars = api.get_bars(CONFIG["ticker"], "1Min",
                             start=open_et.isoformat(), end=end_et.isoformat(),
                             limit=500).df
    except Exception as e:
        log(f"{label} shadow check: could not fetch replay bars: {e}", "WARN")
        return

    if bars is None or bars.empty:
        log(f"{label} shadow check: no replay bars available — skipping", "WARN")
        return

    direction = shadow["direction"]
    entry, stop, target = shadow["entry"], shadow["stop"], shadow["target"]
    outcome, exit_px = None, None
    for _, bar in bars.iterrows():
        hi, lo = float(bar["high"]), float(bar["low"])
        if direction == "bullish":
            if lo <= stop:
                outcome, exit_px = "LOSS", stop; break
            if hi >= target:
                outcome, exit_px = "WIN", target; break
        else:
            if hi >= stop:
                outcome, exit_px = "LOSS", stop; break
            if lo <= target:
                outcome, exit_px = "WIN", target; break
    if outcome is None:
        outcome = "UNRESOLVED"
        exit_px = float(bars["close"].iloc[-1])

    per_share  = (exit_px - entry) if direction == "bullish" else (entry - exit_px)
    shadow_pnl = round(per_share * trade.get("qty", 0), 2)

    log(f"{label} SHADOW CHECK — real trade [{trade.get('strategy')}] closed "
        f"{trade.get('outcome')} (${trade.get('pnl', 0):+,.2f}) | {label} would have: "
        f"{outcome} (${shadow_pnl:+,.2f}) | {shadow.get('reason', '')[:60]}", "TRADE")

    try:
        os.makedirs("trade_logs", exist_ok=True)
        path = os.path.join("trade_logs", csv_name)
        row = {
            "date": str(now_local().date()),
            "real_strategy": trade.get("strategy", ""),
            "real_outcome":  trade.get("outcome", ""),
            "real_pnl":      trade.get("pnl", 0),
            "shadow_direction": direction,
            "shadow_score":  shadow.get("score", ""),
            "shadow_entry":  entry, "shadow_stop": stop, "shadow_target": target,
            "shadow_outcome": outcome, "shadow_exit": round(exit_px, 2),
            "shadow_pnl_est": shadow_pnl,
            "shadow_reason": shadow.get("reason", ""),
            "opened_at":     opened_at.strftime("%H:%M %Z") if hasattr(opened_at, "strftime") else str(opened_at),
        }
        file_exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not file_exists:
                w.writeheader()
            w.writerow(row)
    except Exception as e:
        log(f"{label} shadow check: could not write shadow log: {e}", "WARN")


def _finalize_trade_close(trade):
    """Mark a trade closed: sets state['closed_trade'] (dashboard 'last closed'
    tile, unchanged behavior) AND appends to state['closed_trades_today'].

    v4.70 fix: state['closed_trade'] is a single slot, overwritten on every
    close. save_daily_summary() (which writes the permanent CSV log) only
    ever read that one slot, so if more than one trade closed in the same
    day, every close except the last silently never reached the CSV — the
    bot's own daily_pnl/trades_today counted it correctly, but the permanent
    record lost it. Confirmed: two real wins vanished this way (8/5 10:57 CDT
    +$178.36, 8/6 09:15 CDT ~+$125) after the near-target lock (v4.69) started
    producing more than one real close per day. This list gives
    save_daily_summary() every trade closed today, not just the most recent.
    """
    state["closed_trade"] = trade
    today_list = state.get("closed_trades_today", [])
    oid = trade.get("order_id", "")
    if oid:
        today_list = [t for t in today_list if t.get("order_id") != oid]
    today_list.append(trade)
    state["closed_trades_today"] = today_list

    if trade.get("outcome") == "LOSS":
        # No strategy-name guard needed: _run_shadow_check() itself no-ops when
        # the given shadow key isn't present on the trade. A real range-extreme
        # SPIKE loss is still worth checking against the momentum-spike shadow
        # — they're different triggers that happen to share the "SPIKE" label.
        try:
            _run_shadow_check(trade, "_fvg_shadow", "FVG", "fvg_shadow_log.csv")
        except Exception as e:
            log(f"FVG shadow check failed: {e}", "WARN")
        try:
            _run_shadow_check(trade, "_spike_shadow", "SPIKE MOMENTUM", "spike_shadow_log.csv")
        except Exception as e:
            log(f"SPIKE momentum shadow check failed: {e}", "WARN")

# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════

def now_local():
    return datetime.now(LOCAL_TZ)

def now_et():
    return datetime.now(MARKET_TZ)

def et_to_local_str(et_time_str):
    sh, sm   = map(int, et_time_str.split(":"))
    et_dt    = datetime.now(MARKET_TZ).replace(hour=sh, minute=sm, second=0, microsecond=0)
    local_dt = et_dt.astimezone(LOCAL_TZ)
    return local_dt.strftime("%I:%M %p")

# Cached scheduled market close — set at session start via Alpaca clock.
# Reflects actual close time including half-days (e.g. 13:00 ET on July 3).
_scheduled_close_et = None  # dtime object, or None until first clock refresh

def _refresh_market_clock():
    """Query Alpaca clock and cache today's scheduled close time."""
    global _scheduled_close_et
    try:
        api_result = get_alpaca()
        if api_result[0] is not None:
            clock = api_result[0].get_clock()
            from zoneinfo import ZoneInfo as _ZI
            close_et = clock.next_close.astimezone(_ZI("America/New_York"))
            _scheduled_close_et = close_et.time().replace(second=0, microsecond=0)
            if _scheduled_close_et < dtime(15, 30):
                log(f"Half-day detected — market closes at "
                    f"{_scheduled_close_et.strftime('%H:%M')} ET today", "INFO")
    except Exception:
        _scheduled_close_et = dtime(16, 0)  # fallback to standard close

def get_scheduled_close():
    """Return today's scheduled market close as a dtime, defaulting to 16:00."""
    return _scheduled_close_et if _scheduled_close_et is not None else dtime(16, 0)

def is_market_open():
    now = now_et()
    # Weekend check
    if now.weekday() >= 5:
        return False
    # Basic time window check
    if not (dtime(9, 30) <= now.time() <= dtime(16, 0)):
        return False
    # Holiday check via Alpaca clock — authoritative, knows all NYSE holidays
    try:
        api_result = get_alpaca()
        if api_result[0] is not None:
            clock = api_result[0].get_clock()
            return clock.is_open
    except Exception:
        pass  # If Alpaca unreachable, fall back to time-window result
    return True

def is_in_kill_zone():
    t     = now_et().time()
    close = get_scheduled_close()
    for s, e in CONFIG["kill_zones_et"]:
        sh, sm = map(int, s.split(":"))
        eh, em = map(int, e.split(":"))
        kz_end = min(dtime(eh, em), close)
        if dtime(sh, sm) <= t < kz_end:
            return True
    return False

def get_current_kill_zone():
    t     = now_et().time()
    close = get_scheduled_close()
    for s, e in CONFIG["kill_zones_et"]:
        sh, sm = map(int, s.split(":"))
        eh, em = map(int, e.split(":"))
        kz_end = min(dtime(eh, em), close)
        if dtime(sh, sm) <= t < kz_end:
            return s
    return None

def get_next_kill_zone():
    t = now_et().time()
    for s, e in CONFIG["kill_zones_et"]:
        sh, sm = map(int, s.split(":"))
        if dtime(sh, sm) > t:
            return s
    return None

def minutes_to_next_kill_zone():
    t  = now_et()
    tn = t.time()
    for s, e in CONFIG["kill_zones_et"]:
        sh, sm = map(int, s.split(":"))
        eh, em = map(int, e.split(":"))
        start = dtime(sh, sm)
        end   = dtime(eh, em)
        if start <= tn < end:
            # Inside kill zone — minutes remaining
            end_dt   = t.replace(hour=eh, minute=em, second=0, microsecond=0)
            return -(int((end_dt - t).total_seconds() / 60))  # negative = inside
        elif tn < start:
            start_dt = t.replace(hour=sh, minute=sm, second=0, microsecond=0)
            return int((start_dt - t).total_seconds() / 60)
    return None

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

def log(msg, level="INFO"):
    ts  = now_local().strftime("%H:%M:%S")
    tz  = now_local().strftime("%Z")
    et  = now_et().strftime("%H:%M ET")
    out = f"[{ts} {tz} / {et}] {level}: {msg}"
    try:
        print(out)
    except UnicodeEncodeError:
        # v4.73 fix: found while wiring up performance-based qty scaling —
        # stdout encoding (e.g. plain cp1252 outside run_bot.bat's
        # PYTHONIOENCODING=utf-8) can't represent some characters used in log
        # messages (arrows, stars, checkmarks). print() raising here was
        # propagating straight out of log(), and any caller with its own
        # bare try/except around a log() call (get_performance_scale() is
        # one) silently swallowed the crash and fell back to its "safe"
        # default — confirmed live: performance scaling never engaged even
        # when a strategy's win rate cleared the threshold, because logging
        # the "-> scaling qty" line crashed before the return value made it
        # back to the caller. A log line must never be able to crash its
        # caller, so fall back to an ASCII-safe encode instead.
        print(out.encode("ascii", errors="replace").decode("ascii"))
    state["daily_events"].append({
        "time":    f"{ts} {tz}",
        "level":   level,
        "message": msg,
    })
    # Keep log to last 100 entries for dashboard
    if len(state["daily_events"]) > 100:
        state["daily_events"] = state["daily_events"][-100:]

# ═══════════════════════════════════════════════════════════════
# STATE PERSISTENCE
# ═══════════════════════════════════════════════════════════════

class _SafeEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy/pandas types to native Python types."""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        if hasattr(obj, "item"):
            return obj.item()
        return super().default(obj)


def save_state():
    """Save critical trade state to disk so restarts don't lose position info."""
    try:
        os.makedirs("trade_logs", exist_ok=True)
        today = str(now_local().date())

        def _serialize_trade(t):
            if not t:
                return None
            t = dict(t)
            for key in ("opened_at", "closed_at"):
                if isinstance(t.get(key), datetime):
                    t[key] = t[key].isoformat()
            if "fvg" in t and "formed_at" in t.get("fvg", {}):
                fvg = dict(t["fvg"])
                formed = fvg.get("formed_at")
                if formed is not None and hasattr(formed, "isoformat"):
                    if hasattr(formed, "to_pydatetime"):
                        formed = formed.to_pydatetime()
                    fvg["formed_at"] = formed.isoformat()
                t["fvg"] = fvg
            return t

        payload = {
            "date":               today,
            "traded_today":       state["traded_today"],
            "order_failed_today": state["order_failed_today"],
            "best_score_today":   state["best_score_today"],
            "active_trade":       _serialize_trade(state.get("active_trade")),
            "active_trades":      [_serialize_trade(t) for t in get_active_trades()],
            "closed_trades_today": [_serialize_trade(t) for t in state.get("closed_trades_today", [])],
            "pdt_trades_window":  state.get("pdt_trades_window", []),
            # v4.87 CRITICAL fix: these were never persisted, so every intraday
            # restart lost them — bod_date/bod_equity's own "already set for
            # today" check (a few hundred lines below) could never find a prior
            # save to preserve, so it reset the P&L baseline to CURRENT equity
            # on every restart, silently erasing whatever had already been won
            # or lost that day from the dashboard's P&L. daily_pnl and
            # closed_trade are the direct display fields affected. Confirmed
            # live 2026-09-11: two winning trades (+$242.79, +$625.76) vanished
            # from the dashboard the moment the bot was restarted mid-day.
            "bod_date":           state.get("bod_date"),
            "bod_equity":         state.get("bod_equity", 0),
            "daily_pnl":          state.get("daily_pnl", 0.0),
            "closed_trade":       _serialize_trade(state.get("closed_trade")),
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, cls=_SafeEncoder)

        # Also persist price_history separately so it survives mid-day bot swaps
        # Merges with existing JSON so historical data is never lost on restart
        hist_data = state.get("price_history", [])
        if hist_data:
            try:
                hist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "nvda_price_history.json")
                # Load existing JSON and merge — new points take precedence
                existing = []
                if os.path.exists(hist_file):
                    try:
                        with open(hist_file, "r") as hf:
                            existing = json.load(hf)
                    except Exception:
                        existing = []
                # Merge: keep existing points not in current buffer, add current buffer
                existing_ts = {p["t"] for p in hist_data}
                merged = [p for p in existing if p.get("t") not in existing_ts] + hist_data
                merged.sort(key=lambda x: x.get("t", ""))
                if len(merged) > 2000:
                    merged = merged[-2000:]
                with open(hist_file, "w") as hf:
                    json.dump(merged, hf, cls=_SafeEncoder)
                # Keep state in sync with merged history
                state["price_history"] = merged
            except Exception:
                pass
    except Exception as e:
        print(f"[STATE] Save failed: {e}")


def _find_open_trade_in_recent_logs(qty, side, lookback_days=5):
    """Search recent daily trade CSVs for a still-open row matching this
    reconnected Alpaca position (same qty + side), so the ALPACA SYNC
    reconnect in load_state() can recover the trade's real stop/target/
    strategy/opened_at instead of fabricating generic placeholder values.
    Returns a dict with strategy/stop/target/opened_at/source, or None.
    """
    try:
        for _back in range(1, lookback_days + 1):
            _d = (now_local().date() - timedelta(days=_back))
            _path = os.path.join("trade_logs", f"{_d}_trades.csv")
            if not os.path.exists(_path):
                continue
            try:
                _df = pd.read_csv(_path)
            except Exception:
                continue
            for _, _row in _df.iterrows():
                if (str(_row.get("outcome", "")) == "OPEN"
                        and str(_row.get("fvg_type", "")).lower() == side
                        and int(float(_row.get("qty", 0) or 0)) == qty):
                    _opened_dt = None
                    _oa = str(_row.get("opened_at", "") or "")
                    if _oa:
                        try:
                            _time_part = _oa.split()[0]  # "11:19" from "11:19 EDT"
                            _oh, _om = map(int, _time_part.split(":"))
                            _opened_dt = datetime(_d.year, _d.month, _d.day, _oh, _om,
                                                   tzinfo=LOCAL_TZ)
                        except Exception:
                            _opened_dt = None
                    _stop   = float(_row.get("stop", 0) or 0)
                    _target = float(_row.get("target", 0) or 0)
                    if not _stop or not _target:
                        continue  # incomplete row, keep searching further back
                    return {
                        "strategy":  str(_row.get("strategy", "RESTORED")) or "RESTORED",
                        "stop":      _stop,
                        "target":    _target,
                        "opened_at": _opened_dt,
                        "source":    os.path.basename(_path),
                    }
    except Exception:
        pass
    return None


def load_state():
    """Load state from disk on startup. Only applies if saved date matches today."""
    # v4.67 fix: CRITICAL — this used to `return` directly from inside this
    # try block for both the "no state file" and "state file is from a
    # previous day" cases, which exited the ENTIRE function and skipped the
    # Alpaca-sync reconnection block that's written below (unconditionally,
    # meant to always run). That block is the ONLY thing that finds a real
    # open Alpaca position left over from a prior calendar day and reconnects
    # it — every previous same-day restart this session happened to keep the
    # state file's date matching today, so this never got exercised until a
    # position was genuinely carried across a real midnight boundary.
    # Confirmed live: a short position left open crossed into the next day,
    # the fresh process correctly saw the file was stale and returned early,
    # NEVER reconnected the position, and spent the whole morning scanning
    # for brand-new setups while the real position sat completely untracked,
    # unmonitored, and losing money with nothing watching it. Restructured
    # so the stale/missing-file cases just skip the restore-from-file step
    # instead of exiting the function — execution always reaches the Alpaca
    # sync block now.
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)

            today = str(now_local().date())
            # v4.54 fix: record the state file's own saved date regardless of
            # the branch below. reset_daily_state()'s same-day-restart
            # detection used to rely solely on bod_date, which is only set
            # once a trade CSV exists for today (or reset_daily_state itself
            # has already run) — restarting shortly after the day's FIRST
            # trade opens, before either of those, made it look like a new
            # day and force-closed a live position. The state file's date
            # field is written on every save_state() call with no such
            # dependency, so it's a reliable standalone signal.
            state["_state_file_date"] = payload.get("date")
            if payload.get("date") != today:
                log("State file is from a previous day — starting fresh")
            else:
                # v4.87 CRITICAL fix: state["last_date"] was never restored here,
                # so reset_daily_state()'s primary gate (`if state["last_date"]
                # != today`) saw None on every fresh process and ALWAYS ran its
                # full new-day reset block on intraday restarts — wiping
                # traded_today, daily_pnl, closed_trade, best_fvg_today, mtf
                # state, etc. even though the state file confirms this really
                # is the same day. active_trades was already separately
                # protected (bod_date-based _is_same_day_restart check), which
                # is why only the OTHER fields were silently getting wiped.
                # Setting last_date here, tied to the same "file date matches
                # today" truth as everything else in this branch, closes that
                # gap for good — reset_daily_state() will now correctly skip
                # its reset block on a genuine same-day restart.
                state["last_date"] = now_local().date()
                # Restore flags
                state["traded_today"]       = payload.get("traded_today", False)
                state["order_failed_today"] = payload.get("order_failed_today", False)
                state["best_score_today"]   = payload.get("best_score_today", 0)
                state["pdt_trades_window"]  = payload.get("pdt_trades_window", [])
                # v4.87: restore the P&L baseline — see the matching comment in
                # save_state(). closed_trade is restored below, once
                # _restore_trade() is defined.
                if payload.get("bod_date"):
                    state["bod_date"]   = payload["bod_date"]
                    state["bod_equity"] = payload.get("bod_equity", 0)
                state["daily_pnl"]    = payload.get("daily_pnl", state.get("daily_pnl", 0.0))

                def _restore_trade(t):
                    if not t:
                        return None
                    if isinstance(t.get("opened_at"), str):
                        try:
                            t["opened_at"] = datetime.fromisoformat(t["opened_at"])
                        except Exception:
                            t["opened_at"] = now_local()
                    if isinstance(t.get("closed_at"), str):
                        try:
                            t["closed_at"] = datetime.fromisoformat(t["closed_at"])
                        except Exception:
                            pass
                    if "fvg" in t and isinstance(t["fvg"].get("formed_at"), str):
                        try:
                            t["fvg"]["formed_at"] = datetime.fromisoformat(t["fvg"]["formed_at"])
                        except Exception:
                            pass
                    return t

                # v4.87: restore today's last-closed-trade display now that
                # _restore_trade() is defined — see save_state() comment.
                state["closed_trade"] = _restore_trade(payload.get("closed_trade"))

                # Restore active_trades list (v4.12 multi-trade)
                saved_trades = payload.get("active_trades", [])
                if not saved_trades and payload.get("active_trade"):
                    # Migrate old single-trade state files
                    saved_trades = [payload["active_trade"]]

                state["active_trades"] = []
                for t in saved_trades:
                    restored = _restore_trade(t)
                    if restored:
                        add_active_trade(restored)
                        log(f"STATE RESTORED — {restored.get('strategy','?')} {restored.get('fvg_type','?').upper()} "
                            f"@ ${restored.get('entry',0):.2f} | ID: {restored.get('order_id','?')}", "WARN")

                # v4.70: restore trades already closed earlier today (this same
                # calendar day, possibly an earlier process before a restart) so
                # save_daily_summary() still finds them even if this run never
                # closes another trade itself.
                state["closed_trades_today"] = [
                    _restore_trade(dict(t)) for t in payload.get("closed_trades_today", []) if t
                ]

                if get_active_trades():
                    log("Bot will monitor restored positions — scanning continues for new setups.", "WARN")
                elif state["traded_today"]:
                    log("STATE RESTORED — previous trade complete. Resuming scan for new setups.", "WARN")
                    state["traded_today"] = False

    except Exception as e:
        log(f"State load failed (starting fresh): {e}", "WARN")

    # Alpaca sync — check for open positions not in state file
    try:
        api_chk, _ = get_alpaca()
        if api_chk is not None:
            pos_chk = get_position(api_chk)
            # v4.61 fix: this used to check get_bot_trade() is None, which only
            # asks "is there a non-MANUAL trade tracked?" — it doesn't consider
            # MANUAL trades at all, so whenever a MANUAL trade WAS successfully
            # restored from the state file above, this fallback still fired and
            # added a second "RESTORED" copy of the exact same Alpaca position.
            # Both then got monitored independently (different stop/target),
            # each capable of closing the position and double-recording P&L.
            # Alpaca aggregates one position per symbol, so if ANY trade is
            # already tracked (any strategy), that position is already
            # accounted for — no reconnect needed.
            if pos_chk is not None and not get_active_trades():
                qty_chk   = int(float(pos_chk.qty))
                entry_chk = float(pos_chk.avg_entry_price)
                side_chk  = "bullish" if qty_chk > 0 else "bearish"
                log(f"ALPACA SYNC — open position found not in state file: "
                    f"{side_chk.upper()} {abs(qty_chk)} shares @ ${entry_chk:.2f} "
                    f"— reconnecting", "WARN")

                # v4.59 fix: this used to always fabricate generic stop/target
                # (entry * 0.994/1.006/1.012/0.988) and reset opened_at to "now",
                # discarding the real trade's stop/target/strategy/open-time
                # whenever a position carried across a day boundary (state file
                # from a prior day is intentionally not restored above). A trade
                # left open overnight this way got tagged "RESTORED" with made-up
                # risk levels instead of its real ones, and the reset opened_at
                # meant any later fill-price lookup only searched orders after
                # the RECONNECT moment, not the trade's true open — a real risk
                # for producing a wrong P&L if that lookup ever misses and falls
                # back to a stale candle price. Now searches recent daily trade
                # CSVs for a matching still-open row (same qty + side) and reuses
                # its real stop/target/strategy/opened_at when found.
                enriched = _find_open_trade_in_recent_logs(abs(qty_chk), side_chk)
                restored = {
                    "order_id":  pos_chk.asset_id,
                    "fvg":       {},
                    "fvg_type":  side_chk,
                    "strategy":  enriched.get("strategy", "RESTORED") if enriched else "RESTORED",
                    "entry":     entry_chk,
                    "orig_stop": enriched.get("stop") if enriched else None,
                    "stop":      enriched.get("stop", entry_chk * (0.994 if side_chk == "bullish" else 1.006)) if enriched
                                 else entry_chk * (0.994 if side_chk == "bullish" else 1.006),
                    "target":    enriched.get("target", entry_chk * (1.012 if side_chk == "bullish" else 0.988)) if enriched
                                 else entry_chk * (1.012 if side_chk == "bullish" else 0.988),
                    "qty":       abs(qty_chk),
                    "risk":      0,
                    "equity":    0,
                    "opened_at": (enriched.get("opened_at") if enriched else None) or now_local(),
                    "outcome":   None,
                    "exit_px":   None,
                    "pnl":       None,
                    "qqq_dir":   "neutral",
                    "trend":     "neutral",
                    "managed":   True,
                    "use_trail": False,
                }
                if enriched:
                    log(f"ALPACA SYNC — recovered original {restored['strategy']} details from "
                        f"{enriched['source']}: stop ${restored['stop']:.2f} | target ${restored['target']:.2f} "
                        f"| opened {enriched.get('opened_at')}", "WARN")
                add_active_trade(restored)
                state["traded_today"] = True
    except Exception as e:
        log(f"Alpaca sync check failed: {e}", "WARN")


def load_existing_log():
    """
    On startup, read today's existing trade CSV (if any) and restore
    FVG/trade history so the final daily summary is always complete
    regardless of how many times the bot was restarted.
    """
    try:
        today      = now_local().date()
        log_dir    = "trade_logs"
        csv_path   = os.path.join(log_dir, f"{today}_trades.csv")

        if not os.path.exists(csv_path):
            return  # No prior run today

        df = pd.read_csv(csv_path)
        if df.empty:
            return

        # Restore session start equity from first run of the day
        first_equity = df["start_equity"].iloc[0]
        if first_equity and float(first_equity) > 0:
            state["session_start_equity"] = float(first_equity)
        # Restore BOD equity on same-day restart so day P&L stays accurate
        # If bod_date matches today, keep the original BOD equity baseline
        if state.get("bod_date") == str(now_local().date()) and state.get("bod_equity", 0) > 0:
            pass  # bod_equity already correct — don't overwrite
        else:
            # Different day or no BOD equity — set from current equity
            state["bod_equity"] = float(first_equity)
            state["bod_date"]   = str(now_local().date())
            log(f"LOG RESTORED — session equity from earlier run: ${float(first_equity):,.2f}")

        # Restore trade info if a trade was taken earlier today
        for _, row in df.iterrows():
            if row.get("outcome") not in ("NO_TRADE", "", None) and row.get("entry"):
                log(f"LOG RESTORED — prior trade found: "
                    f"{row.get('fvg_type','?').upper()} @ ${float(row.get('entry',0)):.2f} | "
                    f"Outcome: {row.get('outcome','?')} | PnL: ${float(row.get('pnl',0)):.2f}")

                # If trade closed, restore as closed_trade so summary includes it
                if row.get("outcome") not in ("OPEN",) and not state["active_trade"]:
                    state["traded_today"] = True
                    state["closed_trade"] = {
                        "fvg_type":    row.get("fvg_type", "?"),
                        "trend":       row.get("trend", ""),
                        "entry":       float(row.get("entry", 0)),
                        "stop":        float(row.get("stop", 0)),
                        "target":      float(row.get("target", 0)),
                        "qty":         int(row.get("qty", 0)) if row.get("qty") else 0,
                        "risk":        0,
                        "equity":      float(first_equity),
                        "opened_at":   now_local(),
                        "outcome":     row.get("outcome", "CLOSED"),
                        "exit_px":     float(row.get("exit_price", 0)) if row.get("exit_price") else None,
                        "pnl":         float(row.get("pnl", 0)),
                        "qqq_dir":     row.get("qqq_dir", ""),
                        "fvg": {
                            "score":       int(row.get("fvg_score", 0)),
                            "score_notes": row.get("score_notes", ""),
                            "size":        float(row.get("fvg_size", 0)) if row.get("fvg_size") else 0,
                            "formed_at":   now_local(),
                        },
                    }
                break

    except Exception as e:
        log(f"Log restore failed (non-critical): {e}", "WARN")


# ═══════════════════════════════════════════════════════════════
# LIVE DASHBOARD SERVER
# ═══════════════════════════════════════════════════════════════

# v4.98: the dashboard server is now threaded and the TradingView webhook can
# fire at the same moment as a dashboard click — serialize every manual
# open/close so two requests can never interleave their Alpaca calls.
_TRADE_ACTION_LOCK = threading.Lock()


def open_manual_trade(*args, **kwargs):
    with _TRADE_ACTION_LOCK:
        return _open_manual_trade(*args, **kwargs)


def close_manual_trade(*args, **kwargs):
    with _TRADE_ACTION_LOCK:
        return _close_manual_trade(*args, **kwargs)


def _open_manual_trade(direction, stop, target, qty, managed=True, use_atr=False,
                       atr_mult=1.0, use_trail=False, source="dashboard", note=""):
    """
    v4.98: shared by the dashboard's /manual_trade route and the TradingView
    webhook (was inline in the HTTP handler). Places a real Alpaca order and
    tracks it as a MANUAL trade. Raises ValueError with a user-facing message
    on any rejection; returns {"entry", "stop", "target", "order_id"}.
    """
    direction = (direction or "").lower()
    if direction not in ("bullish", "bearish") or qty <= 0:
        raise ValueError("Invalid trade parameters")

    # Guard: market must be open for real orders
    if not is_market_open():
        raise ValueError("Market is closed — manual orders only accepted during market hours (9:30 AM–4:00 PM ET)")

    api_result = get_alpaca()
    if api_result[0] is None:
        raise ValueError("Cannot connect to Alpaca — check API keys")
    api = api_result[0]

    # v4.63 fix: entry is no longer trusted from the request body at all —
    # the dashboard field it came from could be stale (modal left open,
    # slow network, browser tab backgrounded). Always pull a fresh quote
    # directly from Alpaca right here, right before submitting, so the
    # actual entry used for stop/target math (and the sanity check below)
    # reflects the real live price, not whatever the client last saw.
    try:
        _latest_trade = api.get_latest_trade(CONFIG["ticker"])
        entry = float(_latest_trade.price)
    except Exception as _pe:
        raise ValueError(f"Could not fetch a live price to confirm entry — try again: {_pe}")
    if entry <= 0:
        raise ValueError("Could not get a valid live price — try again")

    # Auto-calculate stop/target from ATR if requested
    if use_atr:
        atr = state.get("last_atr", 0)
        if atr <= 0:
            raise ValueError(
                "ATR not available yet — bot needs at least one scan cycle. "
                "Wait ~15 seconds and try again, or enter stop/target manually."
            )
        stop_dist = atr_mult * atr
        tgt_dist  = stop_dist * CONFIG["risk_reward"]
        if direction == "bullish":
            stop   = round(entry - stop_dist, 2)
            target = round(entry + tgt_dist, 2)
        else:
            stop   = round(entry + stop_dist, 2)
            target = round(entry - tgt_dist, 2)

    if stop <= 0 or target <= 0:
        raise ValueError("Stop and target must be set — uncheck ATR to enter manually")

    # v4.63 fix: sanity-check stop/target against the live entry price —
    # this is what actually prevents "stale data → automatic loss" trades.
    # If the levels don't bracket the real live price correctly (e.g. a
    # target that's already behind entry because price moved since the
    # values were set), reject before ever placing the order instead of
    # letting it fill and close instantly for a loss.
    #
    # v4.77 fix: this rejection was never logged — it's raised and
    # returned straight to the browser as a 400, so a real occurrence
    # left zero trace in bot_console.log. Also, "the price likely
    # moved" is a real cause but not the only (or most common, per a
    # live report) one: manually-typed stop/target on the wrong side
    # of price for the chosen direction (e.g. a SHORT's target above
    # entry instead of below — the reverse of a LONG) produces this
    # exact same rejection with the price never having moved at all.
    # Message now covers both without asserting which one happened.
    if direction == "bullish":
        if not (stop < entry < target):
            log(f"Manual trade rejected — bracket mismatch [LONG] entry=${entry:.2f} "
                f"stop=${stop:.2f} target=${target:.2f} (need stop < price < target)", "WARN")
            raise ValueError(
                f"Live price is ${entry:.2f} — your stop (${stop:.2f}) and target "
                f"(${target:.2f}) don't bracket it correctly for a LONG (need "
                f"stop < price < target). Either the price moved, or stop/target got "
                f"entered on the wrong side of it — please review and retry."
            )
    else:
        if not (target < entry < stop):
            log(f"Manual trade rejected — bracket mismatch [SHORT] entry=${entry:.2f} "
                f"stop=${stop:.2f} target=${target:.2f} (need target < price < stop)", "WARN")
            raise ValueError(
                f"Live price is ${entry:.2f} — your stop (${stop:.2f}) and target "
                f"(${target:.2f}) don't bracket it correctly for a SHORT (need "
                f"target < price < stop). Either the price moved, or stop/target got "
                f"entered on the wrong side of it — please review and retry."
            )

    # place_order raises on failure — the real Alpaca error propagates to the except block
    order = place_order(api, direction, entry, stop, target, qty)

    manual_trade = {
        "fvg_type":    direction,
        "strategy":    "MANUAL",
        "entry":       entry,
        "stop":        stop,
        "orig_stop":   stop,       # preserve original stop for risk/breakeven calc
        "target":      target,
        "qty":         qty,
        "outcome":     "OPEN",
        "pnl":         0.0,
        "opened_at":   datetime.now(MARKET_TZ),
        "order_id":    order.id,   # real Alpaca order ID
        "managed":     managed,
        "use_trail":   use_trail,
        "trail_active": False,
        "trail_stop":   None,
        "fvg":         {"score": 0, "notes": note or "Manual entry"},
        "score_notes": note or f"Manual entry from {source}",
        "source":      source,
    }

    add_active_trade(manual_trade)
    state["traded_today"] = True
    # v4.62 fix: manual trades were never immediately persisted —
    # save_state() only ran via the periodic every-10-scans counter
    # (during active kill-zone scanning) or on a later trade close.
    # A restart shortly after opening a manual trade (before either
    # of those fired) found nothing in session_state.json for it,
    # forcing the ALPACA SYNC fallback to reconnect the real Alpaca
    # position from scratch with fabricated generic stop/target —
    # discarding the real ones set here. Saving immediately closes
    # that window.
    save_state()

    log(f"MANUAL TRADE entered via {source} — {direction.upper()} "
        f"| Entry ${entry:.2f} | Stop ${stop:.2f} | Target ${target:.2f} "
        f"| Qty {qty} | Alpaca ID: {order.id}", "TRADE")

    return {"entry": entry, "stop": stop, "target": target, "order_id": order.id}


def _close_manual_trade(oid="", pnl=0.0):
    """
    v4.98: shared by /close_manual_trade and the TradingView webhook. Closes
    the MANUAL trade matching oid (or the first MANUAL trade when oid is
    empty) and waits for Alpaca to confirm. Raises ValueError on failure.
    """
    # Find the trade to close — by order_id if provided, else first MANUAL
    target_trade = None
    for t in get_active_trades():
        if t.get("strategy") == "MANUAL":
            if not oid or t.get("order_id") == oid:
                target_trade = t
                break

    if target_trade:
        # v4.53 fix: close_all() result was ignored and the trade was
        # marked closed 1s later with no confirmation Alpaca actually
        # closed the position — same desync risk v4.52 fixed elsewhere.
        # Now waits for confirmation before proceeding; on failure to
        # confirm, returns an error so the dashboard shows it wasn't
        # closed instead of silently losing track of a real position.
        api_result = get_alpaca()
        if api_result[0] is not None:
            api = api_result[0]
            try:
                # Cancel any open bracket orders first
                open_orders = api.list_orders(status="open", symbols=[CONFIG["ticker"]])
                for o in open_orders:
                    api.cancel_order(o.id)
            except Exception as e:
                log(f"Could not cancel open orders on manual close: {e}", "WARN")
            _close_ok = close_all(api)
            if not _close_ok:
                log(f"close_all() call failed for manual trade {target_trade.get('order_id','')}", "WARN")
            _confirmed = False
            for _cw in range(10):
                time.sleep(1)
                try:
                    if get_position(api) is None:
                        _confirmed = True
                        break
                except Exception:
                    break
            if not _confirmed:
                raise ValueError(
                    "Close submitted but Alpaca has not confirmed the position is gone yet — "
                    "check Alpaca directly, then retry Confirm Close (bot has not marked this closed)."
                )
            log(f"Alpaca position closed for manual trade {target_trade.get('order_id','')}", "TRADE")

        # Use the P&L you typed in the modal when provided (e.g. you closed
        # the position yourself and know the real number). Otherwise fall
        # back to an estimate from the bot's last cached price.
        cur_px = state.get("last_price", target_trade["entry"])
        if pnl:
            log(f"Using user-provided P&L (${pnl:+.2f}) for manual trade {target_trade.get('order_id','')}", "TRADE")
        else:
            if target_trade.get("fvg_type") == "bullish":
                pnl = round((cur_px - target_trade["entry"]) * target_trade["qty"], 2)
            else:
                pnl = round((target_trade["entry"] - cur_px) * target_trade["qty"], 2)

        target_trade["outcome"] = "MANUAL_CLOSE"
        target_trade["pnl"]     = pnl
        target_trade["exit_px"] = cur_px
        _finalize_trade_close(target_trade)
        remove_active_trade(target_trade)
        if not get_active_trades():
            state["traded_today"] = False
        state["trades_today"] = state.get("trades_today", 0) + 1
        _record_day_trade()
        state["daily_pnl"]    = state.get("daily_pnl", 0.0) + pnl
        log(f"MANUAL TRADE closed | ID: {target_trade.get('order_id','')} | P&L: ${pnl:+.2f}", "TRADE")
        return pnl
    raise ValueError("No matching manual trade to close")


# v4.98: the dashboard server used to bind to every network interface with
# "Access-Control-Allow-Origin: *" on every response and no checks on POST —
# so any device on the same wifi, or ANY website open in your browser, could
# POST /manual_trade and place a real order. Now it binds to 127.0.0.1 by
# default (override with NVDA_BOT_HOST), sends no CORS headers, and every
# POST must be same-origin JSON. Cross-site pages can't send a JSON POST
# without a CORS preflight, which this server never approves.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _host_only(host_header):
    host_header = (host_header or "").strip().lower()
    if host_header.startswith("["):                 # [::1]:8080
        return host_header.split("]")[0] + "]"
    return host_header.rsplit(":", 1)[0] if host_header.count(":") == 1 else host_header


def request_is_trusted(handler, bind_host, is_post):
    """Reject DNS-rebinding (Host) and cross-site (Origin / content type) requests."""
    host = _host_only(handler.headers.get("Host"))
    if bind_host in _LOOPBACK_HOSTS and host not in _LOOPBACK_HOSTS:
        return False
    if not is_post:
        return True
    ctype = (handler.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype != "application/json":
        return False
    origin = handler.headers.get("Origin")
    if origin and origin.rstrip("/").lower() != "http://" + (handler.headers.get("Host") or "").lower():
        return False
    return True


def _dashboard_html():
    """The same UI the control panel serves, in bot-only mode (no Start/Stop/Settings)."""
    try:
        import build_dashboard
        return build_dashboard.render_html(standalone=True).encode("utf-8")
    except Exception as e:
        log(f"Could not render dashboard from build_dashboard.py: {e}", "WARN")
        dash_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "nvda_live_dashboard.html")
        if os.path.exists(dash_path):
            with open(dash_path, "rb") as f:
                return f.read()
        return None


BOT_HTTP_HOST = os.environ.get("NVDA_BOT_HOST", "127.0.0.1")


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress server access logs

    def handle_error_response(self, code, msg):
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(msg.encode())
        except Exception:
            pass

    def do_GET(self):
        if not request_is_trusted(self, BOT_HTTP_HOST, is_post=False):
            self.handle_error_response(403, "Forbidden")
            return
        try:
            self._do_GET_inner()
        except Exception as e:
            traceback.print_exc()
            self.handle_error_response(500, f'Handler error: {e}')

    def _do_GET_inner(self):
        if self.path == '/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            trade = state.get("active_trade") or state.get("closed_trade")
            mins  = minutes_to_next_kill_zone()

            def _fmt_trade(t):
                if not t:
                    return None
                fvg_data = t.get("fvg") or {}
                # v4.94: opened_at used to always render as bare "HH:MM %Z" —
                # fine when every trade closes same-day, misleading now that
                # SWING-6M can carry for days (a 3-day-old trade showing just
                # "09:45 CDT" looks like it opened this morning). Include the
                # date once it's not today, and surface days_open separately
                # so the frontend can show an explicit "(Nd open)" badge.
                _oa = t.get("opened_at")
                _days_open = 0
                if hasattr(_oa, "strftime"):
                    _oa_local = _oa.astimezone(MARKET_TZ) if hasattr(_oa, "astimezone") else _oa
                    if _oa_local.date() == now_local().date():
                        _oa_str = _oa_local.strftime("%H:%M %Z")
                    else:
                        _oa_str = _oa_local.strftime("%m/%d %H:%M %Z")
                        _days_open = (now_local().date() - _oa_local.date()).days
                else:
                    _oa_str = str(_oa) if _oa else ""
                return {
                    "id":        t.get("order_id", ""),
                    "fvg_type":  t.get("fvg_type", ""),
                    "strategy":  t.get("strategy", "UNKNOWN"),
                    "entry":     t.get("entry", 0),
                    "stop":      t.get("stop", 0),
                    "target":    t.get("target", 0),
                    "qty":       t.get("qty", 0),
                    "outcome":   t.get("outcome") or "OPEN",  # v4.97: see CSV-writer fix comment
                    "pnl":       t.get("pnl", 0),
                    "score":     fvg_data.get("score", 0),
                    # v4.58 fix: defensive — same str-vs-datetime hazard as
                    # save_daily_summary(), guarded here too in case a trade
                    # dict ever ends up with a string opened_at.
                    "opened_at": _oa_str,
                    "days_open": _days_open,
                }

            payload = {
                "timestamp":      now_local().strftime("%H:%M:%S %Z"),
                "date":           str(now_local().date()),
                "status":         state["status"],
                "market_open":    is_market_open(),
                "in_kill_zone":   is_in_kill_zone(),
                "current_kz":     get_current_kill_zone(),
                "next_kz":        get_next_kill_zone(),
                "mins_to_kz":     mins,
                "last_price":     state["last_price"],
                "last_trend":     state["last_trend"],
                "last_qqq":       state["last_qqq"],
                "last_scan_time": state["last_scan_time"],
                "last_candles":   state["last_candle_count"],
                "traded_today":   state["traded_today"],
                "best_score":     state["best_score_today"],
                "fvgs_today":     len(state["all_fvgs_today"]),
                "fetch_errors":   state["fetch_errors_today"],
                "equity":         state.get("live_equity") or state["session_start_equity"],
                "bod_equity":     state.get("bod_equity", state["session_start_equity"]),
                # Strategy info
                "active_strategy":  state["active_strategy"],
                "strategy_reason":  state["strategy_reason"],
                "last_vwap":        state["last_vwap"],
                "last_vwap_upper":  state["last_vwap_upper"],
                "last_vwap_lower":  state["last_vwap_lower"],
                "last_atr":         state["last_atr"],
                "vwap_setups_today": len(state["vwap_setups_today"]),
                "all_fvgs": [{
                    "time":       (f["formed_at"].to_pydatetime() if hasattr(f["formed_at"], "to_pydatetime") else f["formed_at"]).strftime("%H:%M"),
                    "type":       f["type"],
                    "size":       f["size"],
                    "score":      f["score"],
                    "entry_zone": f.get("entry_zone", 0),
                    "notes":      f["score_notes"],
                } for f in state["all_fvgs_today"]],
                # v4.12: multi-trade support
                "active_trades": [_fmt_trade(t) for t in get_active_trades()],
                "active_trade":  _fmt_trade(trade),   # legacy single-trade for backward compat
                "closed_trade":  _fmt_trade(state.get("closed_trade")),
                "daily_pnl":     get_daily_pnl(),  # Alpaca equity delta — authoritative
                "log": list(reversed(state["daily_events"][-20:])),
                "price_history": state.get("price_history", [])[-2000:],
                "mtf_bias":        state.get("mtf_bias", "neutral"),
                "weekly_trend":    state.get("weekly_trend", "neutral"),
                "monthly_trend":   state.get("monthly_trend", "neutral"),
                "trail_activated": state.get("trail_activated", False),
                "trail_stop":      state.get("trail_stop", 0.0),
            }
            try:
                self.wfile.write(json.dumps(payload, cls=_SafeEncoder).encode())
            except (ConnectionAbortedError, BrokenPipeError):
                pass  # Browser closed connection before response finished — harmless
        elif self.path == '/history':
            # Full price history for dashboard offline use
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            hist = state.get("price_history", [])
            try:
                self.wfile.write(json.dumps(hist, cls=_SafeEncoder).encode())
            except (ConnectionAbortedError, BrokenPipeError):
                pass
        elif self.path == '/live_price':
            # v4.78: dedicated endpoint for the manual trade modal. state["last_price"]
            # (what /data returns, and what the modal used to display) comes from a
            # 5-minute candle close in the background refresh loop — that can lag the
            # true price by minutes, same order of magnitude as the gap a user actually
            # hit ($227.70 shown in the modal vs $226.32 in the rejection). The
            # /manual_trade handler has always validated against a fresh
            # api.get_latest_trade() tick, not last_price — this endpoint lets the
            # modal show that SAME source, so what the user sees and what actually
            # gets validated against are the same number, not two different feeds.
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                api_result = get_alpaca()
                if api_result[0] is not None:
                    _lt = api_result[0].get_latest_trade(CONFIG["ticker"])
                    payload = {"price": round(float(_lt.price), 2), "timestamp": str(_lt.timestamp)}
                else:
                    payload = {"price": 0, "error": "Alpaca unreachable"}
            except Exception as e:
                payload = {"price": 0, "error": str(e)}
            try:
                self.wfile.write(json.dumps(payload).encode())
            except (ConnectionAbortedError, BrokenPipeError):
                pass
        elif self.path == '/daily_history':
            # v4.82: dedicated endpoint for the dashboard's 6-month chart tab.
            # See _fetch_daily_bars_for_chart() — the rolling price_history
            # buffer only covers ~1-2 weeks, so a multi-month view needs a
            # separate real fetch of daily bars from Alpaca.
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                bars = _fetch_daily_bars_for_chart(CONFIG["ticker"], n_days=200)
            except Exception:
                bars = []
            try:
                self.wfile.write(json.dumps(bars).encode())
            except (ConnectionAbortedError, BrokenPipeError):
                pass
        elif self.path == '/' or self.path == '/dashboard':
            html = _dashboard_html()
            if html:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(html)
                except (ConnectionAbortedError, BrokenPipeError):
                    pass
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Dashboard not found - keep build_dashboard.py next to nvda_autotrader.py')
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """No cross-origin access — the dashboard is always served same-origin."""
        self.handle_error_response(405, "Method not allowed")

    def do_POST(self):
        if not request_is_trusted(self, BOT_HTTP_HOST, is_post=True):
            self.handle_error_response(403, "Forbidden")
            return
        try:
            self._do_POST_inner()
        except Exception as e:
            traceback.print_exc()
            self.handle_error_response(500, f'Handler error: {e}')

    def _do_POST_inner(self):
        """Handle manual trade entry and close requests from dashboard."""
        if self.path == '/manual_trade':
            try:
                length  = int(self.headers.get('Content-Length', 0))
                body    = json.loads(self.rfile.read(length).decode())
                direction = body.get("direction", "").lower()
                managed   = bool(body.get("managed", True))
                result = open_manual_trade(
                    direction,
                    stop      = float(body.get("stop", 0) or 0),
                    target    = float(body.get("target", 0) or 0),
                    qty       = int(body.get("qty", 0) or 0),
                    managed   = managed,
                    use_atr   = bool(body.get("use_atr", False)),
                    atr_mult  = float(body.get("atr_mult", 1.0) or 1.0),
                    use_trail = bool(body.get("use_trail", False)),
                    source    = "dashboard",
                )
                self._send_json(200, {
                    "ok": True,
                    "message": f"Manual {direction} trade entered @ ${result['entry']:.2f} "
                               f"({'managed' if managed else 'log-only'})",
                    "entry":  result["entry"],
                    "stop":   result["stop"],
                    "target": result["target"],
                })
            except Exception as e:
                self._send_json(400, {"ok": False, "error": str(e)})

        elif self.path == '/close_manual_trade':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body   = json.loads(self.rfile.read(length).decode()) if length else {}
                close_manual_trade(body.get("order_id", ""), float(body.get("pnl", 0) or 0))
                self._send_json(200, {"ok": True})
            except Exception as e:
                self._send_json(400, {"ok": False, "error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, code, payload):
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload, cls=_SafeEncoder).encode())
        except (ConnectionAbortedError, BrokenPipeError):
            pass


def start_dashboard_server():
    # v4.98: NVDA_BOT_PORT is set by the control panel (which owns 8080 itself
    # and talks to the bot on 8081). Standalone runs keep the old 8080.
    port = int(os.environ.get("NVDA_BOT_PORT") or CONFIG["dashboard_port"])

    def _run():
        # Auto-restart loop — if the HTTP server crashes (e.g. during a
        # connectivity outage), it restarts automatically rather than leaving
        # the dashboard permanently offline for the rest of the session.
        while True:
            try:
                server = ThreadingHTTPServer((BOT_HTTP_HOST, port), DashboardHandler)
                log(f"Dashboard server started on {BOT_HTTP_HOST or 'all interfaces'}:{port}")
                server.serve_forever()
            except OSError as e:
                # Port already in use — don't retry immediately
                log(f"Dashboard server OSError (port {port} in use?): {e}", "ERROR")
                time.sleep(10)
            except Exception as e:
                log(f"Dashboard server crashed: {e} — restarting in 5s", "WARN")
                time.sleep(5)
                continue  # restart

    try:
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        time.sleep(0.5)  # give server time to start
        if not thread.is_alive():
            log("Dashboard server thread died on startup — dashboard unavailable", "ERROR")
        elif not os.environ.get("NVDA_BOT_PORT"):   # control panel prints its own URL
            print(f"\n  📊 Live dashboard: http://127.0.0.1:{port}")
            print(f"  Open that URL in your browser while the bot runs.")
            print(f"  (Using this URL lets manual trades work — don't open the HTML file directly)\n")
    except Exception as e:
        log(f"Dashboard server failed to start: {e}", "ERROR")

# ═══════════════════════════════════════════════════════════════
# TRADINGVIEW WEBHOOK RECEIVER (v4.98)
# ═══════════════════════════════════════════════════════════════
# TradingView alerts (from nvda_strategy.pine, or any alert you write) POST a
# JSON message here and the bot places the order on Alpaca. Alert message:
#   {"passphrase": "...", "ticker": "NVDA", "action": "buy" | "sell" | "close",
#    "strategy": "SPIKE", "stop": 181.20, "target": 184.90, "qty": 0}
# - "buy"/"long" opens a long, "sell"/"short" opens a short, "close"/"exit"
#   closes any open TradingView trade.
# - stop/target are optional: if missing the bot uses stop_atr_mult × ATR and
#   risk_reward like a dashboard ATR trade.
# - qty is optional: 0/missing sizes like the bot's own trades
#   (risk_per_trade of equity / stop distance); always capped by
#   max_position_pct.
# TradingView can only reach a public HTTPS URL, so run a tunnel (ngrok or
# cloudflared) to 127.0.0.1:<tv_port>. The passphrase is the only thing
# keeping strangers who find that URL from trading — keep it long and secret.

_TV_RECENT = {}          # payload fingerprint -> time, to drop TradingView retries
_TV_MAX_BODY = 10_000


def _tv_parse_direction(action):
    a = str(action or "").strip().lower()
    if a in ("buy", "long", "bullish"):
        return "bullish"
    if a in ("sell", "short", "bearish"):
        return "bearish"
    if a in ("close", "exit", "flat", "close_all"):
        return "close"
    return None


def _tv_qty(direction, stop, qty_req, use_atr):
    api, equity = get_alpaca()
    if api is None or equity <= 0:
        raise ValueError("Cannot reach Alpaca to size the order")
    price = float(api.get_latest_trade(CONFIG["ticker"]).price)
    max_qty = max(1, int(equity * CONFIG["max_position_pct"] / price))
    if qty_req > 0:
        return min(qty_req, max_qty)
    if use_atr:
        risk = CONFIG["stop_atr_mult"] * (state.get("last_atr") or 0)
    else:
        risk = abs(price - stop)
    if risk <= 0:
        raise ValueError("No stop distance available to size the order — send qty in the alert")
    return max(1, min(int(equity * CONFIG["risk_per_trade"] / risk), max_qty))


def handle_tradingview_alert(alert):
    """Validate and execute one TradingView alert. Returns a short result string."""
    ticker = str(alert.get("ticker", CONFIG["ticker"])).split(":")[-1].upper()
    if ticker != CONFIG["ticker"]:
        raise ValueError(f"Alert is for {ticker}, bot trades {CONFIG['ticker']} — ignored")
    direction = _tv_parse_direction(alert.get("action"))
    if direction is None:
        raise ValueError(f"Unknown action {alert.get('action')!r} (use buy, sell or close)")
    strat = str(alert.get("strategy", "TV"))[:40]

    if direction == "close":
        tv_trades = [t for t in get_active_trades()
                     if t.get("strategy") == "MANUAL" and t.get("source") == "tradingview"]
        if not tv_trades:
            return "close: no open TradingView trade"
        for t in tv_trades:
            close_manual_trade(t.get("order_id", ""), 0.0)
        return f"closed {len(tv_trades)} TradingView trade(s)"

    if get_active_trades():
        raise ValueError("A position is already open — TradingView entry skipped "
                         "(the bot holds one NVDA position at a time)")
    stop   = float(alert.get("stop") or 0)
    target = float(alert.get("target") or 0)
    use_atr = stop <= 0 or target <= 0
    qty = _tv_qty(direction, stop, int(float(alert.get("qty") or 0)), use_atr)
    res = open_manual_trade(direction, stop, target, qty, managed=True,
                            use_atr=use_atr, atr_mult=CONFIG["stop_atr_mult"],
                            source="tradingview", note=f"TradingView {strat}")
    return (f"{direction} {qty} @ ${res['entry']:.2f} stop ${res['stop']:.2f} "
            f"target ${res['target']:.2f} ({strat})")


def _tv_process(alert):
    try:
        log(f"TradingView alert → {handle_tradingview_alert(alert)}", "TRADE")
    except Exception as e:
        log(f"TradingView alert rejected: {e}", "WARN")


class TradingViewWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _reply(self, code, payload):
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        except (ConnectionAbortedError, BrokenPipeError):
            pass

    def do_GET(self):
        self._reply(200, {"ok": True, "service": "nvda-autotrader tradingview webhook"})

    def do_POST(self):
        if self.path.split("?")[0] not in ("/", "/tv_webhook"):
            self._reply(404, {"ok": False})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > _TV_MAX_BODY:
                raise ValueError("bad length")
            raw = self.rfile.read(length)
            alert = json.loads(raw.decode("utf-8"))
            if not isinstance(alert, dict):
                raise ValueError("not an object")
        except Exception:
            self._reply(400, {"ok": False, "error": "Alert message must be a JSON object"})
            return
        given = str(alert.get("passphrase", ""))
        if not TV_WEBHOOK_PASSPHRASE or not hmac.compare_digest(
                given.encode(), TV_WEBHOOK_PASSPHRASE.encode()):
            log(f"TradingView webhook: bad passphrase from {self.client_address[0]}", "WARN")
            self._reply(403, {"ok": False, "error": "bad passphrase"})
            return
        # TradingView retries when a reply is slow; drop exact repeats for 30s.
        now = time.time()
        for k in [k for k, ts in _TV_RECENT.items() if now - ts > 30]:
            _TV_RECENT.pop(k, None)
        fp = hashlib.sha256(raw).hexdigest()
        if fp in _TV_RECENT:
            self._reply(200, {"ok": True, "duplicate": True})
            return
        _TV_RECENT[fp] = now
        # Reply right away (TradingView gives up after a few seconds) and
        # place the order in the background — results go to the bot log.
        threading.Thread(target=_tv_process, args=(alert,), daemon=True).start()
        self._reply(200, {"ok": True, "accepted": True})


def start_tradingview_webhook():
    if not TV_WEBHOOK_ENABLED:
        return
    host = os.environ.get("NVDA_TV_HOST", "127.0.0.1")

    def _run():
        while True:
            try:
                srv = ThreadingHTTPServer((host, TV_WEBHOOK_PORT), TradingViewWebhookHandler)
                log(f"TradingView webhook listening on {host}:{TV_WEBHOOK_PORT} "
                    f"(signal source: {SIGNAL_SOURCE})")
                srv.serve_forever()
            except OSError as e:
                log(f"TradingView webhook could not bind port {TV_WEBHOOK_PORT}: {e}", "ERROR")
                time.sleep(30)
            except Exception as e:
                log(f"TradingView webhook crashed: {e} — restarting in 5s", "WARN")
                time.sleep(5)

    threading.Thread(target=_run, daemon=True).start()

# ═══════════════════════════════════════════════════════════════
# DAILY RESET
# ═══════════════════════════════════════════════════════════════

def reset_daily_state():
    today = now_local().date()
    if state["last_date"] != today:
        state["traded_today"]       = False
        state["trades_today"]       = 0
        state["daily_pnl"]          = 0.0
        # Clear price history on new day — removes any stale/bad values
        state["price_history"]      = [p for p in state.get("price_history", [])
                                        if 50 < p.get("p", 0) < 2000]
        state["order_failed_today"] = False
        # Close any open Alpaca positions before resetting — prevents orphaned trades.
        # CRITICAL: Only close if this is a genuine new calendar day reset, NOT a
        # same-day midday restart. A midday restart will have state["last_date"] as ""
        # (default) even though it's the same day — check bod_date/state-file-date
        # to distinguish. bod_date is set during morning BOD setup and persists
        # through restarts; _state_file_date (v4.54) is set from session_state.json's
        # own saved date on every load_state() call and doesn't depend on a trade
        # CSV existing yet, so it correctly catches a restart shortly after the
        # day's first trade opens (before bod_date/any CSV would otherwise exist).
        _is_same_day_restart = (state.get("bod_date") == str(today)
                                 or state.get("_state_file_date") == str(today))
        # v4.53 fix: state["active_trades"]/["active_trade"] were being wiped
        # unconditionally right after this block, even on a same-day restart —
        # so the "preserving open positions" log below was a lie: the trades
        # just restored by load_state() were discarded from memory a moment
        # later, leaving the bot blind to a real open Alpaca position (same
        # failure class as the v4.52 EOD desync, but on the restart path).
        # Now the wipe only happens on a genuine new-day reset.
        if not _is_same_day_restart:
            still_open = False
            # v4.97 fix: this used to unconditionally try to close ANY open
            # trade on a new calendar day — fine before overnight-carrying
            # strategies existed, but SWING-6M (v4.94) is SUPPOSED to cross
            # midnight while still under its hold-cap. This block submitted
            # a close order at every single midnight it was held anyway,
            # and when the market was closed the order just sat pending
            # rather than failing outright — confirmed live as the repeated
            # "a closing market order is already pending" messages, meaning
            # a stale close order from a PRIOR midnight could sit in
            # Alpaca's queue and fill unexpectedly at a LATER market open,
            # independent of the trade's real stop/target. Compounded by a
            # separate bug (the _trades.csv outcome field writing Python
            # None instead of the literal string "OPEN" for a still-open
            # row, breaking _find_open_trade_in_recent_logs()'s recovery
            # lookup — also fixed this version) and the watchdog's hard
            # os._exit() possibly landing between saves: together these let
            # a legitimate SWING-6M position get relabeled "RESTORED" after
            # a crash/restart, losing its exemption and triggering this
            # exact close-attempt loop all weekend (confirmed live
            # 2026-10-03, caught by the user noticing the mislabeled trade).
            _non_exempt_trades = [
                t for t in get_active_trades()
                if not (t.get("strategy") == "SWING-6M"
                        and isinstance(t.get("opened_at"), datetime)
                        and int(np.busday_count(t["opened_at"].date(), today))
                            < CONFIG.get("swing_max_hold_days", 10))
            ]
            if _non_exempt_trades:
                log("New day detected — closing any open positions before reset", "WARN")
                try:
                    _api_reset, _ = get_alpaca()
                    if _api_reset:
                        close_all(_api_reset)
                        # v4.86 CRITICAL fix: close_all() can return True having
                        # only confirmed a closing order is already pending
                        # (e.g. a "day, market" order queued pre-market that
                        # can't fill until 9:30 ET) — NOT that the position is
                        # actually flat. Confirmed live 2026-09-11: this wiped
                        # active_trades to [] while Alpaca still showed 93
                        # open shares, orphaning the position from the bot's
                        # own tracking — get_active_trades() then reported
                        # empty, so the just-fixed main() monitoring loop had
                        # nothing to call monitor_trade() on even though it
                        # was working correctly. Verify actual flatness before
                        # wiping local state; if still open, keep tracking it
                        # so monitoring continues instead of going blind.
                        still_open = get_position(_api_reset) is not None
                except Exception as _e:
                    log(f"Could not close positions on daily reset: {_e}", "WARN")
            if still_open:
                log("Position still open after close attempt (likely a pre-market "
                    "order waiting for the market to reopen) — keeping it tracked "
                    "so monitoring continues, not wiping active_trades", "WARN")
            elif not _non_exempt_trades and get_active_trades():
                # All currently-tracked trades are exempt overnight-carry
                # trades (e.g. SWING-6M under its hold cap) — no close was
                # even attempted above, so don't fall through to the wipe
                # below; that's for the genuinely-nothing-left-open case.
                log("New day detected — all open positions are exempt "
                    "overnight-carry trades, preserving them untouched", "INFO")
            else:
                state["active_trades"] = []
                state["active_trade"]  = None
        elif get_active_trades():
            log("Same-day restart detected — preserving open positions (not closing)", "INFO")
        state["closed_trade"]       = None
        state["closed_trades_today"] = []
        state["best_fvg_today"]     = None
        state["mtf_fetched_today"]  = False
        state["swing_extremes_fetched_today"] = False
        state["mtf_bias"]           = "neutral"
        state["weekly_trend"]       = "neutral"
        state["monthly_trend"]      = "neutral"
        state["gap_direction"]      = "neutral"
        state["gap_pct"]            = 0.0
        state["prev_close"]         = 0.0
        state["best_score_today"]   = 0
        state["all_fvgs_today"]     = []
        state["daily_events"]       = []
        state["last_date"]          = today
        state["fetch_errors_today"] = 0
        # v4.88 fix: _refresh_market_clock() (caches today's scheduled close,
        # e.g. for half-days) used to only ever run once, at process startup.
        # That was fine when the bot always restarted fresh each morning, but
        # the v4.86 fix now keeps a single process alive across midnight and
        # weekends on purpose — so a process that's been running since Friday
        # would still be using Friday's cached close time on Monday. Refresh
        # it here, once per genuine new day, so a half-day or holiday-adjacent
        # schedule change is never missed just because the process didn't
        # happen to restart.
        _refresh_market_clock()
        # Reset strategy state for new day
        state["active_strategy"]    = "FVG"
        state["strategy_reason"]    = ""
        state["kz_strategy_set"]    = None
        state["last_vwap"]          = 0
        state["last_vwap_upper"]    = 0
        state["last_vwap_lower"]    = 0
        state["last_atr"]           = 0
        state["vwap_setups_today"]      = []
        state["last_candle_count_prev"] = 0
        state["stale_scan_count"]       = 0
        state["network_ok"]             = True
        state["fvg_skipped_distance"]   = 0
        state["trade_complete_logged"]  = False
        state["_last_kz_logged"]        = ""
        state["_spike_cooldown_until"]  = ""
        state["daily_momentum"]         = "neutral"  # recalculated at next KZ open
        state["live_equity"]             = 0          # force fresh Alpaca fetch next poll
        state["_equity_poll_count"]      = 0          # reset so first poll of new day refreshes immediately

        print(f"\n{'='*55}")
        print(f"  NEW SESSION: {today}")
        print(f"  Local timezone:  {now_local().strftime('%Z')}")
        print(f"{'='*55}\n")
        # Clear Yahoo Finance cache and rate limit backoff for new session
        _yf_cache.clear()
        global _yf_rate_limited_until
        _yf_rate_limited_until = None
        # MTF analysis runs at first kill zone scan, not here
        # (avoids midnight Yahoo fetches when bot runs overnight)

    # v4.87 CRITICAL fix: this used to live INSIDE the `if state["last_date"]
    # != today:` block above — which meant it depended on that block actually
    # running to ever get a chance to set bod_equity. Now that last_date is
    # correctly restored across a same-day restart (see load_state()), that
    # outer block is correctly SKIPPED on a same-day restart — which meant
    # this code, nested inside it, would never run again for the rest of the
    # day if bod_date happened to still be unset (e.g. the first restart
    # after this persistence fix landed, with an old-format state file).
    # Confirmed live 2026-09-11: bod_equity stayed at 0 all afternoon,
    # silently falling back to a less accurate P&L baseline. Pulled out to
    # its own top-level check, run every call — cheap (a string compare) when
    # already set for today, only hits Alpaca when genuinely needed.
    _today_str = str(today)
    if state.get("bod_date") != _today_str or state.get("bod_equity", 0) <= 0:
        api_result = get_alpaca()
        if api_result[0] is not None:
            _cur_equity = api_result[1]
            state["session_start_equity"] = _cur_equity
            state["bod_equity"] = _cur_equity
            state["bod_date"]   = _today_str
            log(f"BOD equity set: ${_cur_equity:,.2f} for {_today_str}")

# ═══════════════════════════════════════════════════════════════
# YAHOO FINANCE CACHE
_yf_cache        = {}   # {ticker: {"df": DataFrame, "fetched_at": datetime}}
YF_CACHE_SECONDS = 290  # refresh just before each new 5-min bar (~12x/hour max)
YF_BACKOFF_SECONDS = 900       # wait 15 min after a rate limit hit


def _in_yf_fetch_window():
    """
    Returns True only during kill zones and 5 minutes before each opens.
    All Yahoo Finance fetches must pass this check to avoid rate limiting.
    Windows (ET): 09:25-11:00, 11:55-13:00, 13:55-15:00
    """
    now_et = datetime.now(MARKET_TZ)
    t = now_et.hour * 60 + now_et.minute
    windows = [
        (9*60+25,  11*60),   # 09:25-11:00 ET (5 min before morning KZ)
        (11*60+55, 13*60),   # 11:55-13:00 ET (5 min before noon KZ)
        (13*60+55, 15*60),   # 13:55-15:00 ET (5 min before afternoon KZ)
    ]
    return any(start <= t <= end for start, end in windows)
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════════════

def _parse_candles_to_df(bars_data, time_key, today_et):
    """Shared helper — converts a list of bar dicts to a filtered DataFrame.

    Filters to today's session first. If today has no bars yet (IEX lag on
    slow/half-day sessions where bars may not publish for 15-30min after open),
    falls back to the most recent prior trading day's bars so the scanner has
    something to work with rather than returning None and going dark.
    """
    df = pd.DataFrame(bars_data)
    df["ts"] = pd.to_datetime(df[time_key], utc=True)
    df = df.set_index("ts")
    if "o" in df.columns:
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    elif "open" in df.columns:
        df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    df.index = df.index.tz_convert(MARKET_TZ)
    df = df.sort_index()
    df = df[["Open", "High", "Low", "Close", "Volume"]]

    # Try today's session first
    market_open  = datetime(today_et.year, today_et.month, today_et.day, 9, 30, tzinfo=MARKET_TZ)
    market_close = datetime(today_et.year, today_et.month, today_et.day, 16, 0, tzinfo=MARKET_TZ)
    today_df = df[(df.index >= market_open) & (df.index <= market_close)]
    if len(today_df) > 0:
        return today_df

    # Today has no bars yet — IEX lag on slow/half-day sessions.
    # Fall back to the most recent prior day that has bars so the scanner
    # isn't completely blind while waiting for IEX to publish today's data.
    if len(df) > 0:
        most_recent_date = df.index[-1].date()
        if most_recent_date != today_et:
            prior_open  = datetime(most_recent_date.year, most_recent_date.month,
                                   most_recent_date.day, 9, 30, tzinfo=MARKET_TZ)
            prior_close = datetime(most_recent_date.year, most_recent_date.month,
                                   most_recent_date.day, 16, 0, tzinfo=MARKET_TZ)
            prior_df = df[(df.index >= prior_open) & (df.index <= prior_close)]
            if len(prior_df) > 0:
                log(f"IEX has no {today_et} bars yet — using {most_recent_date} "
                    f"as context ({len(prior_df)} bars) while waiting for today's feed", "WARN")
                return prior_df

    return None


def _fetch_yfinance(ticker, bars=200):
    """
    Fetch candles from Yahoo Finance (primary source).
    Free, no API key required, separate from Alpaca servers.
    Uses a 290-second cache to avoid Yahoo rate limiting —
    only fetches from Yahoo when a new 5-min bar is due.
    Returns DataFrame or None.
    """
    global _yf_cache, _yf_rate_limited_until
    now = datetime.now(MARKET_TZ)

    # Skip Yahoo entirely if we're in a rate limit backoff window
    if _yf_rate_limited_until is not None and now < _yf_rate_limited_until:
        cached = _yf_cache.get(ticker)
        return cached["df"] if cached else None

    # Only fetch from Yahoo during kill zones or 5 min before one opens
    # This prevents wasted requests during the between-zone waiting periods
    if not _in_yf_fetch_window():
        # Outside fetch window — return cache if available, else None
        cached = _yf_cache.get(ticker)
        return cached["df"] if cached else None

    # Return cached data if still fresh (within a 5-min bar)
    cached = _yf_cache.get(ticker)
    if cached is not None:
        age = (now - cached["fetched_at"]).total_seconds()
        if age < YF_CACHE_SECONDS:
            return cached["df"]

    # Cache stale or empty — fetch fresh data from Yahoo
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
        today_et    = now.date()
        start_fetch = (now - timedelta(days=2)).strftime("%Y-%m-%d")
        end_fetch   = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        tk  = yf.Ticker(ticker)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df  = tk.history(start=start_fetch, end=end_fetch, interval="5m", auto_adjust=False)
        if df is None or df.empty:
            return None
        # yfinance returns tz-aware index — convert to ET
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(MARKET_TZ)
        df = df.sort_index()
        # Filter to today's session only
        market_open  = datetime(today_et.year, today_et.month, today_et.day, 9, 30, tzinfo=MARKET_TZ)
        market_close = datetime(today_et.year, today_et.month, today_et.day, 16, 0, tzinfo=MARKET_TZ)
        df = df[(df.index >= market_open) & (df.index <= market_close)]
        if df.empty:
            return None
        df = df.rename(columns={"Open": "Open", "High": "High", "Low": "Low",
                                 "Close": "Close", "Volume": "Volume"})
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        # Store in cache
        _yf_cache[ticker] = {"df": df, "fetched_at": now}
        return df
    except ImportError:
        log("yfinance not installed — run: pip install yfinance", "WARN")
        return None
    except Exception as e:
        err_str = str(e)
        if "Too Many Requests" in err_str or "Rate limited" in err_str:
            _yf_rate_limited_until = now + timedelta(seconds=YF_BACKOFF_SECONDS)
            log(f"Yahoo Finance rate limited — backing off for "
                f"{YF_BACKOFF_SECONDS//60} min until "
                f"{_yf_rate_limited_until.strftime('%H:%M')} local", "WARN")
        else:
            log(f"Yahoo Finance fetch failed: {e} — falling back to Alpaca", "WARN")
        return None


def _fetch_alpaca(ticker, bars=200, attempt=1):
    """
    Fetch candles from Alpaca IEX (fallback source).
    Used when Polygon is unavailable or key not set.
    """
    today_et    = datetime.now(MARKET_TZ).date()
    start_fetch = datetime.now(MARKET_TZ) - timedelta(days=2)
    url = (
        f"{ALPACA_DATA_URL}/v2/stocks/{ticker}/bars"
        f"?timeframe=5Min"
        f"&start={start_fetch.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&limit={bars}"
        f"&adjustment=raw"
        f"&feed=iex"
    )
    headers = {
        "APCA-API-KEY-ID":     ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }
    try:
        resp = requests.get(url, headers=headers, timeout=CONFIG["fetch_timeout"])
        if resp.status_code == 429:
            log("Alpaca rate limited — waiting 20s...", "WARN")
            time.sleep(20)
            return _fetch_alpaca(ticker, bars, attempt + 1)
        if resp.status_code != 200:
            log(f"Alpaca data error {resp.status_code}: {resp.text[:200]}", "ERROR")
            return None
        data      = resp.json()
        bars_data = data.get("bars", [])
        if not bars_data:
            log(f"Alpaca returned no bars for {ticker} — market may not be open yet.", "WARN")
            return None
        return _parse_candles_to_df(bars_data, "t", today_et)
    except Exception as e:
        error_type = type(e).__name__
        if attempt < CONFIG["fetch_retries"]:
            log(f"Fetch attempt {attempt} failed [{error_type}]: {e} — retrying in 10s...", "WARN")
            time.sleep(10)
            return _fetch_alpaca(ticker, bars, attempt + 1)
        else:
            state["fetch_errors_today"] += 1
            log(f"Fetch failed after {CONFIG['fetch_retries']} attempts [{error_type}]: {e}", "ERROR")
            return None


def fetch_candles(ticker, bars=200, attempt=1):
    """
    Primary: Alpaca IEX (every scan).
    Fallback: Yahoo Finance hourly cache (max once per hour, only when IEX has < 5 bars).

    Logic:
    - If IEX has >= 5 bars, use it — enough for a full scan.
    - If IEX has 1-4 bars it is still warming up; use cached YF as a floor
      (doesn't fetch YF again — returns the in-memory cache from the last fetch).
    - If IEX has 0 bars AND it's been >= 10 min since kill zone open,
      allow a fresh YF fetch (IEX may be having issues, not just warming up).
    - If IEX has 0 bars and < 10 min since open, suppress entirely — too early.
    """
    df_iex = _fetch_alpaca(ticker, bars, attempt)
    iex_count = len(df_iex) if df_iex is not None else 0

    # IEX has enough bars for a full scan — use it
    if iex_count >= 5:
        return df_iex

    # IEX warming up (1-4 bars): serve from YF cache WITHOUT triggering a new fetch
    # This prevents rate limits while still giving the scanner enough history to work with
    if iex_count >= 1:
        cached = _yf_hourly_cache.get(ticker)
        if cached is not None and len(cached) >= 5:
            return cached  # Return stale YF cache — no new fetch
        # Cache is empty/None — check if YF backoff has expired before giving up
        if _yf_rate_limited_until and datetime.now(MARKET_TZ) < _yf_rate_limited_until:
            return df_iex  # Still in backoff — return thin IEX data
        # Backoff expired or never set — try a fresh YF fetch to rebuild cache
        return _fetch_yf_hourly_fallback(ticker, bars)

    # IEX has 0 bars — check if we should try a fresh YF fetch
    kz_start = get_current_kill_zone()
    if kz_start:
        try:
            h, m      = int(kz_start.split(":")[0]), int(kz_start.split(":")[1])
            kz_open   = datetime.now(MARKET_TZ).replace(hour=h, minute=m, second=0, microsecond=0)
            mins_open = (datetime.now(MARKET_TZ) - kz_open).total_seconds() / 60
            if mins_open < 10:
                return None  # Too early — IEX simply hasn't produced bars yet
        except Exception:
            pass

    # IEX empty AND >= 10 min since open (or no kill zone) — try YF hourly fallback
    return _fetch_yf_hourly_fallback(ticker, bars)


# ── Hourly YF fallback cache ─────────────────────────────────────
_yf_hourly_cache        = {}  # {ticker: DataFrame}
_yf_hourly_last_fetch   = {}  # {ticker: datetime} time of last successful or attempted fetch
_yf_rate_limited_until  = None  # datetime when global rate limit backoff expires
_YF_MIN_INTERVAL_MIN    = 60   # minimum minutes between YF fetches per ticker

def _fetch_yf_hourly_fallback(ticker, bars=200):
    """
    Fetch Yahoo Finance at most once per hour per ticker.
    Backs off 30 minutes after a rate limit hit.
    Never hammers YF — uses cached data aggressively.
    """
    global _yf_hourly_cache, _yf_hourly_last_fetch, _yf_rate_limited_until
    now_et = datetime.now(MARKET_TZ)

    # Respect global rate limit backoff
    if _yf_rate_limited_until and now_et < _yf_rate_limited_until:
        return _yf_hourly_cache.get(ticker)

    # Return cached data if fetched within the minimum interval
    last = _yf_hourly_last_fetch.get(ticker)
    if last is not None:
        elapsed = (now_et - last).total_seconds() / 60
        if elapsed < _YF_MIN_INTERVAL_MIN:
            return _yf_hourly_cache.get(ticker)

    # Attempt a fresh Yahoo fetch — with timeout to prevent blocking the entire bot
    try:
        _yf_result = [None]
        _yf_err    = [None]
        def _yf_worker():
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    _yf_result[0] = yf.Ticker(ticker).history(period="2d", interval="5m")
            except Exception as _we:
                _yf_err[0] = _we
        _t = threading.Thread(target=_yf_worker, daemon=True)
        _t.start()
        _t.join(timeout=8)  # 8 second hard timeout — prevents blocking monitor loop
        if _t.is_alive():
            # YF hung — treat as rate limit to back off
            _yf_hourly_last_fetch[ticker] = now_et
            _yf_rate_limited_until = now_et + timedelta(minutes=30)
            log(f"YF fetch timed out — backing off 30 min "
                f"(retry after {_yf_rate_limited_until.strftime('%H:%M')} ET)", "WARN")
            return _yf_hourly_cache.get(ticker)  # return cached data if available
        if _yf_err[0] is not None:
            raise _yf_err[0]
        raw = _yf_result[0]
        _yf_hourly_last_fetch[ticker] = now_et  # mark attempt regardless of result
        if raw is None or raw.empty:
            _yf_hourly_cache[ticker] = None
            return None
        raw.index = raw.index.tz_convert(MARKET_TZ)
        df = raw[["Open","High","Low","Close","Volume"]].copy()
        df = df.tail(bars)
        _yf_hourly_cache[ticker] = df
        mins_until_next = _YF_MIN_INTERVAL_MIN
        log(f"YF fallback: loaded {len(df)} candles for {ticker} "
            f"(next fetch in ~{mins_until_next} min)", "INFO")
        return df
    except Exception as e:
        _yf_hourly_last_fetch[ticker] = now_et  # count failed attempt too
        # DO NOT wipe cache on rate limit — keep last good data so fetch_candles
        # can still serve stale-but-valid bars during the backoff window
        if "Too Many Requests" in str(e) or "Rate" in str(e) or "429" in str(e):
            _yf_rate_limited_until = now_et + timedelta(minutes=30)
            log(f"YF rate limited — backing off 30 min "
                f"(retry after {_yf_rate_limited_until.strftime('%H:%M')} ET)", "WARN")
        else:
            log(f"YF fallback failed: {e}", "WARN")
        return None

# ═══════════════════════════════════════════════════════════════
# NETWORK HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

def check_network():
    """Ping Google DNS to verify internet connectivity."""
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        if not state["network_ok"]:
            log("Network restored — resuming normal operation", "INFO")
        state["network_ok"] = True
        return True
    except Exception:
        if state["network_ok"]:
            log("NETWORK FAILURE — cannot reach internet. Data may be stale. Check WiFi/hotspot.", "ERROR")
            state["status"] = "NETWORK DOWN — check WiFi/hotspot"
        state["network_ok"] = False
        return False


def check_stale_data(new_candle_count):
    """
    Warn if candle count hasn't grown for too many consecutive scans.
    Threshold is scaled for 15-second poll interval:
      - Warn after 8 scans (2 min) — a new 5-min bar should arrive within 5 min
      - Force YF refresh after 20 scans (5 min) — something is genuinely stuck
    """
    prev = state["last_candle_count_prev"]
    if new_candle_count > prev:
        state["stale_scan_count"]       = 0
        state["last_candle_count_prev"] = new_candle_count
        return True
    state["stale_scan_count"] += 1
    # Only fire STALE DATA warning once per stuck episode (at scan 8) —
    # then suppress until candle count changes. Avoids log spam between 5-min bars.
    if state["stale_scan_count"] == 8:
        log(f"STALE DATA — candle count stuck at {new_candle_count} "
            f"for {state['stale_scan_count']} scans — running network check...", "WARN")
        ok = check_network()
        if ok:
            log(f"Network OK — candle count stable at {new_candle_count} "
                f"(may be between 5-min bars — will log again if still stuck after 20 scans)", "INFO")
    # After 20 stale scans (~5 min), force YF hourly cache to refresh
    if state["stale_scan_count"] >= 20 and state["stale_scan_count"] % 5 == 0:
        # Only force-refresh every 5 scans — not every scan — to avoid log spam
        ticker = CONFIG["ticker"]
        _yf_hourly_last_fetch.pop(ticker, None)
        # Also clear rate limit timer so the forced fetch actually goes through
        global _yf_rate_limited_until
        if _yf_rate_limited_until and datetime.now(MARKET_TZ) >= _yf_rate_limited_until:
            _yf_rate_limited_until = None  # backoff window has passed — allow retry
        if state["stale_scan_count"] == 20:
            log(f"STALE DATA {state['stale_scan_count']} scans — "
                f"forcing YF cache refresh (rate limit cleared: {_yf_rate_limited_until is None})", "WARN")
    state["last_candle_count_prev"] = new_candle_count
    return True


# ═══════════════════════════════════════════════════════════════
# TREND DETECTION
# ═══════════════════════════════════════════════════════════════

def get_trend(df):
    if df is None or len(df) < 5:
        return "neutral"
    try:
        # Use available candles up to trend_lookback
        lookback  = min(CONFIG["trend_lookback"], len(df))
        threshold = CONFIG["trend_threshold"]
        start_px  = df["Close"].iloc[-lookback]
        end_px    = df["Close"].iloc[-1]
        pct_chg   = (end_px - start_px) / start_px * 100
        if pct_chg > threshold:
            return "bullish"
        elif pct_chg < -threshold:
            return "bearish"
        else:
            return "neutral"
    except Exception as e:
        # v4.74 fix: silently returned "neutral" on ANY exception, no log.
        # "neutral" is a real, consequential trading signal here (feeds
        # RANGE's hard trend filter, MTF score thresholds) — a real bug in
        # this function would masquerade as a legitimate "no trend" market
        # read instead of surfacing as an error.
        log(f"get_trend() failed — defaulting to neutral (may not reflect "
            f"the real trend): {type(e).__name__}: {e}", "WARN")
        return "neutral"

# ═══════════════════════════════════════════════════════════════
# QQQ DIRECTION
# ═══════════════════════════════════════════════════════════════

def get_qqq_direction():
    df = fetch_candles(CONFIG["qqq_ticker"], bars=20)
    if df is None or len(df) < 12:
        return "neutral"
    try:
        chg = (df["Close"].iloc[-1] - df["Close"].iloc[-12]) / df["Close"].iloc[-12] * 100
        return "bearish" if chg < -0.15 else "bullish" if chg > 0.15 else "neutral"
    except Exception as e:
        # v4.74 fix: same silent-neutral-on-any-exception issue as get_trend()
        # — this feeds QQQ-alignment scoring, so a real bug here would look
        # like a legitimate "QQQ flat" reading instead of surfacing.
        log(f"get_qqq_direction() failed — defaulting to neutral: "
            f"{type(e).__name__}: {e}", "WARN")
        return "neutral"


# ═══════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME TREND ANALYSIS (v4.10)
# ═══════════════════════════════════════════════════════════════

def get_daily_closes(ticker, n_days=65):
    """
    Fetch last n_days of daily closing prices via Alpaca.
    Used for weekly (20-day) and monthly (60-day) trend detection.
    Uses Alpaca's daily bar endpoint — no rate limiting issues.
    Returns list of closes, most recent last, or None on failure.
    """
    try:
        api, _ = get_alpaca()
        if api is None:
            return None
        end_dt   = datetime.now(MARKET_TZ)
        start_dt = end_dt - timedelta(days=n_days * 2)
        # v4.91 CRITICAL fix: `limit` was set to n_days (65), but a single
        # Alpaca request isn't paginated here — Alpaca fills `limit` from the
        # OLDEST bars in [start, end] first. Since the n_days*2 calendar-day
        # window normally contains ~90+ trading days (well over 65), this
        # silently returned the OLDEST 65 bars in range instead of the most
        # recent 65 — confirmed live: on 2026-09-16 this returned closes from
        # 2026-05-11 through 2026-08-12 (should have reached through
        # 2026-09-15). Every weekly/monthly MTF trend read, daily_momentum
        # calc, and opening-gap comparison sourced from this function has
        # been working off data ~5 weeks stale since this code went live.
        # Fix: request a limit far larger than n_days could ever need (same
        # pattern as _fetch_daily_bars_for_chart()'s limit=1000 below) so the
        # single request always reaches all the way to `end_dt` — the
        # existing `closes[-n_days:]` trailing slice below was already
        # correct, it just never had the right data to slice from.
        url = (
            f"{ALPACA_DATA_URL}/v2/stocks/{ticker}/bars"
            f"?timeframe=1Day"
            f"&start={start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            f"&limit=1000"
            f"&adjustment=raw"
            f"&feed=iex"
        )
        headers = {
            "APCA-API-KEY-ID":     ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        }
        resp = requests.get(url, headers=headers, timeout=CONFIG["fetch_timeout"])
        if resp.status_code != 200:
            log(f"Daily bars fetch error {resp.status_code}", "WARN")
            return None
        bars_data = resp.json().get("bars", [])
        if not bars_data or len(bars_data) < 5:
            return None
        closes = [float(b["c"]) for b in bars_data]
        return closes[-n_days:]
    except Exception as e:
        log(f"Daily close fetch failed: {e}", "WARN")
        return None


def _fetch_daily_bars_for_chart(ticker, n_days=200):
    """
    Fetch up to n_days of daily closes WITH their dates, for the dashboard's
    6-month chart view (GET /daily_history). Deliberately separate from:
      - get_daily_closes() above (MTF trend calc — closes only, no dates,
        capped at 65 days — not enough range and missing the date field
        the chart needs for x-axis labels)
      - the minute-level rolling price_history buffer (state["price_history"]
        / nvda_price_history.json) — capped at 2000 points, which in
        practice only covers about 1-2 weeks of market-hours polling,
        nowhere near enough for a multi-month view
    Returns [{"t": "YYYY-MM-DD", "p": close, "h": high, "l": low}, ...]
    sorted ascending (oldest first), or [] on failure — the dashboard shows
    "no data" rather than erroring if this comes back empty. The "h"/"l"
    fields were added in v4.84 to feed get_swing_extremes() (SWING-3M/6M
    strategy) — the dashboard chart still only reads "t"/"p".

    v4.83 fix: this originally called get_alpaca() first, which does its own
    full account-info round trip before this function's OWN bars request
    even starts — confirmed live, the endpoint took ~14.6s end to end.
    Because the dashboard's HTTPServer is single-threaded (not
    ThreadingHTTPServer), that stalled the ENTIRE dashboard — including the
    regular 5s /data poll driving the live price/status — for the whole 15s,
    not just the chart tab. _fetch_alpaca() (the intraday candle fetcher)
    never had this problem because it never called get_alpaca() either — it
    goes straight to the raw request with the module-level keys, same as
    this now does.
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return []
    try:
        end_dt   = datetime.now(MARKET_TZ)
        start_dt = end_dt - timedelta(days=n_days)
        url = (
            f"{ALPACA_DATA_URL}/v2/stocks/{ticker}/bars"
            f"?timeframe=1Day"
            f"&start={start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            f"&limit=1000"
            f"&adjustment=raw"
            f"&feed=iex"
        )
        headers = {
            "APCA-API-KEY-ID":     ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        }
        resp = requests.get(url, headers=headers, timeout=CONFIG["fetch_timeout"])
        if resp.status_code != 200:
            log(f"Daily chart bars fetch error {resp.status_code}: {resp.text[:200]}", "WARN")
            return []
        bars_data = resp.json().get("bars", [])
        return [{"t": b["t"][:10], "p": round(float(b["c"]), 2),
                 "h": round(float(b["h"]), 2), "l": round(float(b["l"]), 2)} for b in bars_data]
    except Exception as e:
        log(f"Daily chart bars fetch failed: {type(e).__name__}: {e}", "WARN")
        return []


def get_swing_extremes(ticker):
    """
    v4.84: Cache 3-month and 6-month daily high/low in state, once per day.
    Feeds detect_swing_reversion() for both SWING-3M and SWING-6M. Fetches
    once at 6-month depth and slices the most recent 3-month window from
    the same result, reusing _fetch_daily_bars_for_chart() (built for the
    dashboard's 6-month view) instead of a second Alpaca call pattern.
    """
    try:
        bars = _fetch_daily_bars_for_chart(ticker, n_days=CONFIG["swing_lookback_days_6m"])
        if not bars:
            log("Swing extremes fetch returned no bars — SWING disabled today", "WARN")
            return

        def _extremes(subset):
            highs = [b["h"] for b in subset if b.get("h")]
            lows  = [b["l"] for b in subset if b.get("l")]
            return (round(max(highs), 2), round(min(lows), 2)) if highs and lows else (0.0, 0.0)

        state["swing_high_6m"], state["swing_low_6m"] = _extremes(bars)
        n3m = CONFIG["swing_lookback_days_3m"]
        bars_3m = bars[-n3m:] if len(bars) > n3m else bars
        state["swing_high_3m"], state["swing_low_3m"] = _extremes(bars_3m)

        log(f"Swing range 3M: Low ${state['swing_low_3m']:.2f} | High ${state['swing_high_3m']:.2f} | "
            f"6M: Low ${state['swing_low_6m']:.2f} | High ${state['swing_high_6m']:.2f} "
            f"({len(bars)} daily bars)")
    except Exception as e:
        log(f"get_swing_extremes() failed: {type(e).__name__}: {e}", "WARN")


def classify_trend_slope(closes, label=""):
    """
    Classify trend direction from a list of closing prices.
    Uses linear regression slope normalised by average price.
    Returns "bullish", "bearish", or "neutral".
    """
    if not closes or len(closes) < 5:
        return "neutral"
    try:
        x   = np.arange(len(closes))
        y   = np.array(closes, dtype=float)
        m   = float(np.polyfit(x, y, 1)[0])   # slope per day
        avg = float(np.mean(y))
        pct = (m / avg) * 100                 # daily % move
        if pct > 0.15:
            result = "bullish"
        elif pct < -0.15:
            result = "bearish"
        else:
            result = "neutral"
        if label:
            log(f"MTF {label}: slope {pct:+.3f}%/day → {result.upper()}")
        return result
    except Exception as e:
        log(f"Trend slope calc failed: {e}", "WARN")
        return "neutral"


def analyse_opening_gap(daily_closes, current_price):
    """
    Compare today's opening price to yesterday's close.
    Returns (direction, gap_pct, prev_close).
    """
    if not daily_closes or len(daily_closes) < 2:
        return "neutral", 0.0, 0.0
    prev_close = float(daily_closes[-1])
    if prev_close == 0:
        return "neutral", 0.0, 0.0
    gap_pct = (current_price - prev_close) / prev_close * 100
    if gap_pct > 0.5:
        direction = "bullish"
    elif gap_pct < -0.5:
        direction = "bearish"
    else:
        direction = "neutral"
    return direction, round(gap_pct, 2), round(prev_close, 2)


def get_mtf_bias(ticker):
    """
    v4.10: Fetch weekly and monthly trends plus opening gap.
    Stores results in state and returns combined bias string.

    Bias logic:
      monthly + weekly both bullish  → "strong_bullish"  (long only)
      monthly bullish, weekly neutral → "bullish"         (prefer long)
      monthly bullish, weekly bearish → "neutral"         (possible reversal)
      monthly neutral, any weekly    → "neutral"
      monthly bearish, weekly neutral → "bearish"         (prefer short)
      monthly + weekly both bearish  → "strong_bearish"  (short only)
      monthly bearish, weekly bullish → "neutral"         (possible reversal)
    """
    log("MTF analysis — fetching daily closes...")
    closes = get_daily_closes(ticker, n_days=65)
    if not closes:
        log("MTF analysis failed — defaulting to neutral bias", "WARN")
        state["mtf_bias"]      = "neutral"
        state["weekly_trend"]  = "neutral"
        state["monthly_trend"] = "neutral"
        return "neutral"

    weekly  = classify_trend_slope(closes[-20:], "weekly (20d)")
    monthly = classify_trend_slope(closes[-60:], "monthly (60d)")

    # v4.12: Gap detection uses today's first intraday bar open vs prev daily close
    # (Previously used live snapshot price which drifts throughout the day)
    # v4.91 CRITICAL fix: bars=5 here hit the same truncation bug as
    # get_daily_closes() above — _fetch_alpaca()'s start window covers ~2
    # calendar days (~150+ 5-min bars), but limit=5 made Alpaca return the
    # OLDEST 5 bars in that window, not today's. Confirmed live returning a
    # bar from 2 calendar days earlier instead of today's actual open, which
    # fed analyse_opening_gap() a wrong gap direction/pct. bars=300 is
    # comfortably above the true bar count in that window so nothing gets
    # truncated before _parse_candles_to_df() correctly isolates today's
    # session (or the real most recent prior day if today has no bars yet).
    try:
        today_df = _fetch_alpaca(ticker, bars=300)
        if today_df is not None and len(today_df) > 0:
            cur_px = float(today_df["Open"].iloc[0])   # true opening bar
        else:
            api_r, _ = get_alpaca()
            if api_r:
                snap   = api_r.get_snapshot(ticker)
                cur_px = float(snap.latest_trade.price) if snap and snap.latest_trade else 0
            else:
                cur_px = 0
    except Exception as e:
        # v4.74 fix: silently fell back to cur_px=0, no log. That doesn't
        # just mean "gap unknown" — analyse_opening_gap() would compute a
        # gap of roughly -100% from it and write that into state["gap_pct"]/
        # ["gap_direction"] as if it were real, with zero visibility that the
        # fetch actually failed.
        log(f"Could not fetch opening price for gap detection — gap calc "
            f"will be wrong: {type(e).__name__}: {e}", "WARN")
        cur_px = 0

    gap_dir, gap_pct, prev_close = analyse_opening_gap(closes, cur_px)

    # Combined bias table
    if monthly == "bullish" and weekly == "bullish":
        bias = "strong_bullish"
    elif monthly == "bullish" and weekly == "neutral":
        bias = "bullish"
    elif monthly == "bullish" and weekly == "bearish":
        bias = "neutral"
    elif monthly == "bearish" and weekly == "bearish":
        bias = "strong_bearish"
    elif monthly == "bearish" and weekly == "neutral":
        bias = "bearish"
    elif monthly == "bearish" and weekly == "bullish":
        bias = "neutral"
    else:
        bias = "neutral"

    # Gap reinforces or weakens bias
    if gap_dir == "bullish" and bias in ("neutral", "bullish"):
        bias = "bullish" if bias == "neutral" else bias
    elif gap_dir == "bearish" and bias in ("neutral", "bearish"):
        bias = "bearish" if bias == "neutral" else bias

    state["weekly_trend"]  = weekly
    state["monthly_trend"] = monthly
    state["mtf_bias"]      = bias
    state["gap_direction"] = gap_dir
    state["gap_pct"]       = gap_pct
    state["prev_close"]    = prev_close

    # ── Daily momentum detection ──────────────────────────────────────
    # Checks last 5 daily closes for directional momentum (4 of 5 rule)
    # + price position within 20-day range (lower/upper third)
    # Symmetric: works for bullish bounce off lows AND bearish rollover from highs
    momentum = "neutral"
    try:
        if len(closes) >= 6:
            last5     = closes[-5:]   # last 5 daily closes
            up_days   = sum(1 for i in range(1, 5) if last5[i] > last5[i-1])
            down_days = sum(1 for i in range(1, 5) if last5[i] < last5[i-1])

            # 20-day range position: where is current price vs recent high/low?
            recent20   = closes[-20:]
            hi20, lo20 = max(recent20), min(recent20)
            range20    = hi20 - lo20 if hi20 != lo20 else 1
            cur_close  = closes[-1]
            pct_from_lo = (cur_close - lo20) / range20  # 0 = at low, 1 = at high

            if up_days >= 4 and pct_from_lo <= 0.40:
                momentum = "bullish"   # rising off lows
            elif down_days >= 4 and pct_from_lo >= 0.60:
                momentum = "bearish"   # falling from highs

            if momentum != "neutral":
                emoji = "📈" if momentum == "bullish" else "📉"
                log(f"MOMENTUM {momentum.upper()} {emoji} — "
                    f"{up_days if momentum == 'bullish' else down_days}/4 days "
                    f"{'up' if momentum == 'bullish' else 'down'} | "
                    f"Price at {pct_from_lo*100:.0f}% of 20d range "
                    f"(${lo20:.2f}–${hi20:.2f})")
    except Exception as _me:
        log(f"Momentum detection error: {_me}", "WARN")

    state["daily_momentum"] = momentum

    log(f"MTF bias: {bias.upper()} | "
        f"Monthly: {monthly} | Weekly: {weekly} | "
        f"Gap: {gap_dir} ({gap_pct:+.2f}%) | "
        f"Momentum: {momentum.upper()}")
    return bias

# ═══════════════════════════════════════════════════════════════
# VWAP + ATR CALCULATION
# ═══════════════════════════════════════════════════════════════

def calculate_vwap(df):
    """
    Compute true session VWAP from today's candles.
    VWAP = cumulative(typical_price * volume) / cumulative(volume)
    Typical price = (High + Low + Close) / 3
    Returns: (vwap, upper_band, lower_band, atr)
    """
    try:
        if df is None or len(df) < 5:
            return None, None, None, None

        tp  = (df["High"] + df["Low"] + df["Close"]) / 3
        cum_tpv = (tp * df["Volume"]).cumsum()
        cum_vol = df["Volume"].cumsum()
        vwap    = cum_tpv / cum_vol

        # ATR over last N candles — fetch lb+1 rows so shift(1) has a prior close
        lb   = min(CONFIG["vwap_atr_lookback"], len(df) - 1)
        atr_df = df.iloc[-(lb + 1):]          # one extra row for the shift
        hi   = atr_df["High"]
        lo   = atr_df["Low"]
        cl   = atr_df["Close"]
        tr   = pd.concat([
            hi - lo,
            (hi - cl.shift(1)).abs(),
            (lo - cl.shift(1)).abs()
        ], axis=1).max(axis=1).dropna()        # drop the first NaN row from shift
        if tr.empty:
            return None, None, None, None
        atr  = tr.mean()

        current_vwap  = float(vwap.iloc[-1])
        upper_band    = current_vwap + CONFIG["vwap_band_mult"] * atr
        lower_band    = current_vwap - CONFIG["vwap_band_mult"] * atr

        return round(current_vwap, 2), round(upper_band, 2), round(lower_band, 2), round(atr, 3)

    except Exception as e:
        log(f"VWAP calc error: {e}", "WARN")
        return None, None, None, None


# ═══════════════════════════════════════════════════════════════
# STRATEGY SELECTOR
# ═══════════════════════════════════════════════════════════════

def select_strategy(df, trend, qqq_dir, kz):
    """
    At kill zone open, score FVG vs VWAP based on market conditions.
    Returns: ("FVG" or "VWAP", reason_string)

    FVG wins when:
      - Strong directional trend
      - Wide day range (big moves = big gaps)
      - Morning kill zone (9:30 — most gap activity)
      - QQQ aligned with trend

    VWAP wins when:
      - Neutral/weak trend (choppy)
      - Tight range (price oscillating around a mean)
      - Price has been crossing VWAP repeatedly
      - Later in the day (12:00, 14:00 kill zones)
    """
    fvg_score  = 0
    vwap_score = 0
    reasons    = []

    # ── Trend strength ─────────────────────────────────────
    if df is not None and len(df) >= CONFIG["trend_lookback"]:
        start_px = df["Close"].iloc[-CONFIG["trend_lookback"]]
        end_px   = df["Close"].iloc[-1]
        pct_chg  = abs((end_px - start_px) / start_px * 100)
    else:
        pct_chg  = 0

    if pct_chg >= CONFIG["strong_trend_pct"]:
        fvg_score  += 3
        reasons.append(f"strong trend ({pct_chg:.2f}%) → FVG+3")
    elif trend == "neutral":
        vwap_score += 3
        reasons.append(f"neutral trend → VWAP+3")
    else:
        fvg_score  += 1
        vwap_score += 1
        reasons.append(f"weak trend → tied+1")

    # ── Day range (volatility) ──────────────────────────────
    if df is not None and len(df) > 0:
        day_range = df["High"].max() - df["Low"].min()
    else:
        day_range = 0

    if day_range >= CONFIG["wide_range_threshold"]:
        fvg_score  += 2
        reasons.append(f"wide range ${day_range:.2f} → FVG+2")
    elif day_range < CONFIG["wide_range_threshold"] * 0.6:
        vwap_score += 2
        reasons.append(f"tight range ${day_range:.2f} → VWAP+2")
    else:
        vwap_score += 1
        reasons.append(f"moderate range ${day_range:.2f} → VWAP+1")

    # ── Kill zone timing ────────────────────────────────────
    if kz == "09:30":
        fvg_score  += 2
        reasons.append("morning KZ → FVG+2")
    else:
        vwap_score += 1
        reasons.append(f"KZ {kz} → VWAP+1")

    # ── QQQ alignment ───────────────────────────────────────
    if qqq_dir != "neutral" and qqq_dir == trend:
        fvg_score  += 1
        reasons.append("QQQ aligned → FVG+1")
    elif qqq_dir == "neutral":
        vwap_score += 1
        reasons.append("QQQ neutral → VWAP+1")

    # ── VWAP crossing count (choppiness signal) ─────────────
    if df is not None and len(df) >= 10:
        vwap_current, _, _, _ = calculate_vwap(df)
        if vwap_current is not None:
            n_back  = min(20, len(df))          # guard if < 20 candles available
            closes  = df["Close"].values[-n_back:]
            crossings = sum(
                1 for i in range(1, len(closes))
                if (closes[i-1] - vwap_current) * (closes[i] - vwap_current) < 0
            )
            if crossings >= 4:
                vwap_score += 2
                reasons.append(f"VWAP crossings={crossings} (choppy) → VWAP+2")
            elif crossings >= 2:
                vwap_score += 1
                reasons.append(f"VWAP crossings={crossings} → VWAP+1")

    # ── SPIKE score — elevated to equal footing ─────────────
    # SPIKE wins strategy selection when price is at a 5D extreme AND ATR
    # extension is significant. This makes it the explicit primary strategy
    # on those days rather than a silent opportunistic add-on.
    spike_score = 0
    spike_reasons = []
    _hist_px = state.get("price_history", [])
    if len(_hist_px) >= 20 and df is not None and len(df) > 0:
        _cutoff = (now_et() - timedelta(days=7.5)).isoformat()
        _px_vals = [p["p"] for p in _hist_px if p.get("t","") >= _cutoff and p.get("p",0) > 0]
        if _px_vals:
            _lo5d, _hi5d = min(_px_vals), max(_px_vals)
            _prox = CONFIG.get("extreme_proximity_mult", 0.5) * state.get("last_atr", 0.5)
            current_px = float(df["Close"].iloc[-1]) if df is not None and len(df) > 0 else 0
            at_extreme = current_px <= _lo5d + _prox or current_px >= _hi5d - _prox
            if at_extreme:
                spike_score += 3
                side = "LOW" if current_px <= _lo5d + _prox else "HIGH"
                spike_reasons.append(f"at 5D {side} extreme → SPIKE+3")
    # ATR extension — price far from VWAP signals mean-reversion opportunity
    if state.get("last_atr") and state.get("last_vwap"):
        vwap_dist = abs(float(df["Close"].iloc[-1]) - state["last_vwap"]) if df is not None and len(df) > 0 else 0
        atr_mult  = vwap_dist / state["last_atr"] if state["last_atr"] > 0 else 0
        if atr_mult >= CONFIG.get("spike_vwap_mult", 1.5):
            spike_score += 2
            spike_reasons.append(f"VWAP dist {atr_mult:.1f}x ATR → SPIKE+2")
    # High volume confirms the extension — compute locally since select_strategy
    # doesn't receive volume_spike from check_for_entry's scope
    _avg_vol_sel  = df["Volume"].mean() if df is not None and len(df) > 0 else 0
    _last_vol_sel = float(df["Volume"].iloc[-1]) if df is not None and len(df) > 0 else 0
    _vol_spike_sel = _last_vol_sel > _avg_vol_sel * CONFIG["volume_spike_mult"] if _avg_vol_sel > 0 else False
    if _vol_spike_sel:
        spike_score += 2
        spike_reasons.append("volume spike → SPIKE+2")

    if spike_reasons:
        reasons.append(" | ".join(spike_reasons))

    # ── Decision ────────────────────────────────────────────
    reason_str = " | ".join(reasons)
    if spike_score > fvg_score and spike_score > vwap_score:
        chosen = "SPIKE"
    elif fvg_score >= vwap_score:
        chosen = "FVG"
    else:
        chosen = "VWAP"

    # v4.3 FIX: auto-switch VWAP → FVG in morning kill zone
    # if we don't have enough candles for VWAP to be reliable
    if chosen == "VWAP" and kz == "09:30":
        if df is None or len(df) < CONFIG["vwap_min_candles"]:
            chosen = "FVG"
            reason_str += f" | AUTO-SWITCH: only {len(df) if df is not None else 0} candles in morning KZ → FVG"

    # v4.3 FIX: also switch if price is far from VWAP bands
    if chosen == "VWAP" and df is not None and len(df) >= CONFIG["vwap_min_candles"]:
        vwap_chk, upper_chk, lower_chk, _ = calculate_vwap(df)
        if vwap_chk is not None:
            current_px = float(df["Close"].iloc[-1])
            dist_pct   = abs(current_px - vwap_chk) / vwap_chk * 100
            if dist_pct > CONFIG["max_fvg_entry_distance_pct"]:
                chosen = "FVG"
                reason_str += f" | AUTO-SWITCH: price {dist_pct:.1f}% from VWAP → FVG"

    # Build score label correctly for all three strategies
    if chosen == 'SPIKE':
        _score_a, _score_b, _vs = spike_score, max(fvg_score, vwap_score), 'FVG/VWAP'
    elif chosen == 'FVG':
        _score_a, _score_b, _vs = fvg_score, vwap_score, 'VWAP'
    else:
        _score_a, _score_b, _vs = vwap_score, fvg_score, 'FVG'
    return chosen, f"{chosen} {_score_a} vs {_vs} {_score_b}: {reason_str}"


def calculate_atr(df, lookback=None):
    """
    Calculate Average True Range for dynamic stop sizing.
    Uses the configured lookback period, but gracefully degrades to
    whatever candles are available (minimum 3) rather than returning None.
    Returns ATR value or None if fewer than 3 candles available.
    """
    if lookback is None:
        lookback = CONFIG["stop_atr_lookback"]
    try:
        if df is None or len(df) < 3:
            return None
        highs  = df["High"].values
        lows   = df["Low"].values
        closes = df["Close"].values
        trs = []
        for i in range(1, len(df)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i]  - closes[i-1])
            )
            trs.append(tr)
        if not trs:
            return None
        # Use up to `lookback` bars, but work with however many exist
        effective = min(lookback, len(trs))
        return round(float(sum(trs[-effective:]) / effective), 4)
    except Exception as e:
        # v4.74 fix: lower risk than the other silent defaults here since
        # callers already branch explicitly on None (e.g. atr_val or
        # CONFIG["stop_buffer"]) rather than mistaking it for a real value —
        # but still worth a log line instead of zero trace of the failure.
        log(f"calculate_atr() failed: {type(e).__name__}: {e}", "WARN")
        return None


# ═══════════════════════════════════════════════════════════════
# VWAP BOUNCE DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_vwap_bounce(df, trend, qqq_dir):
    """
    Detect a valid VWAP bounce setup on the most recent candles.

    A VWAP bounce requires:
      1. Price touched or crossed the VWAP band (within 1 ATR)
      2. The last closed candle is a strong momentum candle
         (body >= min_body_ratio of range) pointing AWAY from VWAP
      3. Trend and QQQ don't strongly oppose the bounce direction

    Returns: setup dict or None
    """
    try:
        if df is None or len(df) < CONFIG["vwap_min_candles"]:
            return None

        vwap, upper, lower, atr = calculate_vwap(df)
        if vwap is None or atr is None or atr == 0:
            return None

        # Update state with latest VWAP levels
        state["last_vwap"]       = vwap
        state["last_vwap_upper"] = upper
        state["last_vwap_lower"] = lower
        state["last_atr"]        = atr

        # Look at the most recent candle for the bounce signal
        last   = df.iloc[-1]
        prev   = df.iloc[-2]
        hi     = float(last["High"])
        lo     = float(last["Low"])
        op     = float(last["Open"])
        cl     = float(last["Close"])
        rng    = hi - lo
        if rng == 0:
            return None
        body   = abs(cl - op)
        body_r = body / rng

        # Must be a strong momentum candle
        if body_r < CONFIG["vwap_min_body_ratio"]:
            return None

        bounce_type = None

        # ── Long bounce: price touched lower band, bounced up ──
        # Previous candle's low touched the lower VWAP band
        # Current candle is a bullish candle closing above VWAP
        if (float(prev["Low"]) <= lower and
                cl > op and          # bullish candle
                cl > vwap and        # closed above VWAP
                trend != "bearish"   # not fighting a bear trend
                and qqq_dir != "bearish"):
            bounce_type = "bullish"

        # ── Short bounce: price touched upper band, fell ───────
        # Previous candle's high touched the upper VWAP band
        # Current candle is a bearish candle closing below VWAP
        elif (float(prev["High"]) >= upper and
                cl < op and          # bearish candle
                cl < vwap and        # closed below VWAP
                trend != "bullish"   # not fighting a bull trend
                and qqq_dir != "bullish"):
            bounce_type = "bearish"

        if bounce_type is None:
            return None

        # Build setup dict (mirrors FVG structure for entry logic reuse)
        entry_px = float(last["Close"])        # use Close directly, not stale `price`
        if bounce_type == "bullish":
            stop_px   = lower - (atr * 1.5)  # widened — IEX ask spikes
            risk      = abs(entry_px - stop_px)    # abs() guards float rounding
            target_px = entry_px + risk * CONFIG["risk_reward"]
        else:
            stop_px   = upper + (atr * 1.5)  # widened — IEX ask spikes
            risk      = abs(stop_px - entry_px)    # abs() guards float rounding
            target_px = entry_px - risk * CONFIG["risk_reward"]

        if risk <= 0:
            return None

        setup = {
            "type":       bounce_type,
            "formed_at":  df.index[-1],
            "vwap":       vwap,
            "upper_band": upper,
            "lower_band": lower,
            "atr":        atr,
            "body_ratio": round(body_r, 2),
            "entry":      round(entry_px, 2),
            "stop":       round(stop_px, 2),
            "target":     round(target_px, 2),
            "risk":       round(risk, 3),
            "score":      0,
            "score_notes": "",
        }

        # Score the VWAP setup (simpler than FVG scoring)
        score = 0
        notes = []
        if body_r >= 0.65:
            score += 2; notes.append("+2 strong momentum candle")
        else:
            score += 1; notes.append("+1 momentum candle")
        if qqq_dir == bounce_type:
            score += 2; notes.append("+2 QQQ aligned")
        if trend == bounce_type:
            score += 1; notes.append("+1 trend aligned")
        if float(df["Volume"].iloc[-1]) > df["Volume"].mean() * 1.3:
            score += 1; notes.append("+1 high volume")
        if get_current_kill_zone() == "09:30":
            score += 1; notes.append("+1 morning KZ")

        setup["score"]       = score
        setup["score_notes"] = " | ".join(notes)

        return setup

    except Exception as e:
        log(f"VWAP bounce detection error: {e}", "WARN")
        return None

def score_fvg(fvg, qqq_dir, avg_volume, kill_zone_start):
    score = 0
    notes = []
    w     = CONFIG["score_weights"]

    if kill_zone_start == "09:30":
        score += w["morning_window"]
        notes.append(f"+{w['morning_window']} morning window")
    if 0.20 <= fvg["size"] <= 0.50:
        score += w["fvg_ideal_size"]
        notes.append(f"+{w['fvg_ideal_size']} ideal size")
    if (fvg["type"] == "bearish" and qqq_dir == "bearish") or \
       (fvg["type"] == "bullish" and qqq_dir == "bullish"):
        score += w["qqq_aligned"]
        notes.append(f"+{w['qqq_aligned']} QQQ aligned")
    if fvg["body_ratio"] >= 0.70:
        score += w["high_body_ratio"]
        notes.append(f"+{w['high_body_ratio']} strong candle")
    if avg_volume > 0 and fvg.get("volume", 0) > avg_volume * 1.3:
        score += w["large_volume"]
        notes.append(f"+{w['large_volume']} high volume")

    # Momentum bonus — daily price action confirms direction off a high/low
    momentum = state.get("daily_momentum", "neutral")
    if momentum == "bullish" and fvg["type"] == "bullish":
        score += 2; notes.append("+2 daily momentum bullish")
    elif momentum == "bearish" and fvg["type"] == "bearish":
        score += 2; notes.append("+2 daily momentum bearish")

    fvg["score"]       = score
    fvg["score_notes"] = " | ".join(notes) if notes else "no bonuses"
    fvg["qqq_dir"]     = qqq_dir
    fvg["stars"]       = "★" * score + "☆" * (9 - score)
    return fvg


def detect_fvgs(df, trend, mtf_bias="neutral"):
    fvgs    = []
    highs   = df["High"].values
    lows    = df["Low"].values
    opens   = df["Open"].values
    closes  = df["Close"].values
    vols    = df["Volume"].values
    times   = df.index
    avg_vol = df["Volume"].mean()

    for i in range(len(df) - 3, max(len(df) - 150, 0), -1):
        c2_range = highs[i+1] - lows[i+1]
        c2_body  = abs(closes[i+1] - opens[i+1])
        if c2_range == 0:
            continue
        body_ratio = c2_body / c2_range
        if body_ratio < CONFIG["min_body_ratio"]:
            continue

        formed_at = times[i+2]
        fvg_key   = formed_at.strftime("%Y%m%d%H%M")
        if fvg_key in [f.get("key") for f in state["all_fvgs_today"]]:
            continue

        if highs[i+2] < lows[i] and (trend in ("bearish", "neutral") or mtf_bias in ("strong_bearish", "bearish")):
            gap_size = lows[i] - highs[i+2]
            if CONFIG["min_fvg_size"] <= gap_size <= CONFIG["max_fvg_size"]:
                fvgs.append({
                    "key":        fvg_key,
                    "type":       "bearish",
                    "formed_at":  formed_at,
                    "top":        lows[i],
                    "bottom":     highs[i+2],
                    "midpoint":   (lows[i] + highs[i+2]) / 2,
                    "size":       round(gap_size, 3),
                    "body_ratio": round(body_ratio, 2),
                    "volume":     vols[i+1],
                    "avg_volume": avg_vol,
                    "entry_zone": round(highs[i+2] + gap_size * CONFIG["entry_at_fvg_pct"], 2),
                })
        elif lows[i+2] > highs[i] and (trend in ("bullish", "neutral") or mtf_bias in ("strong_bullish", "bullish")):
            gap_size = lows[i+2] - highs[i]
            if CONFIG["min_fvg_size"] <= gap_size <= CONFIG["max_fvg_size"]:
                fvgs.append({
                    "key":        fvg_key,
                    "type":       "bullish",
                    "formed_at":  formed_at,
                    "top":        lows[i+2],
                    "bottom":     highs[i],
                    "midpoint":   (lows[i+2] + highs[i]) / 2,
                    "size":       round(gap_size, 3),
                    "body_ratio": round(body_ratio, 2),
                    "volume":     vols[i+1],
                    "avg_volume": avg_vol,
                    "entry_zone": round(highs[i] + gap_size * (1 - CONFIG["entry_at_fvg_pct"]), 2),
                })

    return fvgs, avg_vol

# ═══════════════════════════════════════════════════════════════
# ALPACA TRADING
# ═══════════════════════════════════════════════════════════════

_ALPACA_TIMEOUT_SEC = 20  # hard timeout — increased from 10s for hotspot/slow connections

def _alpaca_session_with_timeout():
    """Patch requests.Session so every Alpaca call enforces a hard timeout."""
    session = requests.Session()
    _orig_request = session.request
    def _request_with_timeout(*args, **kwargs):
        kwargs.setdefault("timeout", _ALPACA_TIMEOUT_SEC)
        return _orig_request(*args, **kwargs)
    session.request = _request_with_timeout
    return session

def get_alpaca():
    try:
        api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version="v2")
        api._session = _alpaca_session_with_timeout()  # enforce timeout on all SDK calls
        account = api.get_account()
        return api, float(account.portfolio_value)
    except Exception as e:
        log(f"Alpaca error: {e}", "ERROR")
        return None, 0

def get_daily_pnl():
    """
    Get today's P&L using bod_equity as baseline (not Alpaca's last_equity).
    Falls back to state["daily_pnl"] if Alpaca is unreachable.
    """
    try:
        api_result = get_alpaca()
        if api_result[0] is not None:
            account = api_result[0].get_account()
            equity = float(account.equity)
            bod = state.get("bod_equity", 0)
            if bod > 0 and state.get("bod_date") == str(datetime.now(MARKET_TZ).date()):
                return round(equity - bod, 2)
            last_equity = float(account.last_equity)
            return round(equity - last_equity, 2)
    except Exception:
        pass
    return state.get("daily_pnl", 0.0)

def place_order(api, fvg_type, entry, stop, target, qty):
    """
    Submit an Alpaca order.
    Long (bullish): bracket order with stop_loss + take_profit legs.
    Short (bearish): plain market sell — Alpaca IEX free tier does not support
    bracket orders on short sells. Stop and target are monitored by the bot.
    """
    # ── Hard market hours wall ─────────────────────────────────────────────
    # Absolute last line of defense before any order reaches Alpaca.
    # Prevents after-hours trading regardless of what the main loop thinks.
    # Market opens 09:30 ET, closes 16:00 ET. Allow entries only until 15:55 ET
    # (5-minute buffer before close so brackets have time to be managed).
    _now_et = now_et()
    _market_open_time  = dtime(9, 30)
    _market_close_time = dtime(15, 55)
    if not (_market_open_time <= _now_et.time() <= _market_close_time):
        log(f"ORDER BLOCKED — outside market hours ({_now_et.strftime('%H:%M')} ET). "
            f"No orders placed between 15:55–09:30 ET.", "ERROR")
        return None
    try:
        # Cancel any lingering open orders for this ticker before submitting.
        # Bracket child orders (stop/target legs) from a previous trade can
        # persist briefly after the parent fills — submitting a new bracket
        # while they exist causes "bracket orders must be entry orders".
        try:
            stale = api.list_orders(status="open", symbols=[CONFIG["ticker"]])
            if stale:
                log(f"Cancelling {len(stale)} stale open order(s) before entry", "WARN")
                for o in stale:
                    try:
                        api.cancel_order(o.id)
                    except Exception:
                        pass
                # Wait longer and poll more aggressively — a cover order from a
                # previous trade filling during this window causes reversed order
                # timestamps (buy-to-close before sell-to-open) which leaves the
                # bot long instead of short. Must confirm ALL orders gone first.
                for _cw in range(15):  # up to 15 seconds
                    time.sleep(1)
                    try:
                        remaining = api.list_orders(status="open", symbols=[CONFIG["ticker"]])
                        if not remaining:
                            log(f"All stale orders confirmed cancelled after {_cw+1}s", "INFO")
                            break
                        if _cw == 14:
                            log(f"WARNING: {len(remaining)} stale order(s) still open after 15s — "
                                f"aborting entry to avoid reversed position", "ERROR")
                            return None  # abort — don't enter with stale orders still live
                    except Exception:
                        break
                # Extra 1-second buffer after confirmed clear — Alpaca's order
                # book can have a brief propagation delay even after list_orders
                # shows empty, during which a late fill can still arrive.
                time.sleep(1)
        except Exception as _ce:
            log(f"Could not cancel stale orders: {_ce}", "WARN")

        is_long = fvg_type == "bullish"

        if is_long:
            # Enforce minimum $0.05 separation for bracket validation
            stop   = round(min(stop,   entry - 0.05), 2)
            target = round(max(target, entry + 0.05), 2)
            # Re-validate stop against live price — market may have moved since entry calc
            try:
                _live_quote = api.get_latest_trade(CONFIG["ticker"])
                _live_px    = float(_live_quote.price) if _live_quote else entry
                if stop >= _live_px - 0.01:
                    stop = round(_live_px - max(0.10, abs(entry - stop)), 2)
                    log(f"Stop adjusted to ${stop:.2f} — market moved since calculation", "WARN")
                if target <= _live_px + 0.01:
                    target = round(_live_px + max(0.10, abs(target - entry)), 2)
            except Exception:
                pass  # fall through with original values
            order = api.submit_order(
                symbol        = CONFIG["ticker"],
                qty           = qty,
                side          = "buy",
                type          = "market",
                time_in_force = "day",
                order_class   = "bracket",
                stop_loss     = {"stop_price":  stop},
                take_profit   = {"limit_price": target},
            )
        else:
            # Short: plain market sell — bot monitors stop/target via _monitor_bot_trade
            order = api.submit_order(
                symbol        = CONFIG["ticker"],
                qty           = qty,
                side          = "sell",
                type          = "market",
                time_in_force = "day",
            )
        return order
    except Exception as e:
        log(f"Order error: {e}", "ERROR")
        raise  # re-raise so callers can surface the real Alpaca error message

def get_position(api):
    try:
        return api.get_position(CONFIG["ticker"])
    except Exception as e:
        # v4.74 fix: this used to catch ANY exception and return None,
        # indistinguishable from "genuinely flat." A 404 ("position does not
        # exist", confirmed via api.code == 40410000) IS the normal, expected
        # response when flat — but a network timeout, auth failure, or any
        # other API error looked exactly the same to every caller, all of
        # which treat None as "position is closed." This exact confusion
        # (API failure mistaken for flat) was the root mechanism behind this
        # session's worst incident (v4.67 — a real open position went
        # completely untracked overnight). Only the expected 404 stays
        # silent now; anything else is logged so a real outage is visible
        # instead of masquerading as "no position."
        if getattr(e, "status_code", None) != 404:
            log(f"get_position() failed (not a 404 — position status UNKNOWN, "
                f"not necessarily flat): {type(e).__name__}: {e}", "WARN")
        return None

def close_all(api):
    # v4.80 CRITICAL fix: root-caused the v4.68 "11 failed attempts" mystery
    # (2026-07-30 EOD, blamed on "a network hiccup, but not provable" at the
    # time) AND a repeat live incident (2026-08-19 VWAP trade, stayed open
    # overnight). Real cause in both: the hybrid-trail BREAKEVEN LOCK submits
    # a real broker-side protective stop order once a trade reaches 1R
    # profit (api.submit_order(..., type="stop", ...) a few hundred lines
    # below) — but close_all() never cancelled it before trying to flatten
    # the position. That stop order reserves the full share quantity, so
    # Alpaca rejects close_all()'s own market order with "insufficient qty
    # available for order (requested: N, available: 0)" — the bot's two own
    # safety mechanisms fighting each other, not an external order, not a
    # network issue.
    #
    # v4.81 CRITICAL fix to the v4.80 fix: unconditionally cancelling every
    # open order before resubmitting backfired for the exact incident it was
    # meant to prevent. Confirmed live: a plain "day, market" close order
    # submitted after 4pm ET just sits queued — it cannot fill until the
    # market reopens, no matter how many times it's resubmitted. But v4.80's
    # blanket cancel-first step destroyed that queued order on EVERY retry
    # (~every 40s) and replaced it with a fresh one, forever — so a
    # legitimately-pending order that would have filled at next market open
    # never survived long enough to do so. Traced a real stuck position (the
    # same RANGE trade from the v4.79/v4.80 incident) through 600+ cancel/
    # resubmit cycles overnight 8/20→8/21 that all went nowhere; it only
    # finally closed at 8/21 9:20-9:32 ET — i.e. it took until the next
    # regular session, and only survived that one attempt by chance timing.
    # Now: if an order is already open that would fully close the position
    # (same side, sufficient qty), leave it alone and let it wait — only
    # cancel OTHER open orders (the stray protective stop this was actually
    # meant to clear) before submitting a new closing order.
    try:
        try:
            pos_chk = get_position(api)
            open_orders = api.list_orders(status="open", symbols=[CONFIG["ticker"]])
            if pos_chk is not None:
                needed_side = "sell" if float(pos_chk.qty) > 0 else "buy"
                needed_qty  = abs(int(float(pos_chk.qty)))
                # v4.88 CRITICAL fix: this used to match ANY open order with the
                # right side/qty — including a resting take-profit LIMIT order
                # that's still open simply because price never reached it. A
                # limit order sitting far from the market is not "a closing
                # order already pending" in any meaningful sense — it may never
                # fill. Confirmed live 2026-09-11->09-14: a RANGE long's $220.99
                # take-profit limit was still open when EOD hit; close_all() saw
                # it, concluded a close was already in flight, and returned
                # WITHOUT ever submitting a real market close — while its own
                # "cancel other orders" step (a few lines below, on an earlier
                # call) had already cancelled the position's actual protective
                # stop as collateral damage. The position then had NOTHING
                # genuinely working to close or protect it and rode
                # unsupervised from $218.57 down to $209.88 over the weekend
                # before something else finally closed it. Only a genuine
                # MARKET order — unconditional, fills at whatever price is
                # available — proves a close is actually in flight. A resting
                # limit or stop order must be cancelled here like anything
                # else, not mistaken for one.
                already_closing = any(
                    o.side == needed_side and o.type == "market"
                    and int(float(o.qty or 0)) >= needed_qty
                    for o in open_orders
                )
                if already_closing:
                    log("close_all(): a closing market order is already pending — "
                        "leaving it to fill instead of cancelling and resubmitting "
                        "(it may just be waiting for the market to reopen)", "INFO")
                    return True
            for o in open_orders:
                try:
                    api.cancel_order(o.id)
                except Exception:
                    pass
            if open_orders:
                time.sleep(1)  # give cancels a moment to release the qty hold
        except Exception as _ce:
            log(f"close_all(): could not clear open orders first: {_ce}", "WARN")
        api.close_position(CONFIG["ticker"])
        return True
    except Exception as e:
        log(f"close_all() failed: {type(e).__name__}: {e}", "WARN")
        return False

def _record_day_trade():
    """Record a completed day trade and persist the rolling 5-business-day window."""
    if not CONFIG.get("pdt_protection"):
        return
    today = str(now_et().date())
    window = state.get("pdt_trades_window", [])
    window.append(today)
    # Keep only the last 5 business days worth of dates
    state["pdt_trades_window"] = window[-20:]  # store generously, trim on check

def _pdt_trades_used():
    """Count day trades used in the last 5 business days (rolling window)."""
    if not CONFIG.get("pdt_protection"):
        return 0
    from datetime import timedelta
    today    = now_et().date()
    # Get the last 5 business days (Mon-Fri only)
    biz_days = []
    d = today
    while len(biz_days) < 5:
        if d.weekday() < 5:  # Mon=0 … Fri=4
            biz_days.append(str(d))
        d -= timedelta(days=1)
    window = state.get("pdt_trades_window", [])
    return sum(1 for t in window if t in biz_days)

def _pdt_allowed():
    """Return True if another day trade is allowed under PDT rules."""
    if not CONFIG.get("pdt_protection"):
        return True
    used = _pdt_trades_used()
    limit = CONFIG.get("pdt_max_trades", 3)
    if used >= limit:
        log(f"PDT LIMIT — {used}/{limit} day trades used in last 5 business days "
            f"— no new trades until window clears", "WARN")
        return False
    remaining = limit - used
    if remaining == 1:
        log(f"PDT WARNING — {used}/{limit} day trades used — 1 remaining this week", "WARN")
    return True


# ═══════════════════════════════════════════════════════════════
# SWING REVERSION STRATEGY (v4.84)
# ═══════════════════════════════════════════════════════════════


def detect_swing_reversion(current_price, trend, atr, extreme_high, extreme_low, label):
    """
    Fade price when it's near a multi-month high/low AND the intraday
    trend has already confirmed a turn — not proximity alone, mirroring
    RANGE's "won't buy a floor against a confirmed downtrend" philosophy
    so this doesn't fade a live breakout, only a stalled extreme.

    Generic over one lookback window (called once per window — "3M"/"6M" —
    from check_for_entry()). Stop sits beyond the window's extreme itself
    (not a generic ATR offset from entry) since a new extreme being made is
    the real invalidation of the "this is a top/bottom" thesis.

    Returns (direction, entry, stop, target, risk, reason) or None.
    """
    if not CONFIG.get("swing_trading_enabled", True):
        return None
    if extreme_high <= 0 or extreme_low <= 0 or atr <= 0:
        return None
    prox      = CONFIG["swing_extreme_pct"] / 100 * current_price
    stop_dist = atr * CONFIG["swing_stop_atr_mult"]

    if current_price >= extreme_high - prox and trend == "bearish":
        entry, stop = current_price, round(extreme_high + stop_dist, 2)
        risk = stop - entry
        if risk <= 0:
            return None
        target = round(entry - risk * CONFIG["swing_risk_reward"], 2)
        pct = (extreme_high - current_price) / extreme_high * 100
        reason = (f"SWING-{label}: ${current_price:.2f} within {pct:.1f}% of {label} high "
                  f"${extreme_high:.2f}, intraday trend turned bearish")
        return ("bearish", entry, stop, target, risk, reason)

    if current_price <= extreme_low + prox and trend == "bullish":
        entry, stop = current_price, round(extreme_low - stop_dist, 2)
        risk = entry - stop
        if risk <= 0:
            return None
        target = round(entry + risk * CONFIG["swing_risk_reward"], 2)
        pct = (current_price - extreme_low) / extreme_low * 100
        reason = (f"SWING-{label}: ${current_price:.2f} within {pct:.1f}% of {label} low "
                  f"${extreme_low:.2f}, intraday trend turned bullish")
        return ("bullish", entry, stop, target, risk, reason)

    return None


# ═══════════════════════════════════════════════════════════════
# SPIKE / MEAN-REVERSION STRATEGY (v4.13)
# ═══════════════════════════════════════════════════════════════


def detect_range(price_history, current_price, atr):
    """
    Detect an intraday oscillating range from real-time price history.

    Identifies when price is bouncing between a consistent ceiling and floor
    with >= range_min_swing amplitude and >= range_min_bounces confirmed touches.

    Returns a trade candidate dict or None:
      {
        "direction": "bullish" | "bearish",
        "entry": float,       # current price (aggressive — at the extreme)
        "stop": float,        # just beyond the range extreme
        "target": float,      # opposite range boundary
        "risk": float,        # entry - stop (absolute)
        "rr": float,          # reward / risk ratio
        "score": int,         # quality score
        "reason": str,
        "ceiling": float,
        "floor": float,
        "bounces": int,
      }
    """
    # Tier 1 params
    t1_min_swing   = CONFIG.get("range_min_swing",    2.0)
    t1_tolerance   = CONFIG.get("range_tolerance",    0.60)
    t1_min_bounces = CONFIG.get("range_min_bounces",  2)
    # Tier 2 params
    t2_min_swing   = CONFIG.get("range_t2_min_swing",   1.0)
    t2_max_swing   = CONFIG.get("range_t2_max_swing",   1.99)
    t2_tolerance   = CONFIG.get("range_t2_tolerance",   0.30)
    t2_min_bounces = CONFIG.get("range_t2_min_bounces", 3)
    t2_qty_mult    = CONFIG.get("range_t2_qty_mult",    2.0)
    lookback_m     = CONFIG.get("range_lookback_min",   30)
    # Use broadest params for initial detection, then classify
    min_swing   = t2_min_swing   # detect everything >= $1.00
    tolerance   = t1_tolerance   # start with loose tolerance for peak detection
    min_bounces = t2_min_bounces # require at least 3 touches initially

    if not price_history or len(price_history) < 6:
        return None

    # Use ALL of today's price history — not a fixed rolling window.
    # A fixed lookback (e.g. 45 min) misses range extremes that happened
    # earlier in the session. If price hit $194 at 9:30 and is now at $202
    # at 11:00, a 45-min window only sees $200-202 chop and builds a fake
    # micro-range. Using the full day captures the true floor and ceiling.
    now_ts = datetime.now(MARKET_TZ)
    today_str = now_ts.strftime("%Y-%m-%d")
    recent = [p for p in price_history
              if p.get("t", "")[:10] == today_str
              and p.get("p", 0) > 0]

    if len(recent) < 6:
        return None

    prices = [p["p"] for p in recent]

    # Find local highs and lows using a simple peak/trough detector
    # A local high is higher than both its neighbors; local low is lower
    highs, lows = [], []
    for i in range(1, len(prices) - 1):
        # Use >= on the left side so flat-topped plateaus register as peaks.
        # On 1-minute resolution data the same price often repeats across
        # consecutive points — strict > would miss these real highs/lows.
        if prices[i] >= prices[i-1] and prices[i] > prices[i+1]:
            highs.append(prices[i])
        elif prices[i] <= prices[i-1] and prices[i] < prices[i+1]:
            lows.append(prices[i])

    if len(highs) < min_bounces or len(lows) < min_bounces:
        return None

    # Find the dominant ceiling and floor — the levels that price KEEPS
    # returning to, not just the median of all peaks/troughs.
    # Strategy: find the extreme level (highest high / lowest low) that
    # has at least min_bounces touches within tolerance. This correctly
    # identifies range boundaries even when intermediate chop creates
    # many false peaks/troughs between the real floor and ceiling.

    def find_dominant_level(levels, use_max=True, tol=0.60, min_touches=2):
        """
        Find the dominant range boundary — the most extreme level that price
        has repeatedly confirmed via multiple touches within tolerance.
        Groups nearby levels into clusters, then finds the most extreme
        cluster with enough touches. Falls back to most extreme single level.
        """
        if not levels:
            return None
        sorted_levels = sorted(levels, reverse=use_max)
        # Build clusters of nearby levels
        used = set()
        clusters = []
        for i, level in enumerate(sorted_levels):
            if i in used:
                continue
            cluster = [level]
            for j, other in enumerate(sorted_levels):
                if j != i and j not in used and abs(other - level) <= tol:
                    cluster.append(other)
                    used.add(j)
            used.add(i)
            clusters.append((statistics.median(cluster), len(cluster)))
        # Sort by extremeness (highest for ceiling, lowest for floor)
        clusters.sort(key=lambda x: x[0], reverse=use_max)
        # Return most extreme cluster with enough confirmed touches
        for level, count in clusters:
            if count >= min_touches:
                return level
        # No cluster qualified — return most extreme single level
        return sorted_levels[0]

    # Use broad tolerance for initial ceiling/floor detection
    ceiling = find_dominant_level(highs, use_max=True,  tol=t1_tolerance, min_touches=t1_min_bounces)
    floor   = find_dominant_level(lows,  use_max=False, tol=t1_tolerance, min_touches=t1_min_bounces)
    if ceiling is None or floor is None:
        return None
    amplitude = ceiling - floor

    if amplitude < t2_min_swing:
        return None  # below minimum for either tier

    # Dominant range filter: if the detected range is less than 40% of the
    # total price swing in the lookback window, it's a sub-range within a
    # larger move — skip it to avoid trading noise inside a bigger trend.
    total_swing = max(prices) - min(prices)
    if total_swing > 0 and (amplitude / total_swing) < 0.40:
        return None  # detected range is a sub-range of a larger move — skip

    # Classify into tier based on amplitude and re-apply correct params
    if amplitude >= t1_min_swing:
        tier        = 1
        tolerance   = t1_tolerance
        min_bounces = t1_min_bounces
        qty_mult    = 1.0
    else:
        # $1.00–$1.99 swing — tier 2: tighter tolerance, more bounces required
        tier        = 2
        tolerance   = t2_tolerance
        min_bounces = t2_min_bounces
        qty_mult    = t2_qty_mult

    # Count bounces: how many highs are within tolerance of ceiling,
    # and how many lows are within tolerance of floor
    # Recount bounces using the tier-specific tolerance
    ceiling_touches = sum(1 for h in highs if abs(h - ceiling) <= tolerance)
    floor_touches   = sum(1 for l in lows  if abs(l - floor)   <= tolerance)

    if ceiling_touches < min_bounces or floor_touches < min_bounces:
        return None  # not enough confirmed bounces for this tier

    # Determine if current price is near floor (long entry) or ceiling (short entry)
    near_floor   = current_price <= floor   + tolerance
    near_ceiling = current_price >= ceiling - tolerance

    if not near_floor and not near_ceiling:
        log(f"RANGE: price ${current_price:.2f} mid-range "
            f"(floor ${floor:.2f}±{tolerance} / ceiling ${ceiling:.2f}±{tolerance}) — no entry", "INFO")
        return None  # price is mid-range — no edge entry

    # ── Recency check — range must still be actively oscillating ──────────
    # Check the last 20 price points (not 10) — gives more room for price
    # to have just arrived at an extreme after a full swing from the other side.
    # Use 20% threshold (not 30%) — at the floor/ceiling, we EXPECT the last
    # few points to be flat. What matters is that the broader recent window
    # shows actual movement, not that the last 2 minutes were volatile.
    if len(recent) >= 10:
        last_20 = [p["p"] for p in recent[-20:]]
        recent_min = min(last_20)
        recent_max = max(last_20)
        recent_swing = recent_max - recent_min
        min_active_swing = amplitude * 0.20  # 20% of range — e.g. $1.20 on a $6 range

        if recent_swing < min_active_swing:
            log(f"RANGE: activity check FAILED — recent swing ${recent_swing:.2f} < "
                f"min ${min_active_swing:.2f} (20% of ${amplitude:.2f} range) — drift detected", "INFO")
            return None  # price locked flat — range likely broken, not oscillating

    # Score the setup
    score = 0
    reasons = []

    # Bonus for extra bounces beyond minimum
    extra_bounces = min(ceiling_touches, floor_touches) - min_bounces
    if extra_bounces > 0:
        score += min(extra_bounces * 2, 4)  # cap at +4
        reasons.append(f"+{min(extra_bounces*2,4)} confirmed bounces ({min(ceiling_touches,floor_touches)} total)")

    # Bonus for tight, consistent range
    high_variance = max(highs) - min(highs)
    low_variance  = max(lows)  - min(lows)
    if high_variance <= tolerance and low_variance <= tolerance:
        score += 2
        reasons.append("+2 tight consistent range")
    elif high_variance <= tolerance * 2:
        score += 1
        reasons.append("+1 moderate range consistency")

    # Bonus for large amplitude (more profit potential)
    if amplitude >= min_swing * 2:
        score += 2
        reasons.append(f"+2 wide range ${amplitude:.2f}")
    elif amplitude >= min_swing * 1.5:
        score += 1
        reasons.append(f"+1 good amplitude ${amplitude:.2f}")

    # MTF alignment bonus
    mtf = state.get("mtf_bias", "neutral")
    if near_floor and mtf in ("strong_bullish", "bullish"):
        score += 1
        reasons.append("+1 MTF aligned bullish")
    elif near_ceiling and mtf in ("strong_bearish", "bearish"):
        score += 1
        reasons.append("+1 MTF aligned bearish")

    # v4.66 fix: hard trend filter, added after a losing day (2026-07-27, -$608.88
    # net, 5 of 6 trades were counter-trend RANGE longs during a monthly-low
    # breakdown) made the gap obvious — the MTF-alignment bonus above only ever
    # ADDS score for trend agreement, it never blocks a setup that fights the
    # trend outright. Every one of that day's losing trades had
    # state["last_trend"] reading "bearish" while RANGE bought a "floor" anyway,
    # betting on a bounce that didn't come because the trend wasn't noise, it
    # was a real breakdown. Now rejects outright rather than just scoring lower:
    # no buying a floor in a confirmed bearish trend, no shorting a ceiling in a
    # confirmed bullish trend. Only blocks on a definite trend reading in the
    # counter direction — "neutral" still passes through unaffected.
    _range_trend = state.get("last_trend", "neutral")
    if near_floor and _range_trend == "bearish":
        log(f"RANGE: floor bounce REJECTED — trend is bearish, won't buy a "
            f"floor against a confirmed downtrend (floor ${floor:.2f})", "INFO")
        return None
    if near_ceiling and _range_trend == "bullish":
        log(f"RANGE: ceiling bounce REJECTED — trend is bullish, won't short a "
            f"ceiling against a confirmed uptrend (ceiling ${ceiling:.2f})", "INFO")
        return None

    # Build the trade
    if near_floor:
        direction = "bullish"
        entry  = round(current_price, 2)
        stop   = round(floor - atr * 2.0, 2)   # 2×ATR below floor — room for normal range wicks
        target = round(ceiling - tolerance, 2)  # conservative — just inside ceiling
        risk   = round(entry - stop, 2)
        reward = round(target - entry, 2)
    else:  # near_ceiling
        direction = "bearish"
        entry  = round(current_price, 2)
        stop   = round(ceiling + atr * 2.0, 2)  # 2×ATR above ceiling — room for normal range wicks
        target = round(floor + tolerance, 2)     # conservative — just inside floor
        risk   = round(stop - entry, 2)
        reward = round(entry - target, 2)

    if risk <= 0 or reward <= 0:
        return None

    rr = round(reward / risk, 2)

    # Minimum R:R filter — don't enter if the setup isn't worth the risk.
    # A tight range with a small reward vs stop is noise, not signal.
    if rr < 2.0:
        return None

    reason_str = (f"Range ${floor:.2f}–${ceiling:.2f} (${amplitude:.2f} swing) | "
                  f"{min(ceiling_touches, floor_touches)} bounces confirmed | "
                  f"{'Near floor → LONG' if near_floor else 'Near ceiling → SHORT'} | "
                  + " | ".join(reasons))

    return {
        "direction": direction,
        "entry":     entry,
        "stop":      stop,
        "target":    target,
        "risk":      risk,
        "rr":        rr,
        "score":     score,
        "reason":    reason_str,
        "ceiling":   ceiling,
        "floor":     floor,
        "bounces":   min(ceiling_touches, floor_touches),
        "tier":      tier,
        "qty_mult":  qty_mult,
    }

def _check_spike_reversal(df, current_price, atr, vwap):
    """
    Detect a sharp price spike and enter a mean-reversion counter-trade.

    Conditions for a BEARISH spike (short entry):
      - Last N candles moved up >= spike_atr_mult × ATR
      - Current price is >= spike_vwap_mult × ATR above VWAP
      - Most recent candle shows a bearish close (close < open) — rejection signal
      - No existing bot trade open

    Conditions for a BULLISH spike (long entry):
      - Mirror of the above, downward

    Entry: current price (market order at spike extreme)
    Stop:  spike_stop_mult × ATR beyond the spike high/low
    Target: spike_target_mult × ATR back toward VWAP

    Returns: ("bullish"/"bearish", entry, stop, target, reason) or None
    """
    if atr is None or atr <= 0 or vwap is None or vwap <= 0:
        return None
    if df is None or len(df) < CONFIG["spike_lookback"] + 1:
        return None

    lookback = CONFIG["spike_lookback"]
    spike_atr_mult  = CONFIG["spike_atr_mult"]
    vwap_mult       = CONFIG["spike_vwap_mult"]
    stop_mult       = CONFIG["spike_stop_mult"]
    target_mult     = CONFIG["spike_target_mult"]

    recent = df.iloc[-lookback:]
    move_high = float(recent["High"].max())
    move_low  = float(recent["Low"].min())
    move_open = float(recent["Open"].iloc[0])
    last_open  = float(df["Open"].iloc[-1])
    last_close = float(df["Close"].iloc[-1])

    upward_move   = move_high - move_open
    downward_move = move_open - move_low
    vwap_dist     = current_price - vwap

    # ── BEARISH SPIKE: sharp up-move, price extended above VWAP, rejection candle
    if (upward_move >= spike_atr_mult * atr
            and vwap_dist >= vwap_mult * atr
            and last_close < last_open):  # rejection candle confirms
        spike_high = move_high
        entry  = round(current_price, 2)
        stop   = round(spike_high + stop_mult * atr, 2)
        target = round(current_price - target_mult * atr, 2)
        risk   = round(stop - entry, 2)
        if risk <= 0 or target >= entry:
            return None
        reason = (f"Spike ↑ ${upward_move:.2f} ({upward_move/atr:.1f}×ATR) | "
                  f"VWAP dist ${vwap_dist:.2f} ({vwap_dist/atr:.1f}×ATR) | "
                  f"Rejection candle confirmed")
        return ("bearish", entry, stop, target, risk, reason)

    # ── BULLISH SPIKE: sharp down-move, price extended below VWAP, rejection candle
    if (downward_move >= spike_atr_mult * atr
            and -vwap_dist >= vwap_mult * atr
            and last_close > last_open):  # rejection candle confirms
        spike_low = move_low
        entry  = round(current_price, 2)
        stop   = round(spike_low - stop_mult * atr, 2)
        target = round(current_price + target_mult * atr, 2)
        risk   = round(entry - stop, 2)
        if risk <= 0 or target <= entry:
            return None
        reason = (f"Spike ↓ ${downward_move:.2f} ({downward_move/atr:.1f}×ATR) | "
                  f"VWAP dist ${-vwap_dist:.2f} ({-vwap_dist/atr:.1f}×ATR) | "
                  f"Rejection candle confirmed")
        return ("bullish", entry, stop, target, risk, reason)

    return None


def _check_range_extreme(df, current_price, atr, vwap):
    """
    Detect when price tags a multi-day range extreme and begins reversing.

    Uses price_history to find the N-day high/low. If current price is within
    proximity of that extreme AND shows a reversal candle on the intraday feed,
    enter a counter-trend trade back toward the range midpoint.

    Conditions for BULLISH extreme (long at multi-day low):
      - Current price is within extreme_proximity_mult × ATR of the N-day low
      - Price has moved up from that low (reversal started — not still falling)
      - Last candle is bullish (close > open)
      - Price is below VWAP (confirms extended move down)

    Conditions for BEARISH extreme (short at multi-day high): mirror of above.

    Returns: ("bullish"/"bearish", entry, stop, target, risk, reason) or None
    """
    if atr is None or atr <= 0 or vwap is None or vwap <= 0:
        return None
    if df is None or len(df) < 3:
        return None

    last_open  = float(df["Open"].iloc[-1])
    last_close = float(df["Close"].iloc[-1])

    hist = state.get("price_history", [])
    if len(hist) < 20:
        return None

    lookback_days = CONFIG.get("extreme_lookback_days", 5)
    proximity_mult = CONFIG.get("extreme_proximity_mult", 0.5)  # within 0.5×ATR of extreme
    stop_mult      = CONFIG["spike_stop_mult"]
    target_mult    = CONFIG["spike_target_mult"]

    # Get prices from last N calendar days
    from datetime import timedelta
    cutoff = (now_et() - timedelta(days=lookback_days * 1.5)).isoformat()
    recent_prices = [p["p"] for p in hist if p.get("t", "") >= cutoff and p.get("p", 0) > 0]

    if len(recent_prices) < 10:
        return None

    range_high = max(recent_prices)
    range_low  = min(recent_prices)
    range_size = range_high - range_low

    if range_size <= 0:
        return None

    vwap_dist = current_price - vwap
    proximity = proximity_mult * atr

    # ── BULLISH EXTREME: price near N-day low, starting to reverse up ──
    near_low = current_price <= range_low + proximity
    dist_from_low = current_price - range_low
    min_bounce = 0.10 * atr  # price must have bounced at least 0.1×ATR off the low
    if near_low and dist_from_low >= min_bounce and last_close > last_open and vwap_dist < 0:
        entry  = round(current_price, 2)
        stop   = round(range_low - stop_mult * atr, 2)
        target = round(entry + target_mult * atr, 2)
        risk   = round(entry - stop, 2)
        if risk <= 0 or target <= entry:
            return None
        reason = (f"Range extreme LOW ${range_low:.2f} ({lookback_days}d) | "
                  f"Dist from low ${dist_from_low:.2f} | "
                  f"VWAP dist ${-vwap_dist:.2f} below | Reversal candle confirmed")
        return ("bullish", entry, stop, target, risk, reason)

    # ── BEARISH EXTREME: price near N-day high, starting to reverse down ──
    near_high = current_price >= range_high - proximity
    dist_from_high = range_high - current_price
    # Require price to be at least 0.1×ATR below the high — confirms rejection started
    if near_high and dist_from_high >= min_bounce and last_close < last_open and vwap_dist > 0:
        entry  = round(current_price, 2)
        stop   = round(range_high + stop_mult * atr, 2)
        target = round(entry - target_mult * atr, 2)
        risk   = round(stop - entry, 2)
        if risk <= 0 or target >= entry:
            return None
        reason = (f"Range extreme HIGH ${range_high:.2f} ({lookback_days}d) | "
                  f"Dist from high ${dist_from_high:.2f} | "
                  f"VWAP dist ${vwap_dist:.2f} above | Rejection candle confirmed")
        return ("bearish", entry, stop, target, risk, reason)

    return None
# ═══════════════════════════════════════════════════════════════

def check_for_entry():
    if get_bot_trade() is not None:
        return  # Already have a bot trade open — wait for it to close
    # Post-trade cooldown — prevents Alpaca wash-trade rejection
    _last_close = state.get("last_trade_close_time")
    if _last_close is not None:
        _secs_since = (datetime.now(MARKET_TZ) - _last_close).total_seconds()
        _cooldown   = CONFIG.get("post_trade_cooldown_sec", 90)
        if _secs_since < _cooldown:
            _remaining = int(_cooldown - _secs_since)
            if state.get("_last_cooldown_log") != _remaining // 15:
                state["_last_cooldown_log"] = _remaining // 15
                log(f"Post-trade cooldown — {_remaining}s remaining (wash-trade prevention)")
            return

    if state["order_failed_today"]:
        now_min = now_local().strftime("%H:%M")
        if state.get("_last_order_fail_log") != now_min:
            state["_last_order_fail_log"] = now_min
            log("Order failed earlier today — skipping until next kill zone", "WARN")
        return

    if not _pdt_allowed():
        return
    if not is_in_kill_zone():
        return

    # Check Alpaca BEFORE scanning — catches orders placed in previous scan
    # that state hasn't recorded yet
    try:
        api_early, _ = get_alpaca()
        if api_early is not None:
            pos_early = get_position(api_early)
            if pos_early is not None:
                qty_e   = int(float(pos_early.qty))
                entry_e = float(pos_early.avg_entry_price)
                side_e  = "bullish" if qty_e > 0 else "bearish"
                # Guard: don't reconnect a position that's already tracked in active_trades
                # This prevents the ghost loop where close_all() takes >1s to settle
                already_tracked = any(
                    t.get("order_id") == getattr(pos_early, "asset_id", "unknown")
                    or abs(t.get("entry", 0) - entry_e) < 0.01
                    for t in get_active_trades()
                )
                if already_tracked:
                    # Already monitoring this position — just skip the scan
                    state["status"] = "Position already open — monitoring"
                    return

                # Also skip if we just closed a trade (cooldown active) — the position
                # is likely settling and will be gone on the next poll
                _last_close = state.get("last_trade_close_time")
                if _last_close is not None:
                    _secs_since_close = (datetime.now(MARKET_TZ) - _last_close).total_seconds()
                    if _secs_since_close < 10:
                        log("Skipping reconnect — position likely settling after recent close", "WARN")
                        state["status"] = "Position settling — next poll"
                        return

                # Check if this position was already closed by the bot recently —
                # if so, Alpaca hasn't settled yet. Force-close and don't reconnect.
                # v4.67 fix: CRITICAL — this ternary evaluated its `if` condition
                # (hasattr(_closed_t.get("closed_at"), ...)) which calls
                # `_closed_t.get(...)` — but _closed_t is None on every fresh
                # process until some trade closes that session, so this raised
                # AttributeError: 'NoneType' object has no attribute 'get' on
                # every single call. The surrounding except swallowed it as a
                # generic "Pre-scan Alpaca check failed" WARN, which meant the
                # actual reconnection logic a few lines below never ran either
                # — confirmed live: a real open position sat completely
                # untracked all morning while this crashed every ~15s. Guard
                # the None case explicitly before touching _closed_t at all.
                _closed_t = state.get("closed_trade")
                _already_processed = False
                if _closed_t and hasattr(_closed_t.get("closed_at"), "total_seconds"):
                    _already_processed = (
                        abs(float(_closed_t.get("entry", 0)) - entry_e) < 0.10 and
                        abs(int(_closed_t.get("qty", 0)) - abs(qty_e)) < 5 and
                        (datetime.now(MARKET_TZ) - _closed_t.get("closed_at")).total_seconds() < 300
                    )
                if _already_processed:
                    log(f"DUPLICATE PREVENTED — position already processed as closed, "
                        f"forcing Alpaca close to settle", "WARN")
                    try:
                        api_early.close_position(CONFIG["ticker"])
                    except Exception:
                        pass
                    return

                log(f"DUPLICATE PREVENTED (pre-scan) — position already open "
                    f"({pos_early.qty} shares @ ${entry_e:.2f}) — reconnecting monitor", "WARN")
                state["traded_today"] = True
                state["status"] = "Position already open — monitoring"
                if get_bot_trade() is None:
                    atr_est = state.get("last_atr", abs(entry_e * 0.005)) or abs(entry_e * 0.005)
                    add_active_trade({
                        "order_id":  getattr(pos_early, "asset_id", "unknown"),
                        "fvg":       {},
                        "fvg_type":  side_e,
                        "strategy":  "RESTORED",
                        "entry":     entry_e,
                        "stop":      round(entry_e + atr_est * 1.5, 2) if side_e == "bearish" else round(entry_e - atr_est * 1.5, 2),
                        "target":    round(entry_e - atr_est * 3, 2)   if side_e == "bearish" else round(entry_e + atr_est * 3, 2),
                        "qty":       abs(qty_e),
                        "risk":      0,
                        "equity":    0,
                        "opened_at": now_local(),
                        "outcome":   None,
                        "exit_px":   None,
                        "pnl":       None,
                        "qqq_dir":   "neutral",
                        "trend":     "neutral",
                    })
                return
            open_orders = api_early.list_orders(status="open", symbols=[CONFIG["ticker"]])
            if open_orders:
                log(f"DUPLICATE PREVENTED (pre-scan) — {len(open_orders)} open order(s) "
                    f"for {CONFIG['ticker']} — skipping scan", "WARN")
                state["traded_today"] = True
                state["status"] = "Open orders exist — monitoring only"
                return
    except Exception as e:
        log(f"Pre-scan Alpaca check failed: {e}", "WARN")

    # v4.10: Check daily loss limit before scanning
    # Skip limit check if disabled in CONFIG (useful after overnight position
    # accounting corrupts the daily P&L baseline)
    if CONFIG.get("daily_loss_limit_enabled", True):
        daily_pnl = get_daily_pnl()  # from Alpaca — authoritative
        # Guard: if there are open positions, Alpaca's equity delta includes
        # unrealized P&L from overnight holds — don't let that trigger the
        # loss limit on a fresh trading day
        try:
            _api_ll, _ = get_alpaca()
            _has_pos = _api_ll and get_position(_api_ll) is not None
        except Exception:
            _has_pos = False
        if daily_pnl <= CONFIG["daily_loss_limit"] and not _has_pos:
            log(f"DAILY LOSS LIMIT reached (${daily_pnl:+,.2f}) — "
                f"no more trades today. Limit: ${CONFIG['daily_loss_limit']:,.0f}", "WARN")
            state["status"] = f"Daily loss limit hit (${daily_pnl:+,.2f}) — scanning paused"
            return
        elif daily_pnl <= CONFIG["daily_loss_limit"] and _has_pos:
            log(f"Daily P&L ${daily_pnl:+,.2f} below limit but open position exists — "
                f"skipping limit (overnight position distorting equity delta)", "WARN")

    # v4.10: Run MTF analysis once per day at first kill zone scan
    if not state["mtf_fetched_today"]:
        get_mtf_bias(CONFIG["ticker"])
        state["mtf_fetched_today"] = True

    # v4.84: Cache 3-month/6-month swing highs/lows once per day, same pattern
    if not state.get("swing_extremes_fetched_today"):
        get_swing_extremes(CONFIG["ticker"])
        state["swing_extremes_fetched_today"] = True

    kz = get_current_kill_zone()
    log(f"Scanning — kill zone {kz} ET active")
    state["status"] = f"Scanning — kill zone {kz} ET"

    df = fetch_candles(CONFIG["ticker"], bars=200)

    # If IEX hasn't accumulated enough bars yet, use whatever is available
    # Minimum 5 candles to calculate basic trend and FVG patterns
    # The trend lookback will auto-adjust to available candles
    min_candles = 5

    if df is None or len(df) < min_candles:
        log(f"Insufficient candle data ({len(df) if df is not None else 0} candles, "
            f"need {min_candles}) — skipping scan", "WARN")
        state["status"] = "Waiting for candle data..."
        return

    trend   = get_trend(df)
    qqq_dir = get_qqq_direction()

    # Update live state — only update last_price if candles are from today
    # to prevent stale fallback bars creating phantom price jumps on dashboard
    _scan_bar_date = df.index[-1].date() if hasattr(df.index[-1], 'date') else None
    if _scan_bar_date == now_et().date():
        state["last_price"] = round(float(df["Close"].iloc[-1]), 2)
    else:
        # v4.57 fix: same fallback as the background refresh loop — when
        # today's candle bar isn't available yet, ask Alpaca for just the
        # single most recent trade print instead of leaving last_price
        # frozen (which showed as dead-flat plateaus on the dashboard chart).
        try:
            _api_lt, _ = get_alpaca()
            if _api_lt:
                _latest_trade = _api_lt.get_latest_trade(CONFIG["ticker"])
                if _latest_trade and _latest_trade.price:
                    state["last_price"] = round(float(_latest_trade.price), 2)
        except Exception:
            pass  # leave last_price at its previous value
    state["last_trend"]        = trend
    state["last_qqq"]          = qqq_dir
    state["last_scan_time"]    = now_local().strftime("%H:%M:%S")
    state["last_candle_count"] = len(df)
    check_stale_data(len(df))

    # ── Append to price history on every scan ────────────────────
    scan_px = state["last_price"]
    if 50 < scan_px < 2000:
        ts = datetime.now(MARKET_TZ).strftime("%Y-%m-%dT%H:%M")
        hist = state.get("price_history", [])
        # Dedup: skip if this minute already in recent history, else update price
        _recent_ts1 = {h["t"] for h in hist[-4:]} if hist else set()
        if ts not in _recent_ts1:
            hist.append({
                "t":     ts,
                "p":     scan_px,
                "kz":    get_current_kill_zone() or "",
                "trend": trend,
                "mtf":   state.get("mtf_bias", "neutral"),
            })
            if len(hist) > 2000:
                hist = hist[-2000:]
            state["price_history"] = hist
        else:
            for _h in reversed(hist):
                if _h["t"] == ts:
                    _h["p"] = scan_px
                    break

    latest = df["Close"].iloc[-1]
    spread = df["High"].max() - df["Low"].min()

    # ── Always update VWAP + ATR every scan ──────────────────────
    avg_vol      = df["Volume"].mean()
    last_vol     = float(df["Volume"].iloc[-1])
    volume_spike = last_vol > avg_vol * CONFIG["volume_spike_mult"]

    _vwap, _upper, _lower, _atr = calculate_vwap(df)
    if _vwap is not None:
        state["last_vwap"]       = _vwap
        state["last_vwap_upper"] = _upper
        state["last_vwap_lower"] = _lower
        state["last_atr"]        = _atr

    # Check if this scan's price was saved to history
    hist = state.get("price_history", [])
    ts_now = datetime.now(MARKET_TZ).strftime("%Y-%m-%dT%H:%M")
    hist_saved = hist and hist[-1]["t"] == ts_now
    hist_mark  = f" ✓ hist({len(hist)})" if hist_saved else ""

    log(f"Scan | Trend: {trend} | QQQ: {qqq_dir} | "
        f"MTF: {state['mtf_bias']} | "
        f"NVDA: ${latest:.2f} | Range: ${spread:.2f} | "
        f"VWAP: ${state['last_vwap']:.2f} | ATR: ${state['last_atr']:.3f} | "
        f"VWAP-dist: ${latest - state['last_vwap']:+.2f} | Candles: {len(df)}{hist_mark}")

    # Log 5-day range extremes for situational awareness
    _hist = state.get("price_history", [])
    if len(_hist) >= 20:
        _cutoff = (now_et() - timedelta(days=7.5)).isoformat()
        _px = [p["p"] for p in _hist if p.get("t","") >= _cutoff and p.get("p",0) > 0]
        if _px:
            _lo, _hi = min(_px), max(_px)
            _prox = CONFIG.get("extreme_proximity_mult", 0.5) * state["last_atr"]
            _near = ""
            if latest <= _lo + _prox: _near = " ◀ NEAR 5D LOW"
            elif latest >= _hi - _prox: _near = " ◀ NEAR 5D HIGH"
            log(f"5D range: Low ${_lo:.2f} | High ${_hi:.2f} | Current ${latest:.2f}{_near}")

    # ── Persist price history to disk every 10 scans ──────────────
    state["scan_count_since_save"] = state.get("scan_count_since_save", 0) + 1
    if state["scan_count_since_save"] >= 10:
        state["scan_count_since_save"] = 0
        save_state()

    # ═══════════════════════════════════════════════════════════════
    # PARALLEL STRATEGY EVALUATION — all strategies run every scan
    # Best R:R among valid setups wins. While in a trade, strategies
    # still evaluate and log candidates but do not enter a new position.
    # ═══════════════════════════════════════════════════════════════
    in_trade = get_bot_trade() is not None
    spike_cooldown = state.get("_spike_cooldown_until", "")
    past_cooldown  = now_local().strftime("%H:%M") >= spike_cooldown

    candidates = []  # list of (rr, strategy_name, setup_tuple)

    # ── 1. RANGE strategy — oscillation bounce ──────────────────
    _range = detect_range(state.get("price_history", []), float(latest),
                          state.get("last_atr", 0.5))
    if _range:
        candidates.append((_range["rr"], "RANGE", _range))
        log(f"RANGE DETECTED [{_range['direction'].upper()}] — "
            f"{_range['floor']:.2f}–{_range['ceiling']:.2f} | "
            f"{_range['bounces']} bounces | R:R {_range['rr']:.1f} | "
            f"{'✓ ENTERING' if not in_trade else '⚠ FLAGGED (in trade)'}")

    # ── 2. SPIKE strategy — sharp extension + rejection ─────────
    # v4.72: _check_spike_reversal() (momentum-extension trigger) is disabled
    # from live trading (CONFIG["spike_momentum_enabled"]) — still evaluated
    # every scan for shadow tracking, same treatment as FVG, but no longer
    # short-circuits _check_range_extreme() (the trigger actually carrying
    # SPIKE's profit) the way it used to when both could fire the same scan.
    state["_spike_shadow_this_scan"] = None
    if past_cooldown:
        _spike_momentum = _check_spike_reversal(df, float(latest),
                                                 state.get("last_atr", 0),
                                                 state.get("last_vwap", 0))
        if _spike_momentum:
            sm_dir, sm_entry, sm_stop, sm_target, sm_risk, sm_reason = _spike_momentum
            sm_reward = abs(sm_target - sm_entry)
            sm_rr     = round(sm_reward / sm_risk, 2) if sm_risk > 0 else 0
            state["_spike_shadow_this_scan"] = {
                "direction": sm_dir, "entry": float(sm_entry), "stop": float(sm_stop),
                "target": float(sm_target), "risk": float(sm_risk), "rr": float(sm_rr),
                "reason": sm_reason,
            }
            if CONFIG.get("spike_momentum_enabled", True):
                candidates.append((sm_rr, "SPIKE",
                                    {"direction": sm_dir, "entry": sm_entry, "stop": sm_stop,
                                     "target": sm_target, "risk": sm_risk, "rr": sm_rr,
                                     "reason": sm_reason, "raw": _spike_momentum}))
                log(f"SPIKE MOMENTUM DETECTED [{sm_dir.upper()}] — {sm_reason} | "
                    f"R:R {sm_rr:.1f} | "
                    f"{'✓ COMPETING' if not in_trade else '⚠ FLAGGED (in trade)'}")
            else:
                log(f"SPIKE MOMENTUM DETECTED [{sm_dir.upper()}] — {sm_reason} | "
                    f"R:R {sm_rr:.1f} | ○ SHADOW ONLY (momentum-spike trading disabled)")

        _spike = _check_range_extreme(df, float(latest),
                                      state.get("last_atr", 0),
                                      state.get("last_vwap", 0))
        if _spike:
            s_dir, s_entry, s_stop, s_target, s_risk, s_reason = _spike
            s_reward = abs(s_target - s_entry)
            s_rr     = round(s_reward / s_risk, 2) if s_risk > 0 else 0
            candidates.append((s_rr, "SPIKE",
                                {"direction": s_dir, "entry": s_entry, "stop": s_stop,
                                 "target": s_target, "risk": s_risk, "rr": s_rr,
                                 "reason": s_reason, "raw": _spike}))
            log(f"SPIKE DETECTED [{s_dir.upper()}] — {s_reason} | "
                f"R:R {s_rr:.1f} | "
                f"{'✓ COMPETING' if not in_trade else '⚠ FLAGGED (in trade)'}")

    # ── 3. FVG strategy — gap retrace ───────────────────────────
    # v4.71: kept running every scan (detection + scoring) even though it's
    # disabled from live trading — state["_fvg_shadow_this_scan"] lets
    # whichever OTHER strategy actually wins this scan carry FVG's would-be
    # setup along, so a later loss can be checked against what FVG would
    # have done (see _run_fvg_shadow_check).
    _fvg_result = _evaluate_fvg_strategy(df, trend, qqq_dir, avg_vol, kz, float(latest))
    state["_fvg_shadow_this_scan"] = None
    if _fvg_result:
        f_dir, f_entry, f_stop, f_target, f_risk, f_reason, f_fvg = _fvg_result
        f_reward = abs(f_target - f_entry)
        f_rr     = round(f_reward / f_risk, 2) if f_risk > 0 else 0
        state["_fvg_shadow_this_scan"] = {
            "direction": f_dir, "entry": float(f_entry), "stop": float(f_stop),
            "target": float(f_target), "risk": float(f_risk), "rr": float(f_rr),
            "reason": f_reason, "score": (f_fvg or {}).get("score", 0),
        }
        if CONFIG.get("fvg_trading_enabled", True):
            candidates.append((f_rr, "FVG",
                                {"direction": f_dir, "entry": f_entry, "stop": f_stop,
                                 "target": f_target, "risk": f_risk, "rr": f_rr,
                                 "reason": f_reason, "fvg": f_fvg}))
            log(f"FVG DETECTED [{f_dir.upper()}] — {f_reason[:60]} | "
                f"R:R {f_rr:.1f} | "
                f"{'✓ COMPETING' if not in_trade else '⚠ FLAGGED (in trade)'}")
        else:
            log(f"FVG DETECTED [{f_dir.upper()}] — {f_reason[:60]} | "
                f"R:R {f_rr:.1f} | ○ SHADOW ONLY (FVG trading disabled)")

    # ── 4. VWAP strategy — band bounce ──────────────────────────
    _vwap_result = _evaluate_vwap_strategy(df, trend, qqq_dir, float(latest))
    if _vwap_result:
        v_dir, v_entry, v_stop, v_target, v_risk, v_reason = _vwap_result
        v_reward = abs(v_target - v_entry)
        v_rr     = round(v_reward / v_risk, 2) if v_risk > 0 else 0
        candidates.append((v_rr, "VWAP",
                            {"direction": v_dir, "entry": v_entry, "stop": v_stop,
                             "target": v_target, "risk": v_risk, "rr": v_rr,
                             "reason": v_reason}))
        log(f"VWAP DETECTED [{v_dir.upper()}] — {v_reason[:60]} | "
            f"R:R {v_rr:.1f} | "
            f"{'✓ COMPETING' if not in_trade else '⚠ FLAGGED (in trade)'}")

    # ── 5. SWING strategy — mean reversion from 3M/6M price extremes ──
    for _label, _hi_key, _lo_key in (("3M", "swing_high_3m", "swing_low_3m"),
                                      ("6M", "swing_high_6m", "swing_low_6m")):
        _swing = detect_swing_reversion(float(latest), trend, state.get("last_atr", 0),
                                         state.get(_hi_key, 0), state.get(_lo_key, 0), _label)
        if _swing:
            sw_dir, sw_entry, sw_stop, sw_target, sw_risk, sw_reason = _swing
            sw_rr   = round(abs(sw_target - sw_entry) / sw_risk, 2) if sw_risk > 0 else 0
            sw_name = f"SWING-{_label}"
            # v4.95: SWING-3M is shadow-only — still detected and logged every
            # scan (keeps research data flowing) but never added to candidates,
            # so it can never win the R:R competition or be opened. See the
            # swing_3m_trading_enabled CONFIG comment for why.
            _sw_shadow = _label == "3M" and not CONFIG.get("swing_3m_trading_enabled", False)
            if not _sw_shadow:
                candidates.append((sw_rr, sw_name,
                                    {"direction": sw_dir, "entry": sw_entry, "stop": sw_stop,
                                     "target": sw_target, "risk": sw_risk, "rr": sw_rr,
                                     "reason": sw_reason}))
            log(f"{sw_name} DETECTED [{sw_dir.upper()}] — {sw_reason} | "
                f"R:R {sw_rr:.1f} | "
                + ("○ SHADOW ONLY (SWING-3M same-day trading disabled)" if _sw_shadow
                   else ('✓ COMPETING' if not in_trade else '⚠ FLAGGED (in trade)')))

    # ── Select best R:R and enter if not in trade ────────────────
    if candidates and not in_trade:
        best_rr, best_name, best = max(candidates, key=lambda x: x[0])
        state["active_strategy"] = best_name

        log(f"Best setup: {best_name} | R:R {best_rr:.1f}:1 | "
            f"Entry ${best['entry']:.2f} | Stop ${best['stop']:.2f} | "
            f"Target ${best['target']:.2f}")

        fvg_compat = best.get("fvg") or {
            "score":       best.get("score", 0),
            "score_notes": best.get("reason", ""),
            "size":        0,
            "type":        best["direction"],
            "entry_zone":  best["entry"],
            "formed_at":   datetime.now(MARKET_TZ),
            "qty_mult":    best.get("qty_mult", 1.0),  # tier 2 range gets 2x qty
        }

        _place_trade(best["direction"], best["entry"], best["stop"],
                     best["target"], best["risk"], fvg_compat,
                     best_name, trend, qqq_dir)

        # v4.71/v4.72: if a disabled sub-strategy also had a valid (would-have-
        # traded) setup this same scan, carry it along on the trade that
        # actually got placed so a later loss can be checked against what it
        # would have done instead. No name exclusion for spike momentum vs a
        # winning range-extreme SPIKE trade — they're different triggers that
        # just share the "SPIKE" label, and that comparison is exactly the
        # point.
        _fvg_shadow   = state.get("_fvg_shadow_this_scan")
        _spike_shadow = state.get("_spike_shadow_this_scan")
        if _fvg_shadow or _spike_shadow:
            _bt = get_bot_trade()
            if _bt is not None:
                if _fvg_shadow and best_name != "FVG":
                    _bt["_fvg_shadow"] = _fvg_shadow
                if _spike_shadow:
                    _bt["_spike_shadow"] = _spike_shadow

        if best_name in ("SPIKE", "RANGE") or best_name.startswith("SWING"):
            cooldown_dt = now_local() + timedelta(minutes=5)
            state["_spike_cooldown_until"] = cooldown_dt.strftime("%H:%M")

    elif not candidates:
        state["active_strategy"] = state.get("active_strategy", "SCANNING")


def get_effective_score_threshold(fvg_type, qqq_dir):
    """
    v4.10: Dynamic minimum score based on QQQ alignment AND
    multi-timeframe bias (weekly + monthly trend + gap).

    MTF bias as scoring weight (v4.42 — no longer a hard veto):
      strong_bullish → bearish trades need 4/9 (high bar, not blocked)
      bullish        → bearish trades need 3/9
      strong_bearish → bullish trades need 4/9 (high bar, not blocked)
      bearish        → bullish trades need 3/9
      neutral        → standard QQQ-based thresholds

    v4.89: all the counter-trend bars in this function (previously 5/9 and
    6/9) were lowered — per user request, the goal shifted from protecting
    equity to maximizing real trade data for setup-quality research. MTF
    bias reads directional (not neutral) most days in practice, so these
    counter-trend bars — not the baseline min_score_to_trade — were likely
    the actual reason whole days passed with zero qualifying setups. Still
    higher than the aligned/neutral bars (some differentiation preserved —
    a counter-trend setup should still show a bit more conviction) but far
    more permissive than before.
    """
    mtf = state.get("mtf_bias", "neutral")

    # MTF bias acts as a SCORING WEIGHT, not a hard veto.
    # strong_bullish/bearish adds a penalty to counter-trend thresholds
    # so only higher-conviction setups can trade against the MTF trend.
    # A high-scoring bearish FVG on a clearly bearish intraday day should be
    # tradeable even if the weekly/monthly trend is bullish — the intraday
    # structure wins.
    momentum = state.get("daily_momentum", "neutral")

    if mtf == "strong_bullish" and fvg_type == "bearish":
        if momentum == "bearish":
            # Momentum confirms distribution — reduce penalty slightly
            return 3, "MTF strong bullish — momentum bearish override, raised bar for short"
        else:
            return 4, "MTF strong bullish — high bar for counter-trend short"

    if mtf == "strong_bearish" and fvg_type == "bullish":
        if momentum == "bullish":
            # Momentum confirms accumulation — reduce penalty slightly
            return 3, "MTF strong bearish — momentum bullish override, raised bar for long"
        else:
            return 4, "MTF strong bearish — high bar for counter-trend long"

    # Moderate MTF — raise bar but less aggressively
    if mtf == "bullish" and fvg_type == "bearish":
        return 3, "MTF bullish — raised bar for short"
    if mtf == "bearish" and fvg_type == "bullish":
        return 3, "MTF bearish — raised bar for long"

    # MTF aligned or neutral — use QQQ-based thresholds as before
    if fvg_type == "bullish":
        if qqq_dir == "bullish":
            return CONFIG["min_score_qqq_aligned"], "QQQ aligned ✓"
        elif qqq_dir == "neutral":
            return CONFIG["min_score_qqq_neutral"], "QQQ neutral — raising bar"
        else:
            return 4, "QQQ opposite — high bar"
    else:  # bearish
        if qqq_dir == "bearish":
            return CONFIG["min_score_qqq_aligned"], "QQQ aligned ✓"
        elif qqq_dir == "neutral":
            return CONFIG["min_score_qqq_neutral"], "QQQ neutral — raising bar"
        else:
            return 4, "QQQ opposite — high bar"



def _evaluate_fvg_strategy(df, trend, qqq_dir, avg_vol, kz, current_price):
    """
    Evaluate FVG strategy and return a candidate tuple or None.
    Does NOT place a trade — just evaluates. Used by parallel strategy runner.
    Returns: (direction, entry, stop, target, risk, reason, fvg_dict) or None
    """
    fvgs, _ = detect_fvgs(df, trend, mtf_bias=state.get("mtf_bias", "neutral"))
    for fvg in fvgs:
        fvg = score_fvg(fvg, qqq_dir, avg_vol, kz)
        state["all_fvgs_today"].append(fvg)
        log(f"FVG [{fvg['type'].upper()}] — size ${fvg['size']:.2f} | "
            f"score {fvg['score']}/9 | {fvg['score_notes']}")
        if fvg["score"] > state["best_score_today"]:
            state["best_score_today"] = fvg["score"]
            state["best_fvg_today"]   = fvg

    if state["best_fvg_today"] is None:
        log(f"FVG scan — {len(fvgs)} FVG(s) found, none scoreable (trend: {trend})")
        return None

    # Distance filter
    ez   = state["best_fvg_today"]["entry_zone"]
    dist = abs(current_price - ez) / current_price * 100
    if dist > CONFIG["max_fvg_entry_distance_pct"]:
        # v4.91 fix: state["all_fvgs_today"] is shared with VWAP's fvg_compat
        # dicts (_evaluate_vwap_strategy, same dedup-by-key purpose) — those
        # don't have "top"/"bottom" (only real FVG dicts from detect_fvgs()
        # do). Without this guard, a VWAP entry could satisfy the score/
        # entry_zone filter below, get picked as best_close, and then crash
        # at fvg["top"] a few lines down in the bearish branch — caught by
        # main()'s top-level handler, so live never actually crashed, just
        # silently skipped that scan and retried 60s later.
        close_fvgs = [
            f for f in state["all_fvgs_today"]
            if "top" in f and "bottom" in f
            and f["score"] >= CONFIG["min_score_to_trade"]
            and abs(current_price - f["entry_zone"]) / current_price * 100
               <= CONFIG["max_fvg_entry_distance_pct"]
        ]
        if close_fvgs:
            best_close = max(close_fvgs, key=lambda x: x["score"])
            state["best_fvg_today"]   = best_close
            state["best_score_today"] = best_close["score"]
        else:
            return None

    fvg      = state["best_fvg_today"]
    fvg_type = fvg["type"]
    eff_threshold, qqq_reason = get_effective_score_threshold(fvg_type, qqq_dir)

    if state["best_score_today"] < eff_threshold:
        _wait_key = f"{state['best_score_today']}/{eff_threshold}"
        if state.get("_last_wait_log_key") != _wait_key:
            state["_last_wait_log_key"] = _wait_key
            log(f"Best FVG score {state['best_score_today']}/9 below "
                f"threshold {eff_threshold} ({qqq_reason}) — waiting")
        return None

    atr_val       = calculate_atr(df)
    atr_stop_dist = round(atr_val * CONFIG["stop_atr_mult"], 2) if atr_val else CONFIG["stop_buffer"]
    entry_zone    = fvg["entry_zone"]

    if fvg_type == "bullish":
        entry_low, entry_high = fvg["bottom"], entry_zone
        log(f"Best FVG [BULLISH] score {fvg['score']}/9 — "
            f"watching ${entry_low:.2f}–${entry_high:.2f} (current ${current_price:.2f})")
        if not (entry_low <= current_price <= entry_high):
            return None
        entry  = round(current_price, 2)
        stop   = round(entry - atr_stop_dist, 2)
        risk   = entry - stop
        target = entry + risk * CONFIG["risk_reward"]
    else:
        entry_low, entry_high = entry_zone, fvg["top"]
        log(f"Best FVG [BEARISH] score {fvg['score']}/9 — "
            f"watching ${entry_low:.2f}–${entry_high:.2f} (current ${current_price:.2f})")
        if not (entry_low <= current_price <= entry_high):
            return None
        entry  = round(current_price, 2)
        stop   = round(entry + atr_stop_dist, 2)
        risk   = stop - entry
        target = entry - risk * CONFIG["risk_reward"]

    if risk <= 0:
        return None

    reason = f"score {fvg['score']}/9 | {fvg['score_notes']}"
    return (fvg_type, entry, stop, round(target, 2), round(risk, 2), reason, fvg)


def _evaluate_vwap_strategy(df, trend, qqq_dir, current_price):
    """
    Evaluate VWAP strategy and return a candidate tuple or None.
    Does NOT place a trade — just evaluates. Used by parallel strategy runner.
    Returns: (direction, entry, stop, target, risk, reason) or None
    """
    setup = detect_vwap_bounce(df, trend, qqq_dir)
    vwap  = state["last_vwap"]
    if setup is None:
        return None

    vwap_type = setup.get("type", "bearish")
    vwap_threshold, vwap_qqq_reason = get_effective_score_threshold(vwap_type, qqq_dir)
    if setup["score"] < vwap_threshold:
        return None

    vwap_key = setup["formed_at"].strftime("%Y%m%d%H%M") + "_vwap"
    if vwap_key in [f.get("key") for f in state["all_fvgs_today"]]:
        return None  # already logged this candle

    fvg_compat = {
        "key":         vwap_key,
        "score":       setup["score"],
        "score_notes": setup["score_notes"],
        "size":        round(setup["atr"], 3),
        "formed_at":   setup["formed_at"],
        "type":        setup["type"],
        "entry_zone":  setup["entry"],
        "qqq_dir":     qqq_dir,
        "stars":       "★" * setup["score"] + "☆" * (9 - setup["score"]),
    }
    state["all_fvgs_today"].append(fvg_compat)
    if setup["score"] > state["best_score_today"]:
        state["best_score_today"] = setup["score"]

    reason = f"VWAP bounce {setup['score']}/9 | {setup['score_notes']}"
    return (setup["type"], setup["entry"], setup["stop"],
            setup["target"], setup["risk"], reason)

def _run_fvg_strategy(df, trend, qqq_dir, avg_vol, kz, current_price):
    """Original FVG retrace entry logic."""
    fvgs, _ = detect_fvgs(df, trend)

    log(f"FVG scan — {len(fvgs)} new FVG(s) found")

    for fvg in fvgs:
        fvg = score_fvg(fvg, qqq_dir, avg_vol, kz)
        state["all_fvgs_today"].append(fvg)
        log(f"FVG [{fvg['type'].upper()}] — size ${fvg['size']:.2f} | "
            f"score {fvg['score']}/9 | {fvg['score_notes']}")
        if fvg["score"] > state["best_score_today"]:
            state["best_score_today"] = fvg["score"]
            state["best_fvg_today"]   = fvg

    # v4.3 FIX: filter FVGs whose entry zone is too far from current price
    current_px_now = float(df["Close"].iloc[-1])
    if state["best_fvg_today"] is not None:
        ez     = state["best_fvg_today"]["entry_zone"]
        dist   = abs(current_px_now - ez) / current_px_now * 100
        if dist > CONFIG["max_fvg_entry_distance_pct"]:
            log(f"Best FVG entry zone ${ez:.2f} is {dist:.1f}% from price — too far, scanning for closer FVG")
            state["fvg_skipped_distance"] += 1
            # Try to find a closer valid FVG
            close_fvgs = [
                f for f in state["all_fvgs_today"]
                if f["score"] >= CONFIG["min_score_to_trade"]
                and abs(current_px_now - f["entry_zone"]) / current_px_now * 100 <= CONFIG["max_fvg_entry_distance_pct"]
            ]
            if close_fvgs:
                best_close = max(close_fvgs, key=lambda x: x["score"])
                state["best_fvg_today"]   = best_close
                state["best_score_today"] = best_close["score"]
                log(f"Found closer FVG: score {best_close['score']}/9 @ entry ${best_close['entry_zone']:.2f}")
            else:
                state["best_fvg_today"]   = None
                state["best_score_today"] = 0

    # v4.7: Dynamic threshold based on QQQ alignment
    eff_threshold, qqq_reason = get_effective_score_threshold(
        state["best_fvg_today"]["type"] if state["best_fvg_today"] else "bullish",
        qqq_dir
    )

    if state["best_fvg_today"] is None or state["best_score_today"] < eff_threshold:
        if state["best_fvg_today"] is None:
            log(f"No scoreable FVGs found (trend: {trend})")
            state["status"] = f"FVG scan — no setups | Trend: {trend}"
        else:
            # Only log when the score or threshold changes — suppress repeated identical messages
            _wait_key = f"{state['best_score_today']}/{eff_threshold}"
            if state.get("_last_wait_log_key") != _wait_key:
                state["_last_wait_log_key"] = _wait_key
                log(f"Best FVG score {state['best_score_today']}/9 below "
                    f"threshold {eff_threshold} ({qqq_reason}) — waiting")
            state["status"] = (f"FVG — score {state['best_score_today']}/9 "
                               f"below threshold {eff_threshold} ({qqq_reason})")
        return

    fvg        = state["best_fvg_today"]
    entry_zone = fvg["entry_zone"]
    fvg_type   = fvg["type"]

    # v4.12: ATR-based stop distance (promised in v4.3 but stop_buffer was still used)
    # Falls back to stop_buffer if ATR unavailable (insufficient candles)
    atr_val      = calculate_atr(df)
    atr_stop_dist = round(atr_val * CONFIG["stop_atr_mult"], 2) if atr_val else CONFIG["stop_buffer"]
    log(f"FVG stop distance: ${atr_stop_dist:.2f} "
        f"({'ATR×' + str(CONFIG['stop_atr_mult']) if atr_val else 'fixed fallback'})")

    if fvg_type == "bullish":
        entry_low  = fvg["bottom"]
        entry_high = entry_zone
        log(f"Best FVG [BULLISH] score {fvg['score']}/9 — "
            f"waiting for retrace into ${entry_low:.2f}–${entry_high:.2f} "
            f"(current: ${current_price:.2f})")
        state["status"] = f"FVG — watching BULLISH ${entry_low:.2f}–${entry_high:.2f}"
        if not (entry_low <= current_price <= entry_high):
            return
        entry  = float(current_price)
        stop   = round(entry - atr_stop_dist, 2)
        risk   = entry - stop
        target = entry + risk * CONFIG["risk_reward"]
    else:
        entry_low  = entry_zone
        entry_high = fvg["top"]
        log(f"Best FVG [BEARISH] score {fvg['score']}/9 — "
            f"waiting for retrace into ${entry_low:.2f}–${entry_high:.2f} "
            f"(current: ${current_price:.2f})")
        state["status"] = f"FVG — watching BEARISH ${entry_low:.2f}–${entry_high:.2f}"
        if not (entry_low <= current_price <= entry_high):
            return
        entry  = float(current_price)
        stop   = round(entry + atr_stop_dist, 2)
        risk   = stop - entry
        target = entry - risk * CONFIG["risk_reward"]

    if risk <= 0:
        return

    _place_trade(fvg_type, entry, stop, target, risk, fvg, "FVG",
                 state["last_trend"], state["last_qqq"])


def _run_vwap_strategy(df, trend, qqq_dir, current_price):
    """VWAP bounce entry logic."""
    setup = detect_vwap_bounce(df, trend, qqq_dir)

    vwap  = state["last_vwap"]
    upper = state["last_vwap_upper"]
    lower = state["last_vwap_lower"]
    atr   = state["last_atr"]

    if vwap > 0:
        log(f"VWAP: ${vwap:.2f} | Upper band: ${upper:.2f} | "
            f"Lower band: ${lower:.2f} | ATR: ${atr:.3f}")

    if setup is None:
        log(f"VWAP scan — no bounce setup confirmed "
            f"(price ${current_price:.2f} vs VWAP ${vwap:.2f})")
        state["status"] = (f"VWAP — watching for bounce near "
                           f"${lower:.2f}–${upper:.2f}")
        return

    # v4.12: Fixed key — setup uses 'type', not 'direction'
    vwap_type = setup.get("type", "bearish")   # was setup.get("direction") — always returned None
    vwap_threshold, vwap_qqq_reason = get_effective_score_threshold(vwap_type, qqq_dir)
    if setup["score"] < vwap_threshold:
        log(f"VWAP [{setup['type'].upper()}] bounce score {setup['score']}/9 "
            f"below threshold {vwap_threshold} ({vwap_qqq_reason}) — skipping | {setup['score_notes']}")
        state["status"] = f"VWAP bounce score {setup['score']}/9 below threshold {vwap_threshold}"
        state["vwap_setups_today"].append(setup)
        return

    log(f"VWAP BOUNCE [{setup['type'].upper()}] confirmed! "
        f"Score {setup['score']}/9 | {setup['score_notes']}")
    state["vwap_setups_today"].append(setup)

    # Build a minimal fvg-compatible dict for logging/summary
    vwap_key = setup["formed_at"].strftime("%Y%m%d%H%M") + "_vwap"
    # Guard against duplicate entries (same candle re-scanned)
    if vwap_key in [f.get("key") for f in state["all_fvgs_today"]]:
        log("VWAP setup already logged this candle — skipping duplicate")
        return   # nothing new to act on

    fvg_compat = {
        "key":         vwap_key,
        "score":       setup["score"],
        "score_notes": setup["score_notes"],
        "size":        round(setup["atr"], 3),
        "formed_at":   setup["formed_at"],
        "type":        setup["type"],
        "entry_zone":  setup["entry"],
        "qqq_dir":     qqq_dir,
        "stars":       "★" * setup["score"] + "☆" * (9 - setup["score"]),
    }
    state["all_fvgs_today"].append(fvg_compat)
    if setup["score"] > state["best_score_today"]:
        state["best_score_today"] = setup["score"]

    _place_trade(setup["type"], setup["entry"], setup["stop"], setup["target"],
                 setup["risk"], fvg_compat, "VWAP",
                 state["last_trend"], state["last_qqq"])



def get_performance_scale(strategy):
    """
    Read master_trade_log.csv and compute win rate over last N trades
    for the given strategy. Returns a qty multiplier:
      - win rate > 50% over last 10 trades → 1.5x risk_per_trade
      - otherwise → 1.0x (no scaling)

    Called once per kill zone open, result cached in state.
    """
    if not CONFIG.get("perf_scale_enabled"):
        return 1.0

    log_path = os.path.join("trade_logs", "master_trade_log.csv")
    if not os.path.exists(log_path):
        return 1.0

    try:
        lookback = CONFIG.get("perf_scale_lookback", 10)
        threshold = CONFIG.get("perf_scale_threshold", 0.50)
        mult      = CONFIG.get("perf_scale_mult", 1.5)

        import csv as _csv
        with open(log_path, newline="", encoding="utf-8") as f:
            rows = list(_csv.DictReader(f))

        # Filter to this strategy's completed trades (win or loss, not NO_TRADE)
        strat_trades = [
            r for r in rows
            if r.get("strategy", "").upper() == strategy.upper()
            and r.get("outcome", "") in ("WIN", "LOSS", "EOD_CLOSE", "CLOSED")
            and r.get("pnl", "") not in ("", "0", "0.0")
        ]

        if len(strat_trades) < lookback:
            return 1.0  # not enough history yet

        recent = strat_trades[-lookback:]
        wins   = sum(1 for r in recent if float(r.get("pnl", 0)) > 0)
        win_rate = wins / len(recent)

        if win_rate > threshold:
            log(f"[PERF SCALE] {strategy} win rate {win_rate:.0%} over last "
                f"{lookback} trades → scaling qty {mult}x", "INFO")
            return mult
        return 1.0

    except Exception as e:
        log(f"[PERF SCALE] Could not read trade log: {e}", "WARN")
        return 1.0

def _place_trade(fvg_type, entry, stop, target, risk, fvg, strategy, trend, qqq_dir):
    """Shared order placement — called by both FVG and VWAP strategies."""
    if risk <= 0:
        return

    api_result = get_alpaca()
    if api_result[0] is None:
        return
    api, equity = api_result

    # v4.5 FIX: Check Alpaca directly for open positions before placing order
    # This prevents duplicate trades when the bot reconnects after a dropout
    existing_pos = get_position(api)
    if existing_pos is not None:
        qty_p   = int(float(existing_pos.qty))
        entry_p = float(existing_pos.avg_entry_price)
        side_p  = "bullish" if qty_p > 0 else "bearish"
        log(f"DUPLICATE PREVENTED — position already open on Alpaca "
            f"({existing_pos.qty} shares @ ${entry_p:.2f}) — reconnecting monitor", "WARN")
        if not get_bot_trade():  # Only restore if no bot trade already tracked
            atr_est_p = abs(entry_p * 0.005)
            restored = {
                "order_id":  getattr(existing_pos, "asset_id", "unknown"),
                "fvg":       {},
                "fvg_type":  side_p,
                "strategy":  "RESTORED",
                "entry":     entry_p,
                "stop":      entry_p + atr_est_p if side_p == "bearish" else entry_p - atr_est_p,
                "target":    entry_p - atr_est_p * 2 if side_p == "bearish" else entry_p + atr_est_p * 2,
                "qty":       abs(qty_p),
                "risk":      0,
                "equity":    0,
                "opened_at": now_local(),
                "outcome":   None,
                "exit_px":   None,
                "pnl":       None,
                "qqq_dir":   "neutral",
                "trend":     "neutral",
            }
            add_active_trade(restored)
        return

    # Also check for any open/pending orders today
    try:
        open_orders = api.list_orders(status="open", symbols=[CONFIG["ticker"]])
        if open_orders:
            log(f"DUPLICATE PREVENTED — {len(open_orders)} open order(s) already exist "
                f"for {CONFIG['ticker']} — skipping new order", "WARN")
            state["traded_today"] = True
            state["status"] = "Open orders exist — monitoring only"
            return
    except Exception as e:
        log(f"Could not check open orders: {e}", "WARN")

    # Performance-based scaling — boosts risk_per_trade when strategy
    # win rate exceeds 50% over last 10 trades for this strategy type
    perf_scale  = get_performance_scale(strategy)

    # Range tier 2 qty multiplier — 2x shares for tighter $1–$1.99 ranges
    # to offset lower per-share profit. Passed via fvg dict from detect_range.
    range_mult  = fvg.get("qty_mult", 1.0) if fvg else 1.0

    effective_risk_pct = CONFIG["risk_per_trade"] * perf_scale
    risk_based_qty = int((equity * effective_risk_pct) / risk)
    risk_based_qty = int(risk_based_qty * range_mult)
    max_qty        = int((equity * CONFIG["max_position_pct"]) / entry)
    qty            = max(1, min(risk_based_qty, max_qty))

    scale_note = ""
    if perf_scale > 1.0: scale_note += f" [PERF SCALE {perf_scale}x]"
    if range_mult > 1.0: scale_note += f" [RANGE T2 {range_mult}x qty]"

    log(f"[{strategy}] Position: {qty} shares @ ${entry:.2f} = "
        f"${qty * entry:,.2f} ({qty * entry / equity * 100:.1f}% of equity){scale_note}")
    log(f"[{strategy}] ENTERING {fvg_type.upper()} | "
        f"Entry ${entry:.2f} | Stop ${stop:.2f} | Target ${target:.2f} | Qty {qty} | "
        f"Risk ${risk * qty:,.2f}", "TRADE")

    state["status"] = f"[{strategy}] ENTERING {fvg_type.upper()} @ ${entry:.2f}"

    try:
        order = place_order(api, fvg_type, entry, stop, target, qty)
    except Exception as order_err:
        err_msg = str(order_err)
        if strategy == "SPIKE":
            log(f"Spike order failed ({err_msg}) — FVG/VWAP strategies unaffected", "ERROR")
            state["status"] = "Spike order failed — continuing FVG/VWAP scan"
        else:
            log(f"Order failed ({err_msg}) — will not retry until next kill zone", "ERROR")
            state["order_failed_today"] = True
            state["status"] = f"Order failed: {err_msg[:80]}"
            save_state()
        return

    # v4.90: snapshot longer-horizon trend context at entry time — `trend`
    # above is the short intraday read (25-candle lookback); these capture
    # the 5-day momentum, monthly (60-day) slope, and position relative to
    # the 3-month/6-month range, none of which were previously persisted
    # per-trade. Without this, comparing which lookback actually predicts
    # outcomes requires cross-referencing bot_console.log by timestamp.
    swing_pos_6m = ""
    _hi6, _lo6 = state.get("swing_high_6m", 0), state.get("swing_low_6m", 0)
    if _hi6 > 0 and _lo6 > 0:
        _prox6 = CONFIG["swing_extreme_pct"] / 100 * entry
        if entry >= _hi6 - _prox6:
            swing_pos_6m = "near_6m_high"
        elif entry <= _lo6 + _prox6:
            swing_pos_6m = "near_6m_low"
        else:
            swing_pos_6m = "mid_range"

    new_trade = {
        "order_id":  order.id,
        "fvg":       fvg,
        "fvg_type":  fvg_type,
        "strategy":  strategy,
        "entry":     entry,
        "stop":      stop,
        "orig_stop": stop,
        "target":    target,
        "qty":       qty,
        "risk":      risk,
        "equity":    equity,
        "opened_at": now_local(),
        "outcome":   None,
        "exit_px":   None,
        "pnl":       None,
        "qqq_dir":   qqq_dir,
        "trend":     trend,
        "monthly_trend":  state.get("monthly_trend", ""),
        "daily_momentum": state.get("daily_momentum", ""),
        "swing_pos_6m":   swing_pos_6m,
    }
    add_active_trade(new_trade)
    state["traded_today"]    = True
    state["trail_activated"] = False
    state["trail_peak"]      = 0.0
    state["trail_stop"]      = 0.0
    state["status"] = f"[{strategy}] TRADE OPEN [{fvg_type.upper()}] @ ${entry:.2f}"
    log(f"Order placed — ID: {order.id} | Strategy: {strategy}", "TRADE")
    save_state()

# ═══════════════════════════════════════════════════════════════
# TRADE MONITORING
# ═══════════════════════════════════════════════════════════════

def _confirm_and_finalize_close(api, trade, outcome, exit_px, pnl, label, max_wait=8):
    """
    v4.88: shared close-confirmation path for every place _monitor_bot_trade
    decides a trade should close (target hit, stop hit, trailing stop hit).
    Before this, TARGET HIT / STOP HIT (both directions) and TRAILING STOP
    HIT (both directions) each had their own copy of a "wait up to N seconds,
    then finalize" loop — and every single copy finalized (remove_active_trade
    + _finalize_trade_close + daily_pnl update) UNCONDITIONALLY once the wait
    loop ended, regardless of whether get_position() ever actually confirmed
    the position was gone. Only the near-target-lock branch had this right
    (an `if not confirmed: return False` gate). Confirmed live 2026-09-11:
    this exact gap let the bot believe a trade had closed via stop-hit while
    the real Alpaca position stayed open — it was removed from active_trades
    and never monitored again, riding unsupervised for the rest of the
    weekend. One shared, correctly-gated implementation instead of six
    near-identical copies that can't be forgotten or drift out of sync again.

    Returns True if the close was confirmed and the trade finalized; False if
    not yet confirmed (caller should return False too, so the next poll
    cycle retries — the trade stays in active_trades, still being watched).
    """
    close_ok = close_all(api)
    if not close_ok:
        log(f"{label}: close_all() call failed (API error) — will retry next scan cycle", "WARN")
    confirmed = False
    for _ in range(max_wait):
        time.sleep(1)
        try:
            if get_position(api) is None:
                confirmed = True
                break
        except Exception:
            break
    if not confirmed:
        retry_count = trade.get("_close_retry_count", 0) + 1
        trade["_close_retry_count"] = retry_count
        state["status"] = f"{label} close unconfirmed (attempt {retry_count}) — retrying"
        save_state()
        if retry_count >= 8:
            log(f"{label} CLOSE STILL UNCONFIRMED after {retry_count} attempts — "
                f"CHECK ALPACA MANUALLY, bot will keep retrying", "ERROR")
        return False

    duration = int((now_local() - trade["opened_at"]).total_seconds() / 60)
    trade.update({"outcome": outcome, "exit_px": round(exit_px, 2),
                  "pnl": round(pnl, 2), "closed_at": now_local(),
                  "duration_min": duration})
    remove_active_trade(trade)
    _finalize_trade_close(trade)
    state["daily_pnl"]    = state.get("daily_pnl", 0.0) + round(pnl, 2)
    state["trades_today"] = state.get("trades_today", 0) + 1
    _record_day_trade()
    state["trail_activated"] = False
    state["trail_peak"]      = 0.0
    state["trail_stop"]      = 0.0
    save_state()
    return True


def _monitor_bot_trade(trade, api):
    """Monitor a single bot (Alpaca) trade. Returns True if trade closed."""
    fvg_type = trade.get("fvg_type", "bearish")

    # ── EOD force-close inside monitor ───────────────────────────────────
    # end_of_day_check() only runs from the main scan loop, which never
    # gets reached while _monitor_bot_trade is running. If it's past the
    # scheduled close time with a position open, close it here directly.
    # Use 15:55 ET as a hard cap — get_scheduled_close() can return 16:00
    # which is too late (summary fires first and position stays open).
    #
    # v4.88 CRITICAL fix: the `_now_et_mon.time() >= _scheduled_close` check
    # compares bare times-of-day with no date attached. It correctly holds
    # true for the rest of a trading day once past close, but the INSTANT
    # the clock crosses midnight, now_et().time() resets to ~00:00:00 — which
    # is less than 15:55, so this silently stopped being true. Execution then
    # fell through to the live tick-based target/stop checks below, which
    # were never meant to run outside real market hours and (at the time)
    # trusted Alpaca's reported current_price with no freshness/sanity check
    # at all. Confirmed live 2026-09-11 23:00 CDT (exactly midnight ET): the
    # instant this gate went false, "Alpaca returned no bars for NVDA" and
    # "YF rate limited" fired in the same breath, and the very next line was
    # a false STOP HIT — the position was marked closed and abandoned in the
    # bot's own bookkeeping while the real Alpaca position stayed open,
    # unsupervised, all weekend. Added `or not is_market_open()` — that check
    # is fully date/weekday-aware (re-evaluates now_et() fresh every call, no
    # cached/bare-time comparison), so it correctly stays true through the
    # entire gap until the next real session open, not just until midnight.
    # The bare time check is kept for the 15:55-16:00 ET window specifically,
    # where the market is technically still open but we want to force-close
    # 5 minutes early.
    _scheduled_close = min(get_scheduled_close(), dtime(15, 55))
    _now_et_mon = now_et()

    # v4.94: SWING-6M is exempted from the same-day EOD force-close. Its
    # mean-reversion-from-6-month-extreme thesis is a genuinely multi-day
    # setup — backtesting showed forcing it closed every day like every
    # other strategy meant it reached its real target only ~11% of the
    # time vs ~30% when allowed to run to actual resolution (total R across
    # the 2020-2026 backtest window flips from -16.21 to +31.50). Still
    # bounded: force-closed once swing_max_hold_days trading days have
    # elapsed even if neither stop nor target has hit, so this can't become
    # an unbounded, months-long bagholding position. Every other strategy's
    # EOD behavior below is completely unchanged.
    _is_swing6m = trade.get("strategy") == "SWING-6M"
    _swing_hold_cap_hit = False
    if _is_swing6m:
        _biz_days_held = int(np.busday_count(trade["opened_at"].date(), _now_et_mon.date()))
        _swing_hold_cap_hit = _biz_days_held >= CONFIG.get("swing_max_hold_days", 10)
    _swing_exempt = _is_swing6m and not _swing_hold_cap_hit

    if _swing_exempt:
        if not is_market_open():
            # Carrying past today's close is the whole point, but the price
            # data outside real market hours is exactly what caused the
            # v4.88 false-stop-hit bug (stale/invalid price trusted as real).
            # Pause entirely rather than check stop/target against it —
            # resumes normal monitoring the moment the next session opens.
            return False
        # Market is open on a later day than entry — fall through to the
        # normal in-session stop/target monitoring below, same as any trade.
    elif _now_et_mon.time() >= _scheduled_close or not is_market_open():
        log("EOD — closing open position from within monitor (main loop unreachable)"
            + (" [SWING-6M hold-day cap reached]" if _is_swing6m else ""), "TRADE")
        _eod_exit_px  = state.get("last_price", trade.get("entry", 0))
        _eod_confirmed = False
        try:
            _eod_pos = get_position(api)
            if _eod_pos is not None:
                _eod_exit_px = float(_eod_pos.current_price)
            # Always attempt close regardless of position check result —
            # get_position() can return None on network hiccup even when
            # position exists, causing close to be skipped silently
            _eod_close_ok = close_all(api)
            if not _eod_close_ok:
                log("EOD close_all() call failed (API error) — will retry next scan cycle", "WARN")
            # Wait up to 10s for confirmation
            for _ew in range(10):
                time.sleep(1)
                try:
                    if get_position(api) is None:
                        log("Position confirmed closed at EOD", "TRADE")
                        _eod_confirmed = True
                        break
                except Exception:
                    break
            else:
                log("EOD close not confirmed within 10s — position may still be open, "
                    "will retry next scan cycle (~15s)", "WARN")
        except Exception as _eod_e:
            log(f"EOD monitor close failed: {_eod_e} — will retry next scan cycle", "WARN")

        # v4.52 fix: previously the trade was marked closed here regardless of
        # whether Alpaca actually confirmed the position was gone. That caused
        # the bot's internal state (daily_pnl, active_trades, trade log) to say
        # "closed" while the real Alpaca position stayed open, requiring manual
        # intervention. Now: only book the trade as closed once confirmed.
        # If not confirmed, leave it in active_trades — the caller (monitor_trade /
        # between-KZ / post-KZ loops) re-invokes this function every poll cycle,
        # so the close attempt retries automatically.
        if not _eod_confirmed:
            _eod_retry_count = trade.get("_eod_retry_count", 0) + 1
            trade["_eod_retry_count"] = _eod_retry_count
            state["status"] = f"EOD close unconfirmed (attempt {_eod_retry_count}) — retrying"
            save_state()
            # Escalate after ~2 minutes of retries (roughly 8 cycles at 15s poll)
            # so this is loudly visible instead of silently retrying forever.
            if _eod_retry_count >= 8:
                log(f"EOD CLOSE STILL UNCONFIRMED after {_eod_retry_count} attempts — "
                    f"CHECK ALPACA MANUALLY, bot will keep retrying", "ERROR")
            return False

        trade["outcome"]  = "EOD_CLOSE"
        trade["exit_px"]  = _eod_exit_px
        trade["pnl"]      = round(
            (trade["exit_px"] - trade["entry"]) * trade["qty"]
            if fvg_type == "bullish"
            else (trade["entry"] - trade["exit_px"]) * trade["qty"], 2)
        _finalize_trade_close(trade)
        state["daily_pnl"] = state.get("daily_pnl", 0.0) + trade["pnl"]
        state["trades_today"] = state.get("trades_today", 0) + 1
        _record_day_trade()
        remove_active_trade(trade)
        save_state()
        return True

    pos = get_position(api)

    if pos is None:
        # Guard: position may not be visible yet immediately after fill.
        # Alpaca's positions endpoint can lag 10-30 seconds after a short
        # sell fills — returning None during this window causes the bot to
        # incorrectly process the trade as closed and submit a buy-to-close
        # against a position that isn't showing yet.
        opened_at = trade.get("opened_at")
        if opened_at:
            seconds_open = (now_local() - opened_at).total_seconds()
            if seconds_open < 30:
                log(f"Position not visible yet ({seconds_open:.0f}s since entry) — "
                    f"waiting for Alpaca position to propagate", "INFO")
                return False

        try:
            order_status = api.get_order(trade["order_id"]).status
            if order_status in ("new", "partially_filled", "pending_new", "accepted"):
                log(f"Order still pending ({order_status}) — not yet filled, continuing to wait")
                state["status"] = f"Order pending fill ({order_status})..."
                return False
        except Exception:
            pass

        # ── FVG time-stop ────────────────────────────────────────────────────
        # Close FVG trades that haven't reached 70% of target after 45 minutes.
        # Captures partial profit rather than risking full reversal to stop.
        _trade_strategy = trade.get("strategy", "UNKNOWN")
        if _trade_strategy == "FVG" and CONFIG.get("fvg_time_stop_min"):
            _opened = trade.get("opened_at")
            if _opened:
                _mins_open = (now_local() - _opened).total_seconds() / 60
                if _mins_open >= CONFIG["fvg_time_stop_min"]:
                    _pos_ts = get_position(api)
                    _cur_ts = float(_pos_ts.current_price) if _pos_ts else state.get("last_price", trade["entry"])
                    _full_move = abs(trade["target"] - trade["entry"])
                    if _full_move > 0:
                        if fvg_type == "bullish":
                            _progress = (_cur_ts - trade["entry"]) / _full_move
                        else:
                            _progress = (trade["entry"] - _cur_ts) / _full_move
                        _pct_needed = CONFIG.get("fvg_time_stop_pct", 0.70)
                        if _progress < _pct_needed:
                            log(f"FVG TIME-STOP — {_mins_open:.0f} min open, "
                                f"progress {_progress:.0%} < {_pct_needed:.0%} — "
                                f"closing to capture partial profit", "TRADE")
                            _ts_pnl = (_cur_ts - trade["entry"]) * trade["qty"] if fvg_type == "bullish"                                       else (trade["entry"] - _cur_ts) * trade["qty"]
                            _ts_close_ok = close_all(api)
                            if not _ts_close_ok:
                                log("FVG time-stop: close_all() call failed (API error) — will retry next scan cycle", "WARN")
                            _confirmed = False
                            for _w in range(20):
                                time.sleep(1)
                                try:
                                    if get_position(api) is None:
                                        _confirmed = True; break
                                except Exception:
                                    break
                            # v4.52 fix: previously fell through and marked the trade
                            # closed even when Alpaca never confirmed the close, causing
                            # the same state-desync as the EOD bug (daily_pnl/active_trades
                            # said "closed" while the real position stayed open). Now only
                            # book it closed on confirmation; otherwise retry next cycle.
                            if not _confirmed:
                                _ts_retry_count = trade.get("_ts_retry_count", 0) + 1
                                trade["_ts_retry_count"] = _ts_retry_count
                                state["status"] = f"FVG time-stop close unconfirmed (attempt {_ts_retry_count}) — retrying"
                                save_state()
                                if _ts_retry_count >= 8:
                                    log(f"FVG TIME-STOP CLOSE STILL UNCONFIRMED after {_ts_retry_count} attempts — "
                                        f"CHECK ALPACA MANUALLY, bot will keep retrying", "ERROR")
                                return False
                            remove_active_trade(trade)
                            trade["outcome"] = "CLOSED"
                            trade["exit_px"] = round(_cur_ts, 2)
                            trade["pnl"]     = round(_ts_pnl, 2)
                            _finalize_trade_close(trade)
                            state["daily_pnl"]    = state.get("daily_pnl", 0.0) + round(_ts_pnl, 2)
                            state["trades_today"] = state.get("trades_today", 0) + 1
                            _record_day_trade()
                            save_state()
                            return True

        df = fetch_candles(CONFIG["ticker"], bars=10)
        if df is not None:
            last_px = df["Close"].iloc[-1]
            # v4.52 fix: only update last_price if this bar is from today.
            # fetch_candles() can fall back to stale IEX/YF bars from a prior
            # day on no-bar days (e.g. Fridays) — writing that stale close into
            # last_price caused phantom price jumps on the dashboard chart.
            _mon_bar_date = df.index[-1].date() if hasattr(df.index[-1], 'date') else None
            if _mon_bar_date == now_et().date():
                state["last_price"] = round(float(last_px), 2)

            if fvg_type == "bullish":
                if last_px >= trade["target"]:
                    outcome = "WIN"
                elif last_px <= trade["stop"]:
                    outcome = "LOSS"
                else:
                    outcome = "CLOSED"
            else:
                if last_px <= trade["target"]:
                    outcome = "WIN"
                elif last_px >= trade["stop"]:
                    outcome = "LOSS"
                else:
                    outcome = "CLOSED"

            # ── Use actual Alpaca fill price, not theoretical target/stop ──
            # The bot detects close via price crossing target/stop, but the
            # actual bracket fill may differ due to slippage. Reading the
            # real fill from Alpaca ensures P&L reflects what actually happened.
            exit_px = float(last_px)  # fallback to current price
            try:
                if api:
                    # Look for orders filled AFTER this trade opened
                    # to avoid picking up fills from previous trades
                    _opened_at_str = trade.get("opened_at")
                    _cover_side = "buy" if fvg_type == "bearish" else "sell"
                    # Convert opened_at to ISO string for Alpaca API
                    _after_str = None
                    if _opened_at_str:
                        if hasattr(_opened_at_str, 'isoformat'):
                            _after_str = _opened_at_str.isoformat()
                        else:
                            _after_str = str(_opened_at_str)
                    _closed_orders = api.list_orders(
                        status="closed",
                        symbols=[CONFIG["ticker"]],
                        limit=10,
                        after=_after_str
                    )
                    for _o in sorted(_closed_orders,
                                     key=lambda x: str(x.filled_at or ""),
                                     reverse=True):
                        if (_o.side == _cover_side
                                and _o.filled_avg_price
                                and _o.filled_qty
                                and _o.position_intent in ("buy_to_close", "sell_to_close", None)):
                            exit_px = round(float(_o.filled_avg_price), 4)
                            log(f"Actual fill price from Alpaca: ${exit_px:.4f} "
                                f"(vs theoretical {'target' if outcome == 'WIN' else 'stop'}: "
                                f"${trade['target'] if outcome == 'WIN' else trade['stop']:.2f})")
                            break
                    else:
                        # v4.59 fix: this fell through silently before — no log at
                        # all when no matching fill was found, leaving exit_px on
                        # the `last_px` candle-close fallback with zero visibility
                        # that it happened. That fallback can be badly stale
                        # (IEX has repeatedly lacked current-day bars), producing
                        # a silently-wrong P&L. Now always logged loudly so a bad
                        # number is at least visible instead of trusted quietly.
                        log(f"No matching Alpaca fill found for exit price — "
                            f"using last candle close ${exit_px:.2f} as a fallback "
                            f"(may be stale) — verify this trade's P&L manually", "ERROR")
            except Exception as _fe:
                log(f"Could not fetch actual fill price: {_fe} — using last price", "WARN")

            # Recalculate outcome based on actual fill vs entry
            if fvg_type == "bullish":
                pnl = (exit_px - trade["entry"]) * trade["qty"]
            else:
                pnl = (trade["entry"] - exit_px) * trade["qty"]
            # Override outcome based on actual P&L (fill may differ from signal)
            if outcome in ("WIN", "LOSS"):
                outcome = "WIN" if pnl > 0 else "LOSS"

            duration = int((now_local() - trade["opened_at"]).total_seconds() / 60)
            trade.update({"outcome": outcome, "exit_px": float(exit_px),
                          "pnl": round(pnl, 2), "closed_at": now_local(),
                          "duration_min": duration})
            log(f"TRADE CLOSED — {outcome} | PnL: ${pnl:,.2f} | Duration: {duration}min", "TRADE")
            state["status"]       = f"Trade closed: {outcome} | PnL: ${pnl:,.2f}"
            # v4.95 fix: this reconciliation path (position found gone on
            # Alpaca — an externally-closed position, e.g. a manual close_all()
            # outside the bot's own stop/target/EOD checks) never called
            # remove_active_trade(), unlike every other close path in this
            # file (EOD close, FVG time-stop). The trade got fully logged and
            # P&L'd correctly, but stayed stuck in state["active_trades"]
            # forever — confirmed live twice this week (2026-09-29, 09-30)
            # after manually closing a stale/unwanted position, requiring a
            # hand-edit of session_state.json to clear it. Root cause, not
            # the network flakiness it looked like at the time.
            remove_active_trade(trade)
            _finalize_trade_close(trade)
            state["daily_pnl"]    = state.get("daily_pnl", 0.0) + round(pnl, 2)
            state["trades_today"] = state.get("trades_today", 0) + 1
            _record_day_trade()
            log(f"Trade #{state['trades_today']} closed — resuming scan | "
                f"Day P&L so far: ${state['daily_pnl']:+,.2f}")
            save_state()
            return True
        return False

    # Position is open
    unreal = float(pos.unrealized_pl)
    cur_px     = float(pos.current_price)
    fill_price = float(pos.avg_entry_price)

    # v4.88 defense-in-depth: reject an obviously-broken price before it can
    # ever reach the target/stop comparisons below. The EOD gate fix above
    # (now date-aware via is_market_open()) should prevent this function from
    # reaching this point at all outside real market hours, which was the
    # actual mechanism behind the 2026-09-11 false stop-hit — but this is a
    # second, independent layer: if Alpaca ever reports a zero/negative
    # current_price for any other reason during real market hours, don't let
    # it anywhere near a stop/target decision. Skip this poll and retry next
    # cycle rather than trusting a value that can't be real.
    if cur_px <= 0:
        log(f"_monitor_bot_trade: Alpaca reported an invalid current_price "
            f"({cur_px}) — skipping this poll, will retry next cycle", "WARN")
        return False

    state["last_price"] = round(cur_px, 2)

    # Sync trade entry to actual fill price on first monitor (fill may differ from requested)
    # This ensures breakeven/trail calculations use the real cost basis
    if not trade.get("_entry_synced") and abs(fill_price - trade["entry"]) > 0.01:
        log(f"Entry synced to fill: ${trade['entry']:.2f} → ${fill_price:.2f} "
            f"(slippage: ${fill_price - trade['entry']:+.2f})")
        # v4.65 fix: this used to update ONLY entry, leaving stop/target at their
        # original absolute price levels. Large slippage (fast-moving strategies
        # like RANGE re-entering repeatedly near a boundary) could push the synced
        # entry past the original target/stop, making the setup directionally
        # invalid — e.g. a SHORT's target ending up ABOVE the new entry. The
        # target/stop-hit checks only compare cur_px against trade["target"]/
        # ["stop"], with no validity check against entry, so this produced an
        # immediate false "target hit → WIN" classification with a NEGATIVE real
        # P&L (confirmed live: RANGE short, entry synced to $206.32 with target
        # still at $206.84 — above entry — logged WIN with pnl -$50.78). Now
        # recomputes stop/target from the new entry, preserving the ORIGINAL
        # risk/reward distances, so the setup stays directionally sane regardless
        # of slippage magnitude.
        _stop_dist   = abs(trade["entry"] - trade["stop"])
        _target_dist = abs(trade["target"] - trade["entry"])
        trade["entry"] = fill_price
        if fvg_type == "bullish":
            trade["stop"]   = round(fill_price - _stop_dist, 2)
            trade["target"] = round(fill_price + _target_dist, 2)
        else:
            trade["stop"]   = round(fill_price + _stop_dist, 2)
            trade["target"] = round(fill_price - _target_dist, 2)
        trade["orig_stop"]     = trade["stop"]
        trade["_entry_synced"] = True
    elif not trade.get("_entry_synced"):
        if not trade.get("orig_stop"):
            trade["orig_stop"] = trade["stop"]
        trade["_entry_synced"] = True

    # v4.88 fix: this had no market-hours guard at all — with the v4.86 fix
    # keeping the bot alive and calling monitor_trade() through nights and
    # weekends (so a still-open position stays watched), this ran on every
    # one of those off-hours polls too, writing Alpaca's frozen "last known"
    # price into price_history with the REAL current wall-clock timestamp.
    # Confirmed live: entries dated a Sunday afternoon, all the same price,
    # from a position monitored over a weekend — the chart showed fake
    # "trading" during a period NVDA was never open. Only log real market
    # data.
    if 50 < cur_px < 2000 and is_market_open():
        kz = get_current_kill_zone() or state.get("last_kz", "open")
        state["last_kz"] = kz
        ts = datetime.now(MARKET_TZ).strftime("%Y-%m-%dT%H:%M")
        hist = state.get("price_history", [])
        _recent_ts2 = {h["t"] for h in hist[-4:]} if hist else set()
        if ts not in _recent_ts2:
            hist.append({"t": ts, "p": round(cur_px, 2), "kz": kz,
                         "trend": state.get("last_trend") or "neutral",
                         "mtf":   state.get("mtf_bias")  or "neutral"})
            state["price_history"] = hist[-2000:]
        else:
            for _h in reversed(hist):
                if _h["t"] == ts:
                    _h["p"] = round(cur_px, 2)
                    break

    # ── Near-target time lock ───────────────────────────────────────────────
    # See CONFIG["near_target_lock_min"/"near_target_lock_pct"] for rationale:
    # tight-target strategies can sit most of the way to target for a long
    # time without the R-multiple trail ever engaging. Once open long enough
    # and mostly there, bank it instead of gambling on the last few cents.
    if CONFIG.get("near_target_lock_min"):
        _ntl_opened = trade.get("opened_at")
        if _ntl_opened:
            _ntl_mins = (now_local() - _ntl_opened).total_seconds() / 60
            if _ntl_mins >= CONFIG["near_target_lock_min"]:
                _ntl_full_move = abs(trade["target"] - trade["entry"])
                if _ntl_full_move > 0:
                    _ntl_progress = ((cur_px - trade["entry"]) / _ntl_full_move if fvg_type == "bullish"
                                      else (trade["entry"] - cur_px) / _ntl_full_move)
                    _ntl_pct = CONFIG.get("near_target_lock_pct", 0.85)
                    if _ntl_progress >= _ntl_pct:
                        log(f"NEAR-TARGET LOCK — {_ntl_mins:.0f} min open, "
                            f"{_ntl_progress:.0%} of the way to target (${trade['target']:.2f}) — "
                            f"closing now to bank the profit instead of waiting for the exact tick", "TRADE")
                        _ntl_pnl = ((cur_px - trade["entry"]) * trade["qty"] if fvg_type == "bullish"
                                    else (trade["entry"] - cur_px) * trade["qty"])
                        return _confirm_and_finalize_close(
                            api, trade, "WIN" if _ntl_pnl > 0 else "LOSS", cur_px, _ntl_pnl,
                            "NEAR-TARGET LOCK", max_wait=20)

    # Fetch latest candle for wick detection — used by both trail and fixed target checks
    _wick_df  = fetch_candles(CONFIG["ticker"], bars=2)
    _bar_high = float(_wick_df["High"].iloc[-1]) if _wick_df is not None else cur_px
    _bar_low  = float(_wick_df["Low"].iloc[-1])  if _wick_df is not None else cur_px

    # Hybrid trailing stop
    if CONFIG.get("hybrid_trail") and state.get("last_atr", 0) > 0:
        atr       = state["last_atr"]
        entry     = trade["entry"]
        orig_stop = trade.get("orig_stop", trade["stop"])
        risk      = abs(entry - orig_stop)

        move = (cur_px - entry) if fvg_type == "bullish" else (entry - cur_px)

        # RANGE trades skip breakeven — price bouncing back toward entry is
        # expected oscillation behavior, not a reversal. Breakeven would close
        # the trade for near-zero profit right when it's about to drop to target.
        # RANGE uses original stop + trailing stop only (no breakeven middle step).
        _skip_be = (trade.get("strategy") == "RANGE")

        if not state["trail_activated"] and not _skip_be and move >= risk:
            # Add a small buffer beyond entry so the BE stop isn't triggered
            # by a single tick. For SHORT: stop = entry + buffer (above entry).
            # For LONG: stop = entry - buffer (below entry).
            # Buffer = half the spread/tick size, capped at 20% of original risk
            # so it doesn't eat too much of the protected profit.
            _be_buffer = round(min(0.10, risk * 0.20), 2)
            if fvg_type == "bearish":
                new_stop = round(entry + _be_buffer, 2)  # SHORT: stop above entry
            else:
                new_stop = round(entry - _be_buffer, 2)  # LONG: stop below entry
            if new_stop != trade["stop"]:
                trade["stop"] = new_stop
                trade["orig_stop"] = orig_stop
                log(f"BREAKEVEN LOCK — stop moved to ${new_stop:.2f} "
                    f"(entry ${entry:.2f} + ${_be_buffer:.2f} buffer)", "TRADE")
                try:
                    orders = api.list_orders(status="open", symbols=[CONFIG["ticker"]])
                    for o in orders:
                        if o.order_class == "bracket" or o.type in ("stop", "stop_limit"):
                            api.cancel_order(o.id)
                    side = "sell" if fvg_type == "bullish" else "buy"
                    qty  = trade["qty"] if fvg_type == "bullish" else abs(int(trade["qty"]))
                    api.submit_order(symbol=CONFIG["ticker"], qty=qty, side=side,
                                     type="stop", time_in_force="day", stop_price=str(new_stop))
                except Exception as e:
                    log(f"Could not update stop to breakeven: {e}", "WARN")

        if not state["trail_activated"] and move >= risk * 2:
            state["trail_activated"] = True
            state["trail_peak"]      = cur_px
            trail_dist               = round(atr * CONFIG["trail_atr_mult"], 2)
            state["trail_stop"] = round(cur_px - trail_dist if fvg_type == "bullish"
                                        else cur_px + trail_dist, 2)
            try:
                orders = api.list_orders(status="open", symbols=[CONFIG["ticker"]])
                for o in orders:
                    if o.type in ("limit", "take_profit"):
                        api.cancel_order(o.id)
            except Exception as e:
                log(f"Could not cancel target order: {e}", "WARN")
            log(f"TRAILING STOP ACTIVATED — trail: ${state['trail_stop']:.2f}", "TRADE")

        if state["trail_activated"]:
            trail_dist = round(atr * CONFIG["trail_atr_mult"], 2)
            if fvg_type == "bullish":
                if cur_px > state["trail_peak"]:
                    state["trail_peak"] = cur_px
                    # Cap trail stop above target — trail must never be set below
                    # target for a LONG, otherwise it triggers before target is reached
                    _raw_trail = round(cur_px - trail_dist, 2)
                    state["trail_stop"] = max(_raw_trail, trade["target"] + 0.01)
                    trade["stop"] = state["trail_stop"]
                if cur_px <= state["trail_stop"]:  # _bar_low removed — stale bars trigger early
                    pnl = (cur_px - entry) * trade["qty"]
                    log(f"TRAILING STOP HIT — WIN | Exit ${cur_px:.2f} | PnL: ${pnl:+,.2f}", "TRADE")
                    return _confirm_and_finalize_close(api, trade, "WIN", cur_px, pnl,
                                                        "TRAILING STOP HIT", max_wait=20)
            else:
                if cur_px < state["trail_peak"] or state["trail_peak"] == 0.0:
                    state["trail_peak"] = cur_px
                    # Cap trail stop below target — trail must never be set above
                    # target for a SHORT, otherwise it triggers before target is reached
                    _raw_trail = round(cur_px + trail_dist, 2)
                    state["trail_stop"] = min(_raw_trail, trade["target"] - 0.01)
                    trade["stop"] = state["trail_stop"]
                if cur_px >= state["trail_stop"]:  # _bar_high removed — stale bars trigger early
                    pnl = (entry - cur_px) * trade["qty"]
                    log(f"TRAILING STOP HIT — WIN | Exit ${cur_px:.2f} | PnL: ${pnl:+,.2f}", "TRADE")
                    return _confirm_and_finalize_close(api, trade, "WIN", cur_px, pnl,
                                                        "TRAILING STOP HIT", max_wait=20)

    trade["pnl"] = round(unreal, 2)
    trail_note = f" | Trail: ${state['trail_stop']:.2f}" if state.get("trail_activated") and state.get("trail_stop") else ""

    # Fixed target/stop check — catches cases where trailing stop hasn't activated yet.
    # Uses BOTH cur_px (last tick) AND latest candle high/low (fetched above) so fast
    # wicks through target/stop don't escape between 15-second polls.
    if not state.get("trail_activated"):
        # LONG: target hit if cur_px OR candle high reached target
        # LONG: target hit if cur_px reached target (_bar_high excluded — stale bars)
        if fvg_type == "bullish" and cur_px >= trade["target"]:
            _exit = trade["target"]
            pnl = (_exit - trade["entry"]) * trade["qty"]
            log(f"TARGET HIT [BULLISH] — WIN | Exit ${_exit:.2f} | PnL: ${pnl:+,.2f}", "TRADE")
            return _confirm_and_finalize_close(api, trade, "WIN", _exit, pnl, "TARGET HIT [BULLISH]")
        # LONG: stop hit if cur_px OR candle low breached stop
        # LONG: stop hit if cur_px breached stop (_bar_low excluded — stale bars)
        elif fvg_type == "bullish" and cur_px <= trade["stop"]:
            _exit = trade["stop"]
            pnl = (_exit - trade["entry"]) * trade["qty"]
            log(f"STOP HIT [BULLISH] — LOSS | Exit ${_exit:.2f} | PnL: ${pnl:+,.2f}", "TRADE")
            return _confirm_and_finalize_close(api, trade, "LOSS", _exit, pnl, "STOP HIT [BULLISH]")
        # SHORT: target hit if cur_px reached target
        # NOTE: _bar_low intentionally excluded — stale/fallback IEX bars from
        # a prior session have lows that falsely trigger today's target price.
        elif fvg_type == "bearish" and cur_px <= trade["target"]:
            _exit = trade["target"]
            pnl = (trade["entry"] - _exit) * trade["qty"]
            log(f"TARGET HIT [BEARISH] — WIN | Exit ${_exit:.2f} | PnL: ${pnl:+,.2f}", "TRADE")
            return _confirm_and_finalize_close(api, trade, "WIN", _exit, pnl, "TARGET HIT [BEARISH]")
        # SHORT: stop hit if cur_px breached stop
        # NOTE: _bar_high excluded — stale IEX bars can falsely trigger stops.
        elif fvg_type == "bearish" and cur_px >= trade["stop"]:
            _exit = trade["stop"]
            pnl = (trade["entry"] - _exit) * trade["qty"]
            log(f"STOP HIT [BEARISH] — LOSS | Exit ${_exit:.2f} | PnL: ${pnl:+,.2f}", "TRADE")
            return _confirm_and_finalize_close(api, trade, "LOSS", _exit, pnl, "STOP HIT [BEARISH]")

    now_min = now_local().strftime("%H:%M")
    # Log every poll if price within 20% of stop distance (stress zone) — otherwise once/min
    stop_dist   = abs(cur_px - trade["stop"])
    risk_dist   = abs(trade["entry"] - trade.get("orig_stop", trade["stop"]))
    near_stop   = risk_dist > 0 and stop_dist <= risk_dist * 0.20
    should_log  = near_stop or trade.get("_last_log_min") != now_min
    if should_log:
        trade["_last_log_min"] = now_min
        stress = " ⚠ NEAR STOP" if near_stop else ""
        log(f"Position open [{(fvg_type or "unknown").upper()}] — ${cur_px:.2f} | "
            f"Unrealized: ${unreal:,.2f} | Target: ${trade['target']:.2f} | Stop: ${trade['stop']:.2f}{trail_note}{stress}")
    return False


def _monitor_manual_trade(trade):
    """Monitor a single manual trade — now backed by a real Alpaca bracket order."""
    # v4.56 fix: this used to bail out here immediately whenever cached
    # state["last_price"] was 0 — which happens on every restart (last_price
    # isn't persisted) and stays 0 indefinitely once a trade is open, because
    # the background refresh that would normally populate it is deliberately
    # skipped while any trade is active. That made this function permanently
    # unable to self-heal: it never got far enough to fetch the real Alpaca
    # position price that would have fixed last_price, so a manual trade
    # opened right after a restart went completely unmonitored — no entry
    # sync, no target/stop checks, no P&L — until the bot was restarted while
    # flat. Manual shorts have no broker-side stop order (IEX limitation), so
    # this silently removed the only thing protecting the position. Now the
    # cur_px<=0 bailout only applies as a last resort, after attempting to
    # pull a live price straight from the Alpaca position below.
    fvg_type = trade.get("fvg_type", "bearish")
    cur_px   = state.get("last_price", 0)

    # Check if Alpaca already closed the position (stop or target fill)
    api_result = get_alpaca()
    if api_result[0] is not None:
        api = api_result[0]

        # ── Sync entry price to actual Alpaca fill on first monitor call ──
        # The dashboard entry comes from what was typed in the manual trade
        # modal, not the actual fill. This causes P&L to be wrong whenever
        # there's slippage. Query the actual fill price once and update.
        #
        # v4.60 fix: this used to search list_orders(after=trade["opened_at"])
        # for a matching fill — but opened_at is stamped AFTER place_order()
        # returns, and a market order can fill (in Alpaca's paper engine)
        # before that stamp happens. That made the "after" filter exclude the
        # exact fill it needed, and the loop's fallthrough (`else:` — no match
        # found) silently marked _entry_synced=True anyway, permanently giving
        # up without ever correcting entry. Confirmed live: a $10-share LONG
        # showed entry $206.65 (typed price) vs the real $209.73 fill,
        # inflating displayed P&L by $30+. Fixed by fetching the exact order
        # by its own ID instead of fuzzy-matching by timestamp/side — there's
        # no ambiguity about which order this is. If it isn't filled yet,
        # _entry_synced is left False so this retries next poll instead of
        # giving up.
        if not trade.get("_entry_synced"):
            try:
                _order_chk = api.get_order(trade["order_id"])
                if _order_chk.filled_avg_price:
                    _real_entry = round(float(_order_chk.filled_avg_price), 4)
                    if abs(_real_entry - trade["entry"]) > 0.01:
                        log(f"Manual entry synced to fill: ${trade['entry']:.2f} → "
                            f"${_real_entry:.4f} (slippage: ${_real_entry - trade['entry']:+.2f})")
                        # v4.65 fix: same class of bug as the bot-trade entry-sync —
                        # only entry was updated, leaving stop/target at their
                        # original absolute levels, which slippage could push past,
                        # making the setup directionally invalid (target on the
                        # wrong side of the new entry). Recompute stop/target from
                        # the new entry, preserving the original risk/reward
                        # distances, so it stays sane regardless of slippage.
                        _stop_dist   = abs(trade["entry"] - trade["stop"])
                        _target_dist = abs(trade["target"] - trade["entry"])
                        trade["entry"] = _real_entry
                        if fvg_type == "bullish":
                            trade["stop"]   = round(_real_entry - _stop_dist, 2)
                            trade["target"] = round(_real_entry + _target_dist, 2)
                        else:
                            trade["stop"]   = round(_real_entry + _stop_dist, 2)
                            trade["target"] = round(_real_entry - _target_dist, 2)
                        trade["orig_stop"] = trade["stop"]
                    trade["_entry_synced"] = True
                # else: order not filled yet — retry next poll cycle
            except Exception as _sync_e:
                log(f"Could not sync manual entry to fill (will keep trying): {_sync_e}", "WARN")

        pos = get_position(api)
        if pos is None:
            # v4.75 fix: CRITICAL — this branch had no grace period before
            # treating "no position" as "closed," unlike _monitor_bot_trade()'s
            # sibling check (which waits up to 30s for Alpaca's positions
            # endpoint to catch up after a fill). Confirmed live: a manual
            # trade placed at 09:59:34 CDT was polled again at 09:59:35 — one
            # second later — got pos=None because the fill genuinely hadn't
            # propagated yet, and was immediately marked "auto-closed WIN,
            # PnL $+0.00" while the real position stayed open on Alpaca. It
            # was never removed from active_trades either (no
            # remove_active_trade() call below), so it kept being monitored
            # indefinitely with a permanently wrong outcome/pnl label stuck
            # on it while the dashboard showed WIN for a trade that was, in
            # reality, still open. Add the same 30s guard as the bot-trade
            # path before trusting pos is None.
            opened_at = trade.get("opened_at")
            if opened_at:
                seconds_open = (now_local() - opened_at).total_seconds()
                if seconds_open < 30:
                    log(f"Manual position not visible yet ({seconds_open:.0f}s "
                        f"since entry) — waiting for Alpaca position to propagate")
                    return False

            # Position gone — bracket order was filled (stop or target hit)
            # Determine outcome from last known price vs entry.
            # If cur_px was never populated (e.g. this trade was never
            # successfully monitored before Alpaca shows it gone), fall back
            # to entry rather than reporting a bogus $0 exit/PnL.
            entry  = trade["entry"]
            if cur_px <= 0:
                cur_px = entry
            pnl_est = (cur_px - entry) * trade["qty"] if fvg_type == "bullish" \
                      else (entry - cur_px) * trade["qty"]
            outcome = "WIN" if pnl_est >= 0 else "LOSS"
            duration = int((now_local() - trade["opened_at"]).total_seconds() / 60)
            trade.update({"outcome": outcome, "exit_px": cur_px,
                          "pnl": round(pnl_est, 2), "closed_at": datetime.now(MARKET_TZ),
                          "duration_min": duration})
            log(f"MANUAL TRADE auto-closed by Alpaca [{trade['order_id']}] — "
                f"{outcome} | Exit ~${cur_px:.2f} | PnL: ${pnl_est:+,.2f}", "TRADE")
            _finalize_trade_close(trade)
            state["daily_pnl"]    = state.get("daily_pnl", 0.0) + round(pnl_est, 2)
            state["trades_today"] = state.get("trades_today", 0) + 1
            _record_day_trade()
            # v4.75 fix: this never removed the trade from active_trades —
            # missing here entirely (the bot-trade sibling always has this).
            # Combined with the missing grace period above, a false-positive
            # "closed" trade stayed in active_trades forever, still being
            # monitored, permanently stuck showing a stale WIN/LOSS label
            # while the real position kept trading on Alpaca underneath it.
            remove_active_trade(trade)
            log(f"Trade #{state['trades_today']} closed — Day P&L: ${state['daily_pnl']:+,.2f}")
            save_state()
            return True
        else:
            # Use real unrealized P&L from Alpaca position
            cur_px = float(pos.current_price)
            state["last_price"] = round(cur_px, 2)

    if cur_px <= 0:
        # Only reachable if Alpaca itself was unreachable above AND there was
        # no cached price to fall back on — genuinely nothing to check against
        # yet. Retried next poll cycle.
        return False

    entry     = trade["entry"]
    risk      = abs(entry - trade.get("orig_stop", trade["stop"]))
    use_trail = trade.get("use_trail", False)

    if use_trail and risk > 0:
        atr = state.get("last_atr", risk * 0.5) or risk * 0.5
        if fvg_type == "bullish":
            profit = cur_px - entry
            if not trade.get("trail_active") and profit >= risk * 2:
                trade["trail_stop"]   = round(cur_px - atr, 2)
                trade["trail_active"] = True
                trade["stop"]         = trade["trail_stop"]
                log(f"MANUAL TRAIL [{trade['order_id']}] activated — stop: ${trade['trail_stop']:.2f}", "TRADE")
            elif not trade.get("trail_active") and profit >= risk:
                if trade["stop"] < entry:
                    trade["stop"] = entry
                    log(f"MANUAL BREAKEVEN [{trade['order_id']}] — stop: ${entry:.2f}", "TRADE")
            elif trade.get("trail_active"):
                new_trail = round(cur_px - atr, 2)
                if new_trail > trade["stop"]:
                    trade["stop"] = new_trail
                    trade["trail_stop"] = new_trail
        else:
            profit = entry - cur_px
            if not trade.get("trail_active") and profit >= risk * 2:
                trade["trail_stop"]   = round(cur_px + atr, 2)
                trade["trail_active"] = True
                trade["stop"]         = trade["trail_stop"]
                log(f"MANUAL TRAIL [{trade['order_id']}] activated — stop: ${trade['trail_stop']:.2f}", "TRADE")
            elif not trade.get("trail_active") and profit >= risk:
                if trade["stop"] > entry:
                    trade["stop"] = entry
                    log(f"MANUAL BREAKEVEN [{trade['order_id']}] — stop: ${entry:.2f}", "TRADE")
            elif trade.get("trail_active"):
                new_trail = round(cur_px + atr, 2)
                if new_trail < trade["stop"]:
                    trade["stop"] = new_trail
                    trade["trail_stop"] = new_trail

    unreal = (cur_px - entry) * trade["qty"] if fvg_type == "bullish" else (entry - cur_px) * trade["qty"]
    trade["pnl"] = round(unreal, 2)

    # Wick detection — fetch latest candle bar high/low so fast moves between
    # 15-second polls don't escape (mirrors _monitor_bot_trade logic)
    _wick_df  = fetch_candles(CONFIG["ticker"], bars=2)
    _bar_high = float(_wick_df["High"].iloc[-1]) if _wick_df is not None else cur_px
    _bar_low  = float(_wick_df["Low"].iloc[-1])  if _wick_df is not None else cur_px

    if fvg_type == "bullish":
        if cur_px >= trade["target"]:  # _bar_high excluded — stale bars
            outcome, exit_px = "WIN",  trade["target"]
            pnl = (exit_px - entry) * trade["qty"]
        elif cur_px <= trade["stop"]:  # _bar_low excluded — stale bars
            outcome, exit_px = "LOSS", trade["stop"]
            pnl = (exit_px - entry) * trade["qty"]
        else:
            now_min = now_local().strftime("%H:%M")
            if trade.get("_last_log_min") != now_min:
                trade["_last_log_min"] = now_min
                log(f"Manual [LONG {trade['order_id']}] ${cur_px:.2f} | "
                    f"Unreal: ${unreal:+.2f} | Target: ${trade['target']:.2f} | Stop: ${trade['stop']:.2f}")
            return False
    else:
        if cur_px <= trade["target"]:  # _bar_low excluded — stale bars
            outcome, exit_px = "WIN",  trade["target"]
            pnl = (entry - exit_px) * trade["qty"]
        elif cur_px >= trade["stop"]:  # _bar_high excluded — stale bars
            outcome, exit_px = "LOSS", trade["stop"]
            pnl = (entry - exit_px) * trade["qty"]
        else:
            now_min = now_local().strftime("%H:%M")
            if trade.get("_last_log_min") != now_min:
                trade["_last_log_min"] = now_min
                log(f"Manual [SHORT {trade['order_id']}] ${cur_px:.2f} | "
                    f"Unreal: ${unreal:+.2f} | Target: ${trade['target']:.2f} | Stop: ${trade['stop']:.2f}")
            return False

    # Close position AND cancel any remaining bracket legs (stop/target child orders)
    # Without this, a filled bracket stop order creates a ghost position on next poll
    if trade.get("managed", True):
        # v4.53 fix: previously called close_all() and unconditionally fell through
        # to mark the trade closed 1s later regardless of whether Alpaca actually
        # confirmed the position was gone (or whether close_all even succeeded) —
        # same state-desync risk the v4.52 fix addressed for bot trades, just not
        # extended to manual trades. Now waits for confirmation and retries via the
        # normal poll loop (monitor_trade / between-KZ / post-KZ) if not confirmed.
        _manual_close_confirmed = False
        try:
            api_result = get_alpaca()
            if api_result[0] is not None:
                _api_close = api_result[0]
                # Cancel all open orders first (bracket legs), then close position
                try:
                    stale_orders = _api_close.list_orders(status="open",
                                                          symbols=[CONFIG["ticker"]])
                    for _o in stale_orders:
                        try:
                            _api_close.cancel_order(_o.id)
                        except Exception:
                            pass
                    if stale_orders:
                        time.sleep(1)
                except Exception:
                    pass
                _close_ok = close_all(_api_close)
                if not _close_ok:
                    log("Manual close_all() call failed (API error) — will retry next scan cycle", "WARN")
                for _mw in range(10):
                    time.sleep(1)
                    try:
                        if get_position(_api_close) is None:
                            _manual_close_confirmed = True
                            break
                    except Exception:
                        break
            else:
                log("Manual trade close skipped — Alpaca unreachable, will retry next scan cycle", "WARN")
        except Exception as _ce:
            log(f"Could not close Alpaca position on manual trade exit: {_ce}", "WARN")

        if not _manual_close_confirmed:
            _mt_retry_count = trade.get("_close_retry_count", 0) + 1
            trade["_close_retry_count"] = _mt_retry_count
            state["status"] = f"Manual trade close unconfirmed (attempt {_mt_retry_count}) — retrying"
            if _mt_retry_count >= 8:
                log(f"MANUAL TRADE CLOSE STILL UNCONFIRMED after {_mt_retry_count} attempts — "
                    f"CHECK ALPACA MANUALLY, bot will keep retrying", "ERROR")
            return False

    duration = int((now_local() - trade["opened_at"]).total_seconds() / 60)
    trade.update({"outcome": outcome, "exit_px": exit_px,
                  "pnl": round(pnl, 2), "closed_at": now_local(),
                  "duration_min": duration})
    log(f"MANUAL TRADE CLOSED [{trade['order_id']}] — {outcome} | "
        f"Exit ${exit_px:.2f} | PnL: ${pnl:+,.2f} | Duration: {duration}min", "TRADE")
    _finalize_trade_close(trade)
    state["daily_pnl"]    = state.get("daily_pnl", 0.0) + round(pnl, 2)
    state["trades_today"] = state.get("trades_today", 0) + 1
    _record_day_trade()
    log(f"Trade #{state['trades_today']} closed — Day P&L: ${state['daily_pnl']:+,.2f}")
    save_state()
    return True


def monitor_trade():
    trades = get_active_trades()
    if not trades:
        return

    to_remove = []
    api_cache  = {}  # fetch Alpaca API once per monitor_trade call

    for trade in list(trades):
        strategy = trade.get("strategy", "UNKNOWN")
        if strategy == "MANUAL":
            closed = _monitor_manual_trade(trade)
        else:
            # Get Alpaca API (cached)
            if "api" not in api_cache:
                api_result = get_alpaca()
                if api_result[0] is None:
                    continue
                api_cache["api"] = api_result[0]
            closed = _monitor_bot_trade(trade, api_cache["api"])

        if closed:
            to_remove.append(trade)

    for t in to_remove:
        remove_active_trade(t)

    open_trades = get_active_trades()
    if open_trades:
        parts = []
        for t in open_trades:
            label = "LONG" if t.get("fvg_type") == "bullish" else "SHORT"
            # v4.97 fix: t.get('pnl', 0) only substitutes 0 when the key is
            # missing — an open trade has "pnl": None explicitly set, so this
            # returned None and f"{None:+.2f}" crashed with "unsupported
            # format string passed to NoneType.__format__" every single poll
            # cycle a RESTORED/reconnected trade (which still has pnl=None)
            # was open. Confirmed live 2026-10-03.
            parts.append(f"{t.get('strategy','?')} {label} ${(t.get('pnl') or 0):+.2f}")
        state["status"] = f"TRADES OPEN: {' | '.join(parts)}"
    else:
        state["traded_today"] = False
        # v4.88 fix: this branch never actually touched state["status"], so
        # once the last trade closed, the "TRADES OPEN: ..." string above
        # just sat there untouched — monitor_trade() returns immediately on
        # every later call once active_trades is empty (see the `if not
        # trades: return` at the top), so nothing else was guaranteed to ever
        # overwrite it either. Confirmed live: a status string from a trade
        # that closed Friday was still showing "TRADES OPEN" the following
        # Monday, an hour into the new session, because the bot never
        # actually re-entered a kill zone scan in between to overwrite it.
        # Set an honest, generic status here — check_for_entry() will
        # replace it with something more specific on the next scan anyway.
        if state["status"].startswith("TRADES OPEN"):
            state["status"] = "Position closed — resuming scan"



# ═══════════════════════════════════════════════════════════════
# DAILY SUMMARY
# ═══════════════════════════════════════════════════════════════

def save_daily_summary():
    today    = now_local().date()
    log_dir  = "trade_logs"
    os.makedirs(log_dir, exist_ok=True)

    api_result = get_alpaca()

    # Use BOD equity if available — accurate across same-day restarts
    bod = state.get("bod_equity", 0)
    if bod > 0 and state.get("bod_date") == str(today):
        start_equity = bod
    else:
        start_equity = state["session_start_equity"]

    # Calculate end_equity from start + state["daily_pnl"] rather than trusting
    # Alpaca's portfolio_value — which miscounts on days with rapid short
    # sequences (paper trading accounting bug, confirmed across multiple sessions).
    # state["daily_pnl"] is incremented on every trade close and is always accurate.
    # Use Alpaca's equity - last_equity as authoritative day P&L
    realized_pnl = get_daily_pnl()
    if realized_pnl != 0:
        end_equity = round(start_equity + realized_pnl, 2)
        log(f"EOD equity: ${start_equity:,.2f} + ${realized_pnl:+,.2f} = ${end_equity:,.2f} "
            f"(Alpaca equity: ${api_result[1]:,.2f})")
    else:
        end_equity = api_result[1] if api_result[0] else start_equity

    day_pnl = round(end_equity - start_equity, 2)

    # Collect all trades for today — current session first
    # v4.70 fix: this used to only look at state["closed_trade"], a single
    # slot overwritten on every close — any trade closed earlier the same day
    # got silently dropped from the permanent CSV the moment a second trade
    # closed. state["closed_trades_today"] (via _finalize_trade_close) now
    # holds every trade closed today, so all of them make it into the log.
    all_today = []
    seen_ids  = set()
    for t in state.get("closed_trades_today", []):
        oid = t.get("order_id", "")
        all_today.append(t)
        if oid:
            seen_ids.add(oid)
    for t in get_active_trades():
        oid = t.get("order_id", "")
        if oid not in seen_ids:
            all_today.append(t)
            seen_ids.add(oid)

    # Pull in trades from earlier sessions today via master CSV
    master_path = os.path.join(log_dir, "master_trade_log.csv")
    if os.path.exists(master_path):
        try:
            with open(master_path, newline="", encoding="utf-8") as _f:
                for row in csv.DictReader(_f):
                    if row.get("date") == str(today) and row.get("order_id") not in seen_ids:
                        # Reconstruct minimal trade dict from CSV row
                        all_today.append({
                            "order_id":   row.get("order_id", ""),
                            "fvg_type":   row.get("direction", "").lower(),
                            "strategy":   row.get("strategy", "PRIOR"),
                            "entry":      float(row.get("entry", 0) or 0),
                            "exit_px":    float(row.get("exit_price", 0) or 0),
                            "stop":       float(row.get("stop", 0) or 0),
                            "target":     float(row.get("target", 0) or 0),
                            "qty":        int(float(row.get("qty", 0) or 0)),
                            "pnl":        float(row.get("pnl", 0) or 0),
                            "outcome":    row.get("outcome", ""),
                            "opened_at":  row.get("opened_at", ""),
                            "duration_min": int(float(row.get("duration_min", 0) or 0)),
                            "trend":          row.get("trend", ""),
                            "monthly_trend":  row.get("monthly_trend", ""),
                            "daily_momentum": row.get("daily_momentum", ""),
                            "swing_pos_6m":   row.get("swing_pos_6m", ""),
                            "fvg":        {},
                        })
                        seen_ids.add(row.get("order_id", ""))
        except Exception as _e:
            log(f"Could not read prior trades from master CSV: {_e}", "WARN")

    aoc = all_today[0] if all_today else None  # primary trade for legacy fields

    txt_path = os.path.join(log_dir, f"{today}_summary.txt")
    # Always overwrite — this run has the most complete picture of the day
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"NVDA AUTO TRADER v4.52 — DAILY SUMMARY\n")
        f.write(f"Date: {today}\n{'='*50}\n\n")
        f.write(f"ACCOUNT\n")
        f.write(f"  Start equity:  ${start_equity:,.2f}\n")
        f.write(f"  End equity:    ${end_equity:,.2f}\n")
        f.write(f"  Day P&L:       ${day_pnl:,.2f}\n\n")
        f.write(f"STRATEGY\n")
        f.write(f"  Active strategy: {state['active_strategy']}\n")
        f.write(f"  Selection reason: {state['strategy_reason']}\n")
        f.write(f"  VWAP setups seen: {len(state['vwap_setups_today'])}\n")
        f.write(f"  FVG setups seen:  {len(state['all_fvgs_today'])}\n\n")
        f.write(f"TRADE\n")
        if state["traded_today"] and aoc:
            t = aoc
            fvg_data = t.get('fvg') or {}
            f.write(f"  Traded:        Yes\n")
            f.write(f"  Direction:     {t.get('fvg_type','?').upper()}\n")
            f.write(f"  Trend:         {t.get('trend','?')}\n")
            f.write(f"  FVG score:     {fvg_data.get('score', 0)}/9\n")
            f.write(f"  Score notes:   {fvg_data.get('score_notes', fvg_data.get('notes', 'N/A'))}\n")
            f.write(f"  Entry:         ${t.get('entry', 0):.2f}\n")
            f.write(f"  Stop:          ${t.get('stop', 0):.2f}\n")
            f.write(f"  Target:        ${t.get('target', 0):.2f}\n")
            f.write(f"  Qty:           {t.get('qty', 0)}\n")
            risk = t.get('risk', 0) or 0
            qty  = t.get('qty', 0) or 0
            f.write(f"  Risk:          ${risk * qty:,.2f}\n")
            f.write(f"  QQQ dir:       {t.get('qqq_dir', '?')}\n")
            opened = t.get('opened_at')
            f.write(f"  Opened at:     {opened.strftime('%H:%M %Z') if opened else '?'}\n")
            if t.get("outcome"):
                f.write(f"  Outcome:       {t['outcome']}\n")
                exit_px_val = t.get('exit_px')
                pnl_val     = t.get('pnl')
                f.write(f"  Exit price:    ${exit_px_val:.2f}\n" if exit_px_val is not None else "  Exit price:    OPEN\n")
                f.write(f"  P&L:           ${pnl_val:,.2f}\n"    if pnl_val     is not None else "  P&L:           OPEN\n")
                f.write(f"  Duration:      {t.get('duration_min','?')} min\n")
        else:
            f.write(f"  Traded:        No\n")
            if state["best_fvg_today"]:
                f.write(f"  Best FVG seen: score {state['best_score_today']}/9 "
                        f"(MTF: {state['mtf_bias']} | QQQ threshold applies)\n")
            else:
                f.write(f"  No valid FVGs detected today\n")

        f.write(f"\nFVGs DETECTED TODAY ({len(state['all_fvgs_today'])} total)\n")
        for i, fvg in enumerate(state["all_fvgs_today"], 1):
            formed = fvg["formed_at"]
            if hasattr(formed, "to_pydatetime"):
                formed = formed.to_pydatetime()
            f.write(f"  {i}. {formed.strftime('%H:%M ET')} | "
                    f"[{fvg['type'].upper()}] size ${fvg['size']:.2f} | "
                    f"score {fvg['score']}/9 | QQQ {fvg['qqq_dir']} | "
                    f"{fvg['score_notes']}\n")

        f.write(f"\nCONNECTION HEALTH\n")
        f.write(f"  Fetch errors today: {state['fetch_errors_today']}\n\n")
        f.write(f"EVENT LOG\n")
        for ev in state["daily_events"]:
            f.write(f"  {ev['time']} — {ev['level']}: {ev['message']}\n")
        f.write(f"\nTWEAK NOTES\n")
        f.write(f"  Min score threshold:  {CONFIG['min_score_to_trade']} (aligned) / {CONFIG['min_score_qqq_neutral']} (neutral QQQ)\n")
        f.write(f"  FVG size range:       ${CONFIG['min_fvg_size']}–${CONFIG['max_fvg_size']}\n")
        f.write(f"  Kill zones (ET):      {CONFIG['kill_zones_et']}\n")
        f.write(f"  R:R:                  {CONFIG['risk_reward']}:1\n")
        f.write(f"  Risk per trade:       {CONFIG['risk_per_trade']*100:.1f}%\n")
        f.write(f"  Trend lookback:       {CONFIG['trend_lookback']} candles\n")
        f.write(f"  Trend threshold:      {CONFIG['trend_threshold']}%\n")

    csv_path    = os.path.join(log_dir, f"{today}_trades.csv")
    master_path = os.path.join(log_dir, "master_trade_log.csv")
    rows = []
    for t in all_today:
        fvg_d = t.get("fvg") or {}
        opened = t.get("opened_at")
        rows.append({
            "date":         today,
            "ticker":       CONFIG["ticker"],
            "strategy":     t.get("strategy", "UNKNOWN"),
            "fvg_type":     t.get("fvg_type", ""),
            "trend":        t.get("trend", ""),
            "monthly_trend":  t.get("monthly_trend", ""),
            "daily_momentum": t.get("daily_momentum", ""),
            "swing_pos_6m":   t.get("swing_pos_6m", ""),
            "fvg_score":    fvg_d.get("score", 0),
            "score_notes":  fvg_d.get("score_notes", fvg_d.get("notes", "")),
            "fvg_size":     fvg_d.get("size", ""),
            "qqq_dir":      t.get("qqq_dir", ""),
            "entry":        t.get("entry", ""),
            "stop":         t.get("stop", ""),
            "target":       t.get("target", ""),
            "qty":          t.get("qty", ""),
            "risk_dollars": round((t.get("risk", 0) or 0) * (t.get("qty", 0) or 0), 2),
            # v4.97 fix: dict.get(key, default) only substitutes the default
            # when the key is ABSENT — a still-open trade has "outcome": None
            # explicitly set (not missing), so this was writing a blank CSV
            # cell instead of the literal string "OPEN" every time. That
            # silently broke _find_open_trade_in_recent_logs()'s recovery
            # lookup (which searches for outcome == "OPEN") for exactly the
            # trades it most needs to find — a still-open SWING-6M position
            # carried past an EOD summary. Confirmed live 2026-10-03: a real
            # SWING-6M trade's _trades.csv row had an empty outcome field,
            # the lookup found nothing, and the ALPACA SYNC reconnect fell
            # back to crude guessed stop/target under a generic "RESTORED"
            # label instead of recovering the real SWING-6M trade.
            "outcome":      t.get("outcome") or "OPEN",
            "exit_price":   t.get("exit_px", ""),
            "pnl":          t.get("pnl", ""),
            "duration_min": t.get("duration_min", ""),
            # v4.58 fix: trades reconstructed from master_trade_log.csv (an
            # earlier session's trade, same day) store opened_at as the plain
            # string already written to that CSV, not a datetime — calling
            # .strftime() on it crashed save_daily_summary() with
            # "'str' object has no attribute 'strftime'" any time a restart
            # happened after at least one trade had already closed today.
            "opened_at":    (opened.strftime("%H:%M %Z") if hasattr(opened, "strftime")
                              else str(opened)) if opened else "",
            "start_equity": start_equity,
            "end_equity":   end_equity,
            "day_pnl":      day_pnl,
        })

    if not rows:
        rows.append({
            "date": today, "ticker": CONFIG["ticker"],
            "fvg_type": "none", "trend": "",
            "monthly_trend": state.get("monthly_trend", ""),
            "daily_momentum": state.get("daily_momentum", ""),
            "swing_pos_6m": "",
            "fvg_score": state["best_score_today"], "score_notes": "no trade",
            "fvg_size": "", "qqq_dir": "",
            "entry": "", "stop": "", "target": "",
            "qty": "", "risk_dollars": "",
            "outcome": "NO_TRADE", "exit_price": "",
            "pnl": 0, "duration_min": "",
            "opened_at": "",
            "start_equity": start_equity, "end_equity": end_equity, "day_pnl": day_pnl,
        })

    df_new = pd.DataFrame(rows)
    if os.path.exists(master_path):
        df_master = pd.read_csv(master_path)
        df_master = df_master[df_master["date"].astype(str) != str(today)]
        df_master = pd.concat([df_master, df_new], ignore_index=True)
    else:
        df_master = df_new
    df_master.to_csv(master_path, index=False)
    df_new.to_csv(csv_path, index=False)

    log(f"Summary saved → {txt_path}", "REPORT")
    log(f"Master log updated → {master_path}", "REPORT")

    # Persist price_history to seed file so next session starts with full history
    try:
        hist_file = os.path.join(log_dir, "..", "nvda_price_history.json")
        hist_file = os.path.normpath(hist_file)
        hist_data = state.get("price_history", [])
        with open(hist_file, "w") as hf:
            json.dump(hist_data, hf)

        # Also bake history into dashboard HTML so it works offline
        dash_candidates = [
            os.path.join(log_dir, "..", "nvda_live_dashboard.html"),
            os.path.join(os.path.dirname(__file__), "nvda_live_dashboard.html"),
        ]
        for dash_path in dash_candidates:
            dash_path = os.path.normpath(dash_path)
            if os.path.exists(dash_path):
                with open(dash_path, "r", encoding="utf-8") as df:
                    dash_src = df.read()
                # Replace the embedded history marker
                marker_start = "// __BAKED_HISTORY_START__"
                marker_end   = "// __BAKED_HISTORY_END__"
                hist_json = json.dumps(hist_data, cls=_SafeEncoder)
                baked = (marker_start + "\n"
                         "const BAKED_HISTORY = " + hist_json + ";\n"
                         + marker_end)
                if marker_start in dash_src:
                    dash_src = re.sub(
                        marker_start + r".*?" + marker_end,
                        baked, dash_src, flags=re.DOTALL
                    )
                    with open(dash_path, "w", encoding="utf-8") as df:
                        df.write(dash_src)
                break
    except Exception:
        pass

    print(f"\n{'='*55}")
    print(f"  END OF DAY — {today}")
    # Use equity delta from BOD for accurate cross-session day P&L
    _bod = state.get("bod_equity", 0)
    _bod_date = state.get("bod_date", "")
    if _bod > 0 and _bod_date == str(today) and end_equity > 0:
        _display_pnl = round(end_equity - _bod, 2)
    else:
        _display_pnl = state.get("daily_pnl", day_pnl) or day_pnl
    # Count trades including any loaded from prior sessions today
    _trades_count = max(state.get("trades_today", 0), len([t for t in all_today if t.get("outcome")]))
    print(f"  Day P&L:       ${_display_pnl:+,.2f}  (equity: ${start_equity:,.2f} → ${end_equity:,.2f})")
    print(f"  Trades today:  {_trades_count} (this session: {state.get('trades_today', 0)})")
    print(f"  Loss limit:    ${CONFIG['daily_loss_limit']:,.0f}")
    print(f"  FVGs detected: {len(state['all_fvgs_today'])}")
    print(f"  Fetch errors:  {state['fetch_errors_today']}")
    print(f"  Files in:      trade_logs/")
    print(f"{'='*55}\n")

# ═══════════════════════════════════════════════════════════════
# END OF DAY
# ═══════════════════════════════════════════════════════════════

def end_of_day_check():
    if now_et().time() >= dtime(16, 0):  # 4:00 PM ET — market close (changed from 15:00 which cut the 14:00–15:00 kill zone short)
        trades = get_active_trades()
        if trades:
            log("End of day — closing all open positions...", "TRADE")
            api_result = get_alpaca()
            api = api_result[0] if api_result[0] is not None else None

            for trade in list(trades):
                if trade.get("strategy") == "MANUAL":
                    # v4.53 fix: this branch used to mark MANUAL trades EOD_CLOSE
                    # from an estimated price WITHOUT ever calling close_all() —
                    # the real Alpaca position was never told to close, so it could
                    # sit open indefinitely (or overnight) while the bot believed
                    # it was done. Now mirrors the bot-trade path: close_all() +
                    # confirmation wait, only booking the trade closed once Alpaca
                    # confirms the position is actually gone.
                    cur_px = state.get("last_price", trade["entry"])
                    _confirmed = False
                    if api:
                        try:
                            _pos_eod_m = get_position(api)
                            if _pos_eod_m is not None:
                                cur_px = float(_pos_eod_m.current_price)
                            _close_ok = close_all(api)
                            if not _close_ok:
                                log("Manual EOD close_all() call failed (API error) — will retry next scan cycle", "WARN")
                            for _ew in range(10):
                                time.sleep(1)
                                try:
                                    if get_position(api) is None:
                                        _confirmed = True
                                        break
                                except Exception:
                                    break
                        except Exception as _me:
                            log(f"Manual EOD close failed: {_me} — will retry next scan cycle", "WARN")
                    else:
                        log("Manual EOD close skipped — Alpaca unreachable, will retry next scan cycle", "WARN")

                    if not _confirmed:
                        _eod_retry_count = trade.get("_eod_retry_count", 0) + 1
                        trade["_eod_retry_count"] = _eod_retry_count
                        state["status"] = f"Manual EOD close unconfirmed (attempt {_eod_retry_count}) — retrying"
                        if _eod_retry_count >= 8:
                            log(f"MANUAL EOD CLOSE STILL UNCONFIRMED after {_eod_retry_count} attempts — "
                                f"CHECK ALPACA MANUALLY, bot will keep retrying", "ERROR")
                        continue  # leave trade in active_trades — retried next poll cycle

                    trade["outcome"] = "EOD_CLOSE"
                    trade["exit_px"] = cur_px
                    trade["pnl"]     = round((cur_px - trade["entry"]) * trade["qty"]
                                             if trade.get("fvg_type") == "bullish"
                                             else (trade["entry"] - cur_px) * trade["qty"], 2)
                    _finalize_trade_close(trade)
                    log(f"Manual trade [{trade.get('order_id','')}] closed at EOD | P&L: ${trade['pnl']:+.2f}", "TRADE")
                else:
                    # Bot trade — close on Alpaca
                    if api:
                        pos = get_position(api)
                        if pos is not None:
                            close_all(api)
                            log("Bot position closed at end of day.", "TRADE")
                        else:
                            log("Bot position already closed before EOD sweep.", "TRADE")
                    trade["outcome"] = "EOD_CLOSE"
                    _finalize_trade_close(trade)

                state["trades_today"] = state.get("trades_today", 0) + 1
                _record_day_trade()
                remove_active_trade(trade)

            state["traded_today"] = False
            save_state()
        return True
    return False

# ═══════════════════════════════════════════════════════════════
# WATCHDOG
# ═══════════════════════════════════════════════════════════════

def _watchdog_loop():
    """
    v4.96: runs in its own daemon thread, independent of the main loop, so it
    keeps working even if the main thread is the one that's stuck. Checks
    state["_last_heartbeat"] (set at the top of every main-loop iteration)
    every 10s; if it's gone stale past CONFIG["watchdog_timeout_sec"], the
    main thread is blocked on something that isn't returning — force-exit
    the whole process so Task Scheduler's restart (3 attempts, 1 min apart)
    brings it back clean instead of sitting frozen indefinitely.

    Confirmed live 2026-10-02: the main loop froze silently for ~60 minutes
    immediately after closing a trade (almost certainly an unbounded network
    call inside the resumed check_for_entry() scan — that week had repeated
    SSL/DNS/timeout errors). The dashboard's HTTP server runs in its own
    thread and kept responding the whole time with the last-known state,
    which is exactly what made it look deceptively fine — nothing in
    bot_console.log hinted anything was wrong, and the only visible symptom
    was the price chart not accumulating new points. A human noticing that
    is not a monitoring strategy; this is the actual fix.

    os._exit() (not sys.exit()) is used deliberately: sys.exit() raises
    SystemExit, which only terminates the CALLING thread (this watchdog
    thread) — the hung main thread would keep right on running, unaffected.
    os._exit() terminates the entire process immediately, no cleanup, which
    is exactly what's needed here: the main thread is already stuck and
    isn't going to run any cleanup code anyway.
    """
    while True:
        time.sleep(10)
        try:
            last = state.get("_last_heartbeat", 0)
            stale_for = time.time() - last
            if stale_for > CONFIG.get("watchdog_timeout_sec", 300):
                log(f"WATCHDOG — main loop has not completed an iteration in "
                    f"{stale_for:.0f}s (limit {CONFIG.get('watchdog_timeout_sec', 300)}s) "
                    f"— force-exiting so Task Scheduler can restart cleanly", "CRITICAL")
                try:
                    sys.stdout.flush()
                except Exception:
                    pass
                os._exit(1)
        except Exception:
            # The watchdog itself must never be the thing that crashes —
            # if anything here goes wrong, just keep checking on the next tick.
            pass


# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def main():
    print("\n" + "="*55)
    print("  NVDA DUAL-STRATEGY AUTO TRADER v4.98")
    print("  Strategies: ALL live — VWAP, FVG, SPIKE(range-extreme+momentum), RANGE, SWING-3M/6M | research mode: small size")
    print("  Alpaca Data + Alpaca Paper Trading")
    print("="*55)

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("\nERROR: No Alpaca API keys set.")
        print("  Run:  python build_dashboard.py   then open the Settings tab,")
        print("  paste your keys, click Save, then Start Bot.")
        sys.exit(2)   # non-zero, but the control panel won't auto-restart on code 2

    # ── Auto-archive this version on startup ──────────────────────
    # Saves a timestamped copy to archive\ once per day automatically
    try:
        _script    = os.path.abspath(__file__)
        _arch_dir  = os.path.join(os.path.dirname(_script), "archive")
        os.makedirs(_arch_dir, exist_ok=True)
        with open(_script) as _sf:
            _content = _sf.read()
        _ver_match = re.search(r'v4\.\d+', _content)
        _ver  = _ver_match.group() if _ver_match else "unknown"
        _ts   = datetime.now().strftime("%Y-%m-%d_%H%M")
        _today = datetime.now().strftime("%Y-%m-%d")
        # Only archive once per day per version
        _existing = [f for f in os.listdir(_arch_dir)
                     if f"nvda_autotrader_{_ver}_{_today}" in f]
        if not _existing:
            _dst = os.path.join(_arch_dir, f"nvda_autotrader_{_ver}_{_ts}.py")
            shutil.copy2(_script, _dst)
            print(f"  📁 Archived: archive/{os.path.basename(_dst)}")
    except Exception:
        pass  # Archive failure never blocks the bot

    # Start live dashboard server
    start_dashboard_server()
    start_tradingview_webhook()
    log(f"Mode: {'PAPER' if IS_PAPER else '*** LIVE MONEY ***'} | Signal source: {SIGNAL_SOURCE}")

    log("Connecting to Alpaca...")
    api_result = get_alpaca()
    if api_result[0] is None:
        # v4.93: this used to give up immediately on a single failed attempt,
        # relying entirely on Task Scheduler's own retry (3 attempts, 1 min
        # apart) to cover a morning where wifi simply isn't connected yet —
        # not nearly enough runway. Instead of retrying repeatedly, wait ONCE
        # until a fixed local time and make exactly one more attempt before
        # actually giving up. Skips the wait if that time has already passed
        # (e.g. running well after 9:10, or the setting is disabled).
        _retry_at = CONFIG.get("startup_retry_at_local")
        if _retry_at:
            _now_l = now_local()
            _rh, _rm = (int(x) for x in _retry_at.split(":"))
            _retry_dt = _now_l.replace(hour=_rh, minute=_rm, second=0, microsecond=0)
            if _retry_dt > _now_l:
                _wait_s = (_retry_dt - _now_l).total_seconds()
                log(f"Could not connect to Alpaca — waiting until {_retry_at} local "
                    f"({_wait_s/60:.0f} min) for one more attempt instead of "
                    f"giving up now", "WARN")
                time.sleep(_wait_s)
                log("Retrying Alpaca connection...")
                api_result = get_alpaca()
    if api_result[0] is None:
        print("ERROR: Could not connect to Alpaca. Check your keys in the dashboard Settings tab.")
        sys.exit(3)

    log(f"Connected — Portfolio: ${api_result[1]:,.2f} | {'PAPER' if IS_PAPER else '*** LIVE ***'} MODE")
    _refresh_market_clock()  # detect half-days / early closes at session start

    # Restore state from previous session if bot restarted today
    load_state()

    # Restore trade history from today's log file for complete summaries
    load_existing_log()
    log(f"Data source: Alpaca Market Data (IEX free feed)")

    # Seed price_history from historical JSON — always load to ensure full history
    # even after mid-session restarts
    hist_file = os.path.join(os.path.dirname(__file__), "nvda_price_history.json")
    if os.path.exists(hist_file):
        try:
            with open(hist_file, "r") as hf:
                seed = json.load(hf)
            seed = [p for p in seed if 50 < p.get("p", 0) < 2000]
            # Merge seed with any points already in state (from load_state)
            current = state.get("price_history", [])
            current_ts = {p["t"] for p in current}
            merged = [p for p in seed if p.get("t") not in current_ts] + current
            merged.sort(key=lambda x: x.get("t", ""))
            if len(merged) > 2000:
                merged = merged[-2000:]
            state["price_history"] = merged
            log(f"Loaded {len(merged)} historical price points "
                f"({len(seed)} from JSON + {len(current)} from state)")
        except Exception as e:
            log(f"Could not load price history seed: {e}", "WARN")
    log(f"Local timezone: {now_local().strftime('%Z')}")
    log(f"Min score to trade: {CONFIG['min_score_to_trade']}/9")
    log(f"FVG size range: ${CONFIG['min_fvg_size']}–${CONFIG['max_fvg_size']}")
    log(f"Trend detection: last {CONFIG['trend_lookback']} candles, threshold {CONFIG['trend_threshold']}%")
    log(f"Strategy: ADAPTIVE — FVG Retrace OR VWAP Bounce, chosen at each kill zone open")
    log(f"VWAP bands: ±{CONFIG['vwap_band_mult']}x ATR ({CONFIG['vwap_atr_lookback']}-candle ATR)")
    log(f"Strategy switch trigger: volume spike >{CONFIG['volume_spike_mult']}x avg")
    if CONFIG.get("pdt_protection"):
        used = _pdt_trades_used()
        log(f"PDT PROTECTION ON — {used}/{CONFIG['pdt_max_trades']} trades used in last 5 business days", "WARN")

    state["status"] = "Connected — waiting for market open"

    print()
    for kz in CONFIG["kill_zones_et"]:
        print(f"  Kill zone: {kz[0]}-{kz[1]} ET  "
              f"({et_to_local_str(kz[0])}-{et_to_local_str(kz[1])} local)")
    print()

    log(f"Waiting for market — 9:30 AM ET / {et_to_local_str('09:30')} local")

    # v4.96: start the watchdog thread now, right before the main loop begins —
    # see _watchdog_loop() and the watchdog_timeout_sec CONFIG comment for why.
    state["_last_heartbeat"] = time.time()
    threading.Thread(target=_watchdog_loop, daemon=True).start()

    summary_saved_today = False
    last_summary_date   = None

    while True:
        try:
            state["_last_heartbeat"] = time.time()
            reset_daily_state()
            today = now_local().date()

            if last_summary_date != today:
                summary_saved_today = False

            if not is_market_open():
                now_check = datetime.now(MARKET_TZ)
                # v4.86 CRITICAL fix: confirmed live 2026-09-10 -> 09-11 — a SPIKE
                # long was still open when the market closed. The v4.79 idle loop
                # below correctly kept calling monitor_trade() every 30s all
                # evening (698+ logged retries), but at midnight ET it hit
                # `sys.exit(0)` UNCONDITIONALLY — even with the position still
                # open — because that exit never checked get_active_trades().
                # The process died right then (bot_console.log confirms: last
                # line is exactly 00:00 ET) and nothing restarted it until Task
                # Scheduler's normal 8:20 AM trigger — an 8+ hour window with
                # ZERO monitoring, zero stop protection, and the process not
                # even running to receive Ctrl+C or answer the dashboard. Same
                # gap existed on the weekend-detected exit a few lines up, and
                # on the pre-market "waiting for open" branch below, which never
                # called monitor_trade() at all. Fixed all three: compute
                # has_open once, monitor whenever it's true, and never call
                # sys.exit(0) while it's true — only exit (for the scheduled
                # daily restart) once the bot has confirmed it's actually flat.
                has_open = bool(get_active_trades())
                if has_open:
                    monitor_trade()
                # v4.10: Exit on weekends — prevents 48hr Yahoo rate limit burnout
                if now_check.weekday() >= 5 and not has_open:
                    log(f"Weekend detected ({now_check.strftime('%A')}) — "
                        f"shutting down. Task Scheduler restarts Monday at 8:20 AM.")
                    sys.exit(0)
                # Outside market hours on a weekday — keep dashboard alive but don't trade
                # (also enters here on a weekend if a trade is still open, instead
                # of skipping straight past to the bottom sleep with no monitoring)
                if now_check.hour >= 16 or (now_check.weekday() >= 5 and has_open):
                    if not summary_saved_today:
                        save_daily_summary()
                        summary_saved_today = True
                    log("After market hours — dashboard staying up for review. Bot resumes tomorrow at 9:30 ET.")
                    state["status"] = "After hours — dashboard active"
                    while True:
                        now_idle = datetime.now(MARKET_TZ)
                        # v4.79 CRITICAL fix: this loop used to just sleep — a VWAP
                        # short confirmed live: EOD force-close (inside
                        # _monitor_bot_trade) tried and failed 11 times in the ~5min
                        # window before this loop took over (close_all() rejected by
                        # Alpaca: "insufficient qty available... available: 0" — an
                        # unrelated stop order was reserving the shares). Once this
                        # idle loop started, monitor_trade() was NEVER called again —
                        # no further close attempts, no stop/target checks, nothing —
                        # until the process exited at midnight and reconnected the
                        # NEXT morning. The position sat completely unmonitored
                        # overnight; only luck (favorable price movement) meant it
                        # didn't turn into a real loss. Keep retrying instead of
                        # abandoning it — harmless no-op once actually flat.
                        idle_has_open = bool(get_active_trades())
                        if idle_has_open:
                            monitor_trade()
                        # v4.86: only exit once actually flat — see note above.
                        if not idle_has_open:
                            # Exit at midnight to allow clean restart by Task Scheduler
                            if now_idle.hour == 0 and now_idle.minute < 1:
                                sys.exit(0)
                            # Exit on weekend
                            if now_idle.weekday() >= 5:
                                sys.exit(0)
                        time.sleep(30)
                # Optional early shutdown (e.g. travel day)
                early = CONFIG.get("early_shutdown_et")
                if early:
                    h, m = map(int, early.split(":"))
                    if (now_check.hour, now_check.minute) >= (h, m) and not has_open:
                        log(f"Early shutdown — {early} ET reached. "
                            f"Set CONFIG['early_shutdown_et'] = None to resume normal hours.")
                        if not summary_saved_today:
                            save_daily_summary()
                        sys.exit(0)
                state["status"] = "Market closed — waiting for open"
                time.sleep(CONFIG["poll_seconds"])
                continue

            if end_of_day_check():
                state["status"] = "End of day"
                if not summary_saved_today:
                    save_daily_summary()
                    summary_saved_today = True
                    last_summary_date   = today
                time.sleep(CONFIG["poll_seconds"])
                continue

            # After 4:00 PM ET — stop trading, dashboard stays up
            now_et_chk = datetime.now(MARKET_TZ)
            if now_et_chk.hour >= 16:
                if not summary_saved_today:
                    save_daily_summary()
                    summary_saved_today = True
                state["status"] = "After hours — dashboard active"
                # v4.79 fix: same gap as the idle loop above (this branch is reached
                # instead of that one when is_market_open() still returns True by
                # clock time but this explicit cutoff has passed) — keep retrying
                # any still-open position instead of abandoning it here too.
                if get_active_trades():
                    monitor_trade()
                time.sleep(30)
                continue

            # ── Refresh live portfolio equity every ~5 min ──────────────────
            # session_start_equity is a one-time snapshot; live_equity tracks
            # real Alpaca equity so the dashboard shows current P&L, not BOD.
            _eq_poll = state.get("_equity_poll_count", 0) + 1
            state["_equity_poll_count"] = _eq_poll
            if _eq_poll % 20 == 1:   # every 20 polls ≈ 5 min at 15s interval
                try:
                    _eq_api, _eq_val = get_alpaca()
                    if _eq_api is not None and _eq_val > 0:
                        state["live_equity"] = _eq_val
                except Exception:
                    pass  # non-critical

            # ── Always refresh price + ATR every poll (runs unconditionally) ──
            # Keeps dashboard and manual trade modal live at all times —
            # inside kill zones, between them, and while monitoring trades.
            # check_for_entry() does a deeper 200-bar fetch; this is a lightweight
            # 30-bar fetch just to keep last_price, last_atr, last_vwap current.
            # Skipped only during active trade monitoring (monitor_trade does its own fetch).
            if not get_active_trades():
                try:
                    _df_bg = _fetch_alpaca(CONFIG["ticker"], bars=30)
                    if _df_bg is not None and len(_df_bg) >= 3:
                        # Only update last_price from candles if they are today's data.
                        # Stale fallback bars (e.g. July 15 used on July 20) have a
                        # different close price that overwrites last_price and creates
                        # phantom price jumps on the dashboard chart.
                        _latest_bar_date = _df_bg.index[-1].date() if hasattr(_df_bg.index[-1], 'date') else None
                        _today = now_et().date()
                        if _latest_bar_date == _today:
                            state["last_price"] = round(float(_df_bg["Close"].iloc[-1]), 2)
                        else:
                            # v4.57 fix: when IEX hasn't published a full bar for today
                            # yet, the guard above correctly refuses to write yesterday's
                            # stale close — but that left last_price frozen for the whole
                            # gap, showing as dead-flat plateaus on the dashboard chart.
                            # get_latest_trade() asks for just the single most recent
                            # trade print, no full bar required, so it's available well
                            # before IEX finishes aggregating today's first bar. Same call
                            # pattern place_order() already uses for live-price checks.
                            try:
                                _api_lt, _ = get_alpaca()
                                if _api_lt:
                                    _latest_trade = _api_lt.get_latest_trade(CONFIG["ticker"])
                                    if _latest_trade and _latest_trade.price:
                                        state["last_price"] = round(float(_latest_trade.price), 2)
                            except Exception:
                                pass  # leave last_price at its previous value
                        # Always update scan time, count, ATR, VWAP from available data
                        state["last_scan_time"]    = now_local().strftime("%H:%M:%S")
                        state["last_candle_count"] = len(_df_bg)
                        _atr_bg = calculate_atr(_df_bg)
                        if _atr_bg:
                            state["last_atr"] = _atr_bg
                        _vwap_bg, _upper_bg, _lower_bg, _ = calculate_vwap(_df_bg)
                        if _vwap_bg:
                            state["last_vwap"]       = _vwap_bg
                            state["last_vwap_upper"] = _upper_bg
                            state["last_vwap_lower"] = _lower_bg
                except Exception as _bg_e:
                    # v4.55 fix: this was a bare `except: pass` — a real failure here
                    # left last_atr/last_vwap/last_scan_time stuck at 0/empty
                    # indefinitely (blocking the dashboard's manual-trade ATR
                    # auto-calc) with zero visibility into why. Now logged once
                    # per distinct error message instead of every ~15s, so it's
                    # diagnosable without being spammy.
                    _bg_err_key = str(_bg_e)
                    if state.get("_last_bg_refresh_err") != _bg_err_key:
                        state["_last_bg_refresh_err"] = _bg_err_key
                        log(f"Background price/ATR refresh failed: {_bg_e}", "WARN")

            # ── Always record to price_history every poll, trade open or not ──
            # Decoupled from the active-trade guard above — monitor functions keep
            # last_price current while a trade is open, so it's always safe to record.
            try:
                _px_bg = state.get("last_price", 0)
                if 50 < _px_bg < 2000:
                    _ts_bg = datetime.now(MARKET_TZ).strftime("%Y-%m-%dT%H:%M")
                    _hist  = state.get("price_history", [])
                    _recent_ts = {h["t"] for h in _hist[-4:]} if _hist else set()
                    if _ts_bg not in _recent_ts:
                        _hist.append({"t": _ts_bg, "p": _px_bg, "kz": "",
                                      "trend": state.get("last_trend","neutral"),
                                      "mtf": state.get("mtf_bias","neutral")})
                    else:
                        for _h in reversed(_hist):
                            if _h["t"] == _ts_bg:
                                _h["p"] = _px_bg
                                break
                    if len(_hist) > 2000:
                        _hist = _hist[-2000:]
                    state["price_history"] = _hist
            except Exception:
                pass  # history recording failure is non-critical

            # v4.64 fix: this used to gate on get_active_trades() (ANY trade,
            # including manual) — so a manual trade sitting open silently
            # blocked the bot from ever reaching check_for_entry() and placing
            # its own trade, contradicting the multi-trade architecture this
            # file already documents (active_trades holds bot+manual together;
            # get_bot_trade() specifically means "the bot's own trade"; and
            # check_for_entry() itself already guards on get_bot_trade() is not
            # None, not on any-trade — it was already safe to call alongside a
            # manual trade, just never reached). Restructured: monitoring now
            # always runs whenever anything is open, independent of kill-zone
            # timing (this also fixes the "orphan trade" per-trade loops below
            # having been unreachable dead code — they only ever ran when
            # get_active_trades() was empty, since a non-empty list used to
            # route to monitor_trade() above instead). Scanning for a new bot
            # setup now depends only on whether the BOT has a trade open.
            if get_active_trades():
                monitor_trade()

            if get_bot_trade() is None:
                if is_in_kill_zone():
                    # Log once on kill zone entry
                    cur_kz = get_current_kill_zone()
                    if state.get("_last_kz_logged") != cur_kz:
                        state["_last_kz_logged"] = cur_kz
                        state["stale_scan_count"] = 0  # reset stale counter on new kill zone
                        log(f"Kill zone {cur_kz} ET open — scanning for setups")
                    # v4.98: "tradingview" = only TradingView alerts open trades
                    if SIGNAL_SOURCE == "tradingview":
                        if not get_active_trades():
                            state["status"] = "Waiting for TradingView alerts"
                    else:
                        check_for_entry()
                else:
                    nxt = get_next_kill_zone()
                    if nxt:
                        if state["order_failed_today"]:
                            state["order_failed_today"] = False
                            log(f"Resetting order_failed — will retry in next kill zone at {nxt} ET")
                        else:
                            mins = minutes_to_next_kill_zone()
                            if not get_active_trades():
                                state["status"] = f"Between kill zones — next at {nxt} ET ({mins} min)"
                            # Log once on kill zone exit (transition only)
                            last_kz = state.get("_last_kz_logged", "")
                            if last_kz and last_kz != f"_between_{nxt}":
                                state["_last_kz_logged"] = f"_between_{nxt}"
                                log(f"Kill zone closed — next: {nxt} ET ({et_to_local_str(nxt)} local) in {mins} min")
                    else:
                        if state.get("_last_kz_logged") != "_done":
                            state["_last_kz_logged"] = "_done"
                            log("All kill zones passed for today — monitoring only")
                        if not get_active_trades():
                            state["status"] = "All kill zones passed for today"

            time.sleep(CONFIG["poll_seconds"])

        except KeyboardInterrupt:
            log("Bot stopped by user.")
            active = get_active_trades()
            if active:
                log("Closing open position(s)...")
                api_result = get_alpaca()
                if api_result[0] is not None:
                    close_all(api_result[0])
                for t in list(active):
                    _finalize_trade_close(t)
                    remove_active_trade(t)
            save_daily_summary()
            break
        except SystemExit:
            raise  # Always let sys.exit() through
        except Exception as e:
            log(f"Unexpected error: {e} — retrying in 60s", "ERROR")
            # Don't retry overnight — exit if market is closed
            # v4.55 fix: this was named `now_et`, shadowing the module-level
            # now_et() function for main()'s ENTIRE scope (Python treats a name
            # as local to a function if it's assigned anywhere in that function,
            # regardless of order). Every call to now_et() elsewhere in main() —
            # including the background price/ATR/VWAP refresh's `now_et().date()`
            # — raised "cannot access local variable 'now_et'" as a result,
            # silently swallowed by that block's bare except. This kept
            # last_atr/last_vwap/last_scan_time stuck at 0/empty between kill
            # zones, which is why the dashboard's manual-trade ATR auto-calc
            # reported "ATR not available yet" even after the bot had been
            # running for a while. Renamed so it no longer collides.
            _err_now_et = datetime.now(MARKET_TZ)
            if _err_now_et.hour >= 16:
                log("Error occurred after market close — shutting down to prevent overnight loop.")
                sys.exit(0)
            time.sleep(60)


if __name__ == "__main__":
    main()
