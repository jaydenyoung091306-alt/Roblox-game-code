#!/usr/bin/env python3
"""
NVDA AutoTrader — Backtester v5.00
==================================

Replays historical 5-minute bars through the bot's REAL code: the actual
check_for_entry(), _place_trade(), monitor_trade() / _monitor_bot_trade(),
reset_daily_state() and end_of_day_check() from build_dashboard.py run
unchanged. Only the outside world is replaced:

  clock   — datetime.now() returns simulated time
  data    — fetch_candles() / daily bars come from the historical data
  broker  — a simulated Alpaca account (market fills, bracket legs, stop
            orders, "day" orders expiring at the close, slippage)

So the results reflect what the bot itself would have done, including its
trailing stop, breakeven lock, FVG time stop, near-target lock, EOD close and
SWING-6M overnight holds — not a re-implementation of the strategies.

USAGE
  python backtest.py --source alpaca   --start 2026-04-01 --end 2026-09-30
        (uses the keys saved in the dashboard; IEX feed, same data the bot sees)
  python backtest.py --source yfinance              (last ~55 days, Yahoo 5m limit)
  python backtest.py --source csv --csv nvda_5m.csv --qqq-csv qqq_5m.csv
  python backtest.py --source synthetic             (made-up prices — only proves
                                                     the machinery works, NOT a result)
Outputs (in ./backtest_results/): trades.csv, equity.csv, summary.txt

ASSUMPTIONS (printed with every report)
  - The bot polls every 15s; each 5-min bar is replayed as 20 ticks along
    open → low → high → close (or open → high → low → close on red bars).
    Real intrabar paths differ; exits that depend on tick order are estimates.
  - Entries are evaluated on completed bars (as the IEX bars API returns them).
  - Fills: market orders at the tick price ± slippage; stop orders at the stop
    price (or the tick if price gapped through); limits at the limit price.
"""

import argparse
import contextlib
import io
import json
import math
import os
import sys
import tempfile
import time as _real_time
import types
from datetime import datetime as _real_datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ET = ZoneInfo("America/New_York")
TICKS_PER_BAR = 20          # 5 min / 15 s poll


# ═══════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════

def _clean(df):
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float).dropna()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(ET)
    df = df[~df.index.duplicated()].sort_index()
    t = df.index.hour * 60 + df.index.minute
    return df[(t >= 9 * 60 + 30) & (t <= 15 * 60 + 55) & (df.index.dayofweek < 5)]


def _daily_from_intraday(df):
    d = df.groupby(df.index.date).agg(Open=("Open", "first"), High=("High", "max"),
                                      Low=("Low", "min"), Close=("Close", "last"),
                                      Volume=("Volume", "sum"))
    d.index = pd.to_datetime(d.index)
    return d


def load_alpaca(start, end, warmup_days):
    import requests
    sys.path.insert(0, HERE)
    s = {}
    try:
        with open(os.path.join(HERE, "nvda_settings.json"), encoding="utf-8") as f:
            s = json.load(f)
    except OSError:
        pass
    key = os.environ.get("ALPACA_API_KEY") or s.get("alpaca_api_key")
    sec = os.environ.get("ALPACA_SECRET_KEY") or s.get("alpaca_secret_key")
    if not key or not sec:
        sys.exit("No Alpaca keys — save them in the dashboard's Settings tab first.")
    hdr = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}

    def bars(sym, tf, a, b):
        out, tok = [], None
        while True:
            p = {"timeframe": tf, "start": a, "end": b, "limit": 10000, "feed": "iex", "adjustment": "raw"}
            if tok:
                p["page_token"] = tok
            r = requests.get(f"https://data.alpaca.markets/v2/stocks/{sym}/bars", headers=hdr, params=p, timeout=60)
            r.raise_for_status()
            j = r.json()
            out += j.get("bars") or []
            tok = j.get("next_page_token")
            if not tok:
                break
        df = pd.DataFrame(out)
        if df.empty:
            sys.exit(f"Alpaca returned no {tf} bars for {sym}")
        df.index = pd.to_datetime(df["t"], utc=True)
        return df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})

    a = (pd.Timestamp(start) - pd.Timedelta(days=warmup_days * 1.6 + 3)).strftime("%Y-%m-%dT00:00:00Z")
    b = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    da = (pd.Timestamp(start) - pd.Timedelta(days=260)).strftime("%Y-%m-%dT00:00:00Z")
    print("Downloading NVDA/QQQ 5-min and daily bars from Alpaca (IEX)…")
    nv, qq = _clean(bars("NVDA", "5Min", a, b)), _clean(bars("QQQ", "5Min", a, b))
    daily = bars("NVDA", "1Day", da, b)[["Open", "High", "Low", "Close", "Volume"]]
    daily.index = pd.to_datetime(daily.index.tz_convert(ET).date)
    return nv, qq, daily


