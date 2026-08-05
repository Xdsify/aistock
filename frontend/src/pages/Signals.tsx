import { useEffect, useState } from 'react';
import { Zap, Check, X, Eye, Brain } from 'lucide-react';
import { useSignalStore } from '../stores/signalStore';
import { useWebSocket } from '../hooks/useWebSocket';
import StockLink from '../components/StockLink';

export default function Signals() {
  useWebSocket();
  const signals = useSignalStore((s) => s.signals);
  const setSignals = useSignalStore((s) => s.setSignals);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<'ALL' | 'BUY' | 'SELL'>('ALL');

  // 挂载时拉取信号历史 (Redis signal:list), 刷新不丢
  useEffect(() => {
    fetch('/api/signals')
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d?.signals?.length) setSignals(d.signals); })
      .catch(() => {});
  }, [setSignals]);

  const filteredSignals = filter === 'ALL'
    ? signals
    : signals.filter((s) => s.action === filter);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">信号面板</h1>
        <div className="flex gap-2">
          {(['ALL', 'BUY', 'SELL'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                filter === f ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {f === 'ALL' ? '全部' : f === 'BUY' ? '买入' : '卖出'}
            </button>
          ))}
        </div>
      </div>

      {filteredSignals.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <Zap className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p>暂无信号，等待策略生成</p>
          <p className="text-sm mt-2">或手动在"策略"页面触发测试</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredSignals.map((signal) => (
            <SignalCard
              key={signal.signal_id}
              signal={signal}
              isExpanded={expandedId === signal.signal_id}
              onToggle={() =>
                setExpandedId(expandedId === signal.signal_id ? null : signal.signal_id)
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SignalCard({
  signal, isExpanded, onToggle,
}: {
  signal: any; isExpanded: boolean; onToggle: () => void;
}) {
  const approveSignal = useSignalStore((s) => s.approveSignal);
  const rejectSignal = useSignalStore((s) => s.rejectSignal);
  const isBuy = signal.action === 'BUY';

  return (
    <div className={`bg-gray-900 rounded-xl border transition-colors ${
      isExpanded ? 'border-blue-500/50' : 'border-gray-800 hover:border-gray-700'
    }`}>
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* 信号方向 */}
          <span className={`px-2 py-1 rounded text-xs font-bold ${
            isBuy ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'
          }`}>
            {isBuy ? '买入' : '卖出'}
          </span>

          {/* 股票代码 */}
          <div>
            <span className="font-mono font-bold"><StockLink symbol={signal.symbol} /></span>
            <span className="text-xs text-gray-500 ml-2">{signal.strategy_name}</span>
          </div>

          {/* 信号强度 */}
          <div className="flex items-center gap-1">
            <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${isBuy ? 'bg-red-500' : 'bg-green-500'}`}
                style={{ width: `${(signal.strength * 100).toFixed(0)}%` }}
              />
            </div>
            <span className="text-xs text-gray-400">
              {(signal.strength * 100).toFixed(0)}%
            </span>
          </div>

          {/* AI置信度 */}
          {signal.ai_confidence > 0 && (
            <span className="flex items-center gap-1 text-xs text-blue-400">
              <Brain className="w-3 h-3" />
              AI: {(signal.ai_confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* 价格信息 */}
          <div className="text-right">
            <div className="font-mono text-sm">@{signal.price}</div>
            <div className="text-xs text-gray-500">
              止{signal.stop_loss}/{signal.take_profit}
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-1">
            {signal.requires_confirmation && (
              <>
                <button className="p-1.5 bg-green-600/80 hover:bg-green-600 rounded-lg" title="批准并下单"
                  onClick={async () => {
                    try {
                      const res = await fetch('/api/signals/approve', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({signal}) });
                      const data = await res.json();
                      if (res.ok) {
                        approveSignal(signal.signal_id);
                        alert(data.message || '信号已批准, 发送到执行引擎');
                      } else {
                        alert(data.detail || data.message || '批准失败');
                      }
                    } catch(e) { alert('请求失败: ' + (e as Error).message); }
                  }}>
                  <Check className="w-4 h-4" />
                </button>
                <button className="p-1.5 bg-red-600/80 hover:bg-red-600 rounded-lg" title="拒绝信号"
                  onClick={async () => {
                    try {
                      const res = await fetch('/api/signals/reject', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({signal_id: signal.signal_id, symbol: signal.symbol, strategy_name: signal.strategy_name}) });
                      if (res.ok) {
                        rejectSignal(signal.signal_id);
                      } else {
                        alert('拒绝失败: ' + res.status);
                      }
                    } catch(e) { alert('请求失败: ' + (e as Error).message); }
                  }}>
                  <X className="w-4 h-4" />
                </button>
              </>
            )}
            <button onClick={onToggle} className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg">
              <Eye className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 展开详情 */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-800 pt-3 space-y-2">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            <div>
              <span className="text-gray-500">信号原因</span>
              <p className="mt-1">{signal.reason}</p>
            </div>
            <div>
              <span className="text-gray-500">仓位比例</span>
              <p className="mt-1">{(signal.position_pct * 100).toFixed(1)}%</p>
            </div>
            <div>
              <span className="text-gray-500">风控状态</span>
              <p className={`mt-1 ${signal.risk_approved ? 'text-green-400' : 'text-red-400'}`}>
                {signal.risk_approved ? '已通过' : '未通过'}
              </p>
            </div>
            <div>
              <span className="text-gray-500">时间</span>
              <p className="mt-1">{new Date(signal.timestamp).toLocaleTimeString('zh-CN')}</p>
            </div>
          </div>
          {signal.ai_notes && (
            <div className="bg-blue-900/20 rounded-lg p-3 text-sm border border-blue-500/20">
              <div className="flex items-center gap-1 text-blue-400 mb-1">
                <Brain className="w-3 h-3" /> AI分析
              </div>
              <p className="text-gray-300">{signal.ai_notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
