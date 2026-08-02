import { Brain, Check, X } from 'lucide-react';

interface SignalCardProps {
  signal: {
    signal_id: string;
    strategy_name: string;
    symbol: string;
    action: 'BUY' | 'SELL';
    strength: number;
    price: number;
    stop_loss: number;
    take_profit: number;
    reason: string;
    ai_confidence: number;
    ai_notes: string;
    requires_confirmation: boolean;
    timestamp: string;
  };
  onApprove: () => void;
  onReject: () => void;
}

export default function SignalCard({ signal, onApprove, onReject }: SignalCardProps) {
  const isBuy = signal.action === 'BUY';

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${
            isBuy ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'
          }`}>
            {isBuy ? '买入' : '卖出'}
          </span>
          <span className="font-mono font-bold">{signal.symbol}</span>
          <span className="text-xs text-gray-500">@ {signal.price}</span>
        </div>

        {signal.ai_confidence > 0 && (
          <div className="flex items-center gap-1 text-xs text-blue-400">
            <Brain className="w-3 h-3" />
            AI: {(signal.ai_confidence * 100).toFixed(0)}%
          </div>
        )}
      </div>

      <p className="text-sm text-gray-400 mb-3">{signal.reason}</p>

      <div className="flex gap-3 text-xs text-gray-500 mb-3">
        <span>止损: {signal.stop_loss}</span>
        <span>止盈: {signal.take_profit}</span>
        <span>强度: {(signal.strength * 100).toFixed(0)}%</span>
      </div>

      {signal.requires_confirmation && (
        <div className="flex gap-2">
          <button
            onClick={onApprove}
            className="flex items-center gap-1 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm"
          >
            <Check className="w-4 h-4" /> 批准
          </button>
          <button
            onClick={onReject}
            className="flex items-center gap-1 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm"
          >
            <X className="w-4 h-4" /> 拒绝
          </button>
        </div>
      )}
    </div>
  );
}
