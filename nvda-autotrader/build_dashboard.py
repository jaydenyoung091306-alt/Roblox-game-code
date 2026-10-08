#!/usr/bin/env python3
"""
NVDA AutoTrader — Dashboard Builder v4.97
==========================================

CLAUDE AI CONTEXT — READ THIS FIRST IF STARTING A NEW CHAT
============================================================
This file is part of a two-file algorithmic paper trading system for NVDA stock.

FILES (all live in the same project folder):
  nvda_autotrader.py        — Main bot (current version: v4.97)
  build_dashboard.py        — This file. Generates nvda_live_dashboard.html
  nvda_live_dashboard.html  — Generated dashboard (do NOT edit directly)
  nvda_price_history.json   — Rolling 2000-point price history
  nvda_bot_state.json       — Persisted session state (trades, P&L, etc.)
  trade_logs/               — Daily summary .txt and master_trade_log.csv

HOW TO RUN:
  1. Start bot:      cd %USERPROFILE%\\Downloads\\NVDA && python nvda_autotrader.py
  2. Rebuild dash:   python build_dashboard.py
  3. View dashboard: http://localhost:8080  (NOT by opening the HTML file directly)
  Task Scheduler runs the bot automatically at 8:20 AM daily.

BROKER & DATA:
  Alpaca paper trading (PAPER MODE). API keys are in nvda_autotrader.py top section.
  Data: Alpaca IEX free feed (15-min delay). YFinance fallback for QQQ/MTF data.
  To go live: change ALPACA_BASE_URL from paper-api to api.alpaca.markets + live keys.

STRATEGIES (five run in parallel):
  1. FVG Retrace     — Fair Value Gap detection, waits for retrace into gap zone
  2. VWAP Bounce     — Monitors price vs VWAP ±1×ATR bands, enters on bounce
  3. Spike Reversal  — Detects sharp spikes ≥2.5×ATR, enters counter-trend
  4. Range Extreme   — Detects price at 5-day high/low with reversal candle (v4.17)
  5. Swing Reversion — Fades price near 3mo/6mo high/low once intraday trend
                        confirms a turn (v4.84, SWING-3M/SWING-6M variants)
  FVG vs VWAP chosen at each kill zone via scoring. Spike + Range Extreme run always.

KILL ZONES (ET):  09:30-11:00 | 12:00-13:00 | 14:00-15:55

KEY CONFIG in nvda_autotrader.py:
  risk_reward:           1.5    (target = 1.5× stop distance)
  stop_atr_mult:         2.0    (bot stop = 2× ATR)
  pdt_protection:        False  (set True for live sub-$25k accounts)
  extreme_lookback_days: 5      (days back for range high/low)
  extreme_proximity_mult:0.5    (within 0.5×ATR of extreme to trigger)
  spike_atr_mult:        2.5    (spike must be ≥2.5×ATR)
  spike_vwap_mult:       1.5    (price must be ≥1.5×ATR from VWAP)

MULTI-TRADE ARCHITECTURE (v4.12+):
  state["active_trades"]  — list of all open trades (bot + manual)
  state["active_trade"]   — legacy alias → first non-MANUAL bot trade or None
  get_bot_trade()         — returns first non-MANUAL trade or None
  Manual trades fire real Alpaca orders. Bot trades use bracket orders for longs,
  plain market sell for shorts (IEX free tier limitation).

DASHBOARD FEATURES:
  - ATR multiplier selector: 0.5× 1× 1.5× 2× 2.5× with live stop/target preview
  - Manual trade modal: LONG/SHORT, qty, stop, target, managed/log-only, trailing stop
  - Chart: 1 Hour / Today / 5 Days / 1 Month views
  - After hours: bot stays alive serving dashboard until midnight (does not trade)

IMPORTANT RULES FOR CLAUDE:
  - ALWAYS bump VERSION in both nvda_autotrader.py header AND this file when making changes
  - ALWAYS run syntax check before presenting files: python3 -c "import ast; ast.parse(open('file').read())"
  - After editing build_dashboard.py, user must run: python build_dashboard.py
  - The bot serves nvda_live_dashboard.html via HTTPServer on port 8080
  - HTTPServer binds to '' (all interfaces) — not 'localhost' (IPv6/IPv4 Windows issue)
  - Short orders use plain market sell (no bracket) — Alpaca IEX free tier limitation
  - Manual trade auto-calc uses atr_mult from dashboard (0.5-2.5×), not hardcoded 2×
  - _check_range_extreme() and _check_spike_reversal() both return:
    ("bullish"/"bearish", entry, stop, target, risk, reason) or None

ACCOUNT STATUS (as of 2026-06-04, not refreshed by this cleanup pass):
  Starting equity (May 26): $100,366.41
  Current equity:           $100,637.63
  Paper trading — Alpaca paper account

HOW TO EDIT THIS DASHBOARD:
  - CSS:       get_css()
  - HTML:      get_body_html()
  - JS:        get_js()  — BAKED_HISTORY is injected automatically from price JSON
  After any edit run: python build_dashboard.py
"""


import json
import os
import re
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

DASHBOARD_FILE   = "nvda_live_dashboard.html"
PRICE_HIST_FILE  = "nvda_price_history.json"
BOT_PORT         = 8080
VERSION          = "v4.97"


# ═══════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════

