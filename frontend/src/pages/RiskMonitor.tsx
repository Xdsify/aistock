import { useState, useEffect } from 'react';
import { AlertTriangle, ShieldCheck, ShieldAlert, Activity, XCircle } from 'lucide-react';
import { useWebSocket } from '../hooks/useWebSocket';

export default function RiskMonitor() {
  useWebSocket();

  const [riskStatus, setRiskStatus] = useState({
    circuit_breakers: {} as Record<string, boolean>,
    trading_blocked: false,
    daily_pnl: 0,
    total_equity: 0,
    daily_loss_pct: 0,
    limits: {
      max_single_stock: 0.20,
      max_sector: 0.40,
      daily_loss_limit: 0.05,
      max_drawdown: 0.08,
    },
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRiskStatus();
    const interval = setInterval(fetchRiskStatus, 10000); // 10s refresh
    return () => clearInterval(interval);
  }, []);

  async function fetchRiskStatus() {
    try {
      const res = await fetch('/api/risk/status');
      if (res.ok) {
        const data = await res.json();
        setRiskStatus(data);
        setError(null);
      }
    } catch (e) {
      setError('风控服务暂不可用');
      // Keep default values when service is unreachable
    } finally {
      setLoading(false);
    }
  }

  async function resetBreaker(breakerType: string) {
    try {
      await fetch(`/api/risk/circuit-breaker/reset?breaker_type=${breakerType}`, { method: 'POST' });
      fetchRiskStatus();
    } catch (e) {
      console.error('重置熔断失败:', e);
    }
  }

  const breakers = riskStatus.circuit_breakers;
  const tradingBlocked = Object.values(breakers).some(Boolean);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">风控监控</h1>
        <div className={`px-3 py-1 rounded-lg text-sm font-bold ${
          tradingBlocked ? 'bg-red-600 animate-pulse' : 'bg-green-600'
        }`}>
          {tradingBlocked ? '交易已阻止' : '交易正常'}
        </div>
      </div>

      {loading && (
        <div className="text-gray-400 text-sm">加载风控数据中...</div>
      )}

      {error && (
        <div className="bg-yellow-900/30 border border-yellow-600/30 rounded-lg p-3 text-sm text-yellow-400">
          {error} — 显示默认值
        </div>
      )}

      {/* 风控指标 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <RiskCard
          title="今日盈亏"
          value={`${riskStatus.daily_pnl >= 0 ? '+' : ''}${riskStatus.daily_pnl.toLocaleString()}元`}
          pct={riskStatus.total_equity > 0
            ? `${((riskStatus.daily_pnl / riskStatus.total_equity) * 100).toFixed(2)}%`
            : '0.00%'}
          icon={Activity}
          color={riskStatus.daily_pnl >= 0 ? 'text-up' : 'text-down'}
        />
        <RiskCard
          title="日亏损上限"
          value={`${(riskStatus.limits.daily_loss_limit * 100).toFixed(0)}%`}
          pct={`当前: ${riskStatus.daily_loss_pct.toFixed(2)}%`}
          icon={AlertTriangle}
          color={riskStatus.daily_loss_pct >= riskStatus.limits.daily_loss_limit * 100 ? 'text-red-400' : 'text-green-400'}
        />
        <RiskCard
          title="单股仓位上限"
          value={`${(riskStatus.limits.max_single_stock * 100).toFixed(0)}%`}
          icon={ShieldAlert}
          color="text-yellow-400"
        />
        <RiskCard
          title="最大回撤"
          value={`${(riskStatus.limits.max_drawdown * 100).toFixed(0)}%`}
          icon={ShieldCheck}
          color="text-blue-400"
        />
      </div>

      {/* 熔断状态 */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <XCircle className="w-5 h-5 text-red-400" />
          熔断状态
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            { key: 'daily_loss_limit', label: '日亏损熔断' },
            { key: 'system_drawdown', label: '系统回撤熔断' },
            { key: 'emergency_stop', label: '紧急停止' },
            { key: 'market_crash', label: '市场崩盘防护' },
          ].map(({ key, label }) => (
            <div key={key} className="flex items-center justify-between bg-gray-800 rounded-lg p-3">
              <span className="text-sm">{label}</span>
              <span className={`px-2 py-1 rounded text-xs font-bold ${
                breakers[key] ? 'bg-red-900/50 text-red-400' : 'bg-green-900/50 text-green-400'
              }`}>
                {breakers[key] ? '已触发' : '正常'}
              </span>
              {breakers[key] && (
                <button
                  className="text-xs text-blue-400 hover:underline ml-2"
                  onClick={() => resetBreaker(key)}
                >
                  重置
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 账户概览 */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h3 className="font-semibold mb-3">账户概览</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-400">总资产</span>
            <div className="text-lg font-bold">¥{riskStatus.total_equity.toLocaleString()}</div>
          </div>
          <div>
            <span className="text-gray-400">今日盈亏</span>
            <div className={`text-lg font-bold ${riskStatus.daily_pnl >= 0 ? 'text-up' : 'text-down'}`}>
              ¥{riskStatus.daily_pnl.toLocaleString()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RiskCard({ title, value, pct, icon: Icon, color }: any) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-400">{title}</span>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      {pct && <div className="text-xs text-gray-500 mt-1">{pct}</div>}
    </div>
  );
}
