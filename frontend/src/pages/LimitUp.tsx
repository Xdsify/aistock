import { useEffect, useState } from 'react';
import { Flame, CalendarDays, AlertTriangle } from 'lucide-react';

interface PoolItem {
  symbol: string;
  name: string;
  change_pct: number;
  price: number;
  turnover_rate: number;
  seal_amount: number;
  first_time: string;
  last_time: string;
  zhaban_count: number;
  lianban: number;
  industry: string;
}

interface PoolResult {
  date: string;
  count: number;
  first_board: number;
  lianban: number;
  max_lianban: number;
  mock?: boolean;
  pools: PoolItem[];
}

type Tab = 'ALL' | 'FIRST' | 'LIANBAN';

function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

function displayDate(dateStr: string): string {
  if (dateStr.length === 8) {
    return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
  }
  return dateStr;
}

export default function LimitUp() {
  const [date, setDate] = useState(formatDate(new Date()));
  const [result, setResult] = useState<PoolResult | null>(null);
  const [tab, setTab] = useState<Tab>('ALL');
  const [loading, setLoading] = useState(false);

  const load = async (d: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/data/market/ztpool?date=${d}`);
      if (res.ok) {
        const data = await res.json();
        setResult(data);
      }
    } catch (e) {
      console.error('获取涨停池失败:', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    load(date);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = result?.pools?.filter((p) =>
    tab === 'FIRST' ? p.lianban === 1 : tab === 'LIANBAN' ? p.lianban >= 2 : true,
  ) || [];

  const tabs: { key: Tab; label: string }[] = [
    { key: 'ALL', label: `全部涨停 (${result?.count ?? 0})` },
    { key: 'FIRST', label: `首板 (${result?.first_board ?? 0})` },
    { key: 'LIANBAN', label: `连板 (${result?.lianban ?? 0})` },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Flame className="w-6 h-6 text-red-500" /> 涨停分析
        </h1>
        <div className="flex items-center gap-2 text-sm">
          <input
            type="date"
            value={date.length === 8 ? `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}` : date}
            onChange={(e) => {
              const v = e.target.value.replace(/-/g, '');
              setDate(v);
              load(v);
            }}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
          <CalendarDays className="w-4 h-4 text-gray-500" />
        </div>
      </div>

      {result?.mock && (
        <div className="bg-yellow-900/30 border border-yellow-600/30 rounded-xl p-3 flex items-center gap-2 text-sm text-yellow-400">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          示例数据（行情服务/AKShare 当前不可用，恢复后自动显示真实涨停池）
        </div>
      )}

      {/* 汇总 */}
      <div className="grid grid-cols-4 gap-3">
        <SummaryBox label="涨停家数" value={result?.count ?? 0} color="text-red-400" />
        <SummaryBox label="首板" value={result?.first_board ?? 0} color="text-yellow-400" />
        <SummaryBox label="连板" value={result?.lianban ?? 0} color="text-orange-400" />
        <SummaryBox label="最高连板" value={result?.max_lianban ?? 0} color="text-purple-400" />
      </div>

      {/* 标签 */}
      <div className="flex gap-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              tab === t.key ? 'bg-red-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-gray-400 text-sm">加载中...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Flame className="w-12 h-12 mx-auto mb-4 opacity-30" />
          {result ? `该日 (${displayDate(result.date)}) 没有符合条件的涨停股` : '暂无数据'}
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-gray-400">
                <th className="p-3">股票</th>
                <th className="p-3 text-right">现价</th>
                <th className="p-3 text-right">涨跌幅</th>
                <th className="p-3 text-center">连板数</th>
                <th className="p-3 text-right">封板资金(亿)</th>
                <th className="p-3 text-center">首次封板</th>
                <th className="p-3 text-center">炸板</th>
                <th className="p-3 text-right">换手率</th>
                <th className="p-3">行业</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr key={p.symbol} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="p-3">
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-gray-500">{p.symbol}</div>
                  </td>
                  <td className="p-3 text-right font-mono">{p.price.toFixed(2)}</td>
                  <td className="p-3 text-right font-mono text-red-400">+{p.change_pct.toFixed(2)}%</td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                      p.lianban >= 3 ? 'bg-red-600 text-white' : p.lianban === 2 ? 'bg-orange-600/80 text-white' : 'bg-gray-700 text-gray-200'
                    }`}>
                      {p.lianban}板
                    </span>
                  </td>
                  <td className="p-3 text-right font-mono">{p.seal_amount.toFixed(2)}</td>
                  <td className="p-3 text-center font-mono text-gray-400">{p.first_time}</td>
                  <td className="p-3 text-center">{p.zhaban_count > 0 ? <span className="text-yellow-400">{p.zhaban_count}次</span> : <span className="text-gray-600">-</span>}</td>
                  <td className="p-3 text-right font-mono">{p.turnover_rate.toFixed(2)}%</td>
                  <td className="p-3"><span className="text-xs bg-gray-800 px-2 py-0.5 rounded">{p.industry || '-'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SummaryBox({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-gray-900 rounded-xl p-3 border border-gray-800 text-center">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