def get_css():
    return """

@import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500;700&display=swap');
:root {
  --bg:#080c14; --surface:#0f1520; --card:#131d2e; --border:#1e2d42;
  --accent:#00e5c0; --red:#ff4560; --yellow:#ffcc44; --blue:#3b82f6;
  --text:#dde8f5; --muted:#4a6080; --win:#00e5c0; --loss:#ff4560;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh;padding:20px;}
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid var(--border);}
.logo{font-family:'Space Mono',monospace;font-size:1rem;color:var(--accent);letter-spacing:.06em;}
.logo span{display:block;font-size:.65rem;color:var(--muted);margin-top:3px;font-style:italic;}
.live-dot{display:flex;align-items:center;gap:8px;font-family:'Space Mono',monospace;font-size:.7rem;color:var(--muted);}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted);}
.dot.live{background:var(--accent);box-shadow:0 0 8px var(--accent);animation:pulse 2s infinite;}
.dot.error{background:var(--red);}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.4;}}
#conn-banner{background:rgba(255,69,96,.12);border:1px solid rgba(255,69,96,.3);border-radius:6px;padding:12px 16px;margin-bottom:20px;font-family:'Space Mono',monospace;font-size:.75rem;color:var(--red);display:none;}
.status-bar{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:12px 18px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;gap:12px;}
.status-text{font-family:'Space Mono',monospace;font-size:.78rem;color:var(--accent);}
.status-meta{font-family:'Space Mono',monospace;font-size:.65rem;color:var(--muted);text-align:right;}
.kz-bar{display:flex;gap:8px;margin-bottom:20px;}
.kz-slot{flex:1;text-align:center;padding:8px 4px;font-family:'Space Mono',monospace;font-size:.65rem;color:var(--muted);background:var(--card);border:1px solid var(--border);border-radius:6px;}
.kz-slot.active{color:var(--accent);border-color:var(--accent);background:rgba(0,229,192,.07);}
.kz-slot.passed{color:var(--border);border-color:var(--border);}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:20px;}
.stat-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;position:relative;overflow:hidden;transition:border-color .3s;}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent);transition:background .3s;}
.stat-card.red::before{background:var(--red);}
.stat-card.yellow::before{background:var(--yellow);}
.stat-card.blue::before{background:var(--blue);}
.stat-label{font-family:'Space Mono',monospace;font-size:.62rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;}
.stat-value{font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;line-height:1;transition:color .3s;}
.stat-value.up{color:var(--win);}.stat-value.down{color:var(--loss);}.stat-value.flat{color:var(--text);}
.stat-sub{font-size:.68rem;color:var(--muted);margin-top:5px;}
.main-grid{display:grid;grid-template-columns:1fr 340px;gap:16px;margin-bottom:16px;}
@media(max-width:900px){.main-grid{grid-template-columns:1fr;}}
.chart-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:18px;}
.chart-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}
.card-title{font-family:'Space Mono',monospace;font-size:.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;}
.range-tabs{display:flex;gap:4px;}
.range-tab{font-family:'Space Mono',monospace;font-size:.62rem;padding:4px 10px;border-radius:4px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;letter-spacing:.05em;}
.range-tab:hover{border-color:var(--accent);color:var(--accent);}
.range-tab.active{background:rgba(0,229,192,.1);border-color:var(--accent);color:var(--accent);}
.chart-wrap{position:relative;height:260px;}
.range-hint{font-family:'Space Mono',monospace;font-size:.6rem;color:var(--muted);text-align:center;margin-top:8px;opacity:.6;}
.trade-panel{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:18px;display:flex;flex-direction:column;gap:14px;}
.trade-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--muted);font-size:.8rem;gap:8px;min-height:160px;}
.trade-empty .icon{font-size:2rem;}
.trade-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04);}
.trade-row:last-child{border-bottom:none;}
.trade-key{font-family:'Space Mono',monospace;font-size:.65rem;color:var(--muted);text-transform:uppercase;}
.trade-val{font-family:'Space Mono',monospace;font-size:.8rem;font-weight:700;}
.fvg-list{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:18px;margin-bottom:16px;}
.fvg-items{display:flex;flex-direction:column;gap:8px;}
.fvg-item{display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--surface);border-radius:5px;border-left:3px solid var(--border);}
.fvg-item.bullish{border-left-color:var(--win);}.fvg-item.bearish{border-left-color:var(--loss);}
.fvg-badge{font-family:'Space Mono',monospace;font-size:.6rem;font-weight:700;padding:2px 6px;border-radius:3px;white-space:nowrap;}
.fvg-badge.bullish{background:rgba(0,229,192,.12);color:var(--win);}.fvg-badge.bearish{background:rgba(255,69,96,.12);color:var(--loss);}
.fvg-details{flex:1;font-size:.75rem;}
.fvg-score{text-align:right;}
.score-pips{display:flex;gap:3px;justify-content:flex-end;}
.pip{width:6px;height:6px;border-radius:1px;}
.pip.on{background:var(--accent);}.pip.off{background:var(--border);}
.fvg-empty{color:var(--muted);font-size:.8rem;text-align:center;padding:24px;}
.log-card{background:var(--card);border:1px solid var(--border);border-radius:8px;margin-bottom:16px;overflow:hidden;}
.log-inner{max-height:240px;overflow-y:auto;}
.log-entry{display:flex;align-items:flex-start;gap:10px;padding:8px 14px;border-bottom:1px solid rgba(255,255,255,.03);font-size:.72rem;}
.log-time{font-family:'Space Mono',monospace;color:var(--muted);white-space:nowrap;font-size:.65rem;padding-top:1px;}
.log-level{font-family:'Space Mono',monospace;font-size:.62rem;padding:2px 5px;border-radius:3px;white-space:nowrap;}
.log-level.INFO{background:rgba(0,229,192,.1);color:var(--accent);}
.log-level.WARN{background:rgba(255,204,68,.1);color:var(--yellow);}
.log-level.ERROR{background:rgba(255,69,96,.1);color:var(--red);}
.log-level.TRADE{background:rgba(59,130,246,.1);color:var(--blue);}
.log-level.REPORT{background:rgba(59,130,246,.1);color:var(--blue);}
.log-msg{color:var(--text);line-height:1.4;word-break:break-word;}

/* ── MANUAL TRADE MODAL ── */
.modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);}
.modal-backdrop.hidden{display:none;}
.modal{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:28px;width:420px;max-width:95vw;position:relative;}
.modal-title{font-family:'Space Mono',monospace;font-size:.9rem;color:var(--accent);margin-bottom:20px;letter-spacing:.05em;}
.modal-close{position:absolute;top:16px;right:16px;background:none;border:none;color:var(--muted);cursor:pointer;font-size:1.1rem;line-height:1;padding:4px 8px;border-radius:4px;}
.modal-close:hover{color:var(--text);background:rgba(255,255,255,.05);}
.field-group{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;}
.field-group.full{grid-template-columns:1fr;}
.field{display:flex;flex-direction:column;gap:6px;}
.field label{font-family:'Space Mono',monospace;font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;}
.field input,.field select{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:10px 12px;color:var(--text);font-family:'Space Mono',monospace;font-size:.8rem;outline:none;transition:border-color .2s;}
.field input[readonly]{color:var(--accent);cursor:not-allowed;border-color:rgba(0,229,192,.3);background:rgba(0,229,192,.05);}
.field input:focus,.field select:focus{border-color:var(--accent);}
.field select option{background:var(--card);}
.atr-row{display:flex;align-items:center;gap:10px;margin-bottom:16px;padding:10px 12px;background:var(--surface);border-radius:6px;border:1px solid var(--border);}
.atr-row label{font-family:'Space Mono',monospace;font-size:.7rem;color:var(--muted);cursor:pointer;flex:1;}
.atr-row input[type=checkbox]{accent-color:var(--accent);width:14px;height:14px;cursor:pointer;}
.atr-hint{font-size:.65rem;color:var(--muted);opacity:.7;}
.atr-mult-btn{background:var(--card);border:1px solid var(--border);color:var(--muted);border-radius:4px;padding:3px 10px;font-size:.7rem;cursor:pointer;font-family:'Space Mono',monospace;transition:all .15s;}
.atr-mult-btn:hover{border-color:var(--accent);color:var(--accent);}
.atr-mult-btn.active{background:var(--accent);border-color:var(--accent);color:#000;font-weight:700;}
.managed-row{display:flex;gap:8px;margin-bottom:20px;}
.managed-btn{flex:1;padding:10px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--muted);font-family:'Space Mono',monospace;font-size:.7rem;cursor:pointer;transition:all .15s;text-align:center;}
.managed-btn.selected-managed{border-color:var(--accent);color:var(--accent);background:rgba(0,229,192,.08);}
.managed-btn.selected-log{border-color:var(--yellow);color:var(--yellow);background:rgba(255,204,68,.08);}
.dir-row{display:flex;gap:8px;margin-bottom:16px;}
.dir-btn{flex:1;padding:10px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--muted);font-family:'Space Mono',monospace;font-size:.75rem;cursor:pointer;transition:all .15s;text-align:center;}
.dir-btn.selected-long{border-color:var(--win);color:var(--win);background:rgba(0,229,192,.08);}
.dir-btn.selected-short{border-color:var(--loss);color:var(--loss);background:rgba(255,69,96,.08);}
.submit-btn{width:100%;padding:12px;border-radius:8px;border:none;background:var(--accent);color:#080c14;font-family:'Space Mono',monospace;font-size:.8rem;font-weight:700;cursor:pointer;letter-spacing:.05em;transition:opacity .15s;}
.submit-btn:hover{opacity:.85;}
.submit-btn:disabled{opacity:.4;cursor:not-allowed;}
.modal-error{color:var(--red);font-family:'Space Mono',monospace;font-size:.7rem;margin-top:10px;display:none;}
.modal-success{color:var(--win);font-family:'Space Mono',monospace;font-size:.7rem;margin-top:10px;display:none;}
.manual-trade-btn{font-family:'Space Mono',monospace;font-size:.65rem;padding:5px 12px;border-radius:5px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .2s;letter-spacing:.05em;}
.manual-trade-btn:hover{border-color:var(--accent);color:var(--accent);}
.close-trade-btn{font-family:'Space Mono',monospace;font-size:.65rem;padding:5px 12px;border-radius:5px;border:1px solid rgba(255,69,96,.4);background:transparent;color:var(--loss);cursor:pointer;transition:all .2s;}
.close-trade-btn:hover{background:rgba(255,69,96,.1);}

"""


# ═══════════════════════════════════════════════════════════════
# BODY HTML
# ═══════════════════════════════════════════════════════════════

