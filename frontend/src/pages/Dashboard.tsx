import { useEffect, useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { usePositionStore } from '../stores/positionStore';
import { useMarketStore } from '../stores/marketStore';
import { useSignalStore } from '../stores/signalStore';
import { TrendingUp, TrendingDown, DollarSign, Activity, ShieldAlert } from 'lucide-react';
import PnLCard from '../components/PnLCard';
import EquityChart from '../components/EquityChart';

export default function Dashboard() {
  useWebSocket();

  const account = usePositionStore((s) => s.account);
  const positions = usePositionStore((s) => s.positions);
  const sentiment = useMarketStore((s) => s.sentiment);
  const updateSentiment = useMarketStore((s) => s.updateSentiment);
  const signals = useSignalStore((s) => s.signals);

  const [accountData, setAccountData] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);

  // 从执行引擎获取真实账户数据 + 交易统计 + 市场情绪兜底 (WS 不可用时走 REST)
  useEffect(() => {
    const fetchStats = () => {
      fetch('/api/stats').then(r => r.ok ? r.json() : null).then(d => d && setStats(d)).catch(() => {});
    };
    fetch('/api/account')
      .then(r => r.json())
      .then(d => setAccountData(d))
      .catch(() => {});
    fetch('/api/data/market/sentiment')
      .then(r => r.json())
      .then(d => { if (d.sentiment) updateSentiment(d.sentiment); })
      .catch(() => {});
    fetchStats();
    // 每5秒刷新
    const t = setInterval(() => {
      fetch('/api/account').then(r => r.json()).then(d => setAccountData(d)).catch(() => {});
      fetch('/api/data/market/sentiment')
        .then(r => r.json())
        .then(d => { if (d.sentiment) updateSentiment(d.sentiment); })
        .catch(() => {});
      fetchStats();
    }, 5000);
    return () => clearInterval(t);
  }, [updateSentiment]);

  const totalEquity = accountData?.total_equity ?? account?.total_equity ?? 500000;
  const totalPnl = accountData?.total_pnl ?? 0;
  const totalPnlPct = accountData?.total_pnl_pct ?? 0;
  const availableCash = accountData?.available_cash ?? account?.available_cash ?? 0;
  const positionList = Object.values(positions);
  const totalMarketValue = positionList.reduce((sum: number, p: any) => sum + (p.market_value || 0), 0);
  const totalUnrealizedPnL = positionList.reduce((sum: number, p: any) => sum + (p.unrealized_pnl || 0), 0);
  const positionPct = totalEquity > 0 ? Math.round(totalMarketValue / totalEquity * 100) : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">交易仪表盘</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-400">
            更新时间: {new Date().toLocaleTimeString('zh-CN')}
          </span>
          <EmergencyStopButton />
        </div>
      </div>

      {/* 概览卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="总资产"
          value={totalEquity.toLocaleString()}
          suffix="元"
          icon={DollarSign}
          iconColor="text-blue-400"
        />
        <StatCard
          title="累计盈亏"
          value={totalPnl > 0 ? `+${totalPnl.toLocaleString()}` : totalPnl.toLocaleString()}
          suffix={`元 (${totalPnlPct > 0 ? '+' : ''}${totalPnlPct}%)`}
          icon={totalPnl > 0 ? TrendingUp : TrendingDown}
          iconColor={totalPnl > 0 ? 'text-up' : 'text-down'}
          valueColor={totalPnl > 0 ? 'text-up' : 'text-down'}
        />
        <StatCard
          title="可用资金"
          value={availableCash.toLocaleString()}
          suffix="元"
          icon={Activity}
          iconColor="text-green-400"
        />
        <StatCard
          title="持仓市值"
          value={totalMarketValue.toLocaleString()}
          suffix="元"
          icon={ShieldAlert}
          iconColor="text-yellow-400"
          sub={`浮动盈亏: ${totalUnrealizedPnL > 0 ? '+' : ''}${totalUnrealizedPnL.toFixed(0)}元`}
        />
      </div>

      {/* 权益曲线 + 盈亏卡片 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-gray-900 rounded-xl p-4 border border-gray-800">
          <h3 className="text-lg font-semibold mb-4">权益曲线</h3>
          <EquityChart />
        </div>
        <div className="space-y-4">
          <PnLCard
            totalPnL={totalPnl}
            totalPnLPct={totalPnlPct}
            winRate={stats?.win_rate ?? 0}
            profitFactor={stats?.profit_factor ?? 0}
            positionPct={positionPct}
          />
        </div>
      </div>

      {/* 实时行情条 */}
      <QuotesBar />

      {/* 市场情绪 + 最近信号 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MarketSentimentCard sentiment={sentiment} />
        <RecentSignalsCard />
      </div>
    </div>
  );
}

function QuotesBar() {
  const quotes = useMarketStore((s) => s.quotes);
  const list = Object.values(quotes).slice(0, 12);

  if (list.length === 0) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 text-sm text-gray-500">
        实时行情: 等待行情数据...(需 AKShare 网络可达)
      </div>
    );
  }
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <h3 className="text-sm font-semibold mb-3 text-gray-400">实时行情</h3>
      <div className="flex gap-3 overflow-x-auto">
        {list.map((q: any) => (
          <div key={q.symbol} className="min-w-[110px] bg-gray-800 rounded-lg p-2 shrink-0">
            <div className="text-xs text-gray-400 truncate">{q.name || q.symbol}</div>
            <div className="font-mono text-sm">{q.price}</div>
            <div className={`text-xs ${q.change_pct >= 0 ? 'text-up' : 'text-down'}`}>
              {q.change_pct >= 0 ? '+' : ''}{q.change_pct}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({
  title, value, suffix, icon: Icon, iconColor, valueColor, sub,
}: {
  title: string; value: string; suffix: string;
  icon: any; iconColor: string; valueColor?: string; sub?: string;
}) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 hover:border-gray-700 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-400">{title}</span>
        <Icon className={`w-5 h-5 ${iconColor}`} />
      </div>
      <div className={`text-xl font-bold ${valueColor || 'text-white'}`}>
        {value}
        <span className="text-sm font-normal text-gray-400 ml-1">{suffix}</span>
      </div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  );
}

function MarketSentimentCard({ sentiment }: { sentiment: any }) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
      <h3 className="text-lg font-semibold mb-3">市场情绪</h3>
      {sentiment ? (
        <div className="space-y-3">
          <div className="flex justify-between">
            <span className="text-gray-400">涨跌比</span>
            <span>{sentiment.advance_decline_ratio?.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">涨停/跌停</span>
            <span>
              <span className="text-up">{sentiment.limit_up_count}</span>
              {' / '}
              <span className="text-down">{sentiment.limit_down_count}</span>
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">平均涨跌幅</span>
            <span className={sentiment.avg_change_pct >= 0 ? 'text-up' : 'text-down'}>
              {sentiment.avg_change_pct?.toFixed(2)}%
            </span>
          </div>
        </div>
      ) : (
        <p className="text-gray-500 text-sm">等待市场数据...</p>
      )}
    </div>
  );
}

function RecentSignalsCard() {
  const allSignals = useSignalStore((s) => s.signals);
  const setSignals = useSignalStore((s) => s.setSignals);
  const signals = allSignals.slice(0, 5);

  // 挂载时拉取信号历史, 刷新不丢
  useEffect(() => {
    fetch('/api/signals')
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d?.signals?.length) setSignals(d.signals); })
      .catch(() => {});
  }, [setSignals]);

  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
      <h3 className="text-lg font-semibold mb-3">最近信号</h3>
      {signals.length > 0 ? (
        <div className="space-y-2">
          {signals.map((s, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
              <div>
                <span className="font-mono text-sm">{s.symbol}</span>
                <span className={`ml-2 px-1.5 py-0.5 rounded text-xs font-bold ${
                  s.action === 'BUY' ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'
                }`}>
                  {s.action === 'BUY' ? '买入' : '卖出'}
                </span>
                {s.ai_confidence > 0 && (
                  <span className="ml-1 text-xs text-blue-400">
                    AI:{(s.ai_confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <span className="text-sm text-gray-400">{s.reason}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-gray-500 text-sm">暂无信号</p>
      )}
    </div>
  );
}

function EmergencyStopButton() {
  const handleStop = async () => {
    if (!confirm('确认紧急停止所有交易? 将取消所有活跃订单!')) return;
    try {
      await fetch('/api/emergency-stop', { method: 'POST' });
      alert('紧急停止已执行');
    } catch (e) {
      alert('执行失败,请检查连接');
    }
  };

  return (
    <button
      onClick={handleStop}
      className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm font-bold transition-colors"
    >
      紧急停止
    </button>
  );
}
