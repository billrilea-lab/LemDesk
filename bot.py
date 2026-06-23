#!/usr/bin/env python3
"""
Crypto.com regime grid bot — backtested, fee-aware, Markov-filtered.

  python3 bot.py rotate           # scan + set best INSTRUMENT in .env
  python3 bot.py compare           # legacy vs current vs hybrid
  python3 bot.py check             # test API + show regime
  python3 bot.py backtest          # walk-forward backtest (run this first)
  python3 bot.py auto              # paper auto (WebSocket)
  python3 bot.py auto --live       # real orders
  python3 bot.py gbt-review        # GBT: self-questions + optimize + scan
  python3 bot.py gbt-loop          # review + rotate if better + backtest + log
  python3 bot.py birdseed-init     # BirdSeedTrade: setup .env + CDC symbols
  python3 bot.py birdseed-review   # profit review + agent brief
  python3 bot.py birdseed-loop     # weekly profit loop
  python3 bot.py birdseed-agent    # Cursor/Claude context JSON + markdown
  python3 bot.py lemdesk-sync    # scrape+RAG+briefs+handoff (smart auto)
  python3 bot.py lemdesk-review  # LEMdesk brief + topology runbook
  python3 bot.py lemdesk-search  # query LEMdesk knowledge base
  python3 bot.py lemdesk-handoff # session handoff for another room
  python3 bot.py lemdesk-health  # desk health score (LEMdesk Pro)
  python3 bot.py lemdesk-desk-up  # morning startup: Docker + DMR + mounts
  python3 bot.py lemdesk-install  # one-shot full install (mac-mini profile)
  python3 bot.py lemdesk-smart-handoff # structured desk pack + prompt
  python3 bot.py lemdesk-pro     # menu bar + local dashboard (:8765)
  python3 bot.py stop / resume     # kill switch
  python3 bot.py learn             # OSS curriculum
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from env_utils import PROJECT_ENV, SECRETS_FILE, load_env, migrate_secrets_to_private

from backtest import (
    candles_to_df,
    optimize_gbt_params,
    print_report,
    run_backtest,
    run_backtest_optimized,
    run_gbt_backtest,
    save_report,
)
from exchange import Exchange, parse_ticker, stream_ticker
from birdseed_trade import (
    BRAND,
    apply_birdseed_env,
    birdseed_config_from_env,
    birdseed_pairs,
    build_agent_brief,
    pick_birdseed_universe,
    print_birdseed_banner,
    run_birdseed_loop,
    run_birdseed_review,
    write_agent_artifacts,
    write_birdseed_drive_doc,
)
from lemdesk_brief import load_knowledge, post_process_all
from gbt_review import apply_gbt_review_fixes, print_gbt_loop_summary, print_gbt_review, run_gbt_profit_loop, run_gbt_review
from gbt_strategy import (
    GbtPaperState,
    SymbolBook,
    equal_allocations,
    gbt_desired_orders,
    parse_gbt_pairs,
)
from indicators import IndicatorSnapshot, indicator_snapshot
from learn import cmd_learn
from rotate import cmd_rotate
from scan import print_scan_report, run_scan, save_scan_report
from strategy import StrategyConfig, build_grid_orders, check_stop_loss, compute_atr_pct, markov_from_closes
import numpy as np

ROOT = Path(__file__).parent
load_env()

API_KEY = os.getenv("CDC_API_KEY", "").strip()
API_SECRET = os.getenv("CDC_API_SECRET", "").strip()
ENV = os.getenv("CDC_ENV", "prod").strip()
PAIR = os.getenv("INSTRUMENT", "SUI_USDT").strip()

PLACEHOLDERS = {"", "your_api_key_here", "your_api_secret_here", "paste_your_api_key_here"}
HALT_FILE = ROOT / ".halt_trading"
PAPER_FILE = ROOT / "paper_state.json"
LOG_DIR = ROOT / "logs"


def _load_cfg() -> StrategyConfig:
    mode = os.getenv("STRATEGY_MODE", "grid").strip().lower()
    cfg = StrategyConfig(
        mode=mode,
        grid_levels=int(os.getenv("GRID_LEVELS", "5")),
        grid_spacing_pct=float(os.getenv("GRID_SPACING_PCT", "1.0")),
        order_size_usdt=float(os.getenv("ORDER_SIZE_USDT", "50")),
        maker_fee=float(os.getenv("MAKER_FEE", "0.00025")),
        max_portfolio_pct=float(os.getenv("MAX_PORTFOLIO_PCT", "0.20")),
        stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.05")),
        markov_threshold=float(os.getenv("MARKOV_THRESHOLD", "0.10")),
        min_atr_pct=float(os.getenv("MIN_ATR_PCT", "0.8")),
        sideways_prob_min=float(os.getenv("SIDEWAYS_PROB_MIN", "0.25")),
        use_indicators=os.getenv("USE_INDICATORS", "1" if mode == "hybrid" else "0") == "1",
        gbt_profit_goal_pct=float(os.getenv("GBT_PROFIT_GOAL_PCT", "5.0")),
        gbt_add_drop_pct=float(os.getenv("GBT_ADD_DROP_PCT", "2.0")),
        gbt_max_lots=int(os.getenv("GBT_MAX_LOTS", "46")),
        gbt_max_symbols=int(os.getenv("GBT_MAX_SYMBOLS", "4")),
        gbt_use_stop_loss=os.getenv("GBT_USE_STOP_LOSS", "0") == "1",
        gbt_regime_filter=os.getenv("GBT_REGIME_FILTER", "1") == "1",
        gbt_min_markov_signal=float(os.getenv("GBT_MIN_MARKOV_SIGNAL", "-0.05")),
        gbt_min_lot_usdt=float(os.getenv("GBT_MIN_LOT_USDT", "5.0")),
        gbt_cash_reserve_pct=float(os.getenv("GBT_CASH_RESERVE_PCT", "0.10")),
        gbt_max_inventory_pct=float(os.getenv("GBT_MAX_INVENTORY_PCT", "0.80")),
        gbt_block_add_in_bear=os.getenv("GBT_BLOCK_ADD_IN_BEAR", "1") == "1",
        gbt_max_solo_drawdown_pct=float(os.getenv("GBT_MAX_SOLO_DRAWDOWN_PCT", "25")),
        gbt_equity_drawdown_brake_pct=float(os.getenv("GBT_EQUITY_DRAWDOWN_BRAKE_PCT", "28")),
    )
    opt_file = LOG_DIR / "backtest_latest.json"
    if opt_file.exists() and os.getenv("USE_OPTIMIZED", "0") == "1":
        try:
            opt = json.loads(opt_file.read_text()).get("optimized_params")
            if opt:
                cfg = StrategyConfig(**{**asdict(cfg), **opt})
        except Exception:
            pass
    return cfg


CFG = _load_cfg()
GBT_PAIRS = parse_gbt_pairs(
    os.getenv("GBT_SYMBOLS", ""),
    PAIR,
    CFG.gbt_max_symbols if CFG.is_gbt else int(os.getenv("GBT_MAX_SYMBOLS", "4")),
)

PAPER_USDT = float(os.getenv("PAPER_USDT_BALANCE", "50"))
AUTO_MIN_SEC = float(os.getenv("AUTO_MIN_SEC", "1"))
GRID_RECENTER_PCT = float(os.getenv("GRID_RECENTER_PCT", "0.15")) / 100
REGIME_REFRESH_SEC = int(os.getenv("REGIME_REFRESH_SEC", "900"))
INTERVAL = int(os.getenv("LOOP_INTERVAL_SEC", "60"))


def keys_configured() -> bool:
    return API_KEY not in PLACEHOLDERS and API_SECRET not in PLACEHOLDERS


def is_halted() -> bool:
    return HALT_FILE.exists()


def halt(reason: str) -> None:
    HALT_FILE.write_text(reason)


def mid_price(bid: float, ask: float, last: float) -> float:
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    if last > 0:
        return last
    return 0.0


def log_event(event: str, data: dict) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    line = json.dumps({"time": datetime.now(timezone.utc).isoformat(), "event": event, **data})
    with (LOG_DIR / f"bot_{datetime.now(timezone.utc):%Y%m%d}.jsonl").open("a") as f:
        f.write(line + "\n")
    print(line)


@dataclass
class PaperState:
    usdt: float = 1000.0
    btc: float = 0.0
    orders: list[dict] = field(default_factory=list)
    grid_anchor: float = 0.0
    total_fees: float = 0.0
    peak_equity: float = 0.0

    def save(self) -> None:
        PAPER_FILE.write_text(
            json.dumps(
                {
                    "usdt": self.usdt,
                    "btc": self.btc,
                    "orders": self.orders,
                    "grid_anchor": self.grid_anchor,
                    "total_fees": self.total_fees,
                    "peak_equity": self.peak_equity,
                },
                indent=2,
            )
        )

    @classmethod
    def load(cls, default_usdt: float) -> PaperState:
        if not PAPER_FILE.exists():
            return cls(usdt=default_usdt, peak_equity=default_usdt)
        d = json.loads(PAPER_FILE.read_text())
        return cls(
            usdt=float(d["usdt"]),
            btc=float(d["btc"]),
            orders=d.get("orders", []),
            grid_anchor=float(d.get("grid_anchor", 0)),
            total_fees=float(d.get("total_fees", 0)),
            peak_equity=float(d.get("peak_equity", d["usdt"])),
        )

    def equity(self, price: float) -> float:
        return self.usdt + self.btc * price

    def fill_orders(self, bid: float, ask: float, fee: float) -> list[dict]:
        fills = []
        for o in self.orders:
            if o.get("status") != "open":
                continue
            if o["side"] == "BUY" and ask <= o["price"]:
                cost = o["price"] * o["qty"]
                fee_paid = cost * fee
                self.usdt -= cost + fee_paid
                self.btc += o["qty"]
                self.total_fees += fee_paid
                o["status"] = "filled"
                fills.append({**o, "fee": fee_paid})
            elif o["side"] == "SELL" and bid >= o["price"]:
                proceeds = o["price"] * o["qty"]
                fee_paid = proceeds * fee
                self.usdt += proceeds - fee_paid
                self.btc -= o["qty"]
                self.total_fees += fee_paid
                o["status"] = "filled"
                fills.append({**o, "fee": fee_paid})
        if fills:
            self.save()
        return fills


def get_live_capital(ex: Exchange) -> float:
    b = ex.balance()
    return float(b.get("total_available_balance", 0))


def get_markov(ex: Exchange) -> dict:
    candles = ex.candles(PAIR, count=120)
    closes = np.array([float(c["c"]) for c in candles])
    highs = np.array([float(c["h"]) for c in candles])
    lows = np.array([float(c["l"]) for c in candles])
    mk = markov_from_closes(closes, CFG)
    mk["atr_pct"] = compute_atr_pct(highs, lows, closes, CFG.atr_period)
    if CFG.indicators_on:
        mk["indicators"] = indicator_snapshot(closes).__dict__
    return mk


def get_btc_balance(ex: Exchange) -> float:
    base = PAIR.split("_")[0]
    for item in ex.balance().get("position_balances", []):
        if item.get("instrument_name") == base:
            return float(item.get("quantity", 0))
    return 0.0


def needs_recenter(anchor: float, price: float) -> bool:
    if anchor <= 0:
        return True
    return abs(price - anchor) / anchor >= GRID_RECENTER_PCT


def reconcile_live_pair(ex: Exchange, pair: str, desired: list[dict]) -> tuple[int, int]:
    open_orders = ex.open_orders(pair)
    desired_keys = {(o["side"], o["price"]) for o in desired}
    open_map = {(o["side"], round(float(o["limit_price"]), 6)): o for o in open_orders}
    cancelled = 0
    for key, order in open_map.items():
        if key not in desired_keys:
            ex.cancel_order(str(order["order_id"]))
            cancelled += 1
    placed = 0
    for o in desired:
        if (o["side"], o["price"]) not in open_map:
            ex.place_order(pair, o["side"], o["price"], o["qty"], str(uuid.uuid4()))
            placed += 1
            log_event("live_order", {**o, "pair": pair})
    return placed, cancelled


def get_base_balance(ex: Exchange, pair: str) -> float:
    base = pair.split("_")[0]
    for item in ex.balance().get("position_balances", []):
        if item.get("instrument_name") == base:
            return float(item.get("quantity", 0))
    return 0.0


def reconcile_live(ex: Exchange, desired: list[dict]) -> tuple[int, int]:
    return reconcile_live_pair(ex, PAIR, desired)


def apply_paper_grid(paper: PaperState, desired: list[dict], price: float, force: bool) -> int:
    if force:
        paper.orders = [o for o in paper.orders if o.get("status") == "filled"]
        paper.grid_anchor = price
    open_keys = {(o["side"], o["price"]) for o in paper.orders if o.get("status") == "open"}
    placed = 0
    for o in desired:
        if (o["side"], o["price"]) not in open_keys:
            paper.orders.append({**o, "status": "open", "id": str(uuid.uuid4())[:8]})
            placed += 1
    paper.save()
    return placed


class GbtAutoBot:
    """Multi-symbol lot trader — buy dips, sell at profit goal (GoBabyTrade-inspired)."""

    def __init__(self, ex: Exchange, live: bool, pairs: list[str]) -> None:
        self.ex = ex
        self.live = live
        self.pairs = pairs
        self.last_action = 0.0
        cap = PAPER_USDT if PAPER_USDT > 0 else 50.0
        if not live and keys_configured() and float(os.getenv("PAPER_USDT_BALANCE", "30")) <= 0:
            try:
                cap = get_live_capital(ex) * CFG.max_portfolio_pct
            except Exception:
                cap = 50.0
        self.capital_usdt = cap
        self.paper = None if live else GbtPaperState.load(cap, pairs)
        if self.paper and not self.paper.allocations:
            self.paper.allocations = equal_allocations(pairs)
            self.paper.save()

        self.markov: dict = {}
        self.markov_at = 0.0

    def refresh_markov(self, pair: str) -> dict:
        now = time.time()
        key = f"mk_{pair}"
        cached = getattr(self, "_mk_cache", {})
        if now - cached.get(f"{key}_at", 0) < REGIME_REFRESH_SEC and cached.get(key):
            return cached[key]
        candles = self.ex.candles(pair, count=120)
        closes = np.array([float(c["c"]) for c in candles])
        mk = markov_from_closes(closes, CFG)
        if not hasattr(self, "_mk_cache"):
            self._mk_cache = {}
        self._mk_cache[key] = mk
        self._mk_cache[f"{key}_at"] = now
        return mk

    def on_tick(self, quotes: dict[str, dict]) -> dict | None:
        if is_halted():
            return {"status": "halted", "reason": HALT_FILE.read_text().strip(), "fix": "python bot.py resume"}

        prices = {p: mid_price(q["bid"], q["ask"], q["last"]) for p, q in quotes.items()}
        total_fills = 0
        total_placed = 0
        total_cancelled = 0
        reasons: dict[str, str] = {}

        if self.paper:
            for pair in self.pairs:
                q = quotes.get(pair)
                if not q:
                    continue
                fills = self.paper.fill_orders(pair, q["bid"], q["ask"], CFG.maker_fee)
                total_fills += len(fills)
                for f in fills:
                    log_event("gbt_fill", {**f, "pair": pair})

        now = time.time()
        if now - self.last_action < AUTO_MIN_SEC and total_fills == 0:
            return None

        deploy = (
            get_live_capital(self.ex) * CFG.max_portfolio_pct
            if self.live
            else (self.paper.equity(prices) if self.paper else self.capital_usdt)
        )
        free_usdt = deploy if self.live else (self.paper.usdt if self.paper else self.capital_usdt)

        eq = self.paper.equity(prices) if self.paper else deploy
        if self.paper:
            self.paper.peak_equity = max(self.paper.peak_equity, eq)
        peak = self.paper.peak_equity if self.paper else eq
        port_dd = 100.0 * (eq / peak - 1.0) if peak > 0 else 0.0

        for pair in self.pairs:
            q = quotes.get(pair)
            if not q:
                continue
            mid = prices[pair]
            alloc = (
                self.paper.allocations.get(pair, 100 / len(self.pairs))
                if self.paper
                else 100 / len(self.pairs)
            )

            if self.live:
                book = SymbolBook(pair=pair, lots=[], last_buy_price=0)
            else:
                book = self.paper.book(pair)

            mk = self.refresh_markov(pair)
            desired, reason = gbt_desired_orders(
                pair, mid, book, free_usdt, deploy, alloc, CFG, mk["regime"], mk["signal"], port_dd
            )
            reasons[pair] = reason

            if self.live:
                p, c = reconcile_live_pair(self.ex, pair, desired)
                total_placed += p
                total_cancelled += c
            elif self.paper:
                total_placed += self.paper.sync_orders(pair, desired)

        result = {
            "mode": "gbt",
            "live": self.live,
            "pairs": self.pairs,
            "prices": {p: round(prices[p], 6) for p in prices},
            "fills": total_fills,
            "placed": total_placed,
            "cancelled": total_cancelled,
            "reasons": reasons,
            "equity": round(eq, 2),
            "portfolio_dd_pct": round(port_dd, 2),
            "gbt_profit_goal_pct": CFG.gbt_profit_goal_pct,
            "gbt_add_drop_pct": CFG.gbt_add_drop_pct,
        }
        if self.paper:
            result["open_lots"] = {p: len(self.paper.book(p).lots) for p in self.pairs}
            result["paper_fees"] = round(self.paper.total_fees, 4)

        self.last_action = now
        if total_fills or total_placed or total_cancelled:
            log_event("gbt_tick", result)
        return result


async def run_gbt_loop(ex: Exchange, live: bool) -> None:
    bot = GbtAutoBot(ex, live, GBT_PAIRS)
    if CFG.is_gbt:
        print_birdseed_banner(CFG, GBT_PAIRS)
    else:
        print(f"GBT {'LIVE' if live else 'paper'} | {len(GBT_PAIRS)} symbols: {', '.join(GBT_PAIRS)}")
        print(
            f"Profit goal {CFG.gbt_profit_goal_pct}% | add on {CFG.gbt_add_drop_pct}% drop | "
            f"max {CFG.gbt_max_lots} lots/symbol | stop-loss {'on' if CFG.gbt_use_stop_loss else 'off'}"
        )
    print(f"{'LIVE' if live else 'Paper'} ${PAPER_USDT:.2f} | poll every {AUTO_MIN_SEC}s\nCtrl+C to stop\n")

    while True:
        try:
            quotes: dict[str, dict] = {}
            for pair in GBT_PAIRS:
                t = ex.ticker(pair)
                m = parse_ticker(t)
                if m:
                    quotes[pair] = m
            if quotes:
                r = bot.on_tick(quotes)
                if r and r.get("status") == "halted":
                    print(json.dumps(r, indent=2))
                    return
        except Exception as e:
            print(f"GBT tick error: {e}")
        await asyncio.sleep(AUTO_MIN_SEC)


class AutoBot:
    def __init__(self, ex: Exchange, live: bool) -> None:
        self.ex = ex
        self.live = live
        self.markov: dict = {}
        self.markov_at = 0.0
        self.last_action = 0.0
        self.grid_anchor = 0.0
        cap = PAPER_USDT if PAPER_USDT > 0 else 30.0
        if not live and keys_configured() and float(os.getenv("PAPER_USDT_BALANCE", "30")) <= 0:
            try:
                cap = get_live_capital(ex) * CFG.max_portfolio_pct
            except Exception:
                cap = 30.0
        self.paper = None if live else PaperState.load(cap)
        self.capital_usdt = cap

    def refresh_markov(self) -> dict:
        now = time.time()
        if now - self.markov_at < REGIME_REFRESH_SEC and self.markov:
            return self.markov
        self.markov = get_markov(self.ex)
        self.markov_at = now
        return self.markov

    def on_tick(self, bid: float, ask: float, last: float) -> dict | None:
        if is_halted():
            return {"status": "halted", "reason": HALT_FILE.read_text().strip(), "fix": "python bot.py resume"}

        price = mid_price(bid, ask, last)
        mk = self.refresh_markov()
        regime, signal = mk["regime"], mk["signal"]
        p_side = mk.get("p_sideways", 0.33)
        atr_pct = mk.get("atr_pct", 1.5)

        if check_stop_loss(self.grid_anchor, price, CFG):
            halt(f"Stop-loss: price {price} dropped {CFG.stop_loss_pct:.0%} below anchor {self.grid_anchor}")
            return {"status": "halted", "reason": "stop-loss triggered", "fix": "python bot.py resume"}

        fills: list[dict] = []
        if self.paper:
            fills = self.paper.fill_orders(bid, ask, CFG.maker_fee)
            for f in fills:
                log_event("paper_fill", {**f, "regime": regime, "signal": round(signal, 3)})

        now = time.time()
        if now - self.last_action < AUTO_MIN_SEC and not fills:
            return None

        capital = get_live_capital(self.ex) * CFG.max_portfolio_pct if self.live else self.paper.usdt if self.paper else self.capital_usdt
        btc_qty = get_btc_balance(self.ex) if self.live else (self.paper.btc if self.paper else 0.0)
        force = needs_recenter(self.grid_anchor, price)

        result: dict = {
            "mode": "live" if self.live else "paper",
            "pair": PAIR,
            "price": price,
            "regime": regime,
            "signal": round(signal, 3),
            "p_sideways": round(p_side, 3),
            "atr_pct": round(atr_pct, 2),
            "return_20d": round(mk.get("return_20d", 0) * 100, 2),
            "recentered": force,
            "fills": len(fills),
            "placed": 0,
            "cancelled": 0,
            "trade_reason": "",
        }

        if force or self.grid_anchor == 0:
            ind = None
            if CFG.indicators_on and mk.get("indicators"):
                ind = IndicatorSnapshot(**mk["indicators"])
            desired, reason = build_grid_orders(
                price, regime, signal, p_side, atr_pct, capital, btc_qty, CFG, ind
            )
            result["orders_wanted"] = len(desired)
            result["trade_reason"] = reason
            if self.live:
                result["placed"], result["cancelled"] = reconcile_live(self.ex, desired)
                self.grid_anchor = price
            elif self.paper:
                result["placed"] = apply_paper_grid(self.paper, desired, price, force)
                self.grid_anchor = self.paper.grid_anchor
                eq = self.paper.equity(price)
                self.paper.peak_equity = max(self.paper.peak_equity, eq)
                result["paper_equity"] = round(eq, 2)
                result["paper_fees"] = round(self.paper.total_fees, 4)

        self.last_action = now
        if fills or force or result["placed"] or result.get("cancelled"):
            log_event("auto_tick", result)
        return result


async def run_rest_auto_loop(ex: Exchange, live: bool) -> None:
    """Fallback: fast REST polling when WebSocket unavailable."""
    bot = AutoBot(ex, live)
    mk = bot.refresh_markov()
    print(f"REST polling mode | {PAIR} | regime={mk['regime']} signal={mk['signal']:.3f}")
    print(f"Paper ${PAPER_USDT:.2f} | ${CFG.order_size_usdt}/trade | every {AUTO_MIN_SEC}s\n")
    while True:
        try:
            m = parse_ticker(ex.ticker(PAIR))
            if m:
                r = bot.on_tick(m["bid"], m["ask"], m["last"])
                if r and r.get("status") == "halted":
                    print(json.dumps(r, indent=2))
                    break
        except Exception as e:
            print(f"Tick error: {e}")
        await asyncio.sleep(AUTO_MIN_SEC)


async def run_auto_loop(ex: Exchange, live: bool) -> None:
    bot = AutoBot(ex, live)
    mk = bot.refresh_markov()
    print(f"Auto {'LIVE' if live else 'paper'} | {PAIR} | regime={mk['regime']} signal={mk['signal']:.3f}")
    print(f"Paper ${PAPER_USDT:.2f} | ${CFG.order_size_usdt}/trade | {CFG.grid_levels} levels | tick every {AUTO_MIN_SEC}s")
    print(f"Regime refresh {REGIME_REFRESH_SEC}s | recenter {GRID_RECENTER_PCT*100:.2f}% move")
    print("Ctrl+C to stop\n")

    last_heartbeat = time.time()

    async def _run_ws() -> None:
        nonlocal last_heartbeat
        async for q in stream_ticker(ex, PAIR):
            r = bot.on_tick(q["bid"], q["ask"], q["last"])
            now = time.time()
            if now - last_heartbeat >= 30:
                eq = bot.paper.equity(q["last"]) if bot.paper else 0
                print(f"  ... alive | ${q['last']:,.2f} | equity ${eq:.2f} | regime {bot.markov.get('regime', '?')}")
                last_heartbeat = now
            if r and r.get("status") == "halted":
                print(json.dumps(r, indent=2))
                return

    while True:
        try:
            await _run_ws()
            print("WebSocket closed — reconnecting in 3s...")
            await asyncio.sleep(3)
        except ssl.SSLCertVerificationError:
            print("WebSocket SSL error — switching to REST polling.\n")
            await run_rest_auto_loop(ex, live)
            return
        except OSError as e:
            print(f"WebSocket error ({e}) — reconnecting in 3s...")
            await asyncio.sleep(3)


def cmd_backtest(args: argparse.Namespace) -> int:
    ex = Exchange(API_KEY, API_SECRET, ENV)
    try:
        days, capital = args.days, args.capital
        if CFG.is_gbt:
            pairs = GBT_PAIRS if len(GBT_PAIRS) > 1 else [PAIR]
            print(f"Fetching {days} daily candles for GBT portfolio: {', '.join(pairs)}...")
            candle_map = {}
            for pair in pairs:
                candle_map[pair] = ex.fetch_daily_history(pair, days)
            if args.optimize:
                frames = {p: candles_to_df(candle_map[p]) for p in pairs}
                result = optimize_gbt_params(frames, capital, CFG)
                print_report(result)
            else:
                result = run_gbt_backtest(candle_map, CFG, capital)
                print_report(result)
        else:
            print(f"Fetching {days} daily candles for {PAIR}...")
            candles = ex.fetch_daily_history(PAIR, days)
            if args.optimize:
                print("Optimizing parameters (324 combinations)...")
                result = run_backtest_optimized(candles, capital)
                print_report(result, title="OPTIMIZED WALK-FORWARD BACKTEST v2")
            else:
                result = run_backtest(candles, CFG, capital)
                print_report(result)
        path = save_report(result)
        print(f"\nSaved: {path}")
        if args.optimize and not CFG.is_gbt:
            print(f"Optimized params saved — restart bot to load: {result.get('optimized_params')}")
        return 0 if result.get("edge_vs_buy_hold_pct", -999) > -10 else 1
    except Exception as e:
        print(f"Backtest failed: {e}", file=sys.stderr)
        return 1
    finally:
        ex.close()


def cmd_check(_: argparse.Namespace) -> int:
    if not PROJECT_ENV.exists():
        print("Missing .env — copy .env.example for strategy settings")
        return 1
    if not keys_configured():
        print(f"Add API keys to {SECRETS_FILE}")
        return 1
    ex = Exchange(API_KEY, API_SECRET, ENV)
    try:
        t = ex.ticker(PAIR)
        print(f"OK  {PAIR} @ {t['a']}  (env={ENV})")
        b = ex.balance()
        avail = float(b.get("total_available_balance", 0))
        print(f"Balance: ${avail:,.2f} available")
        mk = get_markov(ex)
        print(f"Regime: {mk['regime']}  |  20d: {mk['return_20d']*100:+.1f}%  |  signal: {mk['signal']:+.3f}")
        print(f"P(sideways): {mk.get('p_sideways', 0):.2f}  |  ATR: {mk.get('atr_pct', 0):.2f}%")
        print(f"Strategy: {CFG.mode.upper()}  |  order ${CFG.order_size_usdt:.2f}")
        if CFG.is_gbt:
            print(f"GBT symbols: {', '.join(GBT_PAIRS)}")
            print(
                f"GBT profit {CFG.gbt_profit_goal_pct}% | add drop {CFG.gbt_add_drop_pct}% | "
                f"max lots {CFG.gbt_max_lots}"
            )
        deploy = avail * CFG.max_portfolio_pct
        print(f"Capital cap ({CFG.max_portfolio_pct:.0%}): ${deploy:,.2f}")
        return 0
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    finally:
        ex.close()


def cmd_auto(args: argparse.Namespace) -> int:
    if args.live and not keys_configured():
        print("Live needs API keys", file=sys.stderr)
        return 1
    if is_halted():
        print("Halted. Run: python bot.py resume")
        return 1
    ex = Exchange(API_KEY, API_SECRET, ENV)
    try:
        if CFG.is_gbt:
            asyncio.run(run_gbt_loop(ex, args.live))
        else:
            asyncio.run(run_auto_loop(ex, args.live))
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ex.close()
    return 0


def cmd_stop(_: argparse.Namespace) -> int:
    halt("manual stop")
    print("Stopped.")
    return 0


def cmd_resume(_: argparse.Namespace) -> int:
    HALT_FILE.unlink(missing_ok=True)
    print("Resumed.")
    return 0


def cmd_migrate_secrets(_: argparse.Namespace) -> int:
    try:
        result = migrate_secrets_to_private()
    except RuntimeError as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        return 1
    print(f"API keys moved to: {result['secrets_file']}")
    print(f"Strategy config stays in: {PROJECT_ENV}")
    if result["removed"]:
        print(f"Removed from project: {', '.join(result['removed'])}")
    print("Secrets are chmod 600 and outside the git repo.")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Legacy grid vs your current config vs hybrid."""
    pairs = [args.pair] if args.pair else [PAIR]
    ex = Exchange("", "", ENV)
    try:
        for pair in pairs:
            candles = ex.fetch_daily_history(pair, args.days)
            if len(candles) < 60:
                print(f"{pair}: skip (need 60+ candles)")
                continue
            legacy = run_backtest(candles, replace(CFG, mode="grid", use_indicators=False), args.capital)
            current = run_backtest(candles, CFG, args.capital)
            hybrid = run_backtest(candles, replace(CFG, mode="hybrid", use_indicators=True), args.capital)
            print(f"\n=== {pair} (${args.capital:.0f}, {args.days}d) ===")
            print(f"  LEGACY:  {legacy['total_return_pct']:+.2f}%  edge {legacy['edge_vs_buy_hold_pct']:+.2f}%  fills {legacy['total_trades']}")
            print(f"  CURRENT: {current['total_return_pct']:+.2f}%  edge {current['edge_vs_buy_hold_pct']:+.2f}%  fills {current['total_trades']}  ({CFG.mode}+ind={CFG.indicators_on})")
            print(f"  HYBRID:  {hybrid['total_return_pct']:+.2f}%  edge {hybrid['edge_vs_buy_hold_pct']:+.2f}%  fills {hybrid['total_trades']}")
    finally:
        ex.close()
    return 0


