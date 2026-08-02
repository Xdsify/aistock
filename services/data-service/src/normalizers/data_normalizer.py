"""数据标准化器 - 将不同数据源格式统一为内部格式"""
from datetime import datetime
from typing import Optional


class DataNormalizer:
    """数据标准化器"""

    # A股交易所代码映射
    EXCHANGE_MAP = {
        "SH": "SSE",
        "SZ": "SZSE",
        "BJ": "BSE",
        "SSE": "SSE",
        "SZSE": "SZSE",
    }

    # 板块判断
    @staticmethod
    def get_board(symbol: str) -> str:
        """根据代码判断板块"""
        if symbol.startswith("688"):
            return "star"    # 科创板
        elif symbol.startswith(("300", "301")):
            return "gem"     # 创业板
        elif symbol.startswith(("8", "4")):
            return "bse"     # 北交所
        else:
            return "main"    # 主板

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """标准化股票代码为 XXXX.SZ/XXXX.SH 格式"""
        symbol = symbol.strip().upper()
        if "." in symbol:
            return symbol
        # 根据代码判断交易所
        if symbol.startswith(("6", "9")):
            return f"{symbol}.SH"
        elif symbol.startswith(("0", "2", "3")):
            return f"{symbol}.SZ"
        elif symbol.startswith(("8", "4")):
            return f"{symbol}.BJ"
        return symbol

    def normalize_kline(self, raw: dict, source: str = "akshare") -> dict:
        """标准化K线数据"""
        return {
            "symbol": self.normalize_symbol(raw.get("symbol", raw.get("code", ""))),
            "trade_date": str(raw.get("trade_date", raw.get("date", ""))),
            "open": float(raw.get("open", 0)),
            "high": float(raw.get("high", 0)),
            "low": float(raw.get("low", 0)),
            "close": float(raw.get("close", 0)),
            "volume": float(raw.get("volume", 0)),
            "amount": float(raw.get("amount", 0)),
            "source": source,
        }

    def normalize_quote(self, raw: dict, source: str = "akshare") -> dict:
        """标准化实时行情"""
        return {
            "symbol": self.normalize_symbol(raw.get("symbol", raw.get("code", ""))),
            "name": raw.get("name", ""),
            "price": float(raw.get("price", raw.get("current", 0))),
            "open": float(raw.get("open", 0)),
            "high": float(raw.get("high", 0)),
            "low": float(raw.get("low", 0)),
            "pre_close": float(raw.get("pre_close", raw.get("preClose", 0))),
            "volume": float(raw.get("volume", 0)),
            "amount": float(raw.get("amount", 0)),
            "change": float(raw.get("change", 0)),
            "change_pct": float(raw.get("change_pct", raw.get("pctChg", 0))),
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "board": self.get_board(raw.get("symbol", raw.get("code", ""))),
        }


normalizer = DataNormalizer()