def load_yfinance():
    import yfinance as yf
    print("Downloading NVDA/QQQ 5-min (last ~60 days) and daily bars from Yahoo…")
    nv = yf.Ticker("NVDA").history(period="59d", interval="5m", auto_adjust=False)
    qq = yf.Ticker("QQQ").history(period="59d", interval="5m", auto_adjust=False)
    daily = yf.Ticker("NVDA").history(period="2y", interval="1d", auto_adjust=False)
    daily.index = pd.to_datetime(daily.index.tz_localize(None).date)
    if nv.empty or qq.empty:
        sys.exit("Yahoo returned no data (rate limited or blocked).")
    return _clean(nv), _clean(qq), daily[["Open", "High", "Low", "Close", "Volume"]]


def load_csv(path, qqq_path):
    def rd(p):
        df = pd.read_csv(p)
        cols = {c.lower(): c for c in df.columns}
        tcol = next(cols[c] for c in ("timestamp", "datetime", "time", "date", "t") if c in cols)
        df.index = pd.to_datetime(df[tcol], utc=True)
        ren = {cols[k]: v for k, v in (("open", "Open"), ("high", "High"), ("low", "Low"),
                                         ("close", "Close"), ("volume", "Volume")) if k in cols}
        return _clean(df.rename(columns=ren))
    nv = rd(path)
    qq = rd(qqq_path) if qqq_path else None
    if qq is None:
        print("No QQQ file — QQQ direction will read 'neutral' every scan.")
        qq = nv.iloc[0:0]
    return nv, qq, _daily_from_intraday(nv)


