"""AKShare数据采集器"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Optional
import pandas as pd
from loguru import logger

from ..storage import redis_client as _redis

# 用于限时运行可能挂死的 AKShare 同步调用 (eastmoney 在部分网络会长时间卡住)
_KLINE_POOL = ThreadPoolExecutor(max_workers=4)


class AKShareIngestor:
    """AKShare行情数据采集"""

    CACHE_TTL = 60  # 实时行情缓存60秒

    async def get_stock_list(self) -> pd.DataFrame:
        """获取A股股票列表 (同步调用放线程池, 避免阻塞事件循环)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_get_stock_list)

    def _sync_get_stock_list(self) -> pd.DataFrame:
        """同步获取A股股票列表 (线程安全,不碰Redis)"""
        import akshare as ak
        df = ak.stock_info_a_code_name()
        df = df.rename(columns={
            "code": "symbol",
            "name": "name",
        })
        logger.info(f"获取股票列表: {len(df)} 只")
        return df

    async def get_daily_kline(
        self, symbol: str, start_date: str, end_date: str,
        adjust: str = "qfq"
    ) -> Optional[pd.DataFrame]:
        """获取日线K线数据 (同步AKShare调用放在线程池执行)

        Args:
            symbol: 股票代码 (如 '000001')
            start_date: 起始日期 'YYYYMMDD'
            end_date: 截止日期 'YYYYMMDD'
            adjust: 复权类型 qfq(前复权)/hfq(后复权)/None(不复权)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_get_kline_raw, symbol, start_date, end_date, adjust
        )

    def _sync_get_kline_raw(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> Optional[pd.DataFrame]:
        """同步获取日线K线 (线程安全,不碰Redis)

        优先 eastmoney (stock_zh_a_hist), 失败回退 sina (stock_zh_a_daily)。
        某些网络下 eastmoney 的 K 线接口不可达, 但 sina 可用。
        """
        import akshare as ak
        code = symbol.split(".")[0]
        df = None

        # 1) eastmoney (限时 3s, 超时/失败直接放弃, 防止挂死整个请求)
        try:
            future = _KLINE_POOL.submit(
                ak.stock_zh_a_hist,
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date, adjust=adjust,
            )
            df = future.result(timeout=3)
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "trade_date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount",
                })
                df["trade_date"] = pd.to_datetime(df["trade_date"])
        except Exception:
            df = None

        # 2) sina 兜底 (直接传日期范围, 避免拉全量历史)
        if df is None or df.empty:
            try:
                sina_symbol = ("sh" if code.startswith(("6", "9")) else "sz") + code
                df = ak.stock_zh_a_daily(
                    symbol=sina_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust or "",
                )
                if df is not None and not df.empty:
                    df = df.rename(columns={"date": "trade_date"})
                    df["trade_date"] = pd.to_datetime(df["trade_date"])
                    # 再兜底过滤一次日期范围
                    start = pd.to_datetime(start_date)
                    end = pd.to_datetime(end_date)
                    df = df[(df["trade_date"] >= start) & (df["trade_date"] <= end)]
                    if "amount" not in df.columns:
                        df["amount"] = 0
            except Exception as e:
                logger.error(f"sina获取{symbol}日线失败: {e}")
                df = None

        if df is None or df.empty:
            return None

        df["symbol"] = self._format_symbol(symbol)
        return df

    async def get_realtime_quote(self, symbol: str) -> Optional[dict]:
        """获取实时行情 (通过AKShare或缓存)"""
        # 先检查Redis缓存
        cache_key = f"market:realtime:{symbol}"
        cached = await _redis.redis_client.get(cache_key)
        if cached:
            import json
            return json.loads(cached)

        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == symbol.replace(".SZ", "").replace(".SH", "")]
            if row.empty:
                return None

            quote = {
                "symbol": self._format_symbol(symbol),
                "name": row.iloc[0]["名称"],
                "price": float(row.iloc[0]["最新价"]),
                "change_pct": float(row.iloc[0]["涨跌幅"]),
                "change": float(row.iloc[0]["涨跌额"]),
                "volume": float(row.iloc[0]["成交量"]),
                "amount": float(row.iloc[0]["成交额"]),
                "high": float(row.iloc[0]["最高"]),
                "low": float(row.iloc[0]["最低"]),
                "open": float(row.iloc[0]["今开"]),
                "pre_close": float(row.iloc[0]["昨收"]),
                "turnover_rate": float(row.iloc[0].get("换手率", 0)),
                "timestamp": datetime.now().isoformat(),
            }

            # 缓存到Redis
            import json
            await _redis.redis_client.setex(cache_key, self.CACHE_TTL, json.dumps(quote))
            return quote
        except Exception as e:
            logger.error(f"获取{symbol}实时行情失败: {e}")
            return None

    async def get_market_sentiment(self) -> dict:
        """获取市场情绪指标 (基于上证指数日线,快速稳定)"""
        try:
            import akshare as ak
            import pandas as pd

            # 上证指数日线 (速度快，稳定)
            df = ak.stock_zh_index_daily_em(symbol="sh000001")
            latest = df.iloc[-1]
            prev = df.iloc[-2]

            # 近5日走势
            recent5 = df.tail(5)
            up_days = int((recent5["close"] > recent5["open"]).sum())

            # 成交量趋势
            avg_vol_20 = float(df.tail(20)["volume"].mean())
            vol_ratio = round(float(latest["volume"]) / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

            # 20日位置
            high20 = float(df.tail(20)["high"].max())
            low20 = float(df.tail(20)["low"].min())
            close = float(latest["close"])
            if high20 != low20:
                position_20d = round((close - low20) / (high20 - low20) * 100, 1)
            else:
                position_20d = 50.0

            sh_change = round(close / float(prev["close"]) * 100 - 100, 2)

            # 同步获取深证成指和创业板
            try:
                df_sz = ak.stock_zh_index_daily_em(symbol="sz399001")
                sz_change = round(float(df_sz.iloc[-1]["close"]) / float(df_sz.iloc[-2]["close"]) * 100 - 100, 2)
            except Exception:
                sz_change = 0.0

            try:
                df_cy = ak.stock_zh_index_daily_em(symbol="sz399006")
                cy_change = round(float(df_cy.iloc[-1]["close"]) / float(df_cy.iloc[-2]["close"]) * 100 - 100, 2)
            except Exception:
                cy_change = 0.0

            sentiment = {
                "sh_index": round(close, 2),
                "sh_change_pct": sh_change,
                "sz_change_pct": sz_change,
                "cy_change_pct": cy_change,
                "vol_ratio": vol_ratio,
                "position_20d": position_20d,
                "recent5_up_days": up_days,
                "trend": "强势" if position_20d > 60 else ("弱势" if position_20d < 40 else "震荡"),
                "timestamp": datetime.now().isoformat(),
                "source": "上证/深证/创业板指数日线",
            }

            # 缓存情绪数据
            import json
            await _redis.redis_client.setex(
                "market:sentiment", 120, json.dumps(sentiment)
            )
            return sentiment
        except Exception as e:
            logger.error(f"获取市场情绪失败: {e}")
            return {}

    async def get_north_flow(self) -> Optional[float]:
        """获取北向资金净流入"""
        try:
            import akshare as ak
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                return float(latest.get("value", 0))
        except Exception as e:
            logger.error(f"获取北向资金失败: {e}")
        return None

    async def download_all_stocks_daily(
        self, date_str: Optional[str] = None
    ) -> int:
        """批量下载全市场日线数据

        Args:
            date_str: 下载指定日期，默认为最近交易日
        Returns:
            成功下载的股票数量
        """
        if date_str is None:
            # 默认下载最近5天的数据
            end_date = date.today().strftime("%Y%m%d")
            start_date = (date.today() - timedelta(days=7)).strftime("%Y%m%d")
        else:
            end_date = date_str
            start_date = date_str

        stocks = await self.get_stock_list()
        success_count = 0

        for _, row in stocks.iterrows():
            symbol = row["symbol"]
            try:
                df = await self.get_daily_kline(symbol, start_date, end_date)
                if df is not None and not df.empty:
                    # 批量写入数据库由调用方处理
                    success_count += 1
            except Exception:
                continue
            # 控制频率，避免被封
            await asyncio.sleep(0.1)

        logger.info(f"批量下载完成: {success_count}/{len(stocks)}")
        return success_count

    def _format_symbol(self, code: str) -> str:
        """标准化股票代码为 symbol.exchange 格式"""
        code = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
        if code.startswith(("0", "3")):
            return f"{code}.SZ"
        elif code.startswith(("6", "9")):
            return f"{code}.SH"
        elif code.startswith(("4", "8")):
            return f"{code}.BJ"
        return code

    # ======== 纯同步方法 (供run_in_executor在线程中调用,不涉及Redis) ========

    def _sync_get_sentiment_raw(self) -> dict:
        """同步获取市场情绪原始数据 (线程安全,不碰Redis)

        组合: 上证指数日线(趋势) + 全市场实时宽度指标(涨跌家数/涨跌停/平均涨跌幅)
        """
        import akshare as ak
        import pandas as pd

        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        recent5 = df.tail(5)
        high20 = float(df.tail(20)["high"].max())
        low20 = float(df.tail(20)["low"].min())
        close = float(latest["close"])
        position_20d = round((close - low20) / (high20 - low20) * 100, 1) if high20 != low20 else 50
        avg_vol_20 = float(df.tail(20)["volume"].mean())

        result = {
            "sh_index": round(close, 2),
            "sh_change_pct": round(close / float(prev["close"]) * 100 - 100, 2),
            "position_20d": position_20d,
            "vol_ratio": round(float(latest["volume"]) / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0,
            "trend": "强势" if position_20d > 60 else ("弱势" if position_20d < 40 else "震荡"),
            "recent5_up_days": int((recent5["close"] > recent5["open"]).sum()),
            "source": "上证指数日线 + 全市场实时",
        }

        # 全市场宽度指标 (前端 Dashboard 依赖这些字段)
        try:
            spot = ak.stock_zh_a_spot_em()
            chg = pd.to_numeric(spot["涨跌幅"], errors="coerce").fillna(0)
            up = int((chg > 0).sum())
            down = int((chg < 0).sum())
            result["advance_decline_ratio"] = round(up / max(down, 1), 2)
            result["limit_up_count"] = int((chg >= 9.9).sum())
            result["limit_down_count"] = int((chg <= -9.9).sum())
            result["avg_change_pct"] = round(float(chg.mean()), 2)
        except Exception as e:
            logger.warning(f"市场宽度指标获取失败: {e}")
            result["advance_decline_ratio"] = 0.0
            result["limit_up_count"] = 0
            result["limit_down_count"] = 0
            result["avg_change_pct"] = 0.0

        return result

    def _sync_get_spot_map(self) -> dict:
        """同步拉取全市场实时行情 (线程安全,不碰Redis), 返回 {code: quote}"""
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        result = {}
        for _, row in df.iterrows():
            try:
                code = str(row["代码"]).strip()
                result[code] = {
                    "name": row["名称"],
                    "price": float(row["最新价"]),
                    "change_pct": float(row["涨跌幅"]),
                    "change": float(row["涨跌额"]),
                    "volume": float(row["成交量"]),
                    "amount": float(row["成交额"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "open": float(row["今开"]),
                    "pre_close": float(row["昨收"]),
                    "turnover_rate": float(row.get("换手率", 0)),
                }
            except Exception:
                continue  # 跳过停牌/数据异常的行
        return result

    def _sync_get_quote_raw(self, symbol: str) -> dict:
        """同步获取单只股票行情 (线程安全,不碰Redis)"""
        import akshare as ak

        code = symbol.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if row.empty:
            return None

        return {
            "symbol": self._format_symbol(symbol),
            "name": row.iloc[0]["名称"],
            "price": float(row.iloc[0]["最新价"]),
            "change_pct": float(row.iloc[0]["涨跌幅"]),
            "change": float(row.iloc[0]["涨跌额"]),
            "volume": float(row.iloc[0]["成交量"]),
            "amount": float(row.iloc[0]["成交额"]),
            "high": float(row.iloc[0]["最高"]),
            "low": float(row.iloc[0]["最低"]),
            "open": float(row.iloc[0]["今开"]),
            "pre_close": float(row.iloc[0]["昨收"]),
        }


# 单例
akshare = AKShareIngestor()
