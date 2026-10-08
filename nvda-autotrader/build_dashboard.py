#!/usr/bin/env python3
"""
NVDA AutoTrader — Control Panel & Dashboard v4.98
==================================================

CLAUDE AI CONTEXT — READ THIS FIRST IF STARTING A NEW CHAT
============================================================
This file is part of a two-file algorithmic paper trading system for NVDA stock.
Since v4.98 it is the APP: run it and everything is done from the browser.

FILES (all live in the same project folder):
  build_dashboard.py        — This file. Control panel server + dashboard UI.
  nvda_autotrader.py        — The trading bot. Started/stopped by this file.
  nvda_strategy.pine        — TradingView Pine Script port of the strategies.
  nvda_settings.json        — Saved keys + settings (written by the Settings tab;
                              local only, never commit or share it).
  nvda_price_history.json   — Rolling 2000-point price history (written by the bot)
  bot_console.log           — Everything the bot printed (appended by this panel)
  trade_logs/               — Daily summaries + master_trade_log.csv (bot)

HOW TO RUN:
  python build_dashboard.py                       → opens http://127.0.0.1:8080
  python build_dashboard.py --autostart --no-browser
                                                  → Task Scheduler (8:20 AM): panel
                                                    starts and launches the bot itself
  python build_dashboard.py --build-only          → just write nvda_live_dashboard.html

  1. Settings tab: paste Alpaca key ID + secret, pick Paper/Live, Test, Save.
  2. Click Start Bot (top right). Stop/Restart from the same button.
  3. TradingView tab: webhook + Pine Script setup.

HOW IT FITS TOGETHER:
  browser ──▶ this panel (127.0.0.1:8080) ──▶ bot's own server (127.0.0.1:8081)
  - /api/*            handled here (settings, start/stop, console, Pine file)
  - /data, /history, /live_price, /daily_history, /manual_trade,
    /close_manual_trade  proxied to the bot (same JSON as before)
  - Keys are handed to the bot as environment variables when it starts.
  - The bot can still run alone (python nvda_autotrader.py); it then serves
    this same UI itself via render_html(standalone=True) — no Start/Stop or
    Settings in that mode.

SECURITY (v4.98):
  - Binds to 127.0.0.1 only. Requests whose Host isn't loopback are refused
    (DNS rebinding) and POSTs must be same-origin application/json (stops
    other websites from posting to it). Never add CORS headers here.
  - The secret key is never sent back to the browser — only a masked key ID.

IMPORTANT RULES FOR CLAUDE:
  - ALWAYS bump VERSION here AND in nvda_autotrader.py when making changes
  - ALWAYS syntax-check: python3 -c "import ast; ast.parse(open('build_dashboard.py').read())"
  - Bind HTTP servers to 127.0.0.1 — not '' and not 'localhost'
  - Short orders use plain market sell (no bracket) — Alpaca IEX free tier limitation
  - Manual trade auto-calc uses atr_mult from the dashboard (0.5-2.5×)
  - Escape every bot-provided string with esc() before putting it in innerHTML

HOW TO EDIT THE UI:
  - CSS:  CSS string      - HTML: BODY_HTML string      - JS: JS string
  - render_html() stitches them; no build step needed — just restart the panel.
"""

import argparse
import collections
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

VERSION         = "v4.98"
HERE            = os.path.dirname(os.path.abspath(__file__))
BOT_SCRIPT      = os.path.join(HERE, "nvda_autotrader.py")
SETTINGS_FILE   = os.path.join(HERE, "nvda_settings.json")
PRICE_HIST_FILE = os.path.join(HERE, "nvda_price_history.json")
PINE_FILE       = os.path.join(HERE, "nvda_strategy.pine")
CONSOLE_LOG     = os.path.join(HERE, "bot_console.log")
DASHBOARD_FILE  = os.path.join(HERE, "nvda_live_dashboard.html")

PANEL_HOST = "127.0.0.1"
PANEL_PORT = 8080
BOT_HOST   = "127.0.0.1"

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL  = "https://api.alpaca.markets"

DEFAULT_SETTINGS = {
    "alpaca_api_key":    "",
    "alpaca_secret_key": "",
    "trading_mode":      "paper",   # "paper" | "live"
    "signal_source":     "bot",     # "bot" | "tradingview" | "both"
    "auto_restart":      True,      # restart the bot if it crashes / watchdog exits
    "bot_port":          8081,
    "tv_enabled":        False,
    "tv_port":           8090,
    "tv_passphrase":     "",
    "tv_public_url":     "",        # your ngrok / cloudflared https URL (display only)
}

# Bot exit codes that mean "don't restart, a human needs to look":
#   0 clean exit (midnight / weekend), 2 no keys, 3 Alpaca rejected the keys
NO_RESTART_CODES = {0, 2, 3}


# ═══════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════

_settings_lock = threading.Lock()


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            s.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    except (OSError, ValueError):
        pass
    return s


def save_settings(s):
    with _settings_lock:
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
        try:
            os.chmod(tmp, 0o600)   # owner-only on macOS/Linux; no-op on Windows
        except OSError:
            pass
        os.replace(tmp, SETTINGS_FILE)


def mask_key(k):
    if not k:
        return ""
    return k[:4] + "•" * 6 + k[-4:] if len(k) > 10 else "•" * len(k)


def public_settings(s):
    """What the browser may see — the secret key never leaves this process."""
    return {
        "api_key_masked": mask_key(s["alpaca_api_key"]),
        "has_api_key":    bool(s["alpaca_api_key"]),
        "has_secret":     bool(s["alpaca_secret_key"]),
        "trading_mode":   s["trading_mode"],
        "signal_source":  s["signal_source"],
        "auto_restart":   bool(s["auto_restart"]),
        "tv_enabled":     bool(s["tv_enabled"]),
        "tv_port":        int(s["tv_port"]),
        "tv_passphrase":  s["tv_passphrase"],   # needed to paste into the Pine inputs
        "tv_public_url":  s["tv_public_url"],
        "settings_file":  SETTINGS_FILE,
    }


def apply_settings_update(body):
    s = load_settings()
    key = str(body.get("alpaca_api_key") or "").strip()
    sec = str(body.get("alpaca_secret_key") or "").strip()
    if body.get("clear_keys"):
        s["alpaca_api_key"] = s["alpaca_secret_key"] = ""
    if key:
        s["alpaca_api_key"] = key
    if sec:
        s["alpaca_secret_key"] = sec

    mode = body.get("trading_mode")
    if mode in ("paper", "live"):
        if mode == "live" and s["trading_mode"] != "live" and not body.get("confirm_live"):
            raise ValueError("Switching to LIVE needs confirmation")
        s["trading_mode"] = mode
    src = body.get("signal_source")
    if src in ("bot", "tradingview", "both"):
        s["signal_source"] = src
    for flag in ("auto_restart", "tv_enabled"):
        if flag in body:
            s[flag] = bool(body[flag])
    if "tv_port" in body:
        port = int(body["tv_port"])
        if not 1024 <= port <= 65535 or port in (PANEL_PORT, int(s["bot_port"])):
            raise ValueError("Webhook port must be 1024-65535 and not 8080/8081")
        s["tv_port"] = port
    if "tv_passphrase" in body:
        pw = str(body["tv_passphrase"]).strip()
        if pw and len(pw) < 12:
            raise ValueError("Use a passphrase of at least 12 characters")
        s["tv_passphrase"] = pw
    if "tv_public_url" in body:
        s["tv_public_url"] = str(body["tv_public_url"]).strip()[:300]
    if s["tv_enabled"] and not s["tv_passphrase"]:
        raise ValueError("Set a webhook passphrase before enabling TradingView")
    save_settings(s)
    return s


