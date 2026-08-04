import { TrendingUp, Target, Percent } from 'lucide-react';

interface PnLCardProps {
  totalPnL: number;
  totalPnLPct: number;
  winRate: number;
  profitFactor: number;
  positionPct?: number;
}

export default function PnLCard({ totalPnL, totalPnLPct, winRate, profitFactor, positionPct = 0 }: PnLCardProps) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 space-y-4">
      <div>
        <span className="text-xs text-gray-400">累计盈亏</span>
        <div className={`text-2xl font-bold ${totalPnL >= 0 ? 'text-up' : 'text-down'}`}>
          {totalPnL >= 0 ? '+' : ''}{totalPnL.toLocaleString()}
          <span className="text-sm font-normal ml-1">
            ({totalPnLPct >= 0 ? '+' : ''}{totalPnLPct}%)
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-1 text-xs text-gray-400 mb-1">
            <Target className="w-3 h-3" />
            胜率
          </div>
          <div className="text-lg font-bold">{winRate}%</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-1 text-xs text-gray-400 mb-1">
            <Percent className="w-3 h-3" />
            盈亏比
          </div>
          <div className="text-lg font-bold">{profitFactor}</div>
        </div>
      </div>

      {/* 进度条 */}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-400">仓位占比</span>
          <span>{positionPct}%</span>
        </div>
        <div className="w-full bg-gray-800 rounded-full h-2">
          <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${Math.min(positionPct, 100)}%` }} />
        </div>
      </div>
    </div>
  );
}