def cmd_gbt_review(args: argparse.Namespace) -> int:
    report = run_gbt_review(
        CFG,
        GBT_PAIRS,
        capital=args.capital,
        days=args.days,
        optimize=not args.no_optimize,
        scan=not args.no_scan,
    )
    print_gbt_review(report)
    return 0 if report["answers"].get("portfolio_edge") else 1


def cmd_gbt_loop(args: argparse.Namespace) -> int:
    report = run_gbt_profit_loop(
        CFG,
        GBT_PAIRS,
        capital=args.capital,
        days=args.days,
        apply=not args.dry_run,
    )
    print_gbt_loop_summary(report)
    ex = Exchange(API_KEY, API_SECRET, ENV)
    try:
        pairs = report["loop"]["pairs"]
        candle_map = {p: ex.fetch_daily_history(p, args.days) for p in pairs}
        result = run_gbt_backtest(candle_map, CFG, args.capital)
        print_report(result)
        save_report(result)
    finally:
        ex.close()
    return 0 if report["answers"].get("portfolio_edge") else 1


def _birdseed_cfg_pairs() -> tuple[StrategyConfig, list[str]]:
    cfg = replace(birdseed_config_from_env(), mode="gbt")
    pairs = birdseed_pairs(cfg)
    return cfg, pairs