def test_alpaca_keys(key, secret, mode):
    base = LIVE_BASE_URL if mode == "live" else PAPER_BASE_URL
    if not key or not secret:
        return {"ok": False, "error": "Enter both the key ID and the secret key"}
    req = urllib.request.Request(base + "/v2/account", headers={
        "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            acct = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            other = "live" if mode == "paper" else "paper"
            return {"ok": False, "error": f"Alpaca rejected these keys for {mode.upper()} "
                                          f"(HTTP {e.code}). Paper and live accounts have "
                                          f"different keys — are these {other} keys?"}
        return {"ok": False, "error": f"Alpaca returned HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": f"Could not reach Alpaca: {e}"}
    return {
        "ok": True,
        "mode": mode,
        "status": acct.get("status"),
        "equity": float(acct.get("equity") or 0),
        "buying_power": float(acct.get("buying_power") or 0),
        "pattern_day_trader": bool(acct.get("pattern_day_trader")),
        "account": mask_key(str(acct.get("account_number") or "")),
    }


# ═══════════════════════════════════════════════════════════════
# BOT PROCESS
# ═══════════════════════════════════════════════════════════════

class BotProcess:
    def __init__(self):
        self.lock = threading.RLock()
        self.proc = None
        self.lines = collections.deque(maxlen=3000)
        self.line_no = 0
        self.desired = False
        self.started_at = None
        self.restarts = 0
        self.restart_times = collections.deque(maxlen=5)
        self.last_exit = None
        self.last_exit_note = ""
        self.running_mode = None

    # ── console ────────────────────────────────────────────────
    def _add(self, line):
        with self.lock:
            self.line_no += 1
            self.lines.append((self.line_no, line))
        try:
            if os.path.exists(CONSOLE_LOG) and os.path.getsize(CONSOLE_LOG) > 20_000_000:
                os.replace(CONSOLE_LOG, CONSOLE_LOG + ".old")
            with open(CONSOLE_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def note(self, msg):
        self._add(f"[panel {datetime.now().strftime('%H:%M:%S')}] {msg}")

    def console_since(self, after):
        with self.lock:
            out = [{"n": n, "line": l} for n, l in self.lines if n > after]
            return out, self.line_no

    # ── lifecycle ──────────────────────────────────────────────
    def is_running(self):
        with self.lock:
            return self.proc is not None and self.proc.poll() is None

    def start(self, reason="started from dashboard"):
        s = load_settings()
        if not s["alpaca_api_key"] or not s["alpaca_secret_key"]:
            raise ValueError("Add your Alpaca keys in Settings first")
        if not os.path.exists(BOT_SCRIPT):
            raise ValueError(f"Bot script not found: {BOT_SCRIPT}")
        with self.lock:
            if self.is_running():
                return
            env = os.environ.copy()
            env.update({
                "ALPACA_API_KEY":     s["alpaca_api_key"],
                "ALPACA_SECRET_KEY":  s["alpaca_secret_key"],
                "ALPACA_BASE_URL":    LIVE_BASE_URL if s["trading_mode"] == "live" else PAPER_BASE_URL,
                "NVDA_BOT_HOST":      BOT_HOST,
                "NVDA_BOT_PORT":      str(s["bot_port"]),
                "NVDA_SIGNAL_SOURCE": s["signal_source"],
                "NVDA_TV_ENABLED":    "1" if s["tv_enabled"] else "0",
                "NVDA_TV_PASSPHRASE": s["tv_passphrase"],
                "NVDA_TV_PORT":       str(s["tv_port"]),
                "PYTHONIOENCODING":   "utf-8",
                "PYTHONUNBUFFERED":   "1",
            })
            kwargs = {}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            self.proc = subprocess.Popen(
                [sys.executable, "-u", BOT_SCRIPT], cwd=HERE, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1, **kwargs)
            self.desired = True
            self.started_at = time.time()
            self.running_mode = s["trading_mode"]
            self.note(f"bot {reason} (pid {self.proc.pid}, {s['trading_mode'].upper()}, "
                      f"signals: {s['signal_source']})")
            threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()

    def _pump(self, proc):
        for line in proc.stdout:
            self._add(line.rstrip("\r\n"))
        rc = proc.wait()
        self._on_exit(proc, rc)

    def _on_exit(self, proc, rc):
        with self.lock:
            if proc is not self.proc:
                return
            self.proc = None
            self.last_exit = rc
            self.last_exit_note = {
                0: "exited normally (end of day / weekend)",
                2: "no API keys — add them in Settings",
                3: "Alpaca refused the connection — check keys and Paper/Live in Settings",
            }.get(rc, "stopped" if not self.desired else "crashed or was restarted by its watchdog")
            self.note(f"bot exited with code {rc}: {self.last_exit_note}")
            restart = (self.desired and rc not in NO_RESTART_CODES
                       and load_settings().get("auto_restart", True))
            if rc in NO_RESTART_CODES:
                self.desired = False
            if restart:
                now = time.time()
                recent = [t for t in self.restart_times if now - t < 600]
                if len(recent) >= 5:
                    self.desired = False
                    self.note("bot crashed 5 times in 10 minutes — auto-restart paused. "
                              "Check the console, then click Start Bot.")
                    return
                self.restart_times.append(now)
                self.restarts += 1
        if restart:
            threading.Thread(target=self._delayed_restart, daemon=True).start()

    def _delayed_restart(self):
        time.sleep(5)
        with self.lock:
            if not self.desired or self.is_running():
                return
        try:
            self.start(reason="auto-restarted")
        except Exception as e:
            self.note(f"auto-restart failed: {e}")

    def stop(self):
        with self.lock:
            self.desired = False
            proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        self.note("stopping bot (open positions stay open on Alpaca)")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    def status(self):
        s = load_settings()
        with self.lock:
            running = self.is_running()
            return {
                "running":     running,
                "pid":         self.proc.pid if running else None,
                "uptime_s":    int(time.time() - self.started_at) if running and self.started_at else 0,
                "restarts":    self.restarts,
                "desired":     self.desired,
                "last_exit":   self.last_exit,
                "last_exit_note": self.last_exit_note,
                "keys_set":    bool(s["alpaca_api_key"] and s["alpaca_secret_key"]),
                "mode":        self.running_mode if running else s["trading_mode"],
                "saved_mode":  s["trading_mode"],
                "signal_source": s["signal_source"],
            }


BOT = BotProcess()


# ═══════════════════════════════════════════════════════════════
# HTTP — control panel
# ═══════════════════════════════════════════════════════════════

_LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}
_PROXY_GET = {"/data": 8, "/history": 8, "/live_price": 8, "/daily_history": 25}
_PROXY_POST = {"/manual_trade": 60, "/close_manual_trade": 30}


def _host_only(h):
    h = (h or "").strip().lower()
    if h.startswith("["):
        return h.split("]")[0] + "]"
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


class PanelHandler(BaseHTTPRequestHandler):
    server_version = "NVDAPanel/" + VERSION

    def log_message(self, format, *args):
        pass

    # ── helpers ────────────────────────────────────────────────
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            pass

    def _trusted(self, is_post):
        if _host_only(self.headers.get("Host")) not in _LOOPBACK:
            return False
        if not is_post:
            return True
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return False
        origin = self.headers.get("Origin")
        if origin and origin.rstrip("/").lower() != "http://" + (self.headers.get("Host") or "").lower():
            return False
        return True

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 100_000:
            raise ValueError("Request too large")
        raw = self.rfile.read(n) if n else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        return data, raw

    def _proxy(self, method, path, raw=None, timeout=10):
        port = int(load_settings()["bot_port"])
        req = urllib.request.Request(f"http://{BOT_HOST}:{port}{path}", data=raw, method=method)
        if raw is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception:
            return None, None

    # ── GET ────────────────────────────────────────────────────
    def do_GET(self):
        if not self._trusted(False):
            return self._send(403, {"ok": False, "error": "Forbidden"})
        path = self.path.split("?")[0]
        query = self.path[len(path) + 1:] if "?" in self.path else ""
        try:
            if path in ("/", "/dashboard"):
                return self._send(200, render_html(standalone=False), "text/html; charset=utf-8")
            if path == "/api/settings":
                return self._send(200, public_settings(load_settings()))
            if path == "/api/bot/status":
                return self._send(200, BOT.status())
            if path == "/api/bot/console":
                after = 0
                for part in query.split("&"):
                    if part.startswith("after="):
                        after = int(part[6:] or 0)
                lines, last = BOT.console_since(after)
                return self._send(200, {"lines": lines[-1000:], "last": last})
            if path == "/api/pine":
                try:
                    with open(PINE_FILE, "r", encoding="utf-8") as f:
                        return self._send(200, f.read(), "text/plain; charset=utf-8")
                except OSError:
                    return self._send(404, "nvda_strategy.pine not found next to build_dashboard.py",
                                      "text/plain; charset=utf-8")
            if path in _PROXY_GET:
                status, body = self._proxy("GET", path, timeout=_PROXY_GET[path])
                if status is not None:
                    return self._send(status, body)
                if path == "/history":     # bot offline: still show saved history
                    return self._send(200, load_price_history())
                return self._send(503, {"ok": False, "offline": True,
                                        "error": "Bot is not running — click Start Bot"})
            return self._send(404, {"ok": False, "error": "Not found"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

    # ── POST ───────────────────────────────────────────────────
    def do_POST(self):
        if not self._trusted(True):
            return self._send(403, {"ok": False, "error": "Forbidden"})
        path = self.path.split("?")[0]
        try:
            body, raw = self._body()
        except Exception as e:
            return self._send(400, {"ok": False, "error": str(e)})
        try:
            if path == "/api/settings":
                s = apply_settings_update(body)
                return self._send(200, {"ok": True, "settings": public_settings(s),
                                        "restart_needed": BOT.is_running()})
            if path == "/api/test_keys":
                s = load_settings()
                key = str(body.get("alpaca_api_key") or "").strip() or s["alpaca_api_key"]
                sec = str(body.get("alpaca_secret_key") or "").strip() or s["alpaca_secret_key"]
                mode = body.get("trading_mode") if body.get("trading_mode") in ("paper", "live") \
                    else s["trading_mode"]
                return self._send(200, test_alpaca_keys(key, sec, mode))
            if path == "/api/generate_passphrase":
                return self._send(200, {"ok": True, "passphrase": secrets.token_urlsafe(24)})
            if path == "/api/bot/start":
                BOT.start()
                return self._send(200, {"ok": True, "status": BOT.status()})
            if path == "/api/bot/stop":
                BOT.stop()
                return self._send(200, {"ok": True, "status": BOT.status()})
            if path == "/api/bot/restart":
                BOT.stop()
                BOT.start(reason="restarted from dashboard")
                return self._send(200, {"ok": True, "status": BOT.status()})
            if path in _PROXY_POST:
                status, resp = self._proxy("POST", path, raw=raw, timeout=_PROXY_POST[path])
                if status is None:
                    return self._send(503, {"ok": False, "error": "Bot is not running — click Start Bot"})
                return self._send(status, resp)
            return self._send(404, {"ok": False, "error": "Not found"})
        except ValueError as e:
            return self._send(400, {"ok": False, "error": str(e)})
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

    def do_OPTIONS(self):
        self._send(405, {"ok": False})


def load_price_history():
    try:
        with open(PRICE_HIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [p for p in data if isinstance(p, dict) and 50 < float(p.get("p", 0)) < 2000]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# UI — CSS
# ═══════════════════════════════════════════════════════════════

CSS = r"""
:root{
  --bg:#0b0f17; --panel:#111827; --panel-2:#172033; --raise:#1c2740; --border:#243049;
  --text:#e7ecf5; --text-2:#a3afc4; --muted:#6d7a93;
  --accent:#5b8cff; --accent-soft:rgba(91,140,255,.14); --on-accent:#fff;
  --up:#34d399; --up-soft:rgba(52,211,153,.13); --down:#f87171; --down-soft:rgba(248,113,113,.13);
  --warn:#fbbf24; --warn-soft:rgba(251,191,36,.13); --live:#f43f5e;
  --line:#7aa2ff; --fill:rgba(122,162,255,.10); --grid:rgba(148,163,184,.08);
  --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.25);
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  --sans:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  color-scheme:dark;
}
:root[data-theme="light"]{
  --bg:#f4f6fb; --panel:#ffffff; --panel-2:#f7f9fc; --raise:#eef2f8; --border:#e2e8f0;
  --text:#0f172a; --text-2:#475569; --muted:#64748b;
  --accent:#2563eb; --accent-soft:rgba(37,99,235,.10); --on-accent:#fff;
  --up:#15803d; --up-soft:rgba(21,128,61,.10); --down:#dc2626; --down-soft:rgba(220,38,38,.09);
  --warn:#b45309; --warn-soft:rgba(180,83,9,.10); --live:#e11d48;
  --line:#2563eb; --fill:rgba(37,99,235,.08); --grid:rgba(15,23,42,.06);
  --shadow:0 1px 2px rgba(15,23,42,.05),0 6px 18px rgba(15,23,42,.06);
  color-scheme:light;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 var(--sans);-webkit-font-smoothing:antialiased}
button,input,select,textarea{font:inherit;color:inherit}
a{color:var(--accent)}
.mono{font-family:var(--mono)}
.muted{color:var(--muted)} .t2{color:var(--text-2)}
.up{color:var(--up)} .down{color:var(--down)} .warn{color:var(--warn)}
.hidden{display:none!important}

/* ── layout ── */
.app{display:grid;grid-template-columns:220px 1fr;grid-template-rows:auto 1fr;min-height:100vh}
.topbar{grid-column:1/-1;display:flex;align-items:center;gap:16px;padding:10px 20px;border-bottom:1px solid var(--border);background:var(--panel);position:sticky;top:0;z-index:20}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:.2px;white-space:nowrap}
.brand .logo{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--accent),#22c3a6);display:grid;place-items:center;color:#fff;font-size:13px}
.brand small{font-weight:500;color:var(--muted);font-family:var(--mono);font-size:11px}
.ticker{display:flex;align-items:baseline;gap:8px;margin-left:8px}
.ticker .sym{font-weight:700;color:var(--text-2)}
.ticker .px{font:600 20px var(--mono)}
.ticker .chg{font:500 12px var(--mono)}
.spacer{flex:1}
.pill{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid var(--border);background:var(--panel-2);white-space:nowrap}
.pill .dot{width:7px;height:7px;border-radius:50%;background:var(--muted)}
.pill.ok .dot{background:var(--up);box-shadow:0 0 0 3px var(--up-soft)}
.pill.bad .dot{background:var(--down)}
.pill.wait .dot{background:var(--warn)}
.pill.paper{color:var(--accent);border-color:var(--accent-soft);background:var(--accent-soft)}
.pill.live{color:#fff;background:var(--live);border-color:var(--live)}
.side{border-right:1px solid var(--border);background:var(--panel);padding:14px 10px;display:flex;flex-direction:column;gap:2px;position:sticky;top:53px;height:calc(100vh - 53px)}
.nav{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;color:var(--text-2);text-decoration:none;font-weight:500;cursor:pointer;border:0;background:none;width:100%;text-align:left}
.nav:hover{background:var(--raise);color:var(--text)}
.nav.active{background:var(--accent-soft);color:var(--accent)}
.nav svg{width:17px;height:17px;flex:none}
.nav .badge{margin-left:auto;font:600 11px var(--mono);padding:1px 7px;border-radius:999px;background:var(--raise);color:var(--text-2)}
.side .foot{margin-top:auto;padding:10px 12px;font-size:12px;color:var(--muted)}
main{padding:20px;min-width:0}
.view{display:none;animation:fade .15s ease}
.view.active{display:block}
@keyframes fade{from{opacity:.4}to{opacity:1}}
h2{font-size:18px;margin:0 0 4px} .sub{color:var(--muted);margin:0 0 16px;font-size:13px}

/* ── cards ── */
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);min-width:0}
.card-h{display:flex;align-items:center;gap:10px;padding:14px 16px 0}
.card-h h3{font-size:13px;font-weight:600;margin:0;color:var(--text-2);text-transform:uppercase;letter-spacing:.6px}
.card-h .right{margin-left:auto;display:flex;gap:8px;align-items:center}
.card-b{padding:14px 16px 16px}
.grid{display:grid;gap:16px}
.kpis{grid-template-columns:repeat(6,minmax(0,1fr))}
.kpi{padding:14px 16px}
.kpi .lbl{font-size:12px;color:var(--muted);font-weight:500}
.kpi .val{font:600 20px var(--mono);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpi .sm{font-size:12px;color:var(--text-2);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.main-cols{grid-template-columns:minmax(0,1fr) 360px;margin-top:16px}
.stack{display:flex;flex-direction:column;gap:16px;min-width:0}

/* ── banners ── */
.banner{display:flex;gap:12px;align-items:center;padding:12px 16px;border-radius:10px;margin-bottom:16px;border:1px solid var(--border);background:var(--panel-2)}
.banner.warn{border-color:var(--warn-soft);background:var(--warn-soft)}
.banner.live{border-color:var(--live);background:var(--down-soft)}
.banner .grow{flex:1}

/* ── buttons & inputs ── */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:8px 14px;border-radius:8px;border:1px solid var(--border);background:var(--panel-2);font-weight:600;cursor:pointer;white-space:nowrap;transition:background .12s,border-color .12s}
.btn:hover{background:var(--raise)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.btn.primary:hover{filter:brightness(1.08)}
.btn.go{background:var(--up);border-color:var(--up);color:#06281b}
.btn.stop{background:var(--down-soft);border-color:var(--down);color:var(--down)}
.btn.sm{padding:5px 10px;font-size:12px}
.btn.ghost{background:none;border-color:transparent}
.seg{display:inline-flex;padding:3px;border-radius:9px;background:var(--panel-2);border:1px solid var(--border)}
.seg button{border:0;background:none;padding:5px 11px;border-radius:7px;font-size:12px;font-weight:600;color:var(--text-2);cursor:pointer}
.seg button.on{background:var(--raise);color:var(--text);box-shadow:var(--shadow)}
.field{display:flex;flex-direction:column;gap:6px;margin-bottom:14px}
.field label{font-size:12px;font-weight:600;color:var(--text-2)}
.field .hint{font-size:12px;color:var(--muted)}
.input{width:100%;padding:9px 11px;border-radius:8px;border:1px solid var(--border);background:var(--panel-2);outline:none}
.input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.input-row{display:flex;gap:8px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.check{display:flex;gap:10px;align-items:flex-start;padding:10px 0;cursor:pointer}
.check input{margin-top:3px;accent-color:var(--accent)}
.check b{display:block;font-weight:600}
.check span{font-size:12px;color:var(--muted)}
.msg{padding:9px 12px;border-radius:8px;font-size:13px;margin-top:10px}
.msg.ok{background:var(--up-soft);color:var(--up)}
.msg.err{background:var(--down-soft);color:var(--down)}

/* ── chart ── */
.chart-wrap{position:relative;height:340px}
.chart-empty{position:absolute;inset:0;display:grid;place-items:center;color:var(--muted);font-size:13px;pointer-events:none}
.chart-foot{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:8px}
.key{display:inline-flex;align-items:center;gap:6px}
.key i{width:14px;height:0;border-top:2px dashed currentColor;display:inline-block}

/* ── kill-zone timeline ── */
.kz{position:relative;height:30px;border-radius:8px;background:var(--panel-2);border:1px solid var(--border);overflow:hidden}
.kz .zone{position:absolute;top:0;bottom:0;background:var(--accent-soft);border-left:1px solid var(--accent);border-right:1px solid var(--accent);display:grid;place-items:center;font:600 11px var(--mono);color:var(--accent)}
.kz .zone.past{background:var(--raise);border-color:var(--border);color:var(--muted)}
.kz .zone.now{background:var(--accent);color:var(--on-accent)}
.kz .nowline{position:absolute;top:0;bottom:0;width:2px;background:var(--warn)}
.kz-labels{position:relative;height:16px;font:11px var(--mono);color:var(--muted);margin-top:4px}
.kz-labels span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.kz-labels span:first-child{transform:none} .kz-labels span:last-child{transform:translateX(-100%)}
.kz .zone{white-space:nowrap;overflow:hidden}

/* ── trades ── */
.trade{border:1px solid var(--border);border-radius:10px;padding:12px;background:var(--panel-2)}
.trade + .trade{margin-top:10px}
.trade .top{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.dir{font:700 11px var(--mono);padding:3px 8px;border-radius:6px}
.dir.long{background:var(--up-soft);color:var(--up)} .dir.short{background:var(--down-soft);color:var(--down)}
.tag{font:600 11px var(--mono);padding:3px 8px;border-radius:6px;background:var(--raise);color:var(--text-2)}
.trade .pnl{margin-left:auto;font:600 16px var(--mono)}
.kv{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.kv div{font-size:11px;color:var(--muted)}
.kv b{display:block;font:600 13px var(--mono);color:var(--text)}
.prog{position:relative;height:6px;border-radius:3px;background:linear-gradient(90deg,var(--down-soft),var(--raise) 50%,var(--up-soft));margin:12px 0 4px}
.prog.short{background:linear-gradient(90deg,var(--up-soft),var(--raise) 50%,var(--down-soft))}
.prog .mk{position:absolute;top:-4px;width:3px;height:14px;border-radius:2px;background:var(--text);transform:translateX(-1px)}
.prog .en{position:absolute;top:-2px;width:2px;height:10px;background:var(--muted)}
.prog-l{display:flex;justify-content:space-between;font:11px var(--mono);color:var(--muted)}
.empty{padding:26px 10px;text-align:center;color:var(--muted);font-size:13px}
.empty .ico{font-size:22px;margin-bottom:6px;opacity:.7}

/* ── status list ── */
.dl{display:grid;grid-template-columns:auto 1fr;gap:8px 14px;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;text-align:right;font-family:var(--mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ── log & console ── */
.log{max-height:360px;overflow:auto;font-size:12.5px}
.log .e{display:grid;grid-template-columns:62px 54px 1fr;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)}
.log .e:last-child{border-bottom:0}
.lvl{font:700 10px var(--mono);padding:2px 0;border-radius:4px;text-align:center;align-self:start;background:var(--raise);color:var(--text-2)}
.lvl.TRADE{background:var(--accent-soft);color:var(--accent)} .lvl.WARN{background:var(--warn-soft);color:var(--warn)}
.lvl.ERROR,.lvl.CRITICAL{background:var(--down-soft);color:var(--down)}
.console{height:calc(100vh - 230px);min-height:320px;overflow:auto;background:#05080e;color:#cfd8e6;border-radius:10px;padding:12px 14px;font:12px/1.55 var(--mono);white-space:pre-wrap;word-break:break-word}
:root[data-theme="light"] .console{background:#0f172a}
.console .WARN{color:#fbbf24} .console .ERROR,.console .CRITICAL{color:#f87171} .console .TRADE{color:#7aa2ff}
.console .PANEL{color:#5eead4}

/* ── signals ── */
.sig{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid var(--border)}
.sig:last-child{border-bottom:0}
.pips{display:flex;gap:3px}
.pips i{width:7px;height:14px;border-radius:2px;background:var(--raise)}
.pips i.on{background:var(--accent)}

/* ── code ── */
pre.code{margin:0;max-height:420px;overflow:auto;background:var(--panel-2);border:1px solid var(--border);border-radius:10px;padding:12px;font:12px/1.5 var(--mono);white-space:pre}
.steps{counter-reset:s;list-style:none;padding:0;margin:0}
.steps li{counter-increment:s;position:relative;padding:0 0 16px 38px}
.steps li:before{content:counter(s);position:absolute;left:0;top:0;width:26px;height:26px;border-radius:50%;background:var(--accent-soft);color:var(--accent);font-weight:700;display:grid;place-items:center;font-size:13px}
.steps b{display:block;margin-bottom:2px}
.copy-row{display:flex;gap:8px;align-items:center}
.copy-row code{flex:1;min-width:0;overflow:auto;white-space:nowrap;padding:8px 10px;border-radius:8px;background:var(--panel-2);border:1px solid var(--border);font:12px var(--mono)}

/* ── modal ── */
.backdrop{position:fixed;inset:0;background:rgba(3,6,12,.6);backdrop-filter:blur(2px);display:grid;place-items:center;z-index:50;padding:16px}
.modal{width:min(480px,100%);max-height:calc(100vh - 32px);overflow:auto;background:var(--panel);border:1px solid var(--border);border-radius:14px;box-shadow:var(--shadow)}
.modal-h{display:flex;align-items:center;padding:16px 18px;border-bottom:1px solid var(--border)}
.modal-h h3{margin:0;font-size:16px}
.modal-h .x{margin-left:auto}
.modal-b{padding:18px}
.modal-f{display:flex;gap:10px;justify-content:flex-end;padding:14px 18px;border-top:1px solid var(--border)}
.dirpick{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
.dirpick button{padding:12px;border-radius:10px;border:1px solid var(--border);background:var(--panel-2);font-weight:700;cursor:pointer}
.dirpick button.long.on{background:var(--up-soft);border-color:var(--up);color:var(--up)}
.dirpick button.short.on{background:var(--down-soft);border-color:var(--down);color:var(--down)}
.livepx{display:flex;align-items:baseline;gap:8px;padding:10px 12px;border-radius:10px;background:var(--panel-2);border:1px solid var(--border);margin-bottom:14px}
.livepx b{font:600 18px var(--mono)}
.preview{font:12px var(--mono);color:var(--text-2);background:var(--panel-2);border-radius:8px;padding:10px 12px;margin-top:8px}

/* ── toast ── */
.toast{position:fixed;right:20px;bottom:20px;z-index:60;padding:12px 16px;border-radius:10px;background:var(--panel);border:1px solid var(--border);box-shadow:var(--shadow);max-width:380px;font-size:13px}
.toast.ok{border-color:var(--up)} .toast.err{border-color:var(--down)}

/* ── responsive ── */
@media (max-width:1280px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:1080px){.main-cols{grid-template-columns:minmax(0,1fr)}}
@media (max-width:860px){
  .app{grid-template-columns:1fr}
  .side{position:static;height:auto;flex-direction:row;overflow-x:auto;padding:6px 10px;border-right:0;border-bottom:1px solid var(--border)}
  .nav{width:auto;padding:8px 10px;white-space:nowrap} .nav .badge,.side .foot{display:none}
  .topbar{flex-wrap:wrap;gap:10px;padding:10px 16px} .ticker{margin-left:0}
  main{padding:16px} .kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  .chart-wrap{height:260px} .kv{grid-template-columns:repeat(2,1fr)}
}
"""


# ═══════════════════════════════════════════════════════════════
# UI — HTML
# ═══════════════════════════════════════════════════════════════

ICONS = {
    "overview": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/></svg>',
    "trades":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg>',
    "signals":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8a6 6 0 0 1 0 8.4M7.8 16.2a6 6 0 0 1 0-8.4M19.1 4.9a10 10 0 0 1 0 14.2M4.9 19.1a10 10 0 0 1 0-14.2"/></svg>',
    "console":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m4 17 6-5-6-5M12 19h8"/></svg>',
    "settings": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
    "tv":       '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="13" rx="2"/><path d="M8 21h8M7 13l3-3 2 2 4-4"/></svg>',
}

BODY_HTML = r"""
<div class="app">
  <header class="topbar">
    <div class="brand"><div class="logo">NV</div><div>NVDA AutoTrader<br><small>__VERSION__</small></div></div>
    <div class="ticker"><span class="sym">NVDA</span><span class="px" id="tb-price">—</span><span class="chg" id="tb-chg"></span></div>
    <div class="spacer"></div>
    <span class="pill" id="tb-market"><span class="dot"></span><span>Market</span></span>
    <span class="pill paper" id="tb-mode">PAPER</span>
    <span class="pill" id="tb-bot"><span class="dot"></span><span id="tb-bot-text">Bot offline</span></span>
    <button class="btn go panel-only" id="btn-bot" onclick="toggleBot()">▶ Start Bot</button>
    <button class="btn ghost sm" id="btn-theme" onclick="toggleTheme()" title="Toggle light/dark" aria-label="Toggle theme"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor"/></svg></button>
  </header>

  <nav class="side" id="side">
    <button class="nav active" data-view="overview">__I_overview__<span>Overview</span></button>
    <button class="nav" data-view="trades">__I_trades__<span>Trades</span><span class="badge" id="nav-trades">0</span></button>
    <button class="nav" data-view="signals">__I_signals__<span>Signals</span><span class="badge" id="nav-signals">0</span></button>
    <button class="nav panel-only" data-view="console">__I_console__<span>Console</span></button>
    <button class="nav panel-only" data-view="settings">__I_settings__<span>Settings</span></button>
    <button class="nav" data-view="tradingview">__I_tv__<span>TradingView</span></button>
    <div class="foot" id="side-foot">Data refreshes every 5s</div>
  </nav>

  <main>
    <div id="banners"></div>

    <!-- ═══ OVERVIEW ═══ -->
    <section class="view active" id="view-overview">
      <div class="grid kpis">
        <div class="card kpi"><div class="lbl">Equity</div><div class="val" id="k-eq">—</div><div class="sm" id="k-eq-s">—</div></div>
        <div class="card kpi"><div class="lbl">Open P&amp;L</div><div class="val" id="k-pnl">—</div><div class="sm" id="k-pnl-s">No open trade</div></div>
        <div class="card kpi"><div class="lbl">ATR (5m)</div><div class="val" id="k-atr">—</div><div class="sm" id="k-atr-s">Volatility per bar</div></div>
        <div class="card kpi"><div class="lbl">VWAP</div><div class="val" id="k-vwap">—</div><div class="sm" id="k-vwap-s">—</div></div>
        <div class="card kpi"><div class="lbl">Trend · QQQ</div><div class="val" id="k-trend">—</div><div class="sm" id="k-trend-s">—</div></div>
        <div class="card kpi"><div class="lbl">Multi-timeframe</div><div class="val" id="k-mtf">—</div><div class="sm" id="k-mtf-s">—</div></div>
      </div>

      <div class="grid main-cols">
        <div class="stack">
          <div class="card">
            <div class="card-h"><h3>Price</h3>
              <div class="right">
                <div class="seg" id="range-seg">
                  <button data-r="1h">1H</button><button data-r="1d" class="on">Today</button><button data-r="5d">5D</button><button data-r="1m">1M</button><button data-r="6m">6M</button>
                </div>
              </div>
            </div>
            <div class="card-b">
              <div class="chart-wrap"><canvas id="chart" aria-label="NVDA price chart" role="img"></canvas><div class="chart-empty" id="chart-empty">Loading price history…</div></div>
              <div class="chart-foot">
                <span id="chart-range">—</span>
                <span class="key" style="color:var(--accent)"><i></i>VWAP</span>
                <span class="key" style="color:var(--text-2)"><i></i>Entry</span>
                <span class="key" style="color:var(--down)"><i></i>Stop</span>
                <span class="key" style="color:var(--up)"><i></i>Target</span>
              </div>
            </div>
          </div>
          <div class="card">
            <div class="card-h"><h3>Kill zones (ET)</h3><div class="right t2" id="kz-next" style="font-size:12px"></div></div>
            <div class="card-b">
              <div class="kz" id="kz"></div>
              <div class="kz-labels" id="kz-labels"></div>
            </div>
          </div>
        </div>

        <div class="stack">
          <div class="card">
            <div class="card-h"><h3 id="ov-trades-title">Active trade</h3><div class="right"><button class="btn primary sm" onclick="openTradeModal()">+ Manual trade</button></div></div>
            <div class="card-b" id="ov-trades"><div class="empty"><div class="ico">⏳</div>No active trade</div></div>
          </div>
          <div class="card">
            <div class="card-h"><h3>Bot status</h3></div>
            <div class="card-b">
              <div id="st-status" style="font-weight:600;margin-bottom:10px">—</div>
              <dl class="dl">
                <dt>Strategy</dt><dd id="st-strat">—</dd>
                <dt>Signals from</dt><dd id="st-src">—</dd>
                <dt>Last scan</dt><dd id="st-scan">—</dd>
                <dt>Candles · errors</dt><dd id="st-candles">—</dd>
                <dt>Setups today</dt><dd id="st-setups">—</dd>
              </dl>
            </div>
          </div>
          <div class="card">
            <div class="card-h"><h3>Activity</h3></div>
            <div class="card-b"><div class="log" id="ov-log"><div class="empty">No activity yet</div></div></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ TRADES ═══ -->
    <section class="view" id="view-trades">
      <div class="row" style="margin-bottom:16px"><div><h2>Trades</h2><p class="sub" style="margin:0">Open positions the bot is tracking, and the most recent close.</p></div><div class="spacer"></div><button class="btn primary" onclick="openTradeModal()">+ Manual trade</button></div>
      <div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)" id="trades-grid">
        <div class="card"><div class="card-h"><h3>Open</h3></div><div class="card-b" id="tr-open"><div class="empty">No open trades</div></div></div>
        <div class="card"><div class="card-h"><h3>Last closed</h3></div><div class="card-b" id="tr-closed"><div class="empty">Nothing closed yet today</div></div></div>
      </div>
      <p class="sub" style="margin-top:14px">Full history is in <span class="mono">trade_logs/master_trade_log.csv</span>.</p>
    </section>

    <!-- ═══ SIGNALS ═══ -->
    <section class="view" id="view-signals">
      <h2>Signals today</h2><p class="sub">Every FVG / VWAP setup the bot scored today, newest first. Score is out of 9.</p>
      <div class="card"><div class="card-b" id="sig-list"><div class="empty">No setups detected yet today</div></div></div>
    </section>

    <!-- ═══ CONSOLE ═══ -->
    <section class="view" id="view-console">
      <div class="row" style="margin-bottom:12px">
        <div><h2>Console</h2><p class="sub" style="margin:0">Everything the bot prints. Also saved to <span class="mono">bot_console.log</span>.</p></div>
        <div class="spacer"></div>
        <div class="seg" id="con-filter"><button data-f="all" class="on">All</button><button data-f="TRADE">Trades</button><button data-f="WARN">Warnings</button><button data-f="ERROR">Errors</button></div>
        <label class="row t2" style="font-size:12px;gap:6px"><input type="checkbox" id="con-follow" checked> Follow</label>
      </div>
      <div class="console" id="console"><span class="muted">Waiting for the bot to start…</span></div>
    </section>

    <!-- ═══ SETTINGS ═══ -->
    <section class="view" id="view-settings">
      <h2>Settings</h2><p class="sub">Saved to <span class="mono" id="set-file">nvda_settings.json</span> on this computer. Changes apply the next time the bot starts.</p>
      <div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)" id="settings-grid">
        <div class="card">
          <div class="card-h"><h3>Alpaca account</h3><div class="right"><span class="pill" id="set-keystate">No keys</span></div></div>
          <div class="card-b">
            <div class="field">
              <label>Account type</label>
              <div class="seg" id="set-mode"><button data-m="paper" class="on">Paper trading</button><button data-m="live">Live money</button></div>
              <span class="hint">Paper and live accounts have different keys. Get them at app.alpaca.markets → API Keys.</span>
            </div>
            <div class="field">
              <label for="set-key">API key ID</label>
              <input class="input mono" id="set-key" autocomplete="off" spellcheck="false" placeholder="PK…">
              <span class="hint" id="set-key-hint">Leave blank to keep the saved key.</span>
            </div>
            <div class="field">
              <label for="set-secret">Secret key</label>
              <div class="input-row">
                <input class="input mono" id="set-secret" type="password" autocomplete="new-password" spellcheck="false" placeholder="••••••••">
                <button class="btn" type="button" onclick="toggleSecret()" id="btn-show">Show</button>
              </div>
              <span class="hint">Never shown again after saving. Leave blank to keep the saved secret.</span>
            </div>
            <div class="row">
              <button class="btn" onclick="testKeys()" id="btn-test">Test connection</button>
              <button class="btn primary" onclick="saveKeys()">Save keys</button>
              <div class="spacer"></div>
              <button class="btn ghost sm down" onclick="clearKeys()">Remove saved keys</button>
            </div>
            <div id="set-msg"></div>
          </div>
        </div>
        <div class="card">
          <div class="card-h"><h3>Bot behaviour</h3></div>
          <div class="card-b">
            <div class="field">
              <label>Where trades come from</label>
              <div class="seg" id="set-src"><button data-s="bot" class="on">Bot strategies</button><button data-s="tradingview">TradingView alerts</button><button data-s="both">Both</button></div>
              <span class="hint" id="set-src-hint"></span>
            </div>
            <label class="check"><input type="checkbox" id="set-restart"><div><b>Auto-restart if the bot crashes</b><span>Replaces Task Scheduler's retry. Pauses after 5 crashes in 10 minutes.</span></div></label>
            <div class="row" style="margin-top:6px"><button class="btn primary" onclick="saveBehaviour()">Save</button></div>
            <div id="set-msg2"></div>
            <hr style="border:0;border-top:1px solid var(--border);margin:18px 0">
            <p class="t2" style="font-size:13px;margin:0 0 6px"><b>Run automatically every morning</b></p>
            <p class="muted" style="font-size:12px;margin:0">Point Windows Task Scheduler (8:20 AM) at:</p>
            <div class="copy-row" style="margin-top:8px"><code id="cmd-auto">python build_dashboard.py --autostart --no-browser</code><button class="btn sm" onclick="copyText('cmd-auto')">Copy</button></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ TRADINGVIEW ═══ -->
    <section class="view" id="view-tradingview">
      <h2>TradingView</h2>
      <p class="sub">Two ways to use the bot there: <b>forward-test</b> the Pine Script port on TradingView's own simulator (free), and/or let TradingView <b>alerts place Alpaca paper orders</b> through this bot (needs a paid TradingView plan for webhooks).</p>
      <div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)" id="tv-grid">
        <div class="card">
          <div class="card-h"><h3>1 · Pine Script strategy</h3><div class="right"><button class="btn sm" onclick="copyPine()">Copy script</button><button class="btn sm" onclick="downloadPine()">Download</button></div></div>
          <div class="card-b">
            <ol class="steps">
              <li><b>Open an NVDA chart on the 5-minute timeframe</b><span class="muted">The strategies were built for 5m bars, same as the bot.</span></li>
              <li><b>Pine Editor → paste → Save → Add to chart</b><span class="muted">Results appear in the Strategy Tester tab. TradingView simulates fills on live bars — that's its paper trading.</span></li>
              <li><b>Settings (gear) → Inputs</b><span class="muted">Toggle strategies, kill zones and risk. Paste your webhook passphrase if you'll use step 2.</span></li>
            </ol>
            <pre class="code" id="pine-code">Loading…</pre>
          </div>
        </div>
        <div class="card">
          <div class="card-h"><h3>2 · Alerts → Alpaca orders</h3><div class="right"><span class="pill" id="tv-state">Off</span></div></div>
          <div class="card-b">
            <label class="check"><input type="checkbox" id="tv-enabled"><div><b>Accept TradingView alerts</b><span>The bot opens a webhook receiver on this computer. Orders go through the same checks as manual trades.</span></div></label>
            <div class="field">
              <label for="tv-pass">Passphrase</label>
              <div class="input-row"><input class="input mono" id="tv-pass" spellcheck="false" placeholder="Click Generate"><button class="btn" onclick="genPass()">Generate</button><button class="btn" onclick="copyVal('tv-pass')">Copy</button></div>
              <span class="hint">Paste this into the Pine script's "Webhook passphrase" input. Anyone with your webhook URL + passphrase can trade, so keep it secret.</span>
            </div>
            <div class="row" style="gap:12px">
              <div class="field" style="flex:0 0 120px"><label for="tv-port">Local port</label><input class="input mono" id="tv-port" type="number" min="1024" max="65535"></div>
              <div class="field" style="flex:1"><label for="tv-url">Public tunnel URL (optional, for reference)</label><input class="input mono" id="tv-url" spellcheck="false" placeholder="https://xxxx.ngrok-free.app"></div>
            </div>
            <div class="row"><button class="btn primary" onclick="saveTV()">Save</button></div>
            <div id="tv-msg"></div>
            <hr style="border:0;border-top:1px solid var(--border);margin:18px 0">
            <ol class="steps">
              <li><b>Expose the receiver with a tunnel</b><span class="muted">TradingView can only call a public HTTPS address. Run one of:</span>
                <div class="copy-row" style="margin-top:6px"><code id="cmd-ngrok">ngrok http 8090</code><button class="btn sm" onclick="copyText('cmd-ngrok')">Copy</button></div>
                <div class="copy-row" style="margin-top:6px"><code id="cmd-cf">cloudflared tunnel --url http://127.0.0.1:8090</code><button class="btn sm" onclick="copyText('cmd-cf')">Copy</button></div></li>
              <li><b>Webhook URL for the alert</b>
                <div class="copy-row" style="margin-top:6px"><code id="tv-hook">https://YOUR-TUNNEL/tv_webhook</code><button class="btn sm" onclick="copyText('tv-hook')">Copy</button></div></li>
              <li><b>Create the alert</b><span class="muted">Alert → Condition: the strategy → "Order fills only". Notifications → Webhook URL (above). Message:</span>
                <div class="copy-row" style="margin-top:6px"><code id="tv-msgtpl">{{strategy.order.alert_message}}</code><button class="btn sm" onclick="copyText('tv-msgtpl')">Copy</button></div></li>
              <li><b>Settings → "Where trades come from" → TradingView alerts</b><span class="muted">Then restart the bot. "Both" also keeps the bot's own strategies on.</span></li>
            </ol>
          </div>
        </div>
      </div>
    </section>
  </main>
</div>

<!-- ═══ MANUAL TRADE MODAL ═══ -->
<div class="backdrop hidden" id="m-trade" onclick="if(event.target===this)closeTradeModal()">
  <div class="modal" role="dialog" aria-labelledby="m-trade-h">
    <div class="modal-h"><h3 id="m-trade-h">Manual trade</h3><button class="btn ghost sm x" onclick="closeTradeModal()" aria-label="Close">✕</button></div>
    <div class="modal-b">
      <div class="dirpick"><button class="long" id="m-long" onclick="setDir('bullish')">▲ LONG</button><button class="short" id="m-short" onclick="setDir('bearish')">▼ SHORT</button></div>
      <div class="livepx"><span class="muted">Live</span><b id="m-px">—</b><span class="muted" id="m-px-note" style="font-size:12px;margin-left:auto">fetching…</span></div>
      <div class="field"><label for="m-qty">Shares</label><input class="input mono" id="m-qty" type="number" min="1" value="10" oninput="updatePreview()"></div>
      <label class="check" style="padding-top:0"><input type="checkbox" id="m-atr" checked onchange="toggleAtr()"><div><b>Stop &amp; target from ATR</b><span id="m-atr-note">Stop = multiplier × ATR, target = 1.5 × stop distance</span></div></label>
      <div id="m-atr-row" class="field">
        <div class="seg" id="m-mult"><button data-x="0.5">0.5×</button><button data-x="1" class="on">1×</button><button data-x="1.5">1.5×</button><button data-x="2">2×</button><button data-x="2.5">2.5×</button></div>
      </div>
      <div id="m-manual" class="hidden">
        <div class="row" style="gap:12px">
          <div class="field" style="flex:1"><label for="m-stop">Stop</label><input class="input mono" id="m-stop" type="number" step="0.01" oninput="updatePreview()"></div>
          <div class="field" style="flex:1"><label for="m-target">Target</label><input class="input mono" id="m-target" type="number" step="0.01" oninput="updatePreview()"></div>
        </div>
      </div>
      <div class="preview" id="m-preview">Pick a direction.</div>
      <div class="field" style="margin-top:14px">
        <label>Management</label>
        <div class="seg" id="m-managed"><button data-v="1" class="on">Bot manages exits</button><button data-v="0">Log only</button></div>
      </div>
      <label class="check" id="m-trail-row"><input type="checkbox" id="m-trail"><div><b>Trailing stop</b><span>Breakeven at 1R, then trails at 2R</span></div></label>
      <div id="m-msg"></div>
    </div>
    <div class="modal-f"><button class="btn" onclick="closeTradeModal()">Cancel</button><button class="btn primary" id="m-submit" onclick="submitTrade()">Place order</button></div>
  </div>
</div>

<!-- ═══ CLOSE TRADE MODAL ═══ -->
<div class="backdrop hidden" id="m-close" onclick="if(event.target===this)closeCloseModal()">
  <div class="modal" role="dialog" aria-labelledby="m-close-h">
    <div class="modal-h"><h3 id="m-close-h">Close trade</h3><button class="btn ghost sm x" onclick="closeCloseModal()" aria-label="Close">✕</button></div>
    <div class="modal-b">
      <p class="t2" style="margin-top:0">The bot cancels this trade's open orders and market-closes the position on Alpaca, then waits for confirmation.</p>
      <div class="field"><label for="c-pnl">Realized P&amp;L (optional)</label><input class="input mono" id="c-pnl" type="number" step="0.01" placeholder="Leave blank to estimate from last price"></div>
      <div id="c-msg"></div>
    </div>
    <div class="modal-f"><button class="btn" onclick="closeCloseModal()">Cancel</button><button class="btn stop" id="c-submit" onclick="submitClose()">Close position</button></div>
  </div>
</div>

<!-- ═══ GO LIVE MODAL ═══ -->
<div class="backdrop hidden" id="m-live">
  <div class="modal" role="dialog" aria-labelledby="m-live-h">
    <div class="modal-h"><h3 id="m-live-h">Switch to live money?</h3></div>
    <div class="modal-b">
      <p style="margin-top:0">The bot will place <b>real orders with real money</b> on your Alpaca live account. Shorts have no stop on Alpaca's side — if the bot stops running, a short is unprotected.</p>
      <p class="t2">Also turn on PDT protection in <span class="mono">CONFIG</span> if the account is under $25k, and use your <b>live</b> API keys (paper keys won't work).</p>
      <div class="field"><label for="live-confirm">Type LIVE to confirm</label><input class="input mono" id="live-confirm" autocomplete="off"></div>
    </div>
    <div class="modal-f"><button class="btn" onclick="cancelLive()">Stay on paper</button><button class="btn stop" onclick="confirmLive()">Switch to live</button></div>
  </div>
</div>

<div class="toast hidden" id="toast"></div>
"""


# ═══════════════════════════════════════════════════════════════
# UI — JS
# ═══════════════════════════════════════════════════════════════

JS = r"""
const APP = { standalone: __STANDALONE__, version: "__VERSION__" };
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = (v, d=2) => (v == null || isNaN(v)) ? '—' : '$' + Number(v).toLocaleString('en-US', {minimumFractionDigits:d, maximumFractionDigits:d});
const signed = v => (v >= 0 ? '+' : '−') + money(Math.abs(v));
const cap = s => (s || '—').toString().replace(/_/g, ' ').toUpperCase();
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

let D = null, botStatus = null, settings = null;

async function api(path, body, opts = {}) {
  const init = { signal: AbortSignal.timeout(opts.timeout || 10000) };
  if (body !== undefined) {
    init.method = 'POST';
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  try {
    const r = await fetch(path, init);
    const ct = r.headers.get('Content-Type') || '';
    const data = ct.includes('json') ? await r.json() : await r.text();
    if (data && typeof data === 'object' && !Array.isArray(data) && !r.ok && data.ok === undefined) data.ok = false;
    return { status: r.status, data };
  } catch (e) {
    return { status: 0, data: { ok: false, error: e.name === 'TimeoutError' ? 'Timed out' : 'Not reachable' } };
  }
}

function toast(msg, kind = 'ok') {
  const t = $('#toast');
  t.className = 'toast ' + kind; t.textContent = msg;
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add('hidden'), 4500);
}
function showMsg(el, msg, ok) { $(el).innerHTML = msg ? `<div class="msg ${ok ? 'ok' : 'err'}">${esc(msg)}</div>` : ''; }

/* ── theme ───────────────────────────────────────────────── */
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem('nvda-theme', t); } catch (e) {}
  if (chart) { chart.destroy(); chart = null; initChart(); renderChart(); }
}
function toggleTheme() { setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'); }
(function () { let t = 'dark'; try { t = localStorage.getItem('nvda-theme') || 'dark'; } catch (e) {} document.documentElement.dataset.theme = t; })();

/* ── navigation ──────────────────────────────────────────── */
function showView(v) {
  if (!$('#view-' + v)) v = 'overview';
  $$('.view').forEach(e => e.classList.toggle('active', e.id === 'view-' + v));
  $$('.nav').forEach(e => e.classList.toggle('active', e.dataset.view === v));
  if (location.hash !== '#' + v) history.replaceState(null, '', '#' + v);
  if (v === 'tradingview') loadPine();
  if (v === 'console') { pollConsole(); scrollConsole(); }
  if (v === 'overview' && chart) chart.resize();
}
$$('.nav').forEach(b => b.addEventListener('click', () => showView(b.dataset.view)));

/* ── chart ───────────────────────────────────────────────── */
let chart = null, range = '1d', hist = [], sixMonth = null;

const refLines = {
  id: 'refLines',
  afterDatasetsDraw(c) {
    const lines = c.options.plugins.refLines.lines || [];
    const { ctx, chartArea: a, scales: { y } } = c;
    ctx.save();
    ctx.font = '600 11px ' + cssv('--mono');
    lines.forEach(l => {
      const py = y.getPixelForValue(l.v);
      if (py < a.top || py > a.bottom) return;
      ctx.strokeStyle = l.color; ctx.lineWidth = 1.25; ctx.setLineDash(l.dash || [5, 4]);
      ctx.beginPath(); ctx.moveTo(a.left, py); ctx.lineTo(a.right, py); ctx.stroke(); ctx.setLineDash([]);
      const txt = l.label + ' ' + l.v.toFixed(2), w = ctx.measureText(txt).width + 10;
      ctx.fillStyle = l.color; ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(a.right - w, py - 9, w, 18, 4); else ctx.rect(a.right - w, py - 9, w, 18);
      ctx.fill(); ctx.fillStyle = l.ink; ctx.fillText(txt, a.right - w + 5, py + 4);
    });
    const act = c.tooltip && c.tooltip.getActiveElements && c.tooltip.getActiveElements();
    if (act && act.length) {
      const x = act[0].element.x;
      ctx.strokeStyle = cssv('--muted'); ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke();
    }
    ctx.restore();
  }
};

function initChart() {
  if (typeof Chart === 'undefined') { $('#chart-empty').textContent = 'Chart library failed to load (no internet?)'; return; }
  const ctx = $('#chart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{ data: [], borderColor: cssv('--line'), backgroundColor: cssv('--fill'), borderWidth: 2,
      pointRadius: 0, pointHoverRadius: 5, pointHoverBorderWidth: 2, pointHoverBorderColor: cssv('--panel'), pointHoverBackgroundColor: cssv('--line'),
      fill: true, tension: 0.25, spanGaps: true }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      layout: { padding: { right: 4 } },
      plugins: {
        legend: { display: false }, refLines: { lines: [] },
        tooltip: { backgroundColor: cssv('--panel'), titleColor: cssv('--text-2'), bodyColor: cssv('--text'), borderColor: cssv('--border'),
          borderWidth: 1, padding: 10, displayColors: false, titleFont: { family: cssv('--mono'), size: 11 }, bodyFont: { family: cssv('--mono'), size: 13, weight: '600' },
          callbacks: { title: it => it.length ? fullLabel(it[0].dataIndex) : '', label: c => money(c.parsed.y) } }
      },
      scales: {
        x: { grid: { display: false }, border: { color: cssv('--border') },
          ticks: { color: cssv('--muted'), font: { family: cssv('--mono'), size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 7 } },
        y: { position: 'left', grid: { color: cssv('--grid') }, border: { display: false },
          ticks: { color: cssv('--muted'), font: { family: cssv('--mono'), size: 10 }, callback: v => '$' + Number(v).toFixed(0), maxTicksLimit: 6 } }
      }
    },
    plugins: [refLines]
  });
}

const etToday = () => new Date().toLocaleString('sv-SE', { timeZone: 'America/New_York' }).slice(0, 10);
const minsOf = t => { const [d, tm] = t.split('T'); const [y, mo, da] = d.split('-').map(Number); const [h, mi] = (tm || '0:0').split(':').map(Number); return Date.UTC(y, mo - 1, da, h, mi) / 60000; };
const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
let shown = [];

function thin(pts, max) {
  if (pts.length <= max) return pts;
  const step = pts.length / max, out = [];
  for (let i = 0; i < max; i++) out.push(pts[Math.floor(i * step)]);
  out[out.length - 1] = pts[pts.length - 1];
  return out;
}
function lastDates(pts, n) {
  const dates = [...new Set(pts.map(p => p.t.slice(0, 10)))].sort().slice(-n);
  const set = new Set(dates);
  return pts.filter(p => set.has(p.t.slice(0, 10)));
}
function pointsFor(r) {
  if (r === '6m') {
    if (sixMonth === null) { loadSixMonth(); return null; }
    return sixMonth.map(p => ({ t: p.t, p: p.p }));
  }
  const pts = hist.filter(p => p && p.t && p.p > 0).sort((a, b) => a.t < b.t ? -1 : a.t > b.t ? 1 : 0);
  if (!pts.length) return [];
  if (r === '1h' || r === '1d') {
    let day = pts.filter(p => p.t.slice(0, 10) === etToday());
    if (!day.length) day = lastDates(pts, 1);
    if (r === '1h') { const end = minsOf(day[day.length - 1].t); day = day.filter(p => minsOf(p.t) >= end - 60); }
    return day;
  }
  if (r === '5d') return thin(lastDates(pts, 5), 500);
  if (r === '1m') return thin(lastDates(pts, 22), 500);
  return pts;
}
function tickLabel(t, r) {
  const d = t.slice(0, 10), tm = t.slice(11, 16);
  if (r === '1h' || r === '1d') return tm;
  if (r === '6m') return MON[+d.slice(5, 7) - 1] + ' ' + (+d.slice(8, 10));
  return d.slice(5, 7) + '/' + d.slice(8, 10);
}
function fullLabel(i) {
  const p = shown[i]; if (!p) return '';
  return p.t.length > 10 ? p.t.slice(0, 10) + ' ' + p.t.slice(11, 16) + ' ET' : p.t;
}

function renderChart() {
  if (!chart) return;
  const pts = pointsFor(range);
  const empty = $('#chart-empty');
  if (pts === null) { empty.textContent = 'Loading 6 months of daily bars…'; empty.classList.remove('hidden'); return; }
  if (!pts.length) {
    empty.textContent = range === '6m' ? 'Daily bars unavailable — the bot must be running' : 'No price data for this range yet';
    empty.classList.remove('hidden');
    chart.data.labels = []; chart.data.datasets[0].data = []; chart.update('none'); $('#chart-range').textContent = '—';
    return;
  }
  empty.classList.add('hidden');
  shown = pts;
  let prevDay = null;
  chart.data.labels = pts.map(p => {
    if (range === '5d' || range === '1m') { const d = p.t.slice(0, 10); const lbl = d !== prevDay ? tickLabel(p.t, range) : ''; prevDay = d; return lbl; }
    return tickLabel(p.t, range);
  });
  chart.options.scales.x.ticks.autoSkip = !(range === '5d' || range === '1m');
  chart.data.datasets[0].data = pts.map(p => p.p);

  const vals = pts.map(p => p.p), lo = Math.min(...vals), hi = Math.max(...vals);
  const lines = [];
  const intraday = range === '1h' || range === '1d';
  const ink = cssv('--on-accent');
  if (D && intraday && D.last_vwap > 0) lines.push({ v: D.last_vwap, label: 'VWAP', color: cssv('--accent'), ink, dash: [2, 3] });
  const tr = D && (D.active_trades || [])[0];
  if (tr && intraday) {
    lines.push({ v: tr.entry, label: 'Entry', color: cssv('--text-2'), ink: cssv('--panel') });
    lines.push({ v: tr.stop, label: 'Stop', color: cssv('--down'), ink });
    lines.push({ v: tr.target, label: 'Target', color: cssv('--up'), ink });
  }
  const keep = lines.filter(l => l.v > 0 && l.v > lo * 0.97 && l.v < hi * 1.03);
  chart.options.plugins.refLines.lines = keep;
  const all = vals.concat(keep.map(l => l.v));
  const pad = (Math.max(...all) - Math.min(...all)) * 0.06 || 1;
  chart.options.scales.y.suggestedMin = Math.min(...all) - pad;
  chart.options.scales.y.suggestedMax = Math.max(...all) + pad;
  chart.update('none');
  const first = pts[0].p, last = pts[pts.length - 1].p, ch = last - first;
  $('#chart-range').innerHTML = `${pts.length} pts · low ${money(lo)} · high ${money(hi)} · <span class="${ch >= 0 ? 'up' : 'down'}">${ch >= 0 ? '+' : '−'}${money(Math.abs(ch))} (${(ch / first * 100).toFixed(2)}%)</span>`;
}
async function loadSixMonth() {
  if (loadSixMonth.busy) return; loadSixMonth.busy = true;
  const r = await api('/daily_history', undefined, { timeout: 25000 });
  sixMonth = Array.isArray(r.data) ? r.data : [];
  loadSixMonth.busy = false;
  if (!sixMonth.length) setTimeout(() => { sixMonth = null; }, 30000);
  renderChart();
}
$$('#range-seg button').forEach(b => b.addEventListener('click', () => {
  $$('#range-seg button').forEach(x => x.classList.toggle('on', x === b)); range = b.dataset.r; renderChart();
}));

/* ── kill zones ──────────────────────────────────────────── */
const KZ = [['09:30', '11:00'], ['12:00', '13:00'], ['14:00', '15:55']];
const hm = s => { const [h, m] = s.split(':').map(Number); return h * 60 + m; };
function renderKZ() {
  const open = hm('09:30'), close = hm('16:00'), span = close - open;
  const et = new Date().toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false });
  const [h, m] = et.split(':').map(Number), now = h * 60 + m;
  let html = '';
  KZ.forEach(([s, e]) => {
    const a = hm(s), b = hm(e);
    const cls = now >= a && now < b ? 'now' : now >= b ? 'past' : '';
    html += `<div class="zone ${cls}" style="left:${(a - open) / span * 100}%;width:${(b - a) / span * 100}%" title="${s}–${e} ET">${window.innerWidth < 600 ? '' : s + '–' + e}</div>`;
  });
  if (now >= open && now <= close) html += `<div class="nowline" style="left:${(now - open) / span * 100}%"></div>`;
  $('#kz').innerHTML = html;
  if (!$('#kz-labels').childElementCount)
    $('#kz-labels').innerHTML = ['09:30', '11:00', '12:00', '13:00', '14:00', '16:00']
      .map(t => `<span style="left:${(hm(t) - open) / span * 100}%">${t}</span>`).join('');
  let note = '';
  if (D) note = D.in_kill_zone ? 'In kill zone — scanning' : D.next_kz ? `Next: ${D.next_kz} ET (${D.mins_to_kz ?? '?'} min)` : 'All kill zones done';
  $('#kz-next').textContent = note;
}

/* ── data poll ───────────────────────────────────────────── */
async function pollData() {
  const r = await api('/data', undefined, { timeout: 6000 });
  if (r.status === 200 && r.data && r.data.status !== undefined) {
    D = r.data;
    if (Array.isArray(D.price_history) && D.price_history.length) hist = D.price_history;
    renderData();
  } else {
    D = null;
    renderOffline(r.data && r.data.error);
  }
  renderChart(); renderKZ(); renderBot(); renderBanners();
}
async function loadHistoryOnce() {
  const r = await api('/history', undefined, { timeout: 8000 });
  if (Array.isArray(r.data) && r.data.length && !hist.length) { hist = r.data; renderChart(); }
}

function setText(id, v, cls) { const e = $(id); e.textContent = v; if (cls !== undefined) e.className = e.className.replace(/\b(up|down|warn|t2)\b/g, '').trim() + (cls ? ' ' + cls : ''); }
function dirCls(v) { v = (v || '').toLowerCase(); return v.includes('bull') ? 'up' : v.includes('bear') ? 'down' : 'warn'; }

function renderData() {
  const d = D;
  const px = d.last_price || 0;
  $('#tb-price').textContent = px ? money(px) : '—';
  const today = (hist || []).filter(p => p.t && p.t.slice(0, 10) === etToday());
  if (px && today.length) {
    const ch = px - today[0].p;
    $('#tb-chg').textContent = `${ch >= 0 ? '+' : '−'}${Math.abs(ch).toFixed(2)} (${(ch / today[0].p * 100).toFixed(2)}%)`;
    $('#tb-chg').className = 'chg ' + (ch >= 0 ? 'up' : 'down');
  }
  const mk = $('#tb-market');
  mk.className = 'pill ' + (d.market_open ? (d.in_kill_zone ? 'ok' : 'wait') : 'bad');
  mk.lastElementChild.textContent = d.market_open ? (d.in_kill_zone ? `Kill zone ${d.current_kz || ''}` : 'Market open') : 'Market closed';

  const eq = d.equity || 0, bod = d.bod_equity || 0;
  const dayPnl = eq > 0 && bod > 0 ? eq - bod : (d.daily_pnl || 0);
  setText('#k-eq', eq ? money(eq, 0) : '—');
  setText('#k-eq-s', eq && bod ? 'Today ' + signed(dayPnl) : '—', eq && bod ? (dayPnl >= 0 ? 'up' : 'down') : '');

  const open = d.active_trades || [];
  const unreal = open.reduce((s, t) => s + (parseFloat(t.pnl) || 0), 0);
  if (open.length) { setText('#k-pnl', signed(unreal), unreal >= 0 ? 'up' : 'down'); setText('#k-pnl-s', `${open.length} open position${open.length > 1 ? 's' : ''}`); }
  else { setText('#k-pnl', '—', ''); setText('#k-pnl-s', d.closed_trade ? `Last: ${d.closed_trade.outcome} ${signed(parseFloat(d.closed_trade.pnl) || 0)}` : 'No open trade'); }

  setText('#k-atr', d.last_atr ? '$' + Number(d.last_atr).toFixed(3) : '—');
  setText('#k-atr-s', d.last_atr && px ? `${(d.last_atr / px * 100).toFixed(2)}% of price` : 'Volatility per bar');
  setText('#k-vwap', d.last_vwap ? money(d.last_vwap) : '—');
  if (d.last_vwap && px) { const dv = px - d.last_vwap; setText('#k-vwap-s', `Price ${dv >= 0 ? 'above' : 'below'} by ${money(Math.abs(dv))}`, dv >= 0 ? 'up' : 'down'); }
  setText('#k-trend', cap(d.last_trend), dirCls(d.last_trend));
  setText('#k-trend-s', 'QQQ ' + cap(d.last_qqq), dirCls(d.last_qqq));
  setText('#k-mtf', cap(d.mtf_bias), dirCls(d.mtf_bias));
  setText('#k-mtf-s', `Week ${cap(d.weekly_trend)} · Month ${cap(d.monthly_trend)}`);

  $('#st-status').textContent = d.status || '—';
  setText('#st-strat', d.active_strategy || '—');
  setText('#st-src', settings ? ({ bot: 'Bot strategies', tradingview: 'TradingView', both: 'Bot + TradingView' })[settings.signal_source] : (botStatus ? botStatus.signal_source : '—'));
  setText('#st-scan', d.last_scan_time || '—');
  setText('#st-candles', `${d.last_candles || 0} · ${d.fetch_errors || 0}`);
  setText('#st-setups', `${d.fvgs_today || 0} (best ${d.best_score || 0}/9)`);

  // trades
  $('#nav-trades').textContent = open.length;
  $('#ov-trades-title').textContent = open.length > 1 ? `Active trades (${open.length})` : open.length ? 'Active trade' : d.closed_trade ? 'Last trade' : 'Active trade';
  const cards = open.map(tradeCard).join('');
  $('#ov-trades').innerHTML = cards || (d.closed_trade ? tradeCard(d.closed_trade) : `<div class="empty"><div class="ico">⏳</div>No active trade</div>`);
  $('#tr-open').innerHTML = cards || '<div class="empty">No open trades</div>';
  $('#tr-closed').innerHTML = d.closed_trade ? tradeCard(d.closed_trade) : '<div class="empty">Nothing closed yet today</div>';

  // signals
  const sigs = (d.all_fvgs || []).slice().reverse();
  $('#nav-signals').textContent = sigs.length;
  $('#sig-list').innerHTML = sigs.length ? sigs.map(f => `
    <div class="sig">
      <span class="dir ${f.type === 'bullish' ? 'long' : 'short'}">${f.type === 'bullish' ? '▲ LONG' : '▼ SHORT'}</span>
      <div><b class="mono">${esc(f.time)}</b> <span class="t2">· size $${esc(f.size)} · entry ${money(f.entry_zone)}</span><div class="muted" style="font-size:12px;margin-top:2px">${esc(f.notes)}</div></div>
      <div style="text-align:right"><div class="pips">${Array.from({ length: 9 }, (_, i) => `<i class="${i < f.score ? 'on' : ''}"></i>`).join('')}</div><div class="mono muted" style="font-size:11px;margin-top:3px">${esc(f.score)}/9</div></div>
    </div>`).join('') : '<div class="empty">No setups detected yet today</div>';

  // activity log
  const log = d.log || [];
  $('#ov-log').innerHTML = log.length ? log.map(e => `
    <div class="e"><span class="mono muted">${esc((e.time || '').split(' ')[0])}</span><span class="lvl ${esc(e.level)}">${esc(e.level)}</span><span>${esc(e.message)}</span></div>`).join('') : '<div class="empty">No activity yet</div>';
}

function tradeCard(t) {
  const long = t.fvg_type === 'bullish';
  const pnl = parseFloat(t.pnl) || 0;
  const isOpen = !t.outcome || t.outcome === 'OPEN';
  const manual = t.strategy === 'MANUAL';
  const px = D ? D.last_price : 0;
  let prog = '';
  if (isOpen && t.stop && t.target && px) {
    const lo = Math.min(t.stop, t.target), hi = Math.max(t.stop, t.target), span = hi - lo || 1;
    const pos = v => Math.max(0, Math.min(100, (v - lo) / span * 100));
    const left = long ? 'Stop' : 'Target', right = long ? 'Target' : 'Stop';
    prog = `<div class="prog ${long ? '' : 'short'}"><span class="en" style="left:${pos(t.entry)}%"></span><span class="mk" style="left:${pos(px)}%"></span></div>
      <div class="prog-l"><span>${left} ${money(lo)}</span><span>now ${money(px)}</span><span>${right} ${money(hi)}</span></div>`;
  }
  const stopLbl = t.stop && t.entry && t.stop.toFixed(2) === t.entry.toFixed(2) ? 'Stop (BE)' : 'Stop';
  return `<div class="trade">
    <div class="top"><span class="dir ${long ? 'long' : 'short'}">${long ? '▲ LONG' : '▼ SHORT'}</span>
      <span class="tag">${manual ? 'MANUAL' : esc(t.strategy || 'BOT')}</span>
      ${t.days_open > 0 ? `<span class="tag warn">${esc(t.days_open)}d open</span>` : ''}
      <span class="pnl ${pnl >= 0 ? 'up' : 'down'}">${signed(pnl)}</span></div>
    <div class="kv"><div>Entry<b>${money(t.entry)}</b></div><div>${stopLbl}<b class="down">${money(t.stop)}</b></div><div>Target<b class="up">${money(t.target)}</b></div><div>Qty<b>${esc(t.qty)}</b></div></div>
    ${prog}
    <div class="row" style="margin-top:10px;font-size:12px"><span class="muted">${esc(t.opened_at || '')}</span><div class="spacer"></div>
      ${isOpen ? '' : `<span class="tag">${esc(t.outcome)}</span>`}
      ${manual && isOpen ? `<button class="btn stop sm" onclick="openCloseModal('${esc(t.id || '')}')">Close</button>` : ''}</div>
  </div>`;
}

function renderOffline(err) {
  const mk = $('#tb-market'); mk.className = 'pill'; mk.lastElementChild.textContent = 'No data';
  $('#st-status').textContent = APP.standalone ? 'Bot not responding' : (botStatus && botStatus.running ? 'Bot starting up…' : 'Bot is stopped');
}

/* ── bot control (panel only) ────────────────────────────── */
async function pollBot() {
  if (APP.standalone) return;
  const r = await api('/api/bot/status', undefined, { timeout: 4000 });
  if (r.status !== 200) { botStatus = null; renderBot(); return; }
  botStatus = r.data; renderBot();
}
function fmtUp(s) { const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return h ? `${h}h ${m}m` : `${m}m ${s % 60}s`; }
function renderBot() {
  const pill = $('#tb-bot'), txt = $('#tb-bot-text'), btn = $('#btn-bot');
  if (APP.standalone) { pill.className = 'pill ' + (D ? 'ok' : 'bad'); txt.textContent = D ? 'Bot running' : 'Bot offline'; return; }
  const b = botStatus;
  if (!b) { pill.className = 'pill bad'; txt.textContent = 'Panel offline'; btn.disabled = true; return; }
  btn.disabled = false;
  if (b.running) {
    pill.className = 'pill ' + (D ? 'ok' : 'wait'); txt.textContent = D ? `Running · ${fmtUp(b.uptime_s)}` : 'Starting…';
    btn.className = 'btn stop panel-only'; btn.textContent = '■ Stop Bot';
  } else if (D) {
    pill.className = 'pill ok'; txt.textContent = 'Running outside panel';
    btn.className = 'btn go panel-only'; btn.textContent = '▶ Start Bot';
  } else {
    pill.className = 'pill ' + (b.desired ? 'wait' : 'bad'); txt.textContent = b.desired ? 'Restarting…' : 'Stopped';
    btn.className = 'btn go panel-only'; btn.textContent = '▶ Start Bot';
  }
  const mode = b.mode || 'paper', m = $('#tb-mode');
  m.className = 'pill ' + (mode === 'live' ? 'live' : 'paper'); m.textContent = mode === 'live' ? 'LIVE MONEY' : 'PAPER';
  $('#side-foot').textContent = b.restarts ? `Auto-restarts: ${b.restarts}` : 'Data refreshes every 5s';
}
async function toggleBot() {
  const btn = $('#btn-bot'); btn.disabled = true;
  if (botStatus && botStatus.running) {
    const open = D && (D.active_trades || []).length;
    if (open && !confirm('A position is open. Stopping the bot leaves it open on Alpaca.\n\nLongs keep their bracket stop/target on Alpaca. SHORTS HAVE NO PROTECTION while the bot is stopped.\n\nStop anyway?')) { btn.disabled = false; return; }
    const r = await api('/api/bot/stop', {}, { timeout: 20000 });
    toast(r.data.ok ? 'Bot stopped' : (r.data.error || 'Could not stop the bot'), r.data.ok ? 'ok' : 'err');
  } else {
    const r = await api('/api/bot/start', {});
    if (r.data.ok) toast('Bot starting — watch the Console tab');
    else { toast(r.data.error || 'Could not start the bot', 'err'); if ((r.data.error || '').includes('keys')) showView('settings'); }
  }
  await pollBot(); btn.disabled = false;
}

function renderBanners() {
  const out = [];
  if (!APP.standalone && botStatus) {
    if (!botStatus.keys_set) out.push(`<div class="banner warn"><b>Add your Alpaca keys to get started.</b><span class="grow t2">They're saved on this computer only.</span><button class="btn primary sm" onclick="showView('settings')">Open Settings</button></div>`);
    else if (!botStatus.running && D) out.push(`<div class="banner warn"><span class="grow"><b>A bot started outside this panel is running</b> <span class="t2">(e.g. an old Task Scheduler entry for nvda_autotrader.py). Data is live, but Start/Stop can't control it.</span></span></div>`);
    else if (!botStatus.running && !botStatus.desired) out.push(`<div class="banner"><span class="grow"><b>The bot is stopped.</b> <span class="t2">${esc(botStatus.last_exit_note || 'Click Start Bot to begin scanning.')}</span></span><button class="btn go sm" onclick="toggleBot()">▶ Start Bot</button></div>`);
    if (botStatus.running && botStatus.saved_mode !== botStatus.mode) out.push(`<div class="banner warn"><span class="grow">Settings changed to <b>${esc(botStatus.saved_mode.toUpperCase())}</b> — restart the bot to apply.</span><button class="btn sm" onclick="restartBot()">Restart now</button></div>`);
    if (botStatus.mode === 'live') out.push(`<div class="banner live"><b>LIVE MONEY</b><span class="grow">Orders placed by the bot use real funds.</span></div>`);
  }
  if (APP.standalone) out.push(`<div class="banner"><span class="grow t2">Bot-only view. Run <span class="mono">python build_dashboard.py</span> for Start/Stop, Settings and the console.</span></div>`);
  const html = out.join('');
  if ($('#banners').innerHTML !== html) $('#banners').innerHTML = html;
}
async function restartBot() {
  const r = await api('/api/bot/restart', {}, { timeout: 25000 });
  toast(r.data.ok ? 'Bot restarted with new settings' : (r.data.error || 'Restart failed'), r.data.ok ? 'ok' : 'err');
  pollBot();
}

/* ── console ─────────────────────────────────────────────── */
let conAfter = 0, conLines = [], conFilter = 'all';
const lvlOf = l => l.startsWith('[panel') ? 'PANEL' : ((l.match(/\] (INFO|WARN|ERROR|TRADE|CRITICAL):/) || [])[1] || 'INFO');
async function pollConsole() {
  if (APP.standalone) return;
  const r = await api('/api/bot/console?after=' + conAfter, undefined, { timeout: 4000 });
  if (r.status !== 200) return;
  if (r.data.last < conAfter) { conAfter = 0; conLines = []; }
  if (!r.data.lines.length) return;
  conAfter = r.data.lines[r.data.lines.length - 1].n;
  conLines = conLines.concat(r.data.lines.map(x => x.line)).slice(-3000);
  renderConsole();
}
function renderConsole() {
  const el = $('#console');
  const rows = conLines.filter(l => conFilter === 'all' || lvlOf(l) === conFilter || (conFilter === 'ERROR' && lvlOf(l) === 'CRITICAL'));
  el.innerHTML = rows.length ? rows.map(l => `<div class="${lvlOf(l)}">${esc(l)}</div>`).join('') : '<span class="muted">Nothing here yet.</span>';
  scrollConsole();
}
function scrollConsole() { if ($('#con-follow').checked) { const el = $('#console'); el.scrollTop = el.scrollHeight; } }
$$('#con-filter button').forEach(b => b.addEventListener('click', () => { $$('#con-filter button').forEach(x => x.classList.toggle('on', x === b)); conFilter = b.dataset.f; renderConsole(); }));

/* ── settings ────────────────────────────────────────────── */
let pendingMode = 'paper';
function segSet(sel, attr, val) { $$(sel + ' button').forEach(b => b.classList.toggle('on', b.dataset[attr] === val)); }
async function loadSettings() {
  if (APP.standalone) return;
  const r = await api('/api/settings');
  if (r.status !== 200) return;
  settings = r.data;
  pendingMode = settings.trading_mode;
  segSet('#set-mode', 'm', settings.trading_mode);
  segSet('#set-src', 's', settings.signal_source);
  srcHint(settings.signal_source);
  $('#set-restart').checked = settings.auto_restart;
  $('#set-file').textContent = settings.settings_file;
  $('#set-key').placeholder = settings.has_api_key ? settings.api_key_masked + '  (saved)' : 'PK…';
  $('#set-secret').placeholder = settings.has_secret ? '•••••••• (saved)' : 'Paste secret key';
  const ks = $('#set-keystate');
  ks.className = 'pill ' + (settings.has_api_key && settings.has_secret ? 'ok' : 'bad');
  ks.innerHTML = `<span class="dot"></span>${settings.has_api_key && settings.has_secret ? 'Keys saved' : 'No keys'}`;
  $('#tv-enabled').checked = settings.tv_enabled;
  $('#tv-pass').value = settings.tv_passphrase || '';
  $('#tv-port').value = settings.tv_port;
  $('#tv-url').value = settings.tv_public_url || '';
  renderTVInfo();
}
function srcHint(s) {
  $('#set-src-hint').textContent = {
    bot: 'The bot runs its own 6 strategies in the kill zones (current behaviour).',
    tradingview: 'The bot only executes TradingView alerts. Its own strategies stay off. Turn on alerts in the TradingView tab.',
    both: 'Both the bot\'s strategies and TradingView alerts can open trades (one position at a time).'
  }[s];
}
$$('#set-mode button').forEach(b => b.addEventListener('click', () => {
  if (b.dataset.m === 'live' && settings && settings.trading_mode !== 'live') { $('#live-confirm').value = ''; $('#m-live').classList.remove('hidden'); return; }
  pendingMode = b.dataset.m; segSet('#set-mode', 'm', pendingMode);
  if (settings && settings.trading_mode === 'live' && pendingMode === 'paper') saveKeys(true);
}));
$$('#set-src button').forEach(b => b.addEventListener('click', () => { segSet('#set-src', 's', b.dataset.s); srcHint(b.dataset.s); }));
function cancelLive() { $('#m-live').classList.add('hidden'); segSet('#set-mode', 'm', pendingMode); }
async function confirmLive() {
  if ($('#live-confirm').value.trim() !== 'LIVE') { toast('Type LIVE to confirm', 'err'); return; }
  $('#m-live').classList.add('hidden');
  const r = await api('/api/settings', { trading_mode: 'live', confirm_live: true });
  if (r.data.ok) { toast('Switched to LIVE. Enter your live keys and restart the bot.'); pendingMode = 'live'; }
  else toast(r.data.error || 'Could not switch', 'err');
  loadSettings();
}
function toggleSecret() { const i = $('#set-secret'); i.type = i.type === 'password' ? 'text' : 'password'; $('#btn-show').textContent = i.type === 'password' ? 'Show' : 'Hide'; }
async function testKeys() {
  const b = $('#btn-test'); b.disabled = true; b.textContent = 'Testing…';
  const r = await api('/api/test_keys', { alpaca_api_key: $('#set-key').value, alpaca_secret_key: $('#set-secret').value, trading_mode: pendingMode }, { timeout: 20000 });
  const d = r.data;
  showMsg('#set-msg', d.ok ? `Connected to ${d.mode.toUpperCase()} account ${d.account} · equity ${money(d.equity)} · status ${d.status}${d.pattern_day_trader ? ' · flagged PDT' : ''}` : d.error, d.ok);
  b.disabled = false; b.textContent = 'Test connection';
}
async function saveKeys(quiet) {
  const body = { trading_mode: pendingMode };
  const k = $('#set-key').value.trim(), s = $('#set-secret').value.trim();
  if (k) body.alpaca_api_key = k;
  if (s) body.alpaca_secret_key = s;
  const r = await api('/api/settings', body);
  if (r.data.ok) {
    $('#set-key').value = ''; $('#set-secret').value = '';
    if (!quiet) showMsg('#set-msg', r.data.restart_needed ? 'Saved. Restart the bot to use the new keys.' : 'Saved. Click Start Bot when ready.', true);
    loadSettings(); pollBot();
  } else showMsg('#set-msg', r.data.error || 'Could not save', false);
}
async function clearKeys() {
  if (!confirm('Remove the saved Alpaca keys from this computer?')) return;
  const r = await api('/api/settings', { clear_keys: true });
  showMsg('#set-msg', r.data.ok ? 'Keys removed.' : r.data.error, r.data.ok); loadSettings(); pollBot();
}
async function saveBehaviour() {
  const src = ($$('#set-src button').find(b => b.classList.contains('on')) || {}).dataset?.s || 'bot';
  const r = await api('/api/settings', { signal_source: src, auto_restart: $('#set-restart').checked });
  showMsg('#set-msg2', r.data.ok ? (r.data.restart_needed ? 'Saved. Restart the bot to apply.' : 'Saved.') : r.data.error, r.data.ok);
  loadSettings();
}

/* ── TradingView ─────────────────────────────────────────── */
let pineText = null;
async function loadPine() {
  if (pineText !== null) return;
  const r = await api('/api/pine');
  if (APP.standalone || r.status !== 200) { $('#pine-code').textContent = 'Open nvda_strategy.pine from the project folder (served by the control panel only).'; return; }
  pineText = r.data; $('#pine-code').textContent = pineText;
}
async function copyPine() { await loadPine(); if (pineText) { await navigator.clipboard.writeText(pineText); toast('Pine Script copied — paste it into TradingView\'s Pine Editor'); } }
async function downloadPine() {
  await loadPine(); if (!pineText) return;
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([pineText], { type: 'text/plain' })); a.download = 'nvda_strategy.pine'; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function renderTVInfo() {
  const port = $('#tv-port').value || 8090, url = ($('#tv-url').value || '').replace(/\/+$/, '');
  $('#cmd-ngrok').textContent = `ngrok http ${port}`;
  $('#cmd-cf').textContent = `cloudflared tunnel --url http://127.0.0.1:${port}`;
  $('#tv-hook').textContent = (url || 'https://YOUR-TUNNEL') + '/tv_webhook';
  const st = $('#tv-state'), on = settings && settings.tv_enabled;
  st.className = 'pill ' + (on ? 'ok' : ''); st.innerHTML = `<span class="dot"></span>${on ? 'Enabled' : 'Off'}`;
}
['#tv-port', '#tv-url'].forEach(s => $(s).addEventListener('input', renderTVInfo));
async function genPass() { const r = await api('/api/generate_passphrase', {}); if (r.data.ok) $('#tv-pass').value = r.data.passphrase; }
async function saveTV() {
  const r = await api('/api/settings', { tv_enabled: $('#tv-enabled').checked, tv_passphrase: $('#tv-pass').value, tv_port: parseInt($('#tv-port').value || '8090', 10), tv_public_url: $('#tv-url').value });
  showMsg('#tv-msg', r.data.ok ? (r.data.restart_needed ? 'Saved. Restart the bot to apply.' : 'Saved.') : r.data.error, r.data.ok);
  loadSettings();
}
function copyText(id) { navigator.clipboard.writeText($('#' + id).textContent).then(() => toast('Copied')); }
function copyVal(id) { navigator.clipboard.writeText($('#' + id).value).then(() => toast('Copied')); }

/* ── manual trade modal ──────────────────────────────────── */
let mDir = null, mMult = 1, mManaged = true, mPx = 0, mPoll = null;
function openTradeModal() {
  mDir = null; ['#m-long', '#m-short'].forEach(s => $(s).classList.remove('on'));
  showMsg('#m-msg', ''); $('#m-trail').checked = false;
  $('#m-trade').classList.remove('hidden');
  fetchLivePx(); mPoll = setInterval(fetchLivePx, 4000);
  updatePreview();
}
function closeTradeModal() { $('#m-trade').classList.add('hidden'); clearInterval(mPoll); mPoll = null; }
async function fetchLivePx() {
  const r = await api('/live_price', undefined, { timeout: 4000 });
  if (r.data && r.data.price > 0) { mPx = r.data.price; $('#m-px').textContent = money(mPx); $('#m-px-note').textContent = 'last trade · updates every 4s'; }
  else $('#m-px-note').textContent = r.data.error || 'unavailable';
  updatePreview();
}
function setDir(d) { mDir = d; $('#m-long').classList.toggle('on', d === 'bullish'); $('#m-short').classList.toggle('on', d === 'bearish'); updatePreview(); }
function toggleAtr() { const a = $('#m-atr').checked; $('#m-atr-row').classList.toggle('hidden', !a); $('#m-manual').classList.toggle('hidden', a); updatePreview(); }
$$('#m-mult button').forEach(b => b.addEventListener('click', () => { mMult = parseFloat(b.dataset.x); segSet('#m-mult', 'x', b.dataset.x); updatePreview(); }));
$$('#m-managed button').forEach(b => b.addEventListener('click', () => { mManaged = b.dataset.v === '1'; segSet('#m-managed', 'v', b.dataset.v); $('#m-trail-row').classList.toggle('hidden', !mManaged); }));
function levels() {
  const atr = D ? D.last_atr : 0;
  if ($('#m-atr').checked) {
    if (!atr || !mPx || !mDir) return null;
    const sd = mMult * atr, td = sd * 1.5;
    return mDir === 'bullish' ? { stop: mPx - sd, target: mPx + td } : { stop: mPx + sd, target: mPx - td };
  }
  const stop = parseFloat($('#m-stop').value), target = parseFloat($('#m-target').value);
  return stop && target ? { stop, target } : null;
}
function updatePreview() {
  const p = $('#m-preview'), atr = D ? D.last_atr : 0;
  $('#m-atr-note').textContent = atr ? `ATR is $${Number(atr).toFixed(3)} · target = 1.5 × stop distance` : 'ATR not available until the bot has scanned once';
  if (!mDir) { p.textContent = 'Pick LONG or SHORT.'; p.style.color = ''; return; }
  const lv = levels(), qty = parseInt($('#m-qty').value || '0', 10);
  if (!lv || !mPx) { p.textContent = $('#m-atr').checked ? 'Waiting for live price / ATR…' : `For a ${mDir === 'bullish' ? 'LONG' : 'SHORT'}: ${mDir === 'bullish' ? 'stop below, target above' : 'target below, stop above'} ${money(mPx)}`; p.style.color = ''; return; }
  const ok = mDir === 'bullish' ? lv.stop < mPx && mPx < lv.target : lv.target < mPx && mPx < lv.stop;
  const risk = Math.abs(mPx - lv.stop) * qty, reward = Math.abs(lv.target - mPx) * qty;
  p.innerHTML = ok
    ? `Stop ${money(lv.stop)} · Target ${money(lv.target)}<br>Risk <span class="down">${money(risk)}</span> · Reward <span class="up">${money(reward)}</span> · ${(reward / (risk || 1)).toFixed(2)}R · ${money(mPx * qty, 0)} position`
    : `<span class="down">Stop/target don't bracket the live price for a ${mDir === 'bullish' ? 'LONG (need stop < price < target)' : 'SHORT (need target < price < stop)'}.</span>`;
}
async function submitTrade() {
  if (!mDir) return showMsg('#m-msg', 'Pick LONG or SHORT', false);
  const qty = parseInt($('#m-qty').value || '0', 10);
  if (!qty || qty < 1) return showMsg('#m-msg', 'Enter a share quantity', false);
  const useAtr = $('#m-atr').checked, lv = levels();
  if (!useAtr && !lv) return showMsg('#m-msg', 'Enter stop and target', false);
  const b = $('#m-submit'); b.disabled = true; b.textContent = 'Placing…';
  const r = await api('/manual_trade', { direction: mDir, qty, use_atr: useAtr, atr_mult: mMult, stop: useAtr ? 0 : lv.stop, target: useAtr ? 0 : lv.target, managed: mManaged, use_trail: mManaged && $('#m-trail').checked }, { timeout: 60000 });
  b.disabled = false; b.textContent = 'Place order';
  if (r.data.ok) { showMsg('#m-msg', r.data.message, true); setTimeout(closeTradeModal, 1500); pollData(); }
  else showMsg('#m-msg', r.data.error || 'Order failed', false);
}

/* ── close modal ─────────────────────────────────────────── */
let closeId = '';
function openCloseModal(id) { closeId = id || ''; $('#c-pnl').value = ''; showMsg('#c-msg', ''); $('#m-close').classList.remove('hidden'); }
function closeCloseModal() { $('#m-close').classList.add('hidden'); }
async function submitClose() {
  const b = $('#c-submit'); b.disabled = true; b.textContent = 'Closing…';
  const r = await api('/close_manual_trade', { order_id: closeId, pnl: parseFloat($('#c-pnl').value) || 0 }, { timeout: 30000 });
  b.disabled = false; b.textContent = 'Close position';
  if (r.data.ok) { closeCloseModal(); toast('Position closed'); pollData(); } else showMsg('#c-msg', r.data.error || 'Close failed', false);
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeTradeModal(); closeCloseModal(); } });

/* ── start ───────────────────────────────────────────────── */
window.addEventListener('load', () => {
  if (APP.standalone) $$('.panel-only').forEach(e => e.classList.add('hidden'));
  initChart();
  showView((location.hash || '#overview').slice(1));
  loadSettings(); pollBot(); loadHistoryOnce(); pollData(); renderKZ();
  setInterval(pollData, 5000);
  setInterval(pollBot, 3000);
  setInterval(() => { if ($('#view-console').classList.contains('active') || conAfter === 0) pollConsole(); }, 2000);
  setInterval(renderKZ, 30000);
});
"""


# ═══════════════════════════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════════════════════════

def render_html(standalone=False):
    body = BODY_HTML.replace("__VERSION__", VERSION)
    for name, svg in ICONS.items():
        body = body.replace(f"__I_{name}__", svg)
    js = JS.replace("__STANDALONE__", "true" if standalone else "false").replace("__VERSION__", VERSION)
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NVDA AutoTrader</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%235b8cff'/%3E%3Cpath d='M7 21l6-6 4 4 8-9' stroke='white' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>{CSS}</style>
</head>
<body>
{body}
<script>{js}</script>
</body>
</html>"""


def build():
    """Legacy: write the dashboard to nvda_live_dashboard.html (bot-only mode)."""
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(render_html(standalone=True))
    print(f"  Written: {os.path.basename(DASHBOARD_FILE)} ({os.path.getsize(DASHBOARD_FILE) // 1024} KB)")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="NVDA AutoTrader control panel")
    ap.add_argument("--port", type=int, default=PANEL_PORT, help="dashboard port (default 8080)")
    ap.add_argument("--autostart", action="store_true", help="start the bot as soon as the panel opens")
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser window")
    ap.add_argument("--build-only", action="store_true", help="just write nvda_live_dashboard.html and exit")
    args = ap.parse_args()

    if args.build_only:
        build()
        return

    try:
        server = ThreadingHTTPServer((PANEL_HOST, args.port), PanelHandler)
    except OSError as e:
        print(f"\nERROR: port {args.port} is busy ({e}).")
        print("  Is the panel already open, or is an old copy of nvda_autotrader.py")
        print("  still running from Task Scheduler? Close it, or use --port 8085.")
        sys.exit(1)
    server.daemon_threads = True

    url = f"http://{PANEL_HOST}:{args.port}"
    print("\n" + "=" * 55)
    print(f"  NVDA AutoTrader control panel {VERSION}")
    print(f"  Dashboard: {url}")
    print("  Press Ctrl+C here to quit (stops the bot too).")
    print("=" * 55 + "\n")

    if args.autostart:
        try:
            BOT.start(reason="auto-started with the panel")
        except Exception as e:
            print(f"  Could not auto-start the bot: {e}")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        BOT.stop()
        server.server_close()


if __name__ == "__main__":
    main()
