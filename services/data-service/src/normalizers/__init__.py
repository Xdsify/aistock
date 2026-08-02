"""数据标准化"""
import pandas as pd
from datetime import datetime
from typing import Optional


class DataNormalizer:
    """将不同数据源的数据标准化为内部统一格式"""

    @staticmethod
    def kline_record(
        symbol: str, row: pd.Series, period: str = "daily"
    ) -> dict:
        """标准化K线记录"""
        record = {
            "symbol": symbol,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
            "amount": float(row.get("amount", 0)),
        }

        if period == "daily":
            record["trade_date"] = pd.Timestamp(row["trade_date"]).date()
        else:
            record["trade_time"] = pd.Timestamp(row["trade_time"]).to_pydatetime()

        return record

    @staticmethod
    def realtime_quote(raw: dict) -> dict:
        """标准化实时行情"""
        return {
            "symbol": raw["symbol"],
            "name": raw.get("name", ""),
            "price": raw["price"],
            "open": raw.get("open", raw["price"]),
            "high": raw.get("high", raw["price"]),
            "low": raw.get("low", raw["price"]),
            "pre_close": raw.get("pre_close", raw["price"]),
            "change": raw.get("change", 0),
            "change_pct": raw.get("change_pct", 0),
            "volume": raw.get("volume", 0),
            "amount": raw.get("amount", 0),
            "turnover_rate": raw.get("turnover_rate", 0),
            "timestamp": raw.get("timestamp", datetime.now().isoformat()),
        }

    @staticmethod
    def symbol_to_ts_code(symbol: str) -> str:
        """将symbol格式转为Tushare ts_code格式"""
        # 000001.SZ -> 000001.SZ (已经是ts_code格式)
        return symbol

    @staticmethod
    def symbol_to_ak_code(symbol: str) -> str:
        """将symbol格式转为AKShare代码格式"""
        # 000001.SZ -> 000001
        return symbol.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
