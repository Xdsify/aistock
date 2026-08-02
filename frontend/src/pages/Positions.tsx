import { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Lock, Unlock } from 'lucide-react';

interface Position {
  symbol: string;
  name?: string;
  total_qty: number;
  available_sell: number;
  locked_qty: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  updated_at: string;
}

export default function Positions() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [totalEquity, setTotalEquity] = useState(500000);
  const [availableCash, setAvailableCash] = useState(350000);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 从执行引擎获取真实持仓和账户数据
    const fetchData = async () => {
      try {
        const [posRes, acctRes] = await Promise.all([
          fetch('/api/positions'),
          fetch('/api/account'),
        ]);
        if (posRes.ok) {
          const posData = await posRes.json();
          setPositions(Array.isArray(posData) ? posData : []);
        }
        if (acctRes.ok) {
          const acctData = await acctRes.json();
          setTotalEquity(acctData.total_equity || 500000);
          setAvailableCash(acctData.available_cash || 0);
        }
      } catch (e) {
        console.error('获取持仓失败:', e);
      }
      setLoading(false);
    };
    fetchData();
    const t = setInterval(fetchData, 5000);
    return () => clearInterval(t);
  }, []);

  const totalMarketValue = positions.reduce((s, p) => s + (p.market_value || 0), 0);
  const totalUnrealizedPnL = positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);
  const totalRealizedPnL = positions.reduce((s, p) => s + (p.realized_pnl || 0), 0);

  if (loading) return <div className="p-6">加载中...</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">持仓管理</h1>

      {/* 持仓汇总 */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <SummaryBox label="总资产" value={totalEquity.toLocaleString()} color="text-white" />
        <SummaryBox label="可用资金" value={availableCash.toLocaleString()} color="text-green-400" />
        <SummaryBox label="持仓市值" value={totalMarketValue.toLocaleString()} color="text-blue-400" />
        <SummaryBox label="浮动盈亏" value={`${totalUnrealizedPnL >= 0 ? '+' : ''}${totalUnrealizedPnL.toLocaleString()}`}
          color={totalUnrealizedPnL >= 0 ? 'text-up' : 'text-down'} />
        <SummaryBox label="已实现盈亏" value={`${totalRealizedPnL >= 0 ? '+' : ''}${totalRealizedPnL.toLocaleString()}`}
          color={totalRealizedPnL >= 0 ? 'text-up' : 'text-down'} />
      </div>

      {/* 持仓列表 */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-left text-sm text-gray-400">
              <th className="p-3">股票</th>
              <th className="p-3 text-right">持仓/可用</th>
              <th className="p-3 text-right">成本价</th>
              <th className="p-3 text-right">现价</th>
              <th className="p-3 text-right">市值</th>
              <th className="p-3 text-right">盈亏</th>
              <th className="p-3 text-right">盈亏%</th>
              <th className="p-3 text-center">T+1</th>
              <th className="p-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos) => (
              <tr key={pos.symbol} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="p-3">
                  <div className="font-medium">{pos.name || pos.symbol}</div>
                  <div className="text-xs text-gray-500">{pos.symbol}</div>
                </td>
                <td className="p-3 text-right">
                  <div>{pos.total_qty.toLocaleString()}</div>
                  <div className="text-xs text-gray-500">可用 {pos.available_sell.toLocaleString()}</div>
                </td>
                <td className="p-3 text-right font-mono text-sm">{pos.avg_cost.toFixed(2)}</td>
                <td className="p-3 text-right font-mono text-sm">{pos.current_price.toFixed(2)}</td>
                <td className="p-3 text-right font-mono text-sm">{pos.market_value.toLocaleString()}</td>
                <td className={`p-3 text-right font-mono text-sm ${pos.unrealized_pnl >= 0 ? 'text-up' : 'text-down'}`}>
                  {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl.toLocaleString()}
                </td>
                <td className={`p-3 text-right font-mono text-sm ${pos.unrealized_pnl >= 0 ? 'text-up' : 'text-down'}`}>
                  {pos.avg_cost > 0
                    ? ((pos.current_price - pos.avg_cost) / pos.avg_cost * 100).toFixed(2)
                    : '0.00'}%
                </td>
                <td className="p-3 text-center">
                  {pos.locked_qty > 0 ? (
                    <span title={`T+1锁定 ${pos.locked_qty}股`}>
                      <Lock className="w-4 h-4 text-yellow-400 inline" />
                    </span>
                  ) : (
                    <Unlock className="w-4 h-4 text-green-400 inline" />
                  )}
                </td>
                <td className="p-3 text-right">
                  <button
                    className="px-3 py-1 bg-green-600/80 hover:bg-green-600 rounded text-xs disabled:opacity-50"
                    disabled={pos.available_sell <= 0}
                    onClick={async () => {
                      const price = prompt('卖出价格:', pos.current_price?.toString() || '0');
                      const vol = prompt('卖出数量:', pos.available_sell?.toString() || '0');
                      if (!price || !vol) return;
                      try {
                        const res = await fetch('/api/order/manual', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ symbol: pos.symbol, action: 'SELL', price: parseFloat(price), volume: parseInt(vol) }),
                        });
                        const data = await res.json();
                        if (data.success) {
                          alert(`卖出成功! 订单: ${data.order_id}`);
                          window.location.reload();
                        } else {
                          alert('卖出失败: ' + (data.error || '未知错误'));
                        }
                      } catch (e) {
                        alert('请求失败');
                      }
                    }}
                  >
                    卖出
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-gray-900 rounded-xl p-3 border border-gray-800 text-center">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value}</div>
    </div>
  );
}
