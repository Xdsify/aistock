import { useState } from 'react';
import { Play, Pause, BarChart3, Settings2, Activity } from 'lucide-react';

const BUILTIN_STRATEGIES = [
  {
    name: 'ma_cross',
    display: '双均线交叉',
    description: '经典趋势追踪策略，MA5上穿MA20买入',
    category: '趋势',
    status: 'live',
    params: { fast_period: 5, slow_period: 20, stop_loss: 5, take_profit: 12 },
  },
  {
    name: 'rsi_reversal',
    display: 'RSI反转',
    description: '超买超卖反转策略，RSI<30买入',
    category: '反转',
    status: 'paused',
    params: { rsi_period: 14, oversold: 30, overbought: 70 },
  },
  {
    name: 'volume_breakout',
    display: '放量突破',
    description: '成交量放大伴随价格突破',
    category: '突破',
    status: 'backtesting',
    params: { lookback: 20, vol_multiple: 2.0 },
  },
  {
    name: 'bollinger_reversal',
    display: '布林带反转',
    description: '价格触及布林带上下轨反转',
    category: '反转',
    status: 'draft',
    params: { bb_period: 20, bb_std: 2.0 },
  },
];

export default function Strategies() {
  const [strategies] = useState(BUILTIN_STRATEGIES);
  const [testSymbol, setTestSymbol] = useState('000001.SZ');

  const statusColors: Record<string, string> = {
    live: 'bg-green-500', paused: 'bg-yellow-500',
    backtesting: 'bg-blue-500', draft: 'bg-gray-500',
  };
  const statusLabels: Record<string, string> = {
    live: '运行中', paused: '已暂停', backtesting: '回测中', draft: '草稿',
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">策略管理</h1>
        <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm">
          + 新建策略
        </button>
      </div>

      {/* 策略列表 */}
      <div className="space-y-4">
        {strategies.map((s) => (
          <div key={s.name} className="bg-gray-900 rounded-xl border border-gray-800 p-5 hover:border-gray-700">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="font-semibold text-lg">{s.display}</h3>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${statusColors[s.status]} text-white`}>
                    {statusLabels[s.status]}
                  </span>
                  <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">{s.category}</span>
                </div>
                <p className="text-sm text-gray-400 mb-3">{s.description}</p>

                {/* 参数标签 */}
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(s.params).map(([key, val]) => (
                    <span key={key} className="text-xs bg-gray-800 px-2 py-1 rounded text-gray-300">
                      {key}: {val}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex gap-2">
                {s.status === 'live' ? (
                  <button className="p-2 bg-yellow-600/80 hover:bg-yellow-600 rounded-lg" title="暂停策略" onClick={() => alert('策略已暂停(演示)')}>
                    <Pause className="w-4 h-4" />
                  </button>
                ) : (
                  <button className="p-2 bg-green-600/80 hover:bg-green-600 rounded-lg" title="启动策略" onClick={() => alert('策略已启动(演示)')}>
                    <Play className="w-4 h-4" />
                  </button>
                )}
                <button className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg" title="回测" onClick={() => alert('回测功能开发中')}>
                  <BarChart3 className="w-4 h-4" />
                </button>
                <button className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg" title="参数配置" onClick={() => alert('参数配置开发中')}>
                  <Settings2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 快速测试 */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400" />
          快速信号测试
        </h3>
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={testSymbol}
            onChange={(e) => setTestSymbol(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono w-40"
            placeholder="股票代码"
          />
          <button
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm"
            onClick={async () => {
              try {
                const resp = await fetch('/api/strategy/test-signal', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    symbol: testSymbol,
                    open: 12.0, high: 12.5, low: 11.8, close: 12.3, volume: 50000, amount: 615000,
                  }),
                });
                if (!resp.ok) { alert('请求失败: ' + resp.status); return; }
                const data = await resp.json();
                if (data.signals && data.signals.length > 0) {
                  const list = data.signals.map((s: any) => `${s.action} ${s.strategy}: ${s.reason}`).join('\n');
                  alert(`产生 ${data.count} 个信号:\n${list}`);
                } else {
                  alert(`${data.symbol} 未产生信号（可能指标未触发）`);
                }
              } catch (e) {
                alert('请求失败，检查后端是否运行');
              }
            }}
          >
            测试信号
          </button>
        </div>
      </div>
    </div>
  );
}