def make_synthetic(days, seed):
    """Random-walk prices with intraday volatility/volume smiles, occasional
    shocks and gaps. Purely to exercise every code path — NOT market data."""
    rng = np.random.default_rng(seed)
    sessions = pd.bdate_range("2025-10-01", periods=days + 140)
    slots = [(9, 30 + 5 * i) if 30 + 5 * i < 60 else (10 + (30 + 5 * i - 60) // 60, (30 + 5 * i - 60) % 60)
             for i in range(78)]
    idx, rows_n, rows_q = [], [], []
    px, qx = 120.0, 450.0
    regime = 0.0
    for d in sessions:
        if rng.random() < 0.12:
            regime = rng.normal(0, 0.0009)
        px *= math.exp(rng.normal(0, 0.012))           # overnight gap
        qx *= math.exp(rng.normal(0, 0.006))
        for k, (h, m) in enumerate(slots):
            smile = 1.8 - 1.6 * math.sin(math.pi * k / 77)
            r_m = rng.normal(0, 0.0008)
            shock = rng.normal(0, 0.012) if rng.random() < 0.004 else 0.0
            rn = regime / 78 + 1.4 * r_m + rng.normal(0, 0.0013 * smile) + shock
            rq = r_m + rng.normal(0, 0.0005 * smile)
            o, c = px, px * math.exp(rn)
            wig = abs(rng.normal(0, 0.0009 * smile)) * px
            hi, lo = max(o, c) + wig * rng.random(), min(o, c) - wig * rng.random()
            vol = int(rng.lognormal(10.2, 0.4) * smile * (3 if shock else 1))
            qo, qc = qx, qx * math.exp(rq)
            qw = abs(rng.normal(0, 0.0004)) * qx
            idx.append(pd.Timestamp(d.year, d.month, d.day, h, m, tz=ET))
            rows_n.append((o, hi, lo, c, vol))
            rows_q.append((qo, max(qo, qc) + qw, min(qo, qc) - qw, qc, vol * 3))
            px, qx = c, qc
    cols = ["Open", "High", "Low", "Close", "Volume"]
    nv = pd.DataFrame(rows_n, index=pd.DatetimeIndex(idx), columns=cols)
    qq = pd.DataFrame(rows_q, index=pd.DatetimeIndex(idx), columns=cols)
    daily = _daily_from_intraday(nv)
    keep_from = sessions[140 - 8]                      # 8 warmup days of 5m bars
    return nv[nv.index.date >= keep_from.date()], qq[qq.index.date >= keep_from.date()], daily


# ═══════════════════════════════════════════════════════════════
# SIMULATED WORLD
# ═══════════════════════════════════════════════════════════════

class Clock:
    now = _real_datetime(2000, 1, 3, 9, 30, tzinfo=ET)


class SimDatetime(_real_datetime):
    @classmethod
    def now(cls, tz=None):
        n = Clock.now
        r = n.astimezone(tz) if tz else n.astimezone(ET).replace(tzinfo=None)
        return cls(r.year, r.month, r.day, r.hour, r.minute, r.second, r.microsecond, tzinfo=r.tzinfo)


class Feed:
    """Serves 'what Alpaca would return right now': completed bars only."""
    def __init__(self, nv, qq, daily):
        self.data = {"NVDA": nv, "QQQ": qq}
        self.daily = daily
        self.pos = {"NVDA": 0, "QQQ": 0}     # number of completed bars available
        self.day_start = {"NVDA": 0, "QQQ": 0}
        self.ts = {k: v.index for k, v in self.data.items()}

    def advance_to(self, t_complete_before):
        """Make available every bar whose 5 minutes ended at or before t."""
        for sym, idx in self.ts.items():
            self.pos[sym] = int(idx.searchsorted(t_complete_before - pd.Timedelta(minutes=5), side="right"))
            today = pd.Timestamp(t_complete_before.date(), tz=ET)
            self.day_start[sym] = int(idx.searchsorted(today, side="left"))

    def candles(self, sym, bars):
        df = self.data.get(sym)
        if df is None:
            return None
        a, b = self.day_start[sym], self.pos[sym]
        if b <= a:                       # no bars today yet → most recent prior session
            if b == 0:
                return None
            last_day = df.index[b - 1].date()
            a = int(df.index.searchsorted(pd.Timestamp(last_day, tz=ET), side="left"))
        out = df.iloc[a:b]
        return out.iloc[-bars:] if len(out) else None

    def daily_before(self, d, n):
        x = self.daily[self.daily.index < pd.Timestamp(d)]
        return x.iloc[-n:]


class Order(types.SimpleNamespace):
    pass


class Broker:
    """Minimal Alpaca account: one symbol, market/stop/limit/bracket orders."""
    def __init__(self, equity, slippage):
        self.cash_pnl = 0.0
        self.start_equity = equity
        self.slip = slippage
        self.qty = 0
        self.avg = 0.0
        self.px = 0.0
        self.orders = []       # resting
        self.closed = []       # filled / cancelled
        self.n = 0
        self.fills = []        # (time, side, qty, price, reason)
        self.round_trips = []
        self._rt_open = None

    # ── internals ─────────────────────────────────────────────
    def _id(self):
        self.n += 1
        return f"sim-{self.n}"

    def _fill(self, side, qty, price, reason, order=None):
        signed = qty if side == "buy" else -qty
        new_qty = self.qty + signed
        if self.qty != 0 and (self.qty > 0) != (signed > 0):          # reducing / closing
            closing = min(abs(signed), abs(self.qty))
            pnl = (price - self.avg) * closing * (1 if self.qty > 0 else -1)
            self.cash_pnl += pnl
            if self._rt_open is not None:
                self._rt_open["pnl"] += pnl
                self._rt_open["exit_qty"] += closing
                self._rt_open["exit_value"] += closing * price
        if self.qty == 0 or (self.qty > 0) == (signed > 0):
            if self.qty == 0:
                self._rt_open = {"opened": Clock.now, "side": "long" if signed > 0 else "short",
                                 "qty": abs(signed), "entry": price, "pnl": 0.0,
                                 "exit_qty": 0, "exit_value": 0.0}
                self.avg = price
            else:
                self.avg = (self.avg * abs(self.qty) + price * abs(signed)) / abs(new_qty)
        self.qty = new_qty
        if self.qty == 0 and self._rt_open is not None:
            rt = self._rt_open
            rt["closed"] = Clock.now
            rt["exit"] = rt["exit_value"] / rt["exit_qty"] if rt["exit_qty"] else price
            rt["exit_reason"] = reason
            self.round_trips.append(rt)
            self._rt_open = None
            for o in self.orders:                      # flat → cancel remaining legs
                o.status = "canceled"
            self.closed += self.orders
            self.orders = []
        self.fills.append((Clock.now, side, qty, price, reason))
        if order is not None:
            order.status = "filled"
            order.filled_avg_price = str(round(price, 4))
            order.filled_qty = str(qty)
            order.filled_at = Clock.now.isoformat()
            self.closed.append(order)

    def _market_price(self, side):
        return self.px + self.slip if side == "buy" else self.px - self.slip

    # ── called by the simulator each tick ─────────────────────
    def tick(self, price, prev):
        self.px = price
        for o in list(self.orders):
            if o not in self.orders:
                continue
            if o.type == "stop":
                sp = float(o.stop_price)
                hit = price >= sp if o.side == "buy" else price <= sp
                if hit:
                    crossed = (prev < sp) if o.side == "buy" else (prev > sp)
                    fp = (sp if crossed else price) + (self.slip if o.side == "buy" else -self.slip)
                    self.orders.remove(o)
                    self._fill(o.side, int(o.qty), fp, "broker stop", o)
            elif o.type == "limit":
                lp = float(o.limit_price)
                if (price <= lp) if o.side == "buy" else (price >= lp):
                    self.orders.remove(o)
                    self._fill(o.side, int(o.qty), lp, "broker limit", o)

    def expire_day_orders(self):
        for o in self.orders:
            if o.time_in_force == "day":
                o.status = "expired"
                self.closed.append(o)
        self.orders = [o for o in self.orders if o.time_in_force != "day"]

    # ── Alpaca API surface used by the bot ────────────────────
    def get_account(self):
        eq = self.start_equity + self.cash_pnl + (self.px - self.avg) * self.qty
        return types.SimpleNamespace(portfolio_value=str(eq), equity=str(eq), last_equity=str(eq))

    def get_clock(self):
        n = Clock.now.astimezone(ET)
        open_ = n.weekday() < 5 and (9 * 60 + 30) <= n.hour * 60 + n.minute < 16 * 60
        return types.SimpleNamespace(is_open=open_, next_close=n.replace(hour=16, minute=0, second=0))

    def get_latest_trade(self, sym):
        return types.SimpleNamespace(price=self.px, timestamp=Clock.now.isoformat())

    def get_position(self, sym):
        if self.qty == 0:
            e = Exception("position does not exist")
            e.status_code = 404
            raise e
        return types.SimpleNamespace(qty=str(self.qty), avg_entry_price=str(self.avg),
                                     current_price=str(self.px), asset_id="sim-asset",
                                     unrealized_pl=str((self.px - self.avg) * self.qty),
                                     side="long" if self.qty > 0 else "short")

    def list_positions(self):
        return [self.get_position("NVDA")] if self.qty else []

    def list_orders(self, status="open", symbols=None, limit=None, after=None, **kw):
        if status == "open":
            return list(self.orders)
        if status == "closed":
            return list(reversed(self.closed))[: (limit or 50)]
        return list(self.orders) + list(self.closed)

    def get_order(self, oid):
        for o in self.orders + self.closed:
            if o.id == oid:
                return o
        raise Exception("order not found")

    def cancel_order(self, oid):
        for o in list(self.orders):
            if o.id == oid:
                o.status = "canceled"
                self.orders.remove(o)
                self.closed.append(o)

    def submit_order(self, symbol, qty, side, type, time_in_force="day", order_class=None,
                     stop_loss=None, take_profit=None, stop_price=None, limit_price=None, **kw):
        qty = int(float(qty))
        mk = lambda **a: Order(id=self._id(), symbol=symbol, qty=str(qty), side=side, status="new",
                               time_in_force=time_in_force, order_class=order_class or "simple",
                               filled_avg_price=None, filled_qty=None, filled_at=None,
                               position_intent=None, stop_price=None, limit_price=None, **a)
        if type == "market":
            o = mk(type="market")
            self._fill(side, qty, self._market_price(side), "market", o)
            if order_class == "bracket":
                exit_side = "sell" if side == "buy" else "buy"
                for leg in (Order(id=self._id(), symbol=symbol, qty=str(qty), side=exit_side, type="stop",
                                  stop_price=str(stop_loss["stop_price"]), limit_price=None,
                                  time_in_force=time_in_force, order_class="bracket", status="held",
                                  filled_avg_price=None, filled_qty=None, filled_at=None, position_intent=None),
                            Order(id=self._id(), symbol=symbol, qty=str(qty), side=exit_side, type="limit",
                                  limit_price=str(take_profit["limit_price"]), stop_price=None,
                                  time_in_force=time_in_force, order_class="bracket", status="held",
                                  filled_avg_price=None, filled_qty=None, filled_at=None, position_intent=None)):
                    self.orders.append(leg)
            return o
        o = mk(type=type)
        o.stop_price, o.limit_price = stop_price, limit_price
        self.orders.append(o)
        return o

    def close_position(self, sym):
        if self.qty == 0:
            raise Exception("position does not exist")
        for o in list(self.orders):
            self.cancel_order(o.id)
        side = "sell" if self.qty > 0 else "buy"
        self._fill(side, abs(self.qty), self._market_price(side), "close_position",
                   Order(id=self._id(), symbol=sym, qty=str(abs(self.qty)), side=side, type="market",
                         time_in_force="day", order_class="simple", status="new", position_intent=None,
                         filled_avg_price=None, filled_qty=None, filled_at=None))


# ═══════════════════════════════════════════════════════════════
# ENGINE
# ═══════════════════════════════════════════════════════════════

def load_bot(feed, broker, quiet):
    os.environ.setdefault("ALPACA_API_KEY", "backtest")
    os.environ.setdefault("ALPACA_SECRET_KEY", "backtest")
    os.environ["NVDA_TV_ENABLED"] = "0"
    sys.path.insert(0, HERE)
    with contextlib.redirect_stdout(io.StringIO()):
        import build_dashboard as bot

    bot.datetime = SimDatetime
    bot.print = lambda *a, **k: None          # NEW SESSION banners etc.
    bot.time = types.SimpleNamespace(sleep=lambda s: None, time=lambda: Clock.now.timestamp(),
                                     strftime=_real_time.strftime)
    bot.get_alpaca = lambda: (broker, float(broker.get_account().portfolio_value))
    bot.fetch_candles = lambda ticker, bars=200, attempt=1: feed.candles(ticker, bars)
    bot._fetch_alpaca = lambda ticker, bars=200, attempt=1: feed.candles(ticker, bars)

    def daily_closes(ticker, n_days=65):
        d = feed.daily_before(Clock.now.date(), n_days)
        return [float(x) for x in d["Close"]] or None
    bot.get_daily_closes = daily_closes

    def daily_bars(ticker, n_days=200):
        d = feed.daily_before(Clock.now.date(), n_days)
        return [{"t": str(i.date()), "p": round(float(r.Close), 2), "h": float(r.High), "l": float(r.Low)}
                for i, r in d.iterrows()]
    bot._fetch_daily_bars_for_chart = daily_bars
    # never touch the user's real files
    bot.save_state = lambda: None
    bot.save_daily_summary = lambda: None

    events = []
    real_log = bot.log

    def log(msg, level="INFO"):
        events.append((Clock.now, level, msg))
        if not quiet and level in ("TRADE", "ERROR", "CRITICAL"):
            print(f"  {Clock.now:%Y-%m-%d %H:%M} {level}: {msg}")
        bot.state["daily_events"].append({"time": "", "level": level, "message": msg})
        if len(bot.state["daily_events"]) > 100:
            bot.state["daily_events"] = bot.state["daily_events"][-100:]
    bot.log = log
    _ = real_log
    return bot, events


def main_loop_iteration(bot, scan):
    """Mirror of main()'s market-hours branch for one 15-second poll."""
    st = bot.state
    bot.reset_daily_state()
    if bot.end_of_day_check():
        return
    if not bot.get_active_trades():
        df = bot._fetch_alpaca(bot.CONFIG["ticker"], bars=30)
        if df is not None and len(df) >= 3:
            if df.index[-1].date() == bot.now_et().date():
                st["last_price"] = round(float(df["Close"].iloc[-1]), 2)
            else:
                st["last_price"] = round(float(bot.get_alpaca()[0].px), 2)
            a = bot.calculate_atr(df)
            if a:
                st["last_atr"] = a
            v, u, lo, _ = bot.calculate_vwap(df)
            if v:
                st["last_vwap"], st["last_vwap_upper"], st["last_vwap_lower"] = v, u, lo
    px = st.get("last_price", 0)
    if 50 < px < 2000:
        ts = bot.datetime.now(bot.MARKET_TZ).strftime("%Y-%m-%dT%H:%M")
        hist = st.get("price_history", [])
        if not hist or hist[-1]["t"] != ts:
            hist.append({"t": ts, "p": px, "kz": "", "trend": st.get("last_trend", "neutral"),
                         "mtf": st.get("mtf_bias", "neutral")})
        else:
            hist[-1]["p"] = px
        st["price_history"] = hist[-2000:]
    if bot.get_active_trades():
        bot.monitor_trade()
    if scan and bot.get_bot_trade() is None:
        if bot.is_in_kill_zone():
            bot.check_for_entry()
        elif bot.get_next_kill_zone() and st["order_failed_today"]:
            st["order_failed_today"] = False


def bar_path(o, h, l, c):
    pts = [o, l, h, c] if c >= o else [o, h, l, c]
    seg = [abs(pts[i + 1] - pts[i]) for i in range(3)]
    total = sum(seg) or 1.0
    out = []
    for k in range(1, TICKS_PER_BAR + 1):
        d = total * k / TICKS_PER_BAR
        for i in range(3):
            if d <= seg[i] or i == 2:
                f = (d / seg[i]) if seg[i] else 1.0
                out.append(pts[i] + (pts[i + 1] - pts[i]) * min(f, 1.0))
                break
            d -= seg[i]
    out[-1] = c
    return out


def run(nv, qq, daily, args):
    feed = Feed(nv, qq, daily)
    broker = Broker(args.equity, args.slippage)
    bot, events = load_bot(feed, broker, args.quiet)
    for k, v in (args.set or {}).items():
        bot.CONFIG[k] = v
    if args.signal_source:
        bot.SIGNAL_SOURCE = args.signal_source

    days = sorted(set(nv.index.date))
    first_trade_day = days[min(args.warmup, len(days) - 1)]
    if args.start:
        first_trade_day = max(first_trade_day, pd.Timestamp(args.start).date())
    last_day = pd.Timestamp(args.end).date() if args.end else days[-1]
    closed_trades = []
    real_finalize = bot._finalize_trade_close

    def finalize(trade):
        closed_trades.append(dict(trade))
        return real_finalize(trade)
    bot._finalize_trade_close = finalize

    equity_rows = []
    by_day = {d: g for d, g in nv.groupby(nv.index.date)}
    t0 = _real_time.time()
    for di, d in enumerate(days):
        if d > last_day:
            break
        trading = d >= first_trade_day
        bars = by_day[d]
        prev = float(bars["Open"].iloc[0])
        for ts, row in bars.iterrows():
            in_trade = bool(bot.get_active_trades())
            path = bar_path(row.Open, row.High, row.Low, row.Close)
            for k, price in enumerate(path):
                Clock.now = (ts + timedelta(seconds=15 * (k + 1) - 1)).to_pydatetime()
                is_close = k == len(path) - 1
                feed.advance_to(ts + timedelta(minutes=5) if is_close else ts)
                broker.tick(price, prev)
                prev = price
                if in_trade or bot.get_active_trades() or is_close:
                    main_loop_iteration(bot, scan=trading and is_close)
        # after the bell: same as the bot's evening loop (monitor, then idle)
        Clock.now = _real_datetime(d.year, d.month, d.day, 16, 0, 30, tzinfo=ET)
        feed.advance_to(pd.Timestamp(Clock.now))
        bot.reset_daily_state()
        if bot.get_active_trades():          # main(): after hours → monitor only
            bot.monitor_trade()
        broker.expire_day_orders()
        eq = float(broker.get_account().portfolio_value)
        equity_rows.append({"date": str(d), "equity": round(eq, 2), "position": broker.qty})
        if not args.quiet and (di % 10 == 0):
            print(f"  … {d}  equity ${eq:,.2f}  trades {len(broker.round_trips)}  "
                  f"({_real_time.time() - t0:.0f}s)")
    return bot, broker, closed_trades, equity_rows, events, first_trade_day


# ═══════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════

def sanity_checks(broker, closed, tdf, unmatched, args):
    """Invariants that must hold if the simulator and the bot agree with each other."""
    out = []
    rts = broker.round_trips
    out.append((abs(sum(r["pnl"] for r in rts) - broker.cash_pnl) < 0.01,
                f"round-trip P&L sums to broker realized P&L (${broker.cash_pnl:,.2f})"))
    out.append((len(rts) == len(closed) and not unmatched,
                f"every bot-closed trade matches a broker round trip ({len(closed)} bot / {len(rts)} broker)"))
    if not tdf.empty:
        oc = pd.to_datetime(tdf.opened)
        mins = oc.dt.hour * 60 + oc.dt.minute
        in_kz = ((mins >= 570) & (mins < 660)) | ((mins >= 720) & (mins < 780)) | ((mins >= 840) & (mins < 955))
        out.append((bool(in_kz.all()), "every entry is inside a kill zone (09:30-11:00, 12:00-13:00, 14:00-15:55 ET)"))
        multi = tdf[pd.to_datetime(tdf.closed).dt.date != oc.dt.date]
        out.append((bool((multi.strategy == "SWING-6M").all()),
                    f"only SWING-6M is held overnight ({len(multi)} overnight trades)"))
        cap = tdf.entry * tdf.qty <= args.equity * 1.5 * 0.05 + 1
        out.append((bool(cap.all()), "position value stays within max_position_pct (5% of equity)"))
        over = (tdf.opened.values[1:] < tdf.closed.values[:-1]).sum() if len(tdf) > 1 else 0
        out.append((over == 0, "never more than one position open at a time"))
    return out


def report(broker, closed, equity_rows, events, args, first_day, label):
    os.makedirs(args.out, exist_ok=True)
    rts = broker.round_trips
    rows = []
    unmatched = list(closed)

    def match(rt):
        best = None
        for bt in unmatched:
            oa = bt.get("opened_at")
            if hasattr(oa, "timestamp") and abs(oa.timestamp() - rt["opened"].timestamp()) <= 60 \
                    and int(bt.get("qty", 0)) == rt["qty"]:
                best = bt
                break
        if best is not None:
            unmatched.remove(best)
        return best or {}
    for i, rt in enumerate(rts):
        bt = match(rt)
        risk_ps = abs(float(bt.get("entry", rt["entry"])) - float(bt.get("orig_stop", bt.get("stop", rt["entry"])) or rt["entry"]))
        rows.append({
            "opened": rt["opened"].strftime("%Y-%m-%d %H:%M"), "closed": rt["closed"].strftime("%Y-%m-%d %H:%M"),
            "strategy": bt.get("strategy", "?"), "side": rt["side"], "qty": rt["qty"],
            "entry": round(rt["entry"], 2), "exit": round(rt["exit"], 2),
            "stop": bt.get("orig_stop", bt.get("stop")), "target": bt.get("target"),
            "pnl": round(rt["pnl"], 2), "r_multiple": round(rt["pnl"] / (risk_ps * rt["qty"]), 2) if risk_ps else None,
            "bot_outcome": bt.get("outcome"), "bot_booked_pnl": bt.get("pnl"),
            "minutes": int((rt["closed"] - rt["opened"]).total_seconds() / 60),
            "exit_via": rt["exit_reason"],
        })
    tdf = pd.DataFrame(rows)
    edf = pd.DataFrame(equity_rows)
    tdf.to_csv(os.path.join(args.out, "trades.csv"), index=False)
    edf.to_csv(os.path.join(args.out, "equity.csv"), index=False)

    lines = [f"NVDA AutoTrader backtest — {label}",
             f"Period: {first_day} → {edf['date'].iloc[-1] if len(edf) else '?'}  "
             f"({len(edf)} sessions incl. warmup)   Start equity ${args.equity:,.0f}   "
             f"Slippage ${args.slippage:.3f}/share", ""]
    if tdf.empty:
        lines.append("No trades.")
    else:
        def stats(g):
            w = g[g.pnl > 0]
            l = g[g.pnl <= 0]
            pf = w.pnl.sum() / -l.pnl.sum() if len(l) and l.pnl.sum() < 0 else float("inf")
            return {"trades": len(g), "win%": round(100 * len(w) / len(g), 1),
                    "total $": round(g.pnl.sum(), 2), "avg $": round(g.pnl.mean(), 2),
                    "avg R": round(g.r_multiple.dropna().mean(), 2) if g.r_multiple.notna().any() else None,
                    "profit factor": round(pf, 2) if pf != float("inf") else "∞",
                    "avg min": int(g.minutes.mean())}
        st = pd.DataFrame({k: stats(g) for k, g in tdf.groupby("strategy")}).T
        st.loc["ALL"] = stats(tdf)
        lines.append(st.to_string())
        eq = edf.equity
        dd = (eq - eq.cummax()).min()
        lines += ["", f"Net P&L ${tdf.pnl.sum():,.2f} ({tdf.pnl.sum() / args.equity * 100:+.2f}%)   "
                      f"Max drawdown ${dd:,.2f}   Long {int((tdf.side == 'long').sum())} / Short {int((tdf.side == 'short').sum())}",
                  "", "Exit routes:", tdf.groupby(["bot_outcome", "exit_via"]).size().to_string()]
    checks = sanity_checks(broker, closed, tdf, unmatched, args)
    lines += ["", "Consistency checks:"] + [f"  {'PASS' if ok else 'FAIL'}  {msg}" for ok, msg in checks]
    errs = [e for e in events if e[1] in ("ERROR", "CRITICAL")]
    lines += ["", f"Bot ERROR/CRITICAL log lines during the run: {len(errs)}"]
    for e in errs[:15]:
        lines.append(f"  {e[0]:%Y-%m-%d %H:%M} {e[1]}: {e[2][:160]}")
    lines += ["", "Assumptions: 20 ticks per 5-min bar along O→L→H→C (O→H→L→C on red bars); entries on",
              "completed bars; market fills at tick ± slippage, stops at stop price unless gapped.",
              "Past results on one stock over one period say little about the future."]
    text = "\n".join(lines)
    with open(os.path.join(args.out, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("\n" + text)
    print(f"\nWrote {args.out}/trades.csv, equity.csv, summary.txt")
    return tdf, edf


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", choices=["alpaca", "yfinance", "csv", "synthetic"], default="alpaca")
    ap.add_argument("--start"); ap.add_argument("--end")
    ap.add_argument("--csv"); ap.add_argument("--qqq-csv")
    ap.add_argument("--equity", type=float, default=100_000)
    ap.add_argument("--slippage", type=float, default=0.01, help="$/share on market and stop fills")
    ap.add_argument("--warmup", type=int, default=6, help="sessions of 5m data used only to build history")
    ap.add_argument("--signal-source", choices=["bot", "tradingview", "both"])
    ap.add_argument("--synthetic-days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--set", type=json.loads, help='override CONFIG, e.g. \'{"risk_reward": 2.0}\'')
    ap.add_argument("--out", default=os.path.join(HERE, "backtest_results"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    args.out = os.path.abspath(args.out)

    if args.source == "alpaca":
        if not args.start:
            args.start = (pd.Timestamp.now(tz=ET) - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
        nv, qq, daily = load_alpaca(args.start, args.end or pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d"), args.warmup)
        label = "Alpaca IEX 5-min bars"
    elif args.source == "yfinance":
        nv, qq, daily = load_yfinance(); label = "Yahoo 5-min bars"
    elif args.source == "csv":
        if not args.csv:
            sys.exit("--csv path required")
        nv, qq, daily = load_csv(args.csv, args.qqq_csv); label = f"CSV {os.path.basename(args.csv)}"
    else:
        nv, qq, daily = make_synthetic(args.synthetic_days, args.seed)
        label = f"SYNTHETIC random-walk data (seed {args.seed}) — mechanics check only, NOT a performance result"

    print(f"{label}: {len(nv)} NVDA bars, {len(set(nv.index.date))} sessions, "
          f"{len(daily)} daily bars")
    work = tempfile.mkdtemp(prefix="nvda_bt_")
    cwd = os.getcwd()
    os.chdir(work)               # bot writes trade_logs/* relative to cwd — keep them out of the project
    try:
        bot, broker, closed, eq, events, first = run(nv, qq, daily, args)
    finally:
        os.chdir(cwd)
    report(broker, closed, eq, events, args, first, label)


if __name__ == "__main__":
    main()