def cmd_birdseed_init(args: argparse.Namespace) -> int:
    cfg = replace(birdseed_config_from_env(), mode="gbt")
    pairs = pick_birdseed_universe(cfg, args.capital, args.days, args.max_price)
    apply_birdseed_env(pairs)
    load_env()
    cfg = replace(birdseed_config_from_env(), mode="gbt")
    print_birdseed_banner(cfg, pairs)
    print(f"Wrote BirdSeedTrade config → {PROJECT_ENV}")
    print(f"  GBT_SYMBOLS={','.join(pairs)}")
    drive = write_birdseed_drive_doc(cfg, pairs)
    if drive:
        print(f"GC-MM2 status → {drive}")
    print("\nNext:")
    print('  python3 bot.py birdseed-review')
    print('  python3 bot.py auto          # paper')
    return 0


def cmd_birdseed_review(args: argparse.Namespace) -> int:
    cfg, pairs = _birdseed_cfg_pairs()
    report = run_birdseed_review(
        cfg, pairs, args.capital, args.days, not args.no_optimize, not args.no_scan
    )
    print_birdseed_banner(cfg, pairs)
    print_gbt_review(report)
    if not args.dry_run:
        trimmed, env_params, fixes = apply_gbt_review_fixes(report, pairs)
        if fixes:
            apply_birdseed_env(trimmed, {k: str(v) for k, v in env_params.items()})
            load_env()
            cfg = replace(birdseed_config_from_env(), mode="gbt")
            pairs = trimmed
            print("\nApplied fixes:")
            for f in fixes:
                print(f"  → {f}")
    brief = build_agent_brief(cfg, pairs, report)
    json_path, md_path = write_agent_artifacts(brief)
    drive = write_birdseed_drive_doc(cfg, pairs, report)
    print(f"Agent brief → {json_path}")
    print(f"Agent context → {md_path}")
    if drive:
        print(f"GC-MM2 status → {drive}")
    return 0 if report["answers"].get("portfolio_edge") else 1


