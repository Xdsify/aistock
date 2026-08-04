import { useEffect, useState } from 'react';
import { Play, Pause, BarChart3, Settings2, Activity, Plus } from 'lucide-react';

interface StrategyInfo {
  name: string;
  author: string;
  description: string;
  params: Record<string, number | boolean>;
}

const DISPLAY_NAMES: Record<string, string> = {
  ma_cross: '双均线交叉',
  rsi_reversal: 'RSI反转',
  volume_breakout: '放量突破',
  bollinger_reversal: '布林带反转',
};

const CATEGORY_LABELS: Record<string, string> = {
  ma_cross: '趋势',
  rsi_reversal: '反转',
  volume_breakout: '突破',
  bollinger_reversal: '反转',
};

export default function Strategies() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [activeNames, setActiveNames] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [testSymbol, setTestSymbol] = useState('000001.SZ');
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 10000);
    return () => clearInterval(t);
  }, []);

  async function refresh() {
    try {
      const [listRes, activeRes] = await Promise.all([
        fetch('/api/strategy/list'),
        fetch('/api/strategy/active'),
      ]);
      if (listRes.ok) {
        const d = await listRes.json();
        setStrategies(d.strategies || []);
      }
      if (activeRes.ok) {
        const d = await activeRes.json();
        setActiveNames(new Set((d.active || []).map((s: any) => s.name)));
      }
    } catch (e) {
      console.error('获取策略失败:', e);
    }
    setLoading(false);
  }

  async function toggle(name: string) {
    const isActive = activeNames.has(name);
    const res = await fetch(`/api/strategy/${isActive ? 'deactivate' : 'activate'}` + (isActive ? `?name=${encodeURIComponent(name)}` : ''), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: isActive ? undefined : JSON.stringify({ name }),
    });
    if (res.ok) {
      refresh();
    } else {
      alert('操作失败: HTTP ' + res.status);
    }
  }

  async function runBacktest(name: string) {
    const symbol = prompt('回测股票代码:', testSymbol);
    if (!symbol) return;
    try {
      const resp = await fetch('/api/strategy/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy: name, symbol, initial_capital: 100000 }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        alert(data.detail || '回测失败: ' + resp.status);
        return;
      }
      alert(
        `【${DISPLAY_NAMES[name] || name}】${data.symbol} 回测结果\n` +
        `初始资金: ${data.initial_capital.toLocaleString()}\n` +
        `期末资产: ${data.final_equity.toLocaleString()}\n` +
        `总收益率: ${data.total_return_pct}%\n` +
        `胜率: ${data.win_rate}%   盈亏比: ${data.profit_factor}\n` +
        `最大回撤: ${data.max_drawdown_pct}%   交易次数: ${data.trades_count}`
      );
    } catch (e) {
      alert('回测请求失败，检查后端是否运行');
    }
  }

  async function runTest() {
    setTesting(true);
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
    setTesting(false);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">策略管理</h1>
        <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm flex items-center gap-1"
          onClick={() => alert('策略自定义请参考 strategies/ 目录模板')}>
          <Plus className="w-4 h-4" /> 新建策略
        </button>
      </div>

      {loading && <div className="text-gray-400 text-sm">加载策略中...</div>}

      {/* 策略列表 */}
      <div className="space-y-4">
        {strategies.map((s) => {
          const isActive = activeNames.has(s.name);
          return (
            <div key={s.name} className="bg-gray-900 rounded-xl border border-gray-800 p-5 hover:border-gray-700">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-lg">{DISPLAY_NAMES[s.name] || s.name}</h3>
                    <span className={`px-2 py-0.5 rounded text-xs font-bold text-white ${isActive ? 'bg-green-500' : 'bg-gray-500'}`}>
                      {isActive ? '运行中' : '未激活'}
                    </span>
                    <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
                      {CATEGORY_LABELS[s.name] || '策略'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-400 mb-3">{s.description || '(无描述)'}</p>

                  {/* 参数标签 */}
                  <div className="flex gap-2 flex-wrap">
                    {Object.entries(s.params || {}).map(([key, val]) => (
                      <span key={key} className="text-xs bg-gray-800 px-2 py-1 rounded text-gray-300">
                        {key}: {String(val)}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    className={`p-2 rounded-lg ${isActive ? 'bg-yellow-600/80 hover:bg-yellow-600' : 'bg-green-600/80 hover:bg-green-600'}`}
                    title={isActive ? '暂停策略' : '启动策略'}
                    onClick={() => toggle(s.name)}
                  >
                    {isActive ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  </button>
                  <button className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg" title="回测"
                    onClick={() => runBacktest(s.name)}>
                    <BarChart3 className="w-4 h-4" />
                  </button>
                  <button className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg" title="参数配置"
                    onClick={() => alert('参数配置开发中')}>
                    <Settings2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
        {!loading && strategies.length === 0 && (
          <div className="text-center py-10 text-gray-500">暂无策略 (检查 strategy-engine 是否运行)</div>
        )}
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
            disabled={testing}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm"
            onClick={runTest}
          >
            {testing ? '测试中...' : '测试信号'}
          </button>
        </div>
      </div>
    </div>
  );
}
