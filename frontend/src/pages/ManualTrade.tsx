import { useState } from 'react';
import { ShoppingCart, Send, Clock } from 'lucide-react';
import { useMarketStore } from '../stores/marketStore';
import { useStockNames } from '../hooks/useStockNames';
import StockLink from '../components/StockLink';

function isTradingTime(now: Date): boolean {
  const day = now.getDay(); // 0=周日
  if (day === 0 || day === 6) return false;
  const t = now.getHours() * 60 + now.getMinutes();
  return (9 * 60 + 30 <= t && t <= 11 * 60 + 30) || (13 * 60 <= t && t <= 15 * 60);
}

export default function ManualTrade() {
  const [symbol, setSymbol] = useState('000001.SZ');
  const [action, setAction] = useState<'BUY' | 'SELL'>('BUY');
  const [price, setPrice] = useState('');
  const [volume, setVolume] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const quotes = useMarketStore((s) => s.quotes);
  const stockNames = useStockNames();
  const livePrice = quotes[symbol]?.price;
  const stockName = stockNames[symbol] || '';
  const trading = isTradingTime(new Date());

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    const p = parseFloat(price);
    if (!p || p <= 0) {
      setError('请输入有效价格');
      setLoading(false);
      return;
    }
    try {
      const res = await fetch('/api/order/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          name: stockName,
          action,
          price: p,
          volume: volume ? parseInt(volume, 10) : 0,
        }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setResult(data);
      } else {
        setError(data.error || ('下单失败: HTTP ' + res.status));
      }
    } catch (e) {
      setError('请求失败，检查后端是否运行');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <ShoppingCart className="w-6 h-6 text-blue-400" /> 手动交易
      </h1>
      <p className="text-sm text-gray-500">直接下买单/卖单（模拟成交，T+1 当天买入不可卖）</p>

      {!trading && (
        <div className="bg-yellow-900/30 border border-yellow-600/30 rounded-xl p-3 flex items-center gap-2 text-sm text-yellow-400">
          <Clock className="w-4 h-4 shrink-0" />
          当前非交易时段（A股 9:30-11:30 / 13:00-15:00，周一至周五），下单会被拒绝。
          如需测试可把 .env 的 ENFORCE_TRADING_HOURS 设为 false 并重启。
        </div>
      )}

      <form onSubmit={submit} className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">股票代码</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-blue-500"
            placeholder="如 000001.SZ / 600519.SH"
          />
          {stockName && (
            <div className="text-xs text-gray-300 mt-1">
              股票: <span className="text-white">{stockName}</span>
            </div>
          )}
          <div className="text-xs text-blue-400 mt-1">
            <StockLink symbol={symbol} name="查看K线详情 →" />
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">方向</label>
          <div className="flex gap-2">
            <button type="button" onClick={() => setAction('BUY')}
              className={`flex-1 py-2 rounded-lg text-sm font-bold transition-colors ${
                action === 'BUY' ? 'bg-red-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}>
              买入
            </button>
            <button type="button" onClick={() => setAction('SELL')}
              className={`flex-1 py-2 rounded-lg text-sm font-bold transition-colors ${
                action === 'SELL' ? 'bg-green-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}>
              卖出
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">价格</label>
            <input type="number" value={price} onChange={(e) => setPrice(e.target.value)} step="0.01"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-blue-500"
              placeholder="0.00"
            />
            {livePrice != null && (
              <div className="text-xs text-gray-500 mt-1">实时价: <span className="text-white font-mono">{livePrice}</span></div>
            )}
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">数量（股）</label>
            <input type="number" value={volume} onChange={(e) => setVolume(e.target.value)} step="100"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-blue-500"
              placeholder="0 = 自动按仓位"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button type="submit" disabled={loading}
          className={`w-full py-2.5 rounded-lg font-bold text-white transition-colors disabled:opacity-50 ${
            action === 'BUY' ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'
          }`}>
          {loading ? '提交中...' : (
            <span className="flex items-center justify-center gap-2">
              <Send className="w-4 h-4" /> {action === 'BUY' ? '确认买入' : '确认卖出'}
            </span>
          )}
        </button>
      </form>

      {result?.success && (
        <div className="bg-green-900/30 border border-green-500/40 rounded-xl p-4 text-sm">
          下单成功！订单号: <span className="font-mono text-green-300">{result.order_id}</span>
        </div>
      )}
    </div>
  );
}