def get_body_html():
    return """</head>
<body>

<header>
  <div class="logo">NVDA AUTOTRADER<span>{VERSION} · Paper Trading</span></div>
  <div style="display:flex;align-items:center;gap:12px">
    <button class="manual-trade-btn" onclick="openModal()" id="manual-btn">+ Manual Trade</button>
    <div class="live-dot">
      <div class="dot" id="live-dot"></div>
      <span id="live-label">Connecting...</span>
    </div>
  </div>
</header>

<div id="conn-banner">⚠ Bot disconnected — make sure nvda_autotrader.py is running on port 8080</div>

<div class="status-bar">
  <div class="status-text" id="status-text">Waiting for data...</div>
  <div class="status-meta" id="status-meta"></div>
</div>

<div class="kz-bar">
  <div class="kz-slot" id="kz-0">09:30–11:00 ET</div>
  <div class="kz-slot" id="kz-1">12:00–13:00 ET</div>
  <div class="kz-slot" id="kz-2">14:00–15:55 ET</div>
</div>

<div class="stats-grid">
  <div class="stat-card" id="card-price">
    <div class="stat-label">NVDA Price</div>
    <div class="stat-value flat" id="val-price">—</div>
    <div class="stat-sub" id="sub-price">Scanned —</div>
  </div>
  <div class="stat-card yellow" id="card-trend">
    <div class="stat-label">Trend</div>
    <div class="stat-value flat" id="val-trend">—</div>
    <div class="stat-sub">10-candle lookback</div>
  </div>
  <div class="stat-card" id="card-qqq">
    <div class="stat-label">QQQ Direction</div>
    <div class="stat-value flat" id="val-qqq">—</div>
    <div class="stat-sub">Market context</div>
  </div>
  <div class="stat-card" id="card-fvgs">
    <div class="stat-label">FVGs Today</div>
    <div class="stat-value flat" id="val-fvgs">0</div>
    <div class="stat-sub" id="sub-fvgs">Best score: 0/9</div>
  </div>
  <div class="stat-card blue">
    <div class="stat-label">Portfolio</div>
    <div class="stat-value flat" id="val-equity">—</div>
    <div class="stat-sub" id="sub-equity">Paper account</div>
  </div>
  <div class="stat-card" id="card-pnl">
    <div class="stat-label">Trade P&amp;L</div>
    <div class="stat-value flat" id="val-pnl">—</div>
    <div class="stat-sub" id="sub-pnl">No trade yet</div>
  </div>
  <div class="stat-card" id="card-strategy">
    <div class="stat-label">Strategy</div>
    <div class="stat-value flat" id="val-strategy">—</div>
    <div class="stat-sub" id="sub-strategy">Kill zone active</div>
  </div>
  <div class="stat-card" id="card-mtf">
    <div class="stat-label">MTF Bias</div>
    <div class="stat-value flat" id="val-mtf">—</div>
    <div class="stat-sub" id="sub-mtf">Weekly · Monthly</div>
  </div>
</div>

<div class="main-grid">
  <div class="chart-card">
    <div class="chart-header">
      <div class="card-title" style="margin:0">NVDA Price</div>
      <div class="range-tabs">
        <button class="range-tab active" data-range="1h">1 Hour</button>
        <button class="range-tab" data-range="1d">Today</button>
        <button class="range-tab" data-range="5d">5 Days</button>
        <button class="range-tab" data-range="1m">1 Month</button>
        <button class="range-tab" data-range="6m">6 Month</button>
      </div>
    </div>
    <div class="chart-wrap"><canvas id="priceChart"></canvas></div>
    <div class="range-hint" id="range-hint">Loading...</div>
  </div>
  <div class="trade-panel">
    <div class="card-title">Active Trade</div>
    <div id="trade-content">
      <div class="trade-empty"><div class="icon">⏳</div><div>No active trade</div></div>
    </div>
  </div>
</div>

<div class="fvg-list">
  <div class="card-title">FVGs Detected Today</div>
  <div class="fvg-items" id="fvg-items"><div class="fvg-empty">No FVGs detected yet today</div></div>
</div>

<div class="log-card">
  <div style="padding:12px 16px;border-bottom:1px solid var(--border)">
    <div class="card-title" style="margin:0">Live Event Log</div>
  </div>
  <div class="log-inner" id="log-inner">
    <div class="log-entry"><span class="log-msg" style="color:var(--muted)">Waiting for bot data...</span></div>
  </div>
</div>

<!-- ── MANUAL TRADE MODAL ── -->
<div class="modal-backdrop hidden" id="modal-backdrop" onclick="closeModalOutside(event)">
  <div class="modal">
    <div class="modal-title">+ Manual Trade Entry</div>
    <button class="modal-close" onclick="closeModal()">✕</button>

    <div class="dir-row">
      <button class="dir-btn" id="btn-long"  onclick="setDir('bullish')">▲ LONG</button>
      <button class="dir-btn" id="btn-short" onclick="setDir('bearish')">▼ SHORT</button>
    </div>

    <div class="field-group">
      <div class="field">
        <label>Entry Price (live — not editable)</label>
        <input type="number" id="m-entry" step="0.01" placeholder="0.00" readonly>
      </div>
      <div class="field">
        <label>Quantity (shares)</label>
        <input type="number" id="m-qty" step="1" placeholder="0">
      </div>
    </div>
    <div id="m-price-hint" style="font-family:'Space Mono',monospace;font-size:.62rem;color:var(--accent);margin:-8px 0 12px 0;opacity:.8;"></div>

    <div class="atr-row">
      <input type="checkbox" id="m-atr" onchange="toggleAtr()">
      <label for="m-atr">Auto-calculate stop &amp; target from ATR</label>
      <span class="atr-hint" id="atr-hint"></span>
    </div>
    <div id="atr-mult-row" style="display:none;margin:-4px 0 12px 0;">
      <div style="font-size:.65rem;color:var(--muted);margin-bottom:5px;">ATR multiplier for stop distance:</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        <button class="atr-mult-btn" onclick="setAtrMult(0.5)">0.5×</button>
        <button class="atr-mult-btn active" onclick="setAtrMult(1.0)">1×</button>
        <button class="atr-mult-btn" onclick="setAtrMult(1.5)">1.5×</button>
        <button class="atr-mult-btn" onclick="setAtrMult(2.0)">2×</button>
        <button class="atr-mult-btn" onclick="setAtrMult(2.5)">2.5×</button>
      </div>
      <div id="atr-preview" style="font-size:.65rem;color:var(--accent);margin-top:6px;font-family:'Space Mono',monospace;"></div>
    </div>

    <div id="manual-stop-target">
      <div class="field-group">
        <div class="field">
          <label>Stop Price</label>
          <input type="number" id="m-stop" step="0.01" placeholder="0.00" oninput="updateBracketHint()">
        </div>
        <div class="field">
          <label>Target Price</label>
          <input type="number" id="m-target" step="0.01" placeholder="0.00" oninput="updateBracketHint()">
        </div>
      </div>
      <div id="m-bracket-hint" style="font-family:'Space Mono',monospace;font-size:.62rem;margin:-8px 0 12px 0;"></div>
    </div>

    <div style="margin-bottom:12px">
      <div class="field"><label>Monitor Mode</label></div>
      <div class="managed-row" style="margin-top:6px">
        <button class="managed-btn selected-managed" id="btn-managed"  onclick="setManaged(true)">Managed (bot monitors stop/target)</button>
        <button class="managed-btn"                  id="btn-logonly"  onclick="setManaged(false)">Log Only (no auto-close)</button>
      </div>
    </div>

    <div class="atr-row" id="trail-row">
      <input type="checkbox" id="m-trail" onchange="toggleTrail()">
      <label for="m-trail">Enable trailing stop (breakeven at 1:1, trail at 2:1)</label>
      <span class="atr-hint" id="trail-hint"></span>
    </div>

    <button class="submit-btn" id="submit-btn" onclick="submitManualTrade()">Enter Trade</button>
    <div class="modal-error"   id="modal-error"></div>
    <div class="modal-success" id="modal-success"></div>
  </div>
</div>

<!-- ── CLOSE MANUAL TRADE MODAL ── -->
<div class="modal-backdrop hidden" id="close-modal-backdrop" onclick="closeCloseModal(event)">
  <div class="modal">
    <div class="modal-title">✕ Close Manual Trade</div>
    <button class="modal-close" onclick="closeCloseModal()">✕</button>
    <div class="field-group full">
      <div class="field">
        <label>Realized P&amp;L ($)</label>
        <input type="number" id="c-pnl" step="0.01" placeholder="e.g. 45.00 or -22.50">
      </div>
    </div>
    <button class="submit-btn" onclick="submitClose()">Confirm Close</button>
    <div class="modal-error" id="close-error"></div>
  </div>
</div>"""


# ═══════════════════════════════════════════════════════════════
# JAVASCRIPT
# ═══════════════════════════════════════════════════════════════

def get_js(baked_history):
    baked_json = json.dumps(baked_history)

    # Replace the BAKED_HISTORY constant with fresh data
    js = JS_TEMPLATE.replace("__BAKED_HISTORY_PLACEHOLDER__", baked_json)
    return js


# ═══════════════════════════════════════════════════════════════
# JS TEMPLATE
# (BAKED_HISTORY is injected at build time — do not edit that line)
# ═══════════════════════════════════════════════════════════════

