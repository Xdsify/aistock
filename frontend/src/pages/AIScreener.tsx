import { useState } from 'react';
import { Brain, TrendingUp, AlertTriangle, Clock, Zap, Activity } from 'lucide-react';
import { useMarketStore } from '../stores/marketStore';
import StockLink from '../components/StockLink';

interface StockPick {
  symbol: string;
  name: string;
  score: number;
  reason: string;
  suggested_holding_days: number;
  risk_level: string;
}

interface ScreenResult {
  picks: StockPick[];
  market_overview: string;
  strategy_note: string;
  _market_data?: {
    hot_sectors: string[];
    timestamp: string;
  };
  error?: string;
}

export default function AIScreener() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [error, setError] = useState('');
  const quotes = useMarketStore((s) => s.quotes);

  const runScreen = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await fetch('/api/data/ai/screen', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setResult(data);
      }
    } catch (e: any) {
      setError(e.message || '请求失败，检查后端服务');
    }
    setLoading(false);
  };

  // 一键买入: 优先用实时行情价, 没有则手动输入
  async function quickBuy(pick: StockPick) {
    let price = quotes[pick.symbol]?.price;
    if (!price) {
      const p = prompt(`请输入 ${pick.symbol} 买入价格:`, '');
      if (!p) return;
      price = parseFloat(p);
    }
    if (!price || price <= 0) {
      alert('价格无效');
      return;
    }
    try {
      const res = await fetch('/api/strategy/signal/quick-buy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: pick.symbol, name: pick.name, price, position_pct: 0.1 }),
      });
      const data = await res.json();
      if (res.ok) {
        alert(data.message || '买入订单已提交');
      } else {
        alert(data.detail || data.message || '买入失败: ' + res.status);
      }
    } catch (e) {
      alert('请求失败，检查后端是否运行');
    }
  }

  const riskColor: Record<string, string> = {
    LOW: 'text-green-400', MEDIUM: 'text-yellow-400', HIGH: 'text-red-400',
  };
  const riskBg: Record<string, string> = {
    LOW: 'bg-green-900/30', MEDIUM: 'bg-yellow-900/30', HIGH: 'bg-red-900/30',
  };
  const riskLabel: Record<string, string> = {
    LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险',
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="w-6 h-6 text-purple-400" />
            AI 智能选股
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            DeepSeek 扫描全市场，综合技术面+资金面+板块轮动，挑出5只潜力股
          </p>
        </div>
        <button
          onClick={runScreen}
          disabled={loading}
          className={`px-6 py-3 rounded-xl text-lg font-bold transition-all ${
            loading
              ? 'bg-gray-700 cursor-not-allowed'
              : 'bg-purple-600 hover:bg-purple-700 shadow-lg shadow-purple-500/25'
          }`}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin">⚡</span> 分析中...
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <Zap className="w-5 h-5" /> 开始选股
            </span>
          )}
        </button>
      </div>

      {/* 错误 */}
      {error && (
        <div className="bg-red-900/30 border border-red-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="w-5 h-5" />
            {error}
          </div>
        </div>
      )}

      {/* 加载中 */}
      {loading && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-12 text-center">
          <Activity className="w-12 h-12 text-purple-400 mx-auto mb-4 animate-pulse" />
          <p className="text-lg text-gray-300">DeepSeek 正在分析全市场数据...</p>
          <p className="text-sm text-gray-500 mt-2">采集涨幅榜、资金流向、板块热度，约需60秒</p>
        </div>
      )}

      {/* 结果 */}
      {result && !loading && (
        <>
          {/* 市场总览 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-gray-900 rounded-xl border border-gray-700 p-4">
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <TrendingUp className="w-4 h-4" />
                市场判断
              </div>
              <p className="text-lg font-semibold">{result.market_overview}</p>
            </div>
            <div className="bg-gray-900 rounded-xl border border-gray-700 p-4">
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <Brain className="w-4 h-4" />
                操作策略
              </div>
              <p className="text-lg font-semibold text-blue-400">{result.strategy_note}</p>
            </div>
          </div>

          {/* 热门板块 */}
          {result._market_data?.hot_sectors && (
            <div className="flex flex-wrap gap-2">
              <span className="text-sm text-gray-400">热门板块:</span>
              {result._market_data.hot_sectors.map((s: string, i: number) => (
                <span key={i} className="text-xs bg-purple-900/40 text-purple-300 px-2 py-1 rounded">
                  {s}
                </span>
              ))}
            </div>
          )}

          {/* 选股结果 */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-400" />
              精选5只股票
            </h3>
            {result.picks.map((pick, i) => (
              <div
                key={pick.symbol}
                className="bg-gray-900 rounded-xl border border-gray-700 hover:border-purple-500/50 transition-all p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-4">
                    {/* 排名 */}
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold ${
                      i === 0 ? 'bg-yellow-500/20 text-yellow-400' :
                      i === 1 ? 'bg-gray-400/20 text-gray-300' :
                      i === 2 ? 'bg-orange-500/20 text-orange-400' :
                      'bg-gray-600/20 text-gray-500'
                    }`}>
                      {i + 1}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-lg">{pick.symbol}</span>
                        <span className="text-gray-300"><StockLink symbol={pick.symbol} name={pick.name} /></span>
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className={`text-xs px-2 py-0.5 rounded ${riskBg[pick.risk_level]} ${riskColor[pick.risk_level]}`}>
                          {riskLabel[pick.risk_level]}
                        </span>
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          建议持有 {pick.suggested_holding_days} 天
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 评分 */}
                  <div className="text-right">
                    <div className={`text-3xl font-bold ${
                      pick.score >= 80 ? 'text-green-400' :
                      pick.score >= 60 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {pick.score}
                    </div>
                    <div className="text-xs text-gray-500">综合评分</div>
                  </div>
                </div>

                {/* 理由 */}
                <div className="bg-gray-800 rounded-lg p-3 text-sm text-gray-300">
                  <span className="text-gray-500">AI分析: </span>
                  {pick.reason}
                </div>

                {/* 一键买入 */}
                <button
                  onClick={() => quickBuy(pick)}
                  className="mt-3 w-full py-2 bg-red-600/80 hover:bg-red-600 rounded-lg text-sm font-bold transition-colors"
                >
                  买入 {pick.symbol}
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* 空状态 */}
      {!result && !loading && !error && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-16 text-center">
          <Brain className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500 text-lg">点击上方「开始选股」按钮</p>
          <p className="text-gray-600 text-sm mt-2">AI 将扫描全市场数据，为你挑出5只最有潜力的股票</p>
        </div>
      )}
    </div>
  );
}
