import { useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { createChart, ColorType } from 'lightweight-charts';
import { ArrowLeft, TrendingUp, TrendingDown } from 'lucide-react';
import { useStockNames } from '../hooks/useStockNames';

interface Kline {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
}

type Period = 'daily' | 'weekly' | 'monthly';

// 前端按周期重采样 (周线/月线)
function resample(klines: Kline[], period: Period): Kline[] {
  if (period === 'daily') return klines;
  const map = new Map<string, Kline>();
  for (const k of klines) {
    const d = new Date(k.trade_date.slice(0, 10));
    let key: string;
    if (period === 'weekly') {
      const day = (d.getDay() + 6) % 7; // 周一到周日
      const monday = new Date(d);
      monday.setDate(d.getDate() - day);
      key = monday.toISOString().slice(0, 10);
    } else {
      key = k.trade_date.slice(0, 7) + '-01';
    }
    const ex = map.get(key);
    if (!ex) {
      map.set(key, { ...k, trade_date: key });
    } else {
      ex.high = Math.max(ex.high, k.high);
      ex.low = Math.min(ex.low, k.low);
      ex.close = k.close;
      ex.volume += k.volume;
      ex.amount += k.amount;
    }
  }
  return Array.from(map.values()).sort((a, b) => a.trade_date.localeCompare(b.trade_date));
}

export default function StockDetail() {
  const { symbol = '' } = useParams();
  const stockNames = useStockNames();
  const chartRef = useRef<HTMLDivElement>(null);
  const [klines, setKlines] = useState<Kline[]>([]);
  const [quote, setQuote] = useState<any>(null);
  const [period, setPeriod] = useState<Period>('daily');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    // 默认拉近一年 (范围更小, 加载更快)
    const now = new Date();
    const start = new Date();
    start.setFullYear(now.getFullYear() - 1);
    const fmt = (d: Date) => `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
    fetch(`/api/data/kline/${symbol}?start_date=${fmt(start)}&end_date=${fmt(now)}`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (d?.data?.length) setKlines(d.data);
        else if (d?.error) setError(d.error || 'K线获取失败');
      })
      .catch(() => setError('K线获取失败'))
      .finally(() => setLoading(false));
    fetch(`/api/data/quote/${symbol}`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d?.quote) setQuote(d.quote); })
      .catch(() => {});
  }, [symbol]);

  useEffect(() => {
    if (!chartRef.current || klines.length === 0) return;
    const chart = createChart(chartRef.current, {
      layout: { background: { type: ColorType.Solid, color: '#0f172a' }, textColor: '#94a3b8' },
      grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
      width: chartRef.current.clientWidth,
      height: 420,
      timeScale: { borderColor: '#334155' },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#ef4444', downColor: '#22c55e',
      borderUpColor: '#ef4444', borderDownColor: '#22c55e',
      wickUpColor: '#ef4444', wickDownColor: '#22c55e',
    });
    const data = resample(klines, period);
    candleSeries.setData(data.map((k) => ({
      time: k.trade_date.slice(0, 10),
      open: k.open, high: k.high, low: k.low, close: k.close,
    })));

    const volumeSeries = chart.addHistogramSeries({
      priceScaleId: 'volume',
      priceFormat: { type: 'volume' },
    });
    volumeSeries.setData(data.map((k) => ({
      time: k.trade_date.slice(0, 10),
      value: k.volume,
      color: k.close >= k.open ? 'rgba(239,68,68,0.4)' : 'rgba(34,197,94,0.4)',
    })));
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    chart.timeScale().fitContent();
    const resize = () => chartRef.current && chart.applyOptions({ width: chartRef.current.clientWidth });
    window.addEventListener('resize', resize);
    return () => { window.removeEventListener('resize', resize); chart.remove(); };
  }, [klines, period]);

  const name = stockNames[symbol] || symbol;
  const last = klines[klines.length - 1];
  const first = klines[0];
  const rangeChg = last && first ? (last.close - first.close) / first.close * 100 : 0;
  const high = klines.length ? Math.max(...klines.map((k) => k.high)) : 0;
  const low = klines.length ? Math.min(...klines.map((k) => k.low)) : 0;
  const totalVol = klines.length ? klines.reduce((s, k) => s + k.volume, 0) : 0;
  const price = quote?.price ?? last?.close;

  const periods: { key: Period; label: string }[] = [
    { key: 'daily', label: '日K' },
    { key: 'weekly', label: '周K' },
    { key: 'monthly', label: '月K' },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-gray-400 hover:text-white"><ArrowLeft className="w-5 h-5" /></Link>
          <h1 className="text-2xl font-bold">{name}</h1>
          <span className="text-gray-500 font-mono text-sm mt-1">{symbol}</span>
        </div>
        <div className="flex gap-2">
          {periods.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-3 py-1.5 rounded-lg text-sm ${period === p.key ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* 当前价格 */}
      <div className="flex items-end gap-4">
        <div className="text-4xl font-bold font-mono">{price?.toFixed(2) ?? '--'}</div>
        {quote && (
          <div className={`flex items-center gap-1 mb-1 ${quote.change_pct >= 0 ? 'text-up' : 'text-down'}`}>
            {quote.change_pct >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            <span className="font-mono">{quote.change_pct >= 0 ? '+' : ''}{quote.change_pct}%</span>
          </div>
        )}
      </div>

      {error && <div className="bg-red-900/30 border border-red-500/30 rounded-xl p-3 text-sm text-red-400">{error}</div>}

      {/* K线图 */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        {loading ? (
          <div className="text-center py-20 text-gray-500">加载K线中...</div>
        ) : klines.length === 0 ? (
          <div className="text-center py-20 text-gray-500">暂无K线数据（行情服务不可用）</div>
        ) : (
          <div ref={chartRef} />
        )}
      </div>

      {/* 区间统计 */}
      {klines.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <StatBox label="区间涨跌幅" value={`${rangeChg >= 0 ? '+' : ''}${rangeChg.toFixed(2)}%`} color={rangeChg >= 0 ? 'text-up' : 'text-down'} />
          <StatBox label="区间最高" value={high.toFixed(2)} color="text-red-400" />
          <StatBox label="区间最低" value={low.toFixed(2)} color="text-green-400" />
          <StatBox label="区间成交量" value={totalVol >= 1e8 ? (totalVol / 1e8).toFixed(2) + '亿' : (totalVol / 1e4).toFixed(1) + '万'} color="text-white" />
          <StatBox label="最新收盘" value={last.close.toFixed(2)} color="text-white" />
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-gray-900 rounded-xl p-3 border border-gray-800 text-center">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`font-mono text-lg font-bold ${color}`}>{value}</div>
    </div>
  );
}