JS_TEMPLATE = """
// ── BAKED HISTORY ──
// __BAKED_HISTORY_START__
const BAKED_HISTORY = __BAKED_HISTORY_PLACEHOLDER__;
// __BAKED_HISTORY_END__

// ── STATE ──
let chart       = null;
let activeRange = '1h';
let fullHistory = BAKED_HISTORY.length > 0 ? [...BAKED_HISTORY] : [];
let liveBuf     = [];
let lastAtr     = 0;
// 6-month view: null = not fetched yet, [] = fetched but empty/failed.
// Separate from fullHistory/BAKED_HISTORY on purpose — those come from the
// bot's rolling minute-level buffer, which only retains ~1-2 weeks in
// practice, nowhere near enough range. This is fetched fresh from
// /daily_history (real daily bars from Alpaca) the first time the 6 Month
// tab is opened, then cached for the rest of the session.
let sixMonthHistory = null;

// ── CHART INIT ──
function initChart() {
  const ctx = document.getElementById('priceChart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{ data: [],
      borderColor: '#00e5c0', backgroundColor: 'rgba(0,229,192,0.06)',
      borderWidth: 1.5, pointRadius: 1, pointHoverRadius: 4,
      fill: true, tension: 0.3, spanGaps: false }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 200 },
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: false },
        tooltip: { backgroundColor: '#1e2d42', titleColor: '#dde8f5',
          bodyColor: '#4a6080', borderColor: '#1e2d42', borderWidth: 1,
          padding: 10, callbacks: { label: c => ` $${c.parsed.y.toFixed(2)}` } } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.03)' },
          ticks: { color: '#4a6080', font: { family: 'Space Mono', size: 10 },
            maxRotation: 30, minRotation: 30, autoSkip: false, maxTicksLimit: 100,
            padding: 8 } },
        y: { grid: { color: 'rgba(255,255,255,0.03)' },
          ticks: { color: '#4a6080', font: { family: 'Space Mono', size: 9 },
            callback: v => `$${v.toFixed(0)}` } }
      }
    }
  });
}

// ── FILTER ──
// Merge live data from bot with BAKED_HISTORY, preserving all dates
// Live data takes precedence for same timestamps, baked fills in gaps
function mergeWithBaked(liveData) {
  const todayStr = todayET();
  const liveTodayCount = liveData ? liveData.filter(p => p.t && p.t.slice(0,10) === todayStr).length : 0;
  console.log('mergeWithBaked: live=' + (liveData ? liveData.length : 0) + ' today=' + liveTodayCount + ' baked=' + BAKED_HISTORY.length);
  if (!liveData || liveData.length === 0) return [...BAKED_HISTORY];
  if (!BAKED_HISTORY || BAKED_HISTORY.length === 0) return [...liveData].sort((a,b) => a.t.localeCompare(b.t));

  // Sort live data so [0] is the earliest point
  const sortedLive = [...liveData].sort((a,b) => a.t.localeCompare(b.t));
  const liveStart  = sortedLive[0].t;

  // Keep baked points that are either:
  //   - From a different day entirely (not covered by live data at all)
  //   - From today but BEFORE the live session started (pre-restart history)
  // This preserves full-day history across bot restarts.
  const liveDates   = new Set(sortedLive.map(p => p.t.slice(0,10)));
  const bakedToKeep = BAKED_HISTORY.filter(p => {
    const ptDate = p.t.slice(0,10);
    if (!liveDates.has(ptDate)) return true;   // different day — always keep
    return p.t < liveStart;                     // same day — keep only pre-restart points
  });

  const combined = [...bakedToKeep, ...sortedLive];
  combined.sort((a, b) => a.t.localeCompare(b.t));

  // Deduplicate by timestamp
  const seen = new Set();
  return combined.filter(p => {
    if (seen.has(p.t)) return false;
    seen.add(p.t);
    return true;
  });
}

// Merge fullHistory (from bot) with liveBuf, deduplicating
function mergeHistory() {
  if (liveBuf.length === 0) return fullHistory;
  if (fullHistory.length === 0) return liveBuf;
  const liveStart = liveBuf[0].t;
  const base = fullHistory.filter(p => p.t < liveStart);
  return [...base, ...liveBuf];
}

// Get today's date string in ET timezone (YYYY-MM-DD)
function todayET() {
  return new Date().toLocaleString('sv-SE', {timeZone:'America/New_York'}).slice(0,10);
}

// True once bot has responded with data
let botConnected = false;

// Convert stored ET timestamp "YYYY-MM-DDTHH:MM" to epoch ms
// Stored timestamps are ET (UTC-4 EDT). Add 4h to get UTC.
function etToMs(t) {
  const [date, time] = t.split('T');
  const [y, mo, d]   = date.split('-').map(Number);
  const [h, mn]      = time.split(':').map(Number);
  return Date.UTC(y, mo-1, d, h+4, mn);
}

// Fetches real daily bars from the bot (which pulls them fresh from Alpaca)
// for the 6-month chart view. Kicked off lazily the first time that tab is
// opened, then cached in sixMonthHistory for the rest of the session.
async function fetchSixMonthHistory() {
  try {
    const res  = await fetch('/daily_history', {signal: AbortSignal.timeout(20000)});
    const data = await res.json();
    sixMonthHistory = Array.isArray(data) ? data : [];
  } catch (e) {
    sixMonthHistory = [];
    console.log('6-month history fetch failed: ' + e);
  }
  if (activeRange === '6m') updateChart();
}

function filterByRange(range) {
  if (range === '6m') {
    if (sixMonthHistory === null) {
      fetchSixMonthHistory();  // async — updateChart() re-runs once it resolves
      return [];
    }
    return sixMonthHistory;
  }

  const merged = mergeHistory();
  if (!merged.length) return [];

  if (range === '1m') {
    // Last 30 trading days — weekends excluded
    const days  = new Set();
    const etNow = new Date(new Date().toLocaleString('en-US', {timeZone:'America/New_York'}));
    const cur   = new Date(etNow);
    while (days.size < 30) {
      if (cur.getDay() !== 0 && cur.getDay() !== 6) {
        const y  = cur.getFullYear();
        const mo = String(cur.getMonth()+1).padStart(2,'0');
        const d  = String(cur.getDate()).padStart(2,'0');
        days.add(`${y}-${mo}-${d}`);
      }
      cur.setDate(cur.getDate() - 1);
    }
    // For 1 month: condense to open/close per day only
    const inRange = merged.filter(p => days.has(p.t.slice(0,10)));
    return condenseOpenClose(inRange);
  }

  if (range === '1h') {
    // True rolling 60-minute window, scoped to today only — never bleeds into
    // a prior session. mergeHistory() already combines baked (JSON-seeded)
    // history with live scan points, so if the bot restarts midday the gap is
    // filled from baked history rather than showing a hole or falling back to
    // a stale prior day.
    const todayStr  = todayET();
    const allData   = mergeHistory();
    const todayOnly = allData.filter(p => p.t.slice(0,10) === todayStr);
    const sorted    = [...todayOnly].sort((a,b) => a.t.localeCompare(b.t));
    if (sorted.length === 0) return [];

    // Anchor the window to the latest point we actually have for today (not
    // wall-clock "now") so the chart still shows a full hour even if the bot
    // has been offline for a while — it shows the last hour of real data
    // rather than going blank because "now" has moved past all of it.
    const latestMs = etToMs(sorted[sorted.length - 1].t);
    const cutoffMs = latestMs - 60 * 60 * 1000;
    const windowed = sorted.filter(p => etToMs(p.t) >= cutoffMs);

    // Safety floor: if today's session just started and there's less than an
    // hour of data yet, show everything available rather than an empty/sparse
    // chart — same intent as before, just no longer cross-day.
    return windowed.length > 0 ? windowed : sorted;
  }

  if (range === '1d') {
    // Return all raw scan points for today, sorted by time
    const todayStr = todayET();
    const todayPts = merged.filter(p => p.t.slice(0,10) === todayStr)
                           .sort((a,b) => a.t.localeCompare(b.t));
    if (todayPts.length > 0) return todayPts;
    // Fallback: most recent date in history
    const dates = [...new Set(merged.map(p => p.t.slice(0,10)))].sort();
    return merged.filter(p => p.t.slice(0,10) === dates[dates.length-1])
                 .sort((a,b) => a.t.localeCompare(b.t));
  }

  if (range === '5d') {
    const days  = new Set();
    const etNow = new Date(new Date().toLocaleString('en-US', {timeZone:'America/New_York'}));
    const cur   = new Date(etNow);
    while (days.size < 5) {
      if (cur.getDay() !== 0 && cur.getDay() !== 6) {
        const y  = cur.getFullYear();
        const mo = String(cur.getMonth()+1).padStart(2,'0');
        const d  = String(cur.getDate()).padStart(2,'0');
        days.add(`${y}-${mo}-${d}`);
      }
      cur.setDate(cur.getDate() - 1);
    }
    return merged.filter(p => days.has(p.t.slice(0,10)));
  }

  return merged.slice(-60);
}

// Convert a stored ET timestamp "YYYY-MM-DDTHH:MM" to a CT time string "HH:MM CT"
// CT = ET - 1 hour (CDT in summer, CST in winter — browser handles DST automatically)
function etToCT(t) {
  const [datePart, timePart] = t.split('T');
  const [h, mn] = timePart.split(':').map(Number);
  // Parse as ET (UTC-4 EDT / UTC-5 EST) then display in CT
  const etDate = new Date(`${datePart}T${String(h).padStart(2,'0')}:${String(mn).padStart(2,'0')}:00-04:00`);
  return etDate.toLocaleTimeString('en-US', {
    timeZone: 'America/Chicago', hour: '2-digit', minute: '2-digit', hour12: false
  }) + ' CT';
}

const MONTH_ABBR = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function fmtLabel(t, range) {
  const [datePart, timePart] = t.split('T');
  const [y, mo, d] = datePart.split('-');

  if (range === '6m') return MONTH_ABBR[parseInt(mo, 10) - 1];
  if (range === '5d' || range === '1m') return `${mo}/${d}`;

  return etToCT(t);
}

// Determine which points should show an x-axis label based on range
function shouldShowLabel(p, i, pts, range) {
  if (range === '6m') {
    // /daily_history points are plain "YYYY-MM-DD" (no time component) —
    // label the first point of each new calendar month.
    if (i === 0) return true;
    return pts[i-1].t.slice(0,7) !== p.t.slice(0,7);
  }

  const [datePart, timePart] = p.t.split('T');
  const [h, mn] = timePart.split(':').map(Number);
  const minOfDay = h * 60 + mn;

  if (range === '1h') {
    if (pts.length <= 12) return true;
    const etDate  = new Date(datePart + 'T' + String(h).padStart(2,'0') + ':' + String(mn).padStart(2,'0') + ':00-04:00');
    return etDate.getMinutes() % 10 === 0;
  }
  if (range === '1d') {
    // For today: shouldShowLabel not used — we build fixed hourly grid instead
    return true;
  }
  if (range === '5d') {
    // Label the first data point of each trading day
    if (i === 0) return true;
    return pts[i-1].t.slice(0,10) !== p.t.slice(0,10);
  }
  if (range === '1m') {
    // Label the first data point of each trading day
    if (i === 0) return true;
    return pts[i-1].t.slice(0,10) !== p.t.slice(0,10);
  }
  return false;
}

// ── RENDER CHART ──
function updateChart() {
  if (!chart) return;
  const pts = filterByRange(activeRange);
  const ptsLen = Array.isArray(pts) ? pts.length : (pts.points ? pts.points.length : 0);
  console.log('updateChart: range=' + activeRange + ' pts=' + ptsLen + ' fullHistory=' + fullHistory.length);
  if (ptsLen === 0 && !pts._prebuilt) {
    document.getElementById('range-hint').textContent =
      activeRange === '6m' && sixMonthHistory === null
        ? 'Loading 6-month history...'
        : 'No data for this period — try 1 Month';
    chart.data.labels = [];
    chart.data.datasets[0].data = [];
    chart.update('none');
    return;
  }

  let displayPts, labels;
  if (activeRange === '1h') {
    // Last 60 scan points — label every 10th point with the ET time from the data
    displayPts = pts;
    labels = displayPts.map((p, i) => {
      if (i === 0 || i % 10 === 0 || i === displayPts.length - 1) {
        const timePart = p.t.includes('T') ? p.t.slice(11) : p.t;
        return timePart + ' ET';
      }
      return '';
    });
  } else if (activeRange === '5d') {
    displayPts = condenseKillZones(pts);
    labels = displayPts.map((p,i) =>
      shouldShowLabel(p, i, displayPts, activeRange) ? fmtLabel(p.t, activeRange) : '');
  } else if (activeRange === '1d') {
    // All points for today. Label every 30 min using ET timestamp from data directly.
    displayPts = pts;
    let lastLabelMin = -999;
    labels = displayPts.map((p, i) => {
      const timePart = p.t.includes('T') ? p.t.slice(11) : p.t;
      const [h, m]   = timePart.split(':').map(Number);
      const minOfDay = h * 60 + m;
      const isFirst  = i === 0;
      const isLast   = i === displayPts.length - 1;
      const slot30   = Math.floor(minOfDay / 30) * 30;
      if (isFirst || isLast || (slot30 !== Math.floor(lastLabelMin / 30) * 30 && minOfDay - lastLabelMin >= 20)) {
        lastLabelMin = minOfDay;
        return timePart + ' ET';
      }
      return '';
    });
  } else {
    displayPts = pts;
    labels = displayPts.map((p,i) =>
      shouldShowLabel(p, i, displayPts, activeRange) ? fmtLabel(p.t, activeRange) : '');
  }

  chart.data.labels = labels;
  chart.data.datasets[0].data = displayPts.map(p => p.p);
  chart.update('none');
  const lo = Math.min(...displayPts.map(p=>p.p));
  const hi = Math.max(...displayPts.map(p=>p.p));
  document.getElementById('range-hint').textContent =
    displayPts.length + ' points · $' + lo.toFixed(2) + ' – $' + hi.toFixed(2);
}

// For 1 Hour tab: fixed 60-min rolling window, last known price held flat
function build1HourGrid(allPts) {
  const now    = new Date();
  const points = [];
  const labels = [];

  // Build 12 x 5-min slots for the last 60 minutes
  for (let i = 11; i >= 0; i--) {
    const slotTime = new Date(now.getTime() - i * 5 * 60000);

    // Display time in CT to match user's timezone
    const etStr  = slotTime.toLocaleTimeString('en-US', {
      timeZone: 'America/Chicago', hour: '2-digit', minute: '2-digit', hour12: false
    });

    // Find last known price at or before this slot (compare epoch ms)
    const slotMs = slotTime.getTime();
    const before = allPts.filter(p => etToMs(p.t) <= slotMs);
    const lastP  = before.length > 0 ? before[before.length-1].p : null;

    points.push({ t: etStr, p: lastP });
    labels.push(etStr);   // label every point
  }

  return { _prebuilt: true, points, labels };
}

// For 1 Month tab: reduce to 2 points per day (first + last = open/close)
function condenseOpenClose(pts) {
  const byDate = {};
  pts.forEach(p => {
    const d = p.t.slice(0,10);
    if (!byDate[d]) byDate[d] = [];
    byDate[d].push(p);
  });
  const result = [];
  Object.keys(byDate).sort().forEach(date => {
    const day = byDate[date].sort((a,b) => a.t.localeCompare(b.t));
    result.push(day[0]);  // open
    if (day.length > 1) result.push(day[day.length-1]);  // close
  });
  return result;
}

// For Today tab: build fixed hourly grid using ET hour labels
// Each hour slot shows the last known price at or before that time
// v4.12: removed CDT hardcoding (cdtH+1) — now reads ET hour directly from stored timestamps
function buildHourlyGrid(pts) {
  const now    = new Date();
  const etNow  = new Date(now.toLocaleString('en-US', {timeZone: 'America/New_York'}));
  const maxETH = Math.min(etNow.getHours() + (etNow.getMinutes() >= 30 ? 1 : 0), 16);

  const hourSlots = [];
  for (let h = 9; h <= maxETH; h++) hourSlots.push(h);

  const points = [];
  const labels = [];
  const sorted = [...pts].sort((a,b) => a.t.localeCompare(b.t));

  hourSlots.forEach(etH => {
    // Stored timestamps are "YYYY-MM-DDTHH:MM" in ET — read hour directly
    const hourPts = sorted.filter(p => parseInt(p.t.slice(11, 13), 10) === etH);
    const lastP   = hourPts.length > 0 ? hourPts[hourPts.length-1].p : null;

    // Label in ET (matches stored data format)
    const label = String(etH).padStart(2,'0') + ':00 ET';
    points.push({ t: label, p: lastP });
    labels.push(label);
  });

  return { points, labels };
}

// For 5 Days tab: condense each day into 3 kill zone averages
// Stored timestamps may be in local time (CDT = ET+1hr) so we
// convert by checking the kz field stored with each point, or
// fall back to dividing the day into thirds
function condenseKillZones(pts) {
  const byDate = {};
  pts.forEach(p => {
    const date = p.t.slice(0,10);
    if (!byDate[date]) byDate[date] = [];
    byDate[date].push(p);
  });

  const result = [];
  Object.keys(byDate).sort().forEach(date => {
    const dayPts = byDate[date];

    // Try using stored kz field first (new points have this)
    const withKz = dayPts.filter(p => p.kz);
    if (withKz.length > 0) {
      const kzGroups = {};
      withKz.forEach(p => {
        if (!kzGroups[p.kz]) kzGroups[p.kz] = [];
        kzGroups[p.kz].push(p);
      });
      // Also group points with no kz tag as their own bucket
      const noKz = dayPts.filter(p => !p.kz);
      if (noKz.length > 0) kzGroups['session'] = noKz;

      Object.keys(kzGroups).sort().forEach((kz, ki) => {
        const kzPts = kzGroups[kz];
        const avgP  = kzPts.reduce((s,p) => s+p.p, 0) / kzPts.length;
        // v4.12: safe time mapping — only 3 named kill zones; 'session' group gets 10:00
        const kzTimes = {'09:30':'09:30','12:00':'12:00','14:00':'14:00','session':'10:00'};
        const kzTime  = kzTimes[kz] || '10:00';
        result.push({ t: `${date}T${kzTime}`, p: Math.round(avgP*100)/100, kz });
      });
    } else {
      // Fall back: split day into thirds as AM/NOON/PM
      const third = Math.ceil(dayPts.length / 3);
      const slots = [
        { pts: dayPts.slice(0, third),          t: `${date}T09:30`, kz: 'AM' },
        { pts: dayPts.slice(third, third*2),     t: `${date}T12:00`, kz: 'NOON' },
        { pts: dayPts.slice(third*2),            t: `${date}T14:00`, kz: 'PM' },
      ];
      slots.forEach(slot => {
        if (slot.pts.length > 0) {
          const avgP = slot.pts.reduce((s,p) => s+p.p, 0) / slot.pts.length;
          result.push({ t: slot.t, p: Math.round(avgP*100)/100, kz: slot.kz });
        }
      });
    }
  });
  return result;
}

// ── TABS ──
document.querySelectorAll('.range-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.range-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeRange = btn.dataset.range;
    updateChart();
  });
});

// ── FETCH ──
async function fetchData() {
  try {
    const res  = await fetch('/data', {signal: AbortSignal.timeout(4000)});
    const data = await res.json();
    document.getElementById('conn-banner').style.display = 'none';
    document.getElementById('live-dot').className = 'dot live';
    document.getElementById('live-label').textContent = 'LIVE';
    botConnected = true;
    try {
      updateUI(data);
    } catch(uiErr) {
      console.error('updateUI crashed:', uiErr.message, uiErr.stack);
    }
  } catch(e) {
    console.error('fetchData failed:', e.message);
    document.getElementById('live-dot').className = 'dot error';
    document.getElementById('live-label').textContent = 'Offline';
    if (fullHistory.length > 0) {
      document.getElementById('status-text').textContent =
        'Bot offline — showing saved history (' + fullHistory.length + ' points)';
      document.getElementById('conn-banner').style.display = 'none';
    } else {
      document.getElementById('conn-banner').style.display = 'block';
    }
    updateChart();
  }
}

// ── UPDATE UI ──
function updateUI(d) {
  document.getElementById('status-text').textContent = d.status || '—';
  document.getElementById('status-meta').textContent =
    (d.timestamp||'') + ' · ' + (d.last_candles||0) + ' candles · ' + (d.fetch_errors||0) + ' errors';

  // v4.78: the manual-trade modal's entry price used to be kept "live" from
  // here — d.last_price, which is state["last_price"] from a 5-minute candle
  // close in the bot's background refresh loop. That can lag the true price
  // by minutes (confirmed live: modal showed $227.70, the order validation's
  // fresh api.get_latest_trade() tick was $226.32 moments later — a real gap,
  // not a stale display glitch). The modal now runs its own poller against
  // /live_price (see startLivePricePolling()), the same source
  // /manual_trade validates against, so this block only keeps ATR synced —
  // it no longer touches m-entry/m-price-hint at all, to avoid two different
  // price sources fighting over the same field.
  if (lastAtr !== d.last_atr) { lastAtr = d.last_atr || 0; }

  const kzT = [['09:30','11:00'],['12:00','13:00'],['14:00','15:55']];
  const et  = new Date().toLocaleTimeString('en-US',{timeZone:'America/New_York',hour12:false});
  const [h,m] = et.split(':').map(Number); const etM = h*60+m;
  kzT.forEach(([s,e],i) => {
    const [sh,sm]=s.split(':').map(Number),[eh,em]=e.split(':').map(Number);
    const el = document.getElementById('kz-'+i);
    const inKz = etM>=sh*60+sm && etM<eh*60+em, past = etM>=eh*60+em;
    el.className = 'kz-slot'+(inKz?' active':past?' passed':'');
    el.textContent = (inKz?'▶ ':'')+s+'–'+e+' ET';
  });

  // The bot sends state["price_history"] which already contains the full merged
  // history (JSON seed + live points). Just use it directly, supplementing only
  // with baked dates that the bot's history doesn't cover at all.
  if (d.price_history && d.price_history.length > 0) {
    try {
      const live = d.price_history;
      const liveDates  = new Set(live.map(p => p.t.slice(0,10)));
      const liveFirst  = live.reduce((min, p) => p.t < min ? p.t : min, live[0].t);
      // Keep baked points that are either:
      // (a) from a date not covered by live data at all, OR
      // (b) from the same day but BEFORE the first live point (pre-restart history)
      const bakedExtra = BAKED_HISTORY.filter(p => {
        if (!liveDates.has(p.t.slice(0,10))) return true;  // different day
        return p.t < liveFirst;  // same day, pre-restart
      });
      const combined = [...bakedExtra, ...live].sort((a,b) => a.t.localeCompare(b.t));
      const seen = new Set();
      fullHistory = combined.filter(p => {
        if (seen.has(p.t)) return false;
        seen.add(p.t);
        return true;
      });
      updateChart();
    } catch(e) {
      console.error('history merge failed:', e);
    }
  }

  const price = d.last_price || 0;
  if (price > 0) {
    document.getElementById('val-price').textContent = '$'+price.toFixed(2);
    document.getElementById('sub-price').textContent = 'Scanned: '+(d.last_scan_time||'—');
    // Use ET timestamp to match baked history format
    const etStr = new Date().toLocaleString('sv-SE', {timeZone:'America/New_York'}).slice(0,16).replace(' ','T');
    const todayStr = etStr.slice(0,10);
    // Day-rollover guard: liveBuf is capped by COUNT not by date, so if the
    // dashboard stays open across a session boundary it can silently mix
    // yesterday's last points with today's first points. Drop anything not
    // from today before appending.
    if (liveBuf.length > 0 && liveBuf[0].t.slice(0,10) !== todayStr) {
      liveBuf = liveBuf.filter(p => p.t.slice(0,10) === todayStr);
    }
    const lastPt = liveBuf[liveBuf.length-1];
    if (!lastPt || lastPt.t !== etStr) {
      liveBuf.push({t: etStr, p: price});
    } else {
      liveBuf[liveBuf.length-1].p = price; // update same-minute point
    }
    if (liveBuf.length > 120) liveBuf.shift();
    updateChart();
  }

  lastAtr = d.last_atr || 0;
  if (d.trail_activated) document.getElementById('card-pnl').className = 'stat-card yellow';

  const tr = d.last_trend||'neutral';
  document.getElementById('val-trend').textContent = tr.toUpperCase();
  document.getElementById('val-trend').className = 'stat-value '+(tr==='bullish'?'up':tr==='bearish'?'down':'flat');
  document.getElementById('card-trend').className = 'stat-card '+(tr==='bullish'?'':tr==='bearish'?'red':'yellow');

  const qq = d.last_qqq||'neutral';
  document.getElementById('val-qqq').textContent = qq.toUpperCase();
  document.getElementById('val-qqq').className = 'stat-value '+(qq==='bullish'?'up':qq==='bearish'?'down':'flat');

  document.getElementById('val-fvgs').textContent = d.fvgs_today||0;
  document.getElementById('sub-fvgs').textContent = 'Best score: '+(d.best_score||0)+'/9';

  const eq  = d.equity||0;
  const bod = d.bod_equity||0;
  const equityDayPnl = (eq > 0 && bod > 0) ? eq - bod : (d.daily_pnl||0);
  const equityPnlSign = equityDayPnl >= 0 ? '+' : '';
  document.getElementById('val-equity').textContent = eq>0 ? '$'+eq.toLocaleString('en-US',{maximumFractionDigits:0}) : '—';
  const subEqEl = document.getElementById('sub-equity');
  if (subEqEl) {
    subEqEl.textContent = eq>0 && bod>0
      ? 'Day P&L: ' + equityPnlSign + '$' + equityDayPnl.toFixed(2)
      : '—';
    subEqEl.className = 'stat-sub ' + (equityDayPnl >= 0 ? 'up' : 'down');
  }

  // Strategy card
  const strat = d.active_strategy || '—';
  const stratEl = document.getElementById('val-strategy');
  stratEl.textContent = strat;
  stratEl.className = 'stat-value ' + (strat === 'FVG' ? 'up' : strat === 'VWAP' ? 'flat' : 'flat');
  document.getElementById('sub-strategy').textContent =
    d.last_vwap > 0 ? 'VWAP $' + d.last_vwap.toFixed(2) : (d.strategy_reason || '—');

  // MTF bias card
  const mtf = (d.mtf_bias || '—').replace('_', ' ').toUpperCase();
  const mtfEl = document.getElementById('val-mtf');
  mtfEl.textContent = mtf;
  mtfEl.className = 'stat-value ' + (mtf.includes('BULL') ? 'up' : mtf.includes('BEAR') ? 'down' : 'flat');
  document.getElementById('card-mtf').className = 'stat-card ' +
    (mtf.includes('STRONG BULL') ? '' : mtf.includes('BULL') ? '' :
     mtf.includes('STRONG BEAR') ? 'red' : mtf.includes('BEAR') ? 'red' : 'yellow');
  document.getElementById('sub-mtf').textContent =
    (d.weekly_trend ? ('W: ' + d.weekly_trend) : '') +
    (d.monthly_trend ? (' · M: ' + d.monthly_trend) : '');

  // ── Multi-trade panel ────────────────────────────────────────
  const activeTrades = d.active_trades || (d.active_trade ? [d.active_trade] : []);
  const closedTrade  = d.closed_trade;

  // P&L stat card — sum of all open unrealized + day P&L
  const pnlEl = document.getElementById('val-pnl');
  const dayPnl = parseFloat(d.daily_pnl) || 0;
  const unrealSum = activeTrades.reduce((s,t) => s + (parseFloat(t.pnl)||0), 0);
  const displayPnl = activeTrades.length > 0 ? unrealSum : dayPnl;
  if (displayPnl !== 0 || activeTrades.length > 0 || d.traded_today) {
    pnlEl.textContent = (displayPnl>=0?'+':'')+'$'+displayPnl.toFixed(2);
    pnlEl.className = 'stat-value '+(displayPnl>=0?'up':'down');
    document.getElementById('sub-pnl').textContent =
      activeTrades.length > 0 ? `${activeTrades.length} trade${activeTrades.length>1?'s':''} open` :
      (closedTrade ? 'Realized ('+closedTrade.outcome+')' : 'Day P&L');
  } else {
    pnlEl.textContent='—'; pnlEl.className='stat-value flat';
    document.getElementById('sub-pnl').textContent = 'No trade yet';
  }

  // Trade cards — one per active trade, stacked vertically
  const tradeEl = document.getElementById('trade-content');
  function renderTradeCard(trade, idx) {
    const dir = trade.fvg_type||'';
    const col = dir==='bullish'?'var(--win)':'var(--loss)';
    const pnl = parseFloat(trade.pnl)||0;
    const isManual = trade.strategy==='MANUAL';
    const isOpen   = trade.outcome==='OPEN' || trade.outcome==null;
    const stratLabel = isManual ? '📋 MANUAL' : `🤖 ${trade.strategy||'BOT'}`;
    // v4.94: SWING-6M can now carry for multiple days (see swing_max_hold_days) —
    // flag it explicitly instead of leaving a stale-looking timestamp unexplained.
    const daysOpen = trade.days_open || 0;
    const daysBadge = daysOpen > 0 ? ` <span style="color:var(--yellow)">(${daysOpen}d open)</span>` : '';
    return `<div class="trade-card" id="trade-card-${idx}" style="border:1px solid var(--border);border-radius:6px;padding:12px;margin-bottom:10px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span style="font-size:.65rem;color:var(--muted);font-family:'Space Mono',monospace">${stratLabel}</span>
        <span style="font-size:.65rem;color:var(--muted);font-family:'Space Mono',monospace">${trade.opened_at||''}${daysBadge}</span>
      </div>
      <div class="trade-row"><span class="trade-key">Direction</span><span class="trade-val" style="color:${col}">${dir==='bullish'?'▲ LONG':'▼ SHORT'}</span></div>
      <div class="trade-row"><span class="trade-key">Entry</span><span class="trade-val">$${(trade.entry||0).toFixed(2)}</span></div>
      <div class="trade-row"><span class="trade-key">Stop</span><span class="trade-val" style="color:${
        trade.trail_active ? 'var(--win)' :
        (trade.stop||0).toFixed(2) === (trade.entry||0).toFixed(2) ? 'var(--yellow)' :
        'var(--loss)'
      }">${
        trade.trail_active ? '▲ TRAIL $' + (trade.stop||0).toFixed(2) :
        (trade.stop||0).toFixed(2) === (trade.entry||0).toFixed(2) ? 'BE $' + (trade.stop||0).toFixed(2) :
        '$' + (trade.stop||0).toFixed(2)
      }</span></div>
      <div class="trade-row"><span class="trade-key">Target</span><span class="trade-val" style="color:var(--win)">$${(trade.target||0).toFixed(2)}</span></div>
      <div class="trade-row"><span class="trade-key">Qty</span><span class="trade-val">${trade.qty||'—'}</span></div>
      <div class="trade-row"><span class="trade-key">Status</span><span class="trade-val" style="color:${isOpen?'var(--yellow)':trade.outcome==='WIN'?'var(--win)':'var(--loss)'}">${trade.outcome||'OPEN'}</span></div>
      <div class="trade-row"><span class="trade-key">P&L</span><span class="trade-val" style="color:${pnl>=0?'var(--win)':'var(--loss)'}">${(pnl>=0?'+':'')+'$'+pnl.toFixed(2)}</span></div>
      ${isManual && isOpen ? `<button class="close-trade-btn" style="width:100%;margin-top:8px;padding:6px;font-size:.7rem;" onclick="openCloseModalFor('${trade.id||''}')">✕ Close This Trade</button>` : ''}
    </div>`;
  }

  if (activeTrades.length > 0) {
    document.querySelector('.trade-panel').querySelector('.card-title').textContent =
      `Active Trades (${activeTrades.length})`;
    tradeEl.innerHTML = activeTrades.map((t,i) => renderTradeCard(t,i)).join('');
  } else if (closedTrade) {
    document.querySelector('.trade-panel').querySelector('.card-title').textContent = 'Last Trade';
    tradeEl.innerHTML = renderTradeCard(closedTrade, 0);
  } else {
    document.querySelector('.trade-panel').querySelector('.card-title').textContent = 'Active Trade';
    tradeEl.innerHTML='<div class="trade-empty"><div class="icon">⏳</div><div>'+(d.traded_today?'Trade complete':'No active trade')+'</div></div>';
  }

  const fvgEl = document.getElementById('fvg-items');
  if (d.all_fvgs && d.all_fvgs.length > 0) {
    fvgEl.innerHTML = d.all_fvgs.map(f => `
      <div class="fvg-item ${f.type}">
        <span class="fvg-badge ${f.type}">${f.type==='bullish'?'▲ LONG':'▼ SHORT'}</span>
        <div class="fvg-details"><strong>${f.time}</strong> · $${f.size} gap · entry $${f.entry_zone}
        <div style="font-size:.68rem;color:var(--muted);margin-top:2px">${f.notes}</div></div>
        <div class="fvg-score"><div class="score-pips">${Array.from({length:9},(_,i)=>`<div class="pip ${i<f.score?'on':'off'}"></div>`).join('')}</div>
        <div style="font-family:'Space Mono',monospace;font-size:.62rem;color:var(--muted);text-align:right;margin-top:3px">${f.score}/9</div></div>
      </div>`).join('');
  } else {
    fvgEl.innerHTML='<div class="fvg-empty">No FVGs detected yet today</div>';
  }

  const logEl = document.getElementById('log-inner');
  if (d.log && d.log.length > 0) {
    logEl.innerHTML = d.log.map(ev=>`
      <div class="log-entry">
        <span class="log-time">${ev.time.split(' ')[0]}</span>
        <span class="log-level ${ev.level}">${ev.level}</span>
        <span class="log-msg">${ev.message}</span>
      </div>`).join('');
  }
}

// ── MANUAL TRADE ──
let modalDir=null, modalManaged=true, modalTrail=false;
let livePricePollId=null;
// v4.78: fetches from /live_price (a fresh api.get_latest_trade() tick —
// the exact same source /manual_trade validates against), NOT /data's
// last_price (a 5-min candle close that can lag the true price by minutes —
// confirmed live: modal showed $227.70 from last_price while the real
// current price used for validation was $226.32). Showing the user the
// same number the order will actually be checked against is the whole
// point — anything else can look "live" and still be wrong.
async function fetchLivePriceForModal(){
  try {
    const res  = await fetch('/live_price', {signal: AbortSignal.timeout(2000)});
    const data = await res.json();
    if (data.price > 0) {
      document.getElementById('m-entry').value = data.price.toFixed(2);
      document.getElementById('m-price-hint').textContent = 'Live price (last trade tick) — updated just now';
      if (document.getElementById('m-atr').checked) updateAtrPreview();
      updateBracketHint();
    } else {
      document.getElementById('m-price-hint').textContent = 'Could not fetch a live tick: ' + (data.error || 'unknown error');
    }
  } catch(e) {
    document.getElementById('m-price-hint').textContent = 'Could not fetch live price — bot unreachable';
  }
}
function startLivePricePolling(){
  stopLivePricePolling();
  fetchLivePriceForModal();
  livePricePollId = setInterval(fetchLivePriceForModal, 4000);
}
function stopLivePricePolling(){
  if (livePricePollId) { clearInterval(livePricePollId); livePricePollId=null; }
}
async function openModal(){
  try {
    const res  = await fetch('/data', {signal: AbortSignal.timeout(2000)});
    const data = await res.json();
    if (data.last_atr) lastAtr = data.last_atr;
  } catch(e) { /* non-fatal — ATR preview just won't be available yet */ }
  document.getElementById('m-trail').checked = false;
  modalTrail = false;
  document.getElementById('trail-hint').textContent = '';
  document.getElementById('trail-row').style.display = 'flex';
  updateAtrHint();
  document.getElementById('modal-backdrop').classList.remove('hidden');
  startLivePricePolling();
}
function closeModal(){ document.getElementById('modal-backdrop').classList.add('hidden'); clearFb(); stopLivePricePolling(); }
function closeModalOutside(e){ if(e.target===document.getElementById('modal-backdrop')) closeModal(); }
function setDir(d){ modalDir=d; document.getElementById('btn-long').className='dir-btn '+(d==='bullish'?'selected-long':''); document.getElementById('btn-short').className='dir-btn '+(d==='bearish'?'selected-short':''); updateBracketHint(); }
// Live guidance for the manual Stop/Target fields — this exists because a
// real user hit the server's bracket-check rejection (stop/target on the
// wrong side of the live price for a SHORT) after typing values manually,
// and asked why, since the displayed live price looked current. The price
// WAS current — the values they typed just weren't on the right side of it
// for the direction they picked (for a SHORT, target must be BELOW price
// and stop must be ABOVE; it's the reverse of a LONG). Nothing in the form
// said that. This shows the actual requirement live, and colors the fields
// once both are filled in, instead of only finding out after submitting.
function updateBracketHint(){
  const hintEl = document.getElementById('m-bracket-hint');
  if(!hintEl) return;
  const entry = parseFloat(document.getElementById('m-entry').value) || 0;
  if(!modalDir || entry <= 0){ hintEl.textContent=''; return; }
  const below = modalDir === 'bullish' ? 'Stop' : 'Target';
  const above = modalDir === 'bullish' ? 'Target' : 'Stop';
  hintEl.textContent = 'For a ' + (modalDir==='bullish'?'LONG':'SHORT') + ': ' + below +
    ' must be below $' + entry.toFixed(2) + ' · ' + above + ' must be above $' + entry.toFixed(2);
  const stop   = parseFloat(document.getElementById('m-stop').value);
  const target = parseFloat(document.getElementById('m-target').value);
  let ok = true;
  if(stop && target){
    ok = modalDir === 'bullish' ? (stop < entry && entry < target) : (target < entry && entry < stop);
  }
  hintEl.style.color = ok ? 'var(--muted)' : 'var(--red)';
}
let atrMult = 1.0;
function setAtrMult(m){
  atrMult = m;
  document.querySelectorAll('.atr-mult-btn').forEach(b => {
    b.classList.toggle('active', parseFloat(b.textContent) === m);
  });
  updateAtrPreview();
}
function updateAtrPreview(){
  const preview = document.getElementById('atr-preview');
  if(!preview) return;
  if(lastAtr <= 0){ preview.textContent = ''; return; }
  const entry    = parseFloat(document.getElementById('m-entry').value) || 0;
  const stopDist = atrMult * lastAtr;
  const tgtDist  = stopDist * 1.5;
  if(entry > 0 && modalDir){
    const stop   = modalDir === 'bullish' ? (entry - stopDist).toFixed(2) : (entry + stopDist).toFixed(2);
    const target = modalDir === 'bullish' ? (entry + tgtDist).toFixed(2)  : (entry - tgtDist).toFixed(2);
    preview.textContent = 'ATR $' + lastAtr.toFixed(3) + ' | Stop: $' + stop + ' | Target: $' + target + '  (risk $' + stopDist.toFixed(2) + ', reward $' + tgtDist.toFixed(2) + ')';
  } else {
    preview.textContent = 'ATR $' + lastAtr.toFixed(3) + ' stop dist $' + stopDist.toFixed(2) + ', target dist $' + tgtDist.toFixed(2);
  }
}
function toggleAtr(){
  const checked = document.getElementById('m-atr').checked;
  document.getElementById('manual-stop-target').style.display = checked ? 'none' : 'block';
  document.getElementById('atr-mult-row').style.display = checked ? 'block' : 'none';
  updateAtrHint();
  if(checked) updateAtrPreview();
}
function updateAtrHint(){ document.getElementById('atr-hint').textContent = lastAtr > 0 ? ' (ATR: $' + lastAtr.toFixed(3) + ')' : ''; }
function toggleTrail(){
  modalTrail = document.getElementById('m-trail').checked;
  const hint = document.getElementById('trail-hint');
  hint.textContent = modalTrail ? 'Stop moves to breakeven at 1:1R, then trails at 2:1R' : '';
}
function setManaged(v){
  modalManaged=v;
  document.getElementById('btn-managed').className='managed-btn'+(v?' selected-managed':'');
  document.getElementById('btn-logonly').className='managed-btn'+(v?'':' selected-managed');
  // Only show trail option when managed is on
  document.getElementById('trail-row').style.display = v ? 'flex' : 'none';
  if (!v) { document.getElementById('m-trail').checked = false; modalTrail = false; }
}
async function submitManualTrade(){
  const btn=document.getElementById('submit-btn'); clearFb();
  if(!modalDir) return showErr('Select a direction');
  const entry=parseFloat(document.getElementById('m-entry').value), qty=parseInt(document.getElementById('m-qty').value);
  if(!entry||entry<=0) return showErr('No live price yet — close and reopen the trade modal');
  if(!qty||qty<=0) return showErr('Enter a valid quantity');
  const useAtr=document.getElementById('m-atr').checked; let stop=0,target=0;
  if(!useAtr){
    stop=parseFloat(document.getElementById('m-stop').value); target=parseFloat(document.getElementById('m-target').value);
    if(!stop) return showErr('Enter stop'); if(!target) return showErr('Enter target');
    // Mirrors the server's own bracket check (nvda_autotrader.py /manual_trade
    // handler) so this is caught instantly instead of round-tripping to find
    // out — same rule, same message. The live price shown here can still
    // move by the time the server re-checks against its own fresh quote, so
    // the server check stays authoritative; this is just an earlier catch
    // for the common case (values typed on the wrong side of price for the
    // chosen direction), not a replacement for it.
    const bracketOk = modalDir==='bullish' ? (stop<entry && entry<target) : (target<entry && entry<stop);
    if(!bracketOk){
      const need = modalDir==='bullish' ? 'stop < price < target' : 'target < price < stop';
      return showErr('Live price is $'+entry.toFixed(2)+' — your stop ($'+stop.toFixed(2)+') and target ($'+target.toFixed(2)+
        ') do not bracket it correctly for a '+(modalDir==='bullish'?'LONG':'SHORT')+' (need '+need+').');
    }
  }
  btn.disabled=true; btn.textContent='Entering...';
  try{
    const res=await fetch('/manual_trade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({direction:modalDir,entry,stop,target,qty,managed:modalManaged,use_atr:useAtr,atr_mult:atrMult,use_trail:modalTrail})});
    const data=await res.json();
    if(data.ok){ document.getElementById('modal-success').style.display='block'; document.getElementById('modal-success').textContent='✓ '+data.message; setTimeout(closeModal,1800); }
    else showErr(data.error||'Failed');
  }catch(e){ showErr('Bot disconnected'); }
  btn.disabled=false; btn.textContent='Enter Trade';
}
function showErr(msg){ const el=document.getElementById('modal-error'); el.textContent='⚠ '+msg; el.style.display='block'; }
function clearFb(){ ['modal-error','modal-success','close-error'].forEach(id=>{ const el=document.getElementById(id); if(el) el.style.display='none'; }); }
let closeTradeOrderId = '';
function openCloseModalFor(orderId){ closeTradeOrderId=orderId||''; clearFb(); document.getElementById('c-pnl').value=''; document.getElementById('close-modal-backdrop').classList.remove('hidden'); }
function openCloseModal(){ openCloseModalFor(''); }
function closeCloseModal(e){ if(!e||e.target===document.getElementById('close-modal-backdrop')) document.getElementById('close-modal-backdrop').classList.add('hidden'); }
async function submitClose(){
  const pnl=parseFloat(document.getElementById('c-pnl').value)||0;
  try{ const res=await fetch('/close_manual_trade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pnl, order_id: closeTradeOrderId})}); const data=await res.json(); if(data.ok) closeCloseModal(); else{ document.getElementById('close-error').style.display='block'; document.getElementById('close-error').textContent='⚠ '+data.error; } }catch(e){ document.getElementById('close-error').style.display='block'; document.getElementById('close-error').textContent='⚠ Bot disconnected'; }
}

// ── CHART SIZE WATCHDOG ──
// v4.76 fix: Chart.js can measure its container before the CSS grid
// (.main-grid{grid-template-columns:1fr 340px}) finishes its layout pass on
// first load, locking the canvas to a stale/tiny size — reproduced live:
// canvas stuck at 300x260 instead of the chart-wrap container's real
// ~575px+ width, making the price chart render tiny in a mostly-empty card.
// Confirmed in testing that neither a window 'resize' event, nor
// chart.resize(), nor even chart.resize(width, height) with explicit
// correct numbers corrects an already-stuck instance — Chart.js keeps
// redrawing at its originally-measured size regardless. Only destroying and
// recreating the chart instance reliably fixes it. Runs once, shortly after
// load, and only when the canvas doesn't actually match its container —
// harmless no-op in the common case where sizing was already correct.
function fixChartSizeIfStuck() {
  const wrap = document.querySelector('.chart-wrap');
  const cv   = document.getElementById('priceChart');
  if (!chart || !wrap || !cv) return;
  const wrapWidth = wrap.getBoundingClientRect().width;
  const cvWidth   = parseInt(cv.getAttribute('width') || '0', 10);
  if (wrapWidth > 0 && Math.abs(wrapWidth - cvWidth) > 20) {
    console.log('Chart size mismatch (wrap=' + wrapWidth + ' canvas=' + cvWidth + ') — recreating chart');
    chart.destroy();
    initChart();
    updateChart();
  }
}

// Re-check on browser window resize too — there was no resize handling at
// all before, so dragging the window to a new size (or moving it to a
// different monitor) never re-fit the chart. Debounced to avoid rebuilding
// the chart on every pixel during a drag-resize.
let _resizeDebounce = null;
window.addEventListener('resize', () => {
  clearTimeout(_resizeDebounce);
  _resizeDebounce = setTimeout(fixChartSizeIfStuck, 250);
});

// ── START ──
window.addEventListener('load', () => {
  initChart();
  updateChart();  // initial render with baked data
  setTimeout(fixChartSizeIfStuck, 500);

  // Fetch full history from bot on startup — gets today's scans immediately
  fetch('/history', {signal: AbortSignal.timeout(4000)})
    .then(r => r.json())
    .then(hist => {
      console.log('History fetch: got ' + (hist ? hist.length : 0) + ' points');
      if (hist && hist.length > 0) {
        // Find today's points specifically
        const todayStr = todayET();
        const todayPts = hist.filter(p => p.t && p.t.slice(0,10) === todayStr);
        console.log('Today points in history: ' + todayPts.length + ' (today=' + todayStr + ')');
        if (todayPts.length > 0) console.log('First today pt: ' + JSON.stringify(todayPts[0]));
        fullHistory = mergeWithBaked(hist);
        botConnected = true;
        updateChart();
      }
    })
    .catch(e => {
      console.log('History fetch failed: ' + e.message);
    });

  fetchData();
  setInterval(fetchData, 5000);
});
"""


