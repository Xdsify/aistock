import { useEffect, useState } from 'react';

// 常见股票兜底映射 (行情/AKShare 不可用时也能显示名称)
const COMMON_STOCKS: Record<string, string> = {
  '000001.SZ': '平安银行',
  '000002.SZ': '万科A',
  '000858.SZ': '五粮液',
  '600519.SH': '贵州茅台',
  '300750.SZ': '宁德时代',
  '601318.SH': '中国平安',
  '688981.SH': '中芯国际',
  '002594.SZ': '比亚迪',
  '600036.SH': '招商银行',
  '000333.SZ': '美的集团',
  '600030.SH': '中信证券',
  '601899.SH': '紫金矿业',
  '000063.SZ': '中兴通讯',
  '601012.SH': '隆基绿能',
};

/**
 * 股票名称解析: 内置常见股兜底 + 从 data-service 拉全市场列表合并 (行情通时更全)
 */
export function useStockNames() {
  const [names, setNames] = useState<Record<string, string>>(COMMON_STOCKS);

  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 5000); // 行情服务不可用时快速兜底
    fetch('/api/data/stock/list', { signal: ctrl.signal })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (d?.stocks?.length) {
          const map: Record<string, string> = {};
          for (const s of d.stocks) {
            if (s.symbol && s.name) map[s.symbol] = s.name;
          }
          setNames({ ...COMMON_STOCKS, ...map });
        }
      })
      .catch(() => {})
      .finally(() => clearTimeout(timer));
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, []);

  return names;
}