def cmd_birdseed_loop(args: argparse.Namespace) -> int:
    cfg, pairs = _birdseed_cfg_pairs()
    report = run_birdseed_loop(cfg, pairs, args.capital, args.days, apply=not args.dry_run)
    print_birdseed_banner(cfg, report["loop"]["pairs"])
    print_gbt_loop_summary(report)
    brief = build_agent_brief(cfg, report["loop"]["pairs"], report)
    json_path, md_path = write_agent_artifacts(brief)
    drive = write_birdseed_drive_doc(cfg, report["loop"]["pairs"], report)
    print(f"Agent brief → {json_path}")
    if drive:
        print(f"GC-MM2 status → {drive}")
    ex = Exchange(API_KEY, API_SECRET, ENV)
    try:
        loop_pairs = report["loop"]["pairs"]
        candle_map = {p: ex.fetch_daily_history(p, args.days) for p in loop_pairs}
        result = run_gbt_backtest(candle_map, cfg, args.capital)
        print_report(result)
        save_report(result)
    finally:
        ex.close()
    return 0 if report["answers"].get("portfolio_edge") else 1


def cmd_birdseed_agent(args: argparse.Namespace) -> int:
    cfg, pairs = _birdseed_cfg_pairs()
    review = None
    review_path = ROOT / "logs" / "gbt_review_latest.json"
    if review_path.exists():
        try:
            review = json.loads(review_path.read_text())
        except json.JSONDecodeError:
            pass
    if args.fresh:
        review = run_birdseed_review(cfg, pairs, args.capital, args.days, True, True)
    brief = build_agent_brief(cfg, pairs, review)
    json_path, md_path = write_agent_artifacts(brief)
    drive = write_birdseed_drive_doc(cfg, pairs, review)
    print_birdseed_banner(cfg, pairs)
    print(f"Agent brief JSON → {json_path}")
    print(f"Agent context MD  → {md_path}")
    if drive:
        print(f"GC-MM2 status → {drive}")
    print("\nPoint Cursor/Claude at logs/birdseed_agent_context.md for this session.")
    return 0


