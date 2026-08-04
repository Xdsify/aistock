"""回测引擎 - 基于历史K线模拟策略收益"""
from datetime import datetime
from .strategies.base import BarData, Action
from .strategies.registry import get_all_strategies

COMMISSION_RATE = 0.00025   # 佣金 万2.5
STAMP_TAX_RATE = 0.001      # 印花税 千1 (仅卖出)
MIN_COMMISSION = 5.0        # 最低佣金


def _parse_records(records: list[dict], symbol: str) -> list[BarData]:
    bars = []
    for r in records:
        try:
            dt_raw = r.get("trade_date")
            if isinstance(dt_raw, str):
                dt_raw = datetime.fromisoformat(dt_raw) if "T" in dt_raw \
                    else datetime.strptime(dt_raw, "%Y-%m-%d")
            bars.append(BarData(
                symbol=symbol,
                datetime=dt_raw,
                open=float(r.get("open", 0)),
                high=float(r.get("high", 0)),
                low=float(r.get("low", 0)),
                close=float(r.get("close", 0)),
                volume=float(r.get("volume", 0)),
                amount=float(r.get("amount", 0)),
            ))
        except Exception:
            continue
    return bars


def run_backtest(
    strategy_name: str,
    records: list[dict],
    initial_capital: float = 100000.0,
    symbol: str = "",
) -> dict:
    """对给定K线记录跑一次策略回测

    策略的 self.pos 与回测持仓同步, 保证 buy/sell 状态机正确。
    """
    strategy_class = get_all_strategies().get(strategy_name)
    if strategy_class is None:
        raise ValueError(f"策略不存在: {strategy_name}")

    if records:
        symbol = symbol or records[0].get("symbol", "")
    strategy = strategy_class()
    strategy.on_init()

    bars = _parse_records(records, symbol)
    if len(bars) < 30:
        raise ValueError("K线数据不足(至少30根)")

    cash = initial_capital
    shares = 0
    entry_cost = 0.0
    equity_curve = []
    trades = []
    peak = initial_capital
    max_drawdown = 0.0
    wins = 0

    for bar in bars:
        strategy.update_bar(bar)
        signal = strategy.on_bar(bar)
        close = bar.close

        if signal and signal.action == Action.BUY and shares == 0:
            budget = cash * strategy.max_position_pct
            qty = int(budget / close / 100) * 100
            if qty >= 100:
                cost = qty * close
                commission = max(MIN_COMMISSION, cost * COMMISSION_RATE)
                if cost + commission <= cash:
                    cash -= cost + commission
                    shares = qty
                    entry_cost = cost
                    strategy.pos = 1  # 同步策略内部持仓状态
                    trades.append({
                        "date": str(bar.datetime.date()), "action": "BUY",
                        "price": round(close, 2), "qty": qty,
                    })

        elif signal and signal.action == Action.SELL and shares > 0:
            proceeds = shares * close
            commission = max(MIN_COMMISSION, proceeds * COMMISSION_RATE)
            stamp_tax = proceeds * STAMP_TAX_RATE
            cash += proceeds - commission - stamp_tax
            pnl = proceeds - commission - stamp_tax - entry_cost
            if pnl > 0:
                wins += 1
            strategy.pos = 0
            trades.append({
                "date": str(bar.datetime.date()), "action": "SELL",
                "price": round(close, 2), "qty": shares, "pnl": round(pnl, 2),
            })
            shares = 0

        equity = cash + shares * close
        equity_curve.append({"time": str(bar.datetime.date()), "value": round(equity, 2)})
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd

    # 期末强制平仓
    if shares > 0 and bars:
        close = bars[-1].close
        proceeds = shares * close
        commission = max(MIN_COMMISSION, proceeds * COMMISSION_RATE)
        stamp_tax = proceeds * STAMP_TAX_RATE
        cash += proceeds - commission - stamp_tax
        pnl = proceeds - commission - stamp_tax - entry_cost
        if pnl > 0:
            wins += 1
        trades.append({
            "date": str(bars[-1].datetime.date()), "action": "SELL(平仓)",
            "price": round(close, 2), "qty": shares, "pnl": round(pnl, 2),
        })
        shares = 0

    final_equity = cash
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100 if initial_capital else 0
    sell_trades = [t for t in trades if t["action"].startswith("SELL")]
    win_rate = wins / max(len(sell_trades), 1) * 100
    gross_profit = sum(t.get("pnl", 0) for t in sell_trades if t.get("pnl", 0) > 0)
    gross_loss = abs(sum(t.get("pnl", 0) for t in sell_trades if t.get("pnl", 0) < 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 \
        else (999.0 if gross_profit > 0 else 0.0)

    return {
        "strategy": strategy_name,
        "symbol": symbol,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "win_rate": round(win_rate, 1),
        "profit_factor": profit_factor,
        "max_drawdown_pct": round(max_drawdown, 2),
        "trades_count": len(trades),
        "equity_curve": equity_curve,
        "trades": trades[-20:],
    }