# ═══════════════════════════════════════════════════════════════
# BUILD
# ═══════════════════════════════════════════════════════════════

def load_price_history():
    """Load price history from JSON file, return empty list if not found."""
    hist_file = os.path.join(os.path.dirname(__file__), PRICE_HIST_FILE)
    if not os.path.exists(hist_file):
        print(f"  Warning: {PRICE_HIST_FILE} not found - using empty history")
        return []
    with open(hist_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Sanity check
    data = [p for p in data if 50 < p.get("p", 0) < 2000]
    return data


def build():
    print(f"Building {DASHBOARD_FILE}...")

    # Load latest price history
    history = load_price_history()
    print(f"  Loaded {len(history)} price points")
    if history:
        print(f"  Date range: {history[0]['t']} -> {history[-1]['t']}")

    body_html = get_body_html().replace("{VERSION}", VERSION)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NVDA AutoTrader — Live Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
{get_css()}
</style>
</head>
<body>
{body_html}
<script>
{get_js(history)}
</script>
</body>
</html>"""

    out_file = os.path.join(os.path.dirname(__file__), DASHBOARD_FILE)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(out_file) // 1024
    print(f"  Written: {DASHBOARD_FILE} ({size_kb} KB)")
    print(f"  Done")


if __name__ == "__main__":
    build()