def cmd_lemdesk_auto(args: argparse.Namespace) -> int:
    from lemdesk_auto import run_auto

    backend = args.backend
    workers = args.workers
    max_depth = args.max_depth
    full = args.full
    skip_dmr = args.skip_dmr_check
    if args.fast:
        full = True
        backend = "httpx"
        workers = 12
        max_depth = 1
        skip_dmr = True

    results = run_auto(
        full=full,
        backend=backend,
        workers=workers,
        max_depth=max_depth,
        save_raw=args.raw,
        cleanup=not args.no_cleanup,
        handoff_focus=args.focus or "",
        skip_dmr_check=skip_dmr,
    )
    print(f"Auto complete: {results.get('page_count')} pages in {results.get('elapsed_sec')}s")
    if results.get("incoming_cleaned"):
        print(f"  cleaned {results['incoming_cleaned']} incoming files")
    print(f"  meta: {results.get('meta_path')}")
    return 0 if results.get("page_count", 0) > 0 else 1


def cmd_lemdesk_handoff(args: argparse.Namespace) -> int:
    from lemdesk_brief import SESSION_HANDOFF, write_session_handoff

    if args.read:
        if SESSION_HANDOFF.exists():
            print(SESSION_HANDOFF.read_text())
        else:
            print("No handoff file. Run: python3 bot.py lemdesk-handoff")
            return 1
        return 0

    path = write_session_handoff(
        focus=args.focus or "",
        notes=args.notes or "",
        next_steps=args.next_steps or "",
    )
    print(f"Session handoff → {path}")
    print("Open this file when you move to another room/desktop.")
    return 0


