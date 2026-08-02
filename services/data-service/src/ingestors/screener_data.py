"""
选股数据采集器 - 为AI选股提供市场扫描数据
采集: 涨幅榜 / 成交量放大 / 资金流向 / 热门板块
所有AKShare调用都是同步的, 放在线程池运行
"""
import akshare as ak
import pandas as pd
from datetime import datetime
from loguru import logger


def fetch_screening_data() -> dict:
    """采集选股所需的市场数据（纯同步，供run_in_executor调用）

    Returns:
        dict 包含 hot_sectors, top_gainers, volume_leaders, money_flow_leaders
    """
    result = {
        "hot_sectors": [],
        "top_gainers": [],
        "volume_leaders": [],
        "money_flow_leaders": [],
        "timestamp": datetime.now().isoformat(),
    }

    # 1. 涨幅榜 Top 10
    try:
        df = ak.stock_zh_a_spot_em()
        df = df.sort_values("涨跌幅", ascending=False)
        for _, row in df.head(10).iterrows():
            result["top_gainers"].append({
                "symbol": _format_code(row["代码"]),
                "name": row["名称"],
                "change_pct": round(float(row["涨跌幅"]), 2),
                "price": float(row["最新价"]),
                "volume": float(row.get("成交量", 0)),
            })
    except Exception as e:
        logger.error(f"涨幅榜采集失败: {e}")

    # 2. 成交量放大（量比 > 1.5）
    try:
        if len(df) > 0:
            vol_avg = df["成交量"].mean()
            df["量比"] = df["成交量"] / max(vol_avg, 1)
            vol_df = df[df["量比"] > 1.5].sort_values("量比", ascending=False)
            for _, row in vol_df.head(10).iterrows():
                result["volume_leaders"].append({
                    "symbol": _format_code(row["代码"]),
                    "name": row["名称"],
                    "vol_ratio": round(float(row["量比"]), 2),
                    "price": float(row["最新价"]),
                    "change_pct": round(float(row["涨跌幅"]), 2),
                })
    except Exception as e:
        logger.error(f"量比采集失败: {e}")

    # 3. 资金流向（用成交额替代）
    try:
        if len(df) > 0:
            amount_df = df.sort_values("成交额", ascending=False)
            for _, row in amount_df.head(10).iterrows():
                result["money_flow_leaders"].append({
                    "symbol": _format_code(row["代码"]),
                    "name": row["名称"],
                    "amount": round(float(row["成交额"]) / 1e8, 2),  # 转亿元
                    "unit": "亿",
                    "change_pct": round(float(row["涨跌幅"]), 2),
                })
    except Exception as e:
        logger.error(f"资金流向采集失败: {e}")

    # 4. 热门板块
    try:
        sector_df = ak.stock_board_industry_name_em()
        sector_df = sector_df.sort_values("涨跌幅", ascending=False)
        for _, row in sector_df.head(6).iterrows():
            result["hot_sectors"].append(
                f"{row['板块名称']} {float(row['涨跌幅']):+.2f}%"
            )
    except Exception as e:
        logger.error(f"板块采集失败: {e}")

    logger.info(f"选股数据采集完成: {len(result['top_gainers'])}涨幅+"
                f"{len(result['volume_leaders'])}放量+"
                f"{len(result['hot_sectors'])}板块")
    return result


def _format_code(code: str) -> str:
    """格式化股票代码"""
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    elif code.startswith(("6", "9")):
        return f"{code}.SH"
    elif code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code
