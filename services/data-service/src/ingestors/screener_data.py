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


def fetch_zt_pool(date: str) -> dict:
    """涨停股池 (AKShare stock_zt_pool_em, 含连板数/封板资金/炸板次数/行业)

    Args:
        date: 交易日 YYYYMMDD
    """
    import akshare as ak
    df = ak.stock_zt_pool_em(date=date)
    if df is None or df.empty:
        return {"date": date, "count": 0, "pools": []}

    records = []
    for _, row in df.iterrows():
        try:
            records.append({
                "symbol": _format_code(str(row["代码"]).strip()),
                "name": str(row["名称"]),
                "change_pct": round(float(row.get("涨跌幅", 0)), 2),
                "price": round(float(row.get("最新价", 0)), 2),
                "turnover_rate": round(float(row.get("换手率", 0)), 2),
                "seal_amount": round(float(row.get("封板资金", 0)) / 1e8, 2),  # 亿元
                "first_time": str(row.get("首次封板时间", "")),
                "last_time": str(row.get("最后封板时间", "")),
                "zhaban_count": int(row.get("炸板次数", 0)),
                "lianban": int(row.get("连板数", 1)),
                "industry": str(row.get("所属行业", "")),
            })
        except Exception:
            continue

    # 汇总
    lianban_list = [r["lianban"] for r in records]
    return {
        "date": date,
        "count": len(records),
        "first_board": sum(1 for x in lianban_list if x == 1),   # 首板
        "lianban": sum(1 for x in lianban_list if x >= 2),       # 连板
        "max_lianban": max(lianban_list, default=0),             # 最高几板
        "pools": records,
    }


# 示例数据 (行情服务不可用时, 便于预览功能)
MOCK_ZT_POOL = [
    {"symbol": "000001.SZ", "name": "平安银行", "change_pct": 10.02, "price": 12.55, "turnover_rate": 3.2,
     "seal_amount": 1.85, "first_time": "09:35:12", "last_time": "09:35:12", "zhaban_count": 0, "lianban": 1, "industry": "银行"},
    {"symbol": "000858.SZ", "name": "五粮液", "change_pct": 10.00, "price": 152.3, "turnover_rate": 4.1,
     "seal_amount": 3.20, "first_time": "09:42:08", "last_time": "09:42:08", "zhaban_count": 0, "lianban": 1, "industry": "白酒"},
    {"symbol": "300750.SZ", "name": "宁德时代", "change_pct": 20.01, "price": 245.6, "turnover_rate": 5.8,
     "seal_amount": 6.50, "first_time": "10:05:33", "last_time": "10:05:33", "zhaban_count": 1, "lianban": 2, "industry": "电池"},
    {"symbol": "600519.SH", "name": "贵州茅台", "change_pct": 10.00, "price": 1720.0, "turnover_rate": 0.9,
     "seal_amount": 12.30, "first_time": "13:20:45", "last_time": "13:20:45", "zhaban_count": 2, "lianban": 3, "industry": "白酒"},
    {"symbol": "688981.SH", "name": "中芯国际", "change_pct": 20.02, "price": 88.9, "turnover_rate": 6.4,
     "seal_amount": 4.75, "first_time": "09:50:11", "last_time": "09:50:11", "zhaban_count": 0, "lianban": 2, "industry": "半导体"},
    {"symbol": "002594.SZ", "name": "比亚迪", "change_pct": 10.01, "price": 263.4, "turnover_rate": 3.7,
     "seal_amount": 5.10, "first_time": "14:02:19", "last_time": "14:02:19", "zhaban_count": 1, "lianban": 4, "industry": "汽车"},
    {"symbol": "600030.SH", "name": "中信证券", "change_pct": 10.03, "price": 28.4, "turnover_rate": 2.5,
     "seal_amount": 2.05, "first_time": "09:58:40", "last_time": "09:58:40", "zhaban_count": 0, "lianban": 1, "industry": "证券"},
]


def mock_zt_pool(date: str) -> dict:
    """行情不可用时的示例涨停池"""
    pools = [dict(p) for p in MOCK_ZT_POOL]
    for p in pools:
        p["symbol"] = p["symbol"]
    lianban_list = [p["lianban"] for p in pools]
    return {
        "date": date, "count": len(pools), "mock": True,
        "first_board": sum(1 for x in lianban_list if x == 1),
        "lianban": sum(1 for x in lianban_list if x >= 2),
        "max_lianban": max(lianban_list, default=0),
        "pools": pools,
    }


def _format_code(code: str) -> str:
    """格式化股票代码"""
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    elif code.startswith(("6", "9")):
        return f"{code}.SH"
    elif code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code