def cmd_lemdesk_health(args: argparse.Namespace) -> int:
    from lemdesk_pro.desk_health import run_health_check

    report = run_health_check()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Desk Health: {report['score']}/100 ({report['grade']})")
        print(report["summary"])
        print()
        for c in report["checks"]:
            icon = {"ok": "✓", "warn": "!", "fail": "✗"}.get(c["status"], "?")
            print(f"  [{icon}] {c['label']}: {c['detail']}")
    return 0 if report["score"] >= 40 else 1


def cmd_lemdesk_desk_up(args: argparse.Namespace) -> int:
    from lemdesk_pro.desk_up import run_desk_up

    print("=== LEMdesk Desk Up ===")
    report = run_desk_up(
        sync=args.sync,
        open_nas=args.mount_nas,
        heal=args.heal,
        mirror_nas=args.mirror_nas,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    health = report.get("health") or {}
    return 0 if health.get("score", 0) >= 40 else 1


def cmd_lemdesk_backup_gc(_: argparse.Namespace) -> int:
    import subprocess

    script = Path(__file__).parent / "lemdesk" / "scripts" / "sync_gc_backup.sh"
    return subprocess.call([str(script)])


def cmd_lemdesk_install(args: argparse.Namespace) -> int:
    import subprocess

    root = Path(__file__).parent
    script = root / "lemdesk" / "scripts" / "lemdesk_install.sh"
    rc = subprocess.call(["bash", str(script), args.profile])
    if rc == 0 and args.login_item:
        login = root / "lemdesk" / "scripts" / "install_login_item.sh"
        subprocess.call(["bash", str(login), "--with-pro"])
    return rc


def cmd_lemdesk_license(args: argparse.Namespace) -> int:
    from lemdesk_pro.license import license_status, save_license_key

    if args.set:
        path = save_license_key(args.set)
        print(f"License saved → {path}")
        return 0
    st = license_status()
    if args.json:
        print(json.dumps(st, indent=2))
    else:
        print(f"Licensed: {st['licensed']}")
        if st["licensed"]:
            print(f"  Key: {st.get('key_preview')}")
        print(f"  File: {st['path']}")
        print("  Purchase: https://lemdev.com/pricing.html")
    return 0


def cmd_lemdesk_smart_handoff(args: argparse.Namespace) -> int:
    from lemdesk_pro.smart_handoff import write_smart_handoff

    paths = write_smart_handoff(
        focus=args.focus or "",
        notes=args.notes or "",
        next_steps=args.next_steps or "",
    )
    print("Smart Handoff written:")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    print("\nPaste desk_handoff_prompt.md into your next Cursor room.")
    return 0


def cmd_lemdesk_pro(args: argparse.Namespace) -> int:
    from lemdesk_pro.menubar import run_cli_fallback, run_menubar

    if args.cli:
        run_cli_fallback(port=args.port, open_browser=not args.no_open_dashboard)
        return 0
    run_menubar(
        port=args.port,
        open_dashboard=not args.no_open_dashboard,
        dev_mode=args.dev,
    )
    return 0


def cmd_ai_paths(args: argparse.Namespace) -> int:
    import subprocess
    import sys

    script = Path(__file__).parent / "lemdesk" / "scripts" / "ai_path_assistant.py"
    cmd = [sys.executable, str(script), args.ai_cmd]
    if args.ai_cmd == "resolve" and args.name:
        cmd.append(args.name)
    if getattr(args, "json", False):
        cmd.append("--json")
    if getattr(args, "out", ""):
        cmd.extend(["--out", args.out])
    return subprocess.call(cmd)


def cmd_lemdesk_search(args: argparse.Namespace) -> int:
    from lemdesk_brief import search_knowledge

    query = " ".join(args.query)
    hits = search_knowledge(query, limit=args.limit)
    if not hits:
        print(f"No matches for: {query}")
        return 1
    for h in hits:
        print(f"[{h['score']}] {h['title']} ({h['topic']})")
        print(f"  {h['url']}")
        print(f"  {h['snippet'][:300]}")
        print()
    return 0


def cmd_lemdesk_review(_: argparse.Namespace) -> int:
    knowledge = load_knowledge()
    if not knowledge.get("pages"):
        print("No lemdesk/data/knowledge.json — run scrape first:")
        print("  python3 scrape_lemdesk.py --backend httpx --workers 6 --max-depth 2 --post-process")
        return 1
    paths = post_process_all(knowledge)
    print("Docker AI LAN — artifacts refreshed")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    ctx = paths.get("agent_context")
    if ctx:
        print(f"\nPoint Cursor/Claude at {ctx}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    report = run_scan(
        CFG,
        capital=args.capital,
        days=args.days,
        limit=args.limit,
        max_price=args.max_price,
    )
    print_scan_report(report)
    path = save_scan_report(report)
    print(f"\nSaved: {path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Crypto.com hybrid trading bot")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    bt = sub.add_parser("backtest", help="Walk-forward backtest — run before live")
    bt.add_argument("--days", type=int, default=300)
    bt.add_argument("--capital", type=float, default=1000.0)
    bt.add_argument("--optimize", action="store_true", help="Find best params via grid search")
    bt.set_defaults(func=cmd_backtest)
    a = sub.add_parser("auto", help="WebSocket auto mode")
    a.add_argument("--live", action="store_true")
    a.set_defaults(func=cmd_auto)
    sub.add_parser("stop").set_defaults(func=cmd_stop)
    sub.add_parser("resume").set_defaults(func=cmd_resume)
    sub.add_parser("migrate-secrets", help="Move API keys to ~/.config/cursor-crypto/secrets.env").set_defaults(
        func=cmd_migrate_secrets
    )
    sc = sub.add_parser("scan", help="Rank smaller USDT altcoins by backtest edge")
    sc.add_argument("--days", type=int, default=300)
    sc.add_argument("--capital", type=float, default=30.0)
    sc.add_argument("--limit", type=int, default=30)
    sc.add_argument("--max-price", type=float, default=None, help="Only coins priced below this (USDT)")
    sc.set_defaults(func=cmd_scan)
    cp = sub.add_parser("compare", help="Grid vs hybrid backtest")
    cp.add_argument("--pair", default=None, help="Single pair (default: INSTRUMENT from .env)")
    cp.add_argument("--days", type=int, default=300)
    cp.add_argument("--capital", type=float, default=30.0)
    cp.set_defaults(func=cmd_compare)
    rt = sub.add_parser("rotate", help="Scan alts → apply best pick to .env INSTRUMENT")
    rt.add_argument("--days", type=int, default=300)
    rt.add_argument("--capital", type=float, default=50.0)
    rt.add_argument("--limit", type=int, default=30)
    rt.add_argument("--max-price", type=float, default=80.0)
    rt.add_argument("--dry-run", action="store_true", help="Scan only, do not edit .env")
    rt.add_argument("--no-reset-paper", action="store_true", help="Keep paper_state when pair changes")
    rt.set_defaults(func=lambda a: cmd_rotate(a, CFG))
    gr = sub.add_parser("gbt-review", help="Self-review: questions, scan, optimize toward profit")
    gr.add_argument("--days", type=int, default=300)
    gr.add_argument("--capital", type=float, default=50.0)
    gr.add_argument("--no-optimize", action="store_true")
    gr.add_argument("--no-scan", action="store_true")
    gr.set_defaults(func=cmd_gbt_review)
    gl = sub.add_parser("gbt-loop", help="Review + smart rotate + backtest + log (run weekly)")
    gl.add_argument("--days", type=int, default=300)
    gl.add_argument("--capital", type=float, default=50.0)
    gl.add_argument("--dry-run", action="store_true", help="Review only, do not edit .env")
    gl.set_defaults(func=cmd_gbt_loop)
    bi = sub.add_parser("birdseed-init", help=f"{BRAND}: write improved .env + pick CDC symbols")
    bi.add_argument("--days", type=int, default=300)
    bi.add_argument("--capital", type=float, default=50.0)
    bi.add_argument("--max-price", type=float, default=80.0)
    bi.set_defaults(func=cmd_birdseed_init)
    br = sub.add_parser("birdseed-review", help=f"{BRAND}: profit review + optimize + agent brief")
    br.add_argument("--days", type=int, default=300)
    br.add_argument("--capital", type=float, default=50.0)
    br.add_argument("--no-optimize", action="store_true")
    br.add_argument("--no-scan", action="store_true")
    br.add_argument("--dry-run", action="store_true", help="Review only — do not apply fixes to .env")
    br.set_defaults(func=cmd_birdseed_review)
    bl = sub.add_parser("birdseed-loop", help=f"{BRAND}: weekly review + rotate + backtest + agent brief")
    bl.add_argument("--days", type=int, default=300)
    bl.add_argument("--capital", type=float, default=50.0)
    bl.add_argument("--dry-run", action="store_true")
    bl.set_defaults(func=cmd_birdseed_loop)
    ba = sub.add_parser("birdseed-agent", help=f"{BRAND}: export Cursor/Claude agent context files")
    ba.add_argument("--fresh", action="store_true", help="Run full review before writing brief")
    ba.add_argument("--days", type=int, default=300)
    ba.add_argument("--capital", type=float, default=50.0)
    ba.set_defaults(func=cmd_birdseed_agent)
    dar = sub.add_parser(
        "lemdesk-review",
        help="LEMdesk: refresh brief, topology, RAG corpus, super_app index",
    )
    dar.set_defaults(func=cmd_lemdesk_review)
    das = sub.add_parser("lemdesk-search", help="Search LEMdesk knowledge base")
    das.add_argument("query", nargs="+", help="Search terms")
    das.add_argument("--limit", type=int, default=8)
    das.set_defaults(func=cmd_lemdesk_search)
    dah = sub.add_parser("lemdesk-handoff", help="Write/read session handoff for cross-room continuity")
    dah.add_argument("--read", action="store_true", help="Print existing handoff instead of writing")
    dah.add_argument("--focus", default="", help="What you were working on")
    dah.add_argument("--notes", default="", help="Open threads / notes")
    dah.add_argument("--next-steps", default="", help="Bulleted next steps (markdown)")
    dah.set_defaults(func=cmd_lemdesk_handoff)
    dhl = sub.add_parser("lemdesk-health", help="LEMdesk Pro: desk health score")
    dhl.add_argument("--json", action="store_true", help="Print JSON report")
    dhl.set_defaults(func=cmd_lemdesk_health)
    ddu = sub.add_parser(
        "lemdesk-desk-up",
        help="LEMdesk Pro: morning startup (Docker, DMR, mounts, health)",
    )
    ddu.add_argument("--sync", action="store_true", help="Run lemdesk-sync --fast after checks")
    ddu.add_argument("--mount-nas", action="store_true", help="Open NAS mount dialog if missing")
    ddu.add_argument("--heal", action="store_true", help="Auto-fix storage + stale corpus")
    ddu.add_argument("--mirror-nas", action="store_true", help="Mirror corpus to NAS after checks")
    ddu.add_argument("--json", action="store_true", help="Print JSON report")
    ddu.set_defaults(func=cmd_lemdesk_desk_up)
    dins = sub.add_parser("lemdesk-install", help="One-shot LEMdesk install (mac-mini profile)")
    dins.add_argument("--profile", default="mac-mini", choices=["mac-mini", "default"])
    dins.add_argument("--login-item", action="store_true", help="Install launchd login agents")
    dins.set_defaults(func=cmd_lemdesk_install)
    dlic = sub.add_parser("lemdesk-license", help="LEMdesk Pro license key")
    dlic.add_argument("--set", default="", help="Save license key")
    dlic.add_argument("--status", action="store_true", help="Show license status")
    dlic.add_argument("--json", action="store_true")
    dlic.set_defaults(func=cmd_lemdesk_license)
    dbg = sub.add_parser(
        "lemdesk-backup-gc",
        help="Mirror LEMdesk Pro to GC-MM2 lemdev.com/LemDesk/Pro",
    )
    dbg.set_defaults(func=cmd_lemdesk_backup_gc)
    dsh = sub.add_parser(
        "lemdesk-smart-handoff",
        help="LEMdesk Pro: structured desk pack + agent prompt",
    )
    dsh.add_argument("--focus", default="", help="What you were working on")
    dsh.add_argument("--notes", default="", help="Open threads / notes")
    dsh.add_argument("--next-steps", default="", help="Bulleted next steps (markdown)")
    dsh.set_defaults(func=cmd_lemdesk_smart_handoff)
    dlp = sub.add_parser(
        "lemdesk-pro",
        help="LEMdesk Pro: menu bar app + dashboard at http://127.0.0.1:8765",
    )
    dlp.add_argument("--port", type=int, default=8765)
    dlp.add_argument("--cli", action="store_true", help="Headless dashboard (no menu bar)")
    dlp.add_argument("--dev", action="store_true", help="Skip license check (development)")
    dlp.add_argument("--no-open-dashboard", action="store_true", help="Do not open browser on start")
    dlp.set_defaults(func=cmd_lemdesk_pro)
    ap = sub.add_parser("ai-paths", help="AI path registry: wizard, doctor, resolve (Mac/Win/Synology)")
    ap_sub = ap.add_subparsers(dest="ai_cmd", required=True)
    ap_sub.add_parser("wizard", help="Interactive path setup").set_defaults(ai_cmd="wizard")
    ap_sub.add_parser("init", help="Copy template to ~/.config/lemdesk/").set_defaults(ai_cmd="init")
    ap_sub.add_parser("repair", help="Fix corrupt config after bad wizard paste").set_defaults(ai_cmd="repair")
    ap_doc = ap_sub.add_parser("doctor", help="Check all paths")
    ap_doc.add_argument("--json", action="store_true")
    ap_doc.set_defaults(ai_cmd="doctor")
    ap_res = ap_sub.add_parser("resolve", help="Resolve one path name")
    ap_res.add_argument("name")
    ap_res.set_defaults(ai_cmd="resolve")
    ap_exp = ap_sub.add_parser("export", help="Shell export LEMDESK_* vars")
    ap_exp.add_argument("--out", default="")
    ap_exp.set_defaults(ai_cmd="export")
    ap_brf = ap_sub.add_parser("brief", help="Write ai_path_map.md for Cursor")
    ap_brf.add_argument("--out", default="")
    ap_brf.set_defaults(ai_cmd="brief")
    ap.set_defaults(func=cmd_ai_paths, name="")
    daa = sub.add_parser(
        "lemdesk-sync",
        help="Auto pipeline: scrape (smart/full), RAG, briefs, handoff, incoming cleanup",
    )
    daa.add_argument("--full", action="store_true", help="Force full BFS scrape")
    daa.add_argument("--fast", action="store_true", help="Full scrape max speed: httpx, 12 workers, depth 1, no raw")
    daa.add_argument("--backend", default="auto", choices=["auto", "httpx", "crawl4ai"])
    daa.add_argument("--workers", type=int, default=10)
    daa.add_argument("--max-depth", type=int, default=2)
    daa.add_argument("--raw", action="store_true", help="Save raw HTML")
    daa.add_argument("--no-cleanup", action="store_true")
    daa.add_argument("--skip-dmr-check", action="store_true")
    daa.add_argument("--focus", default="", help="Handoff focus line")
    daa.set_defaults(func=cmd_lemdesk_auto)
    daa_legacy = sub.add_parser(
        "lemdesk-auto",
        help="Alias for lemdesk-sync",
    )
    daa_legacy.add_argument("--full", action="store_true")
    daa_legacy.add_argument("--fast", action="store_true")
    daa_legacy.add_argument("--backend", default="auto", choices=["auto", "httpx", "crawl4ai"])
    daa_legacy.add_argument("--workers", type=int, default=10)
    daa_legacy.add_argument("--max-depth", type=int, default=2)
    daa_legacy.add_argument("--raw", action="store_true")
    daa_legacy.add_argument("--no-cleanup", action="store_true")
    daa_legacy.add_argument("--skip-dmr-check", action="store_true")
    daa_legacy.add_argument("--focus", default="")
    daa_legacy.set_defaults(func=cmd_lemdesk_auto)
    lr = sub.add_parser("learn", help="Open-source learning path (cloned repos → our bot)")
    lr.add_argument("--indicators", action="store_true", help="Show live RSI/Stoch/SMA on pair")
    lr.add_argument("--backtest", action="store_true", help="A/B backtest: Markov vs +indicators")
    lr.add_argument("--pair", default=PAIR)
    lr.add_argument("--days", type=int, default=300)
    lr.add_argument("--capital", type=float, default=50.0)
    lr.add_argument("--env", default=ENV)
    lr.set_defaults(func=lambda a: cmd_learn(a, CFG))
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
