import { useState } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import {
  Activity, ShieldAlert, Settings, Briefcase,
  Zap, BarChart3, Brain, Wifi, WifiOff, LogOut, ArrowRightLeft, Flame
} from 'lucide-react';
import { useWebSocket } from './hooks/useWebSocket';
import { usePositionStore } from './stores/positionStore';
import { useMarketStore } from './stores/marketStore';
import { useSignalStore } from './stores/signalStore';
import { useConnectionStore } from './stores/connectionStore';
import ToastContainer from './components/Toast';

// Pages
import Dashboard from './pages/Dashboard';
import RiskMonitor from './pages/RiskMonitor';
import SettingsPage from './pages/Settings';
import Positions from './pages/Positions';
import Signals from './pages/Signals';
import Strategies from './pages/Strategies';
import AIScreener from './pages/AIScreener';
import ManualTrade from './pages/ManualTrade';
import LimitUp from './pages/LimitUp';
import StockDetail from './pages/StockDetail';
import LoginPage from './pages/Login';

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  // 全局 WebSocket 连接
  useWebSocket();

  if (!token) {
    return <LoginPage onLogin={() => setToken(localStorage.getItem('token'))} />;
  }

  return (
    <div className="flex h-screen bg-black text-white">
      <ToastContainer />
      {/* 侧边栏 */}
      <nav className="w-56 bg-gray-950 border-r border-gray-800 flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-lg font-bold text-blue-400">AIStock</h1>
          <p className="text-xs text-gray-500">AI量化交易系统</p>
        </div>

        <div className="flex-1 p-3 space-y-1 overflow-y-auto">
          <NavItem to="/" end icon={Activity} label="仪表盘" />
          <NavItem to="/signals" icon={Zap} label="信号面板" />
          <NavItem to="/positions" icon={Briefcase} label="持仓管理" />
          <NavItem to="/trade" icon={ArrowRightLeft} label="手动交易" />
          <NavItem to="/strategies" icon={BarChart3} label="策略管理" />
          <NavItem to="/ai-screener" icon={Brain} label="AI 选股" />
          <NavItem to="/limit-up" icon={Flame} label="涨停分析" />
          <NavItem to="/risk" icon={ShieldAlert} label="风控监控" />
          <NavItem to="/settings" icon={Settings} label="系统设置" />
        </div>

        <StatusBar />
      </nav>

      {/* 主内容 */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/signals" element={<Signals />} />
          <Route path="/positions" element={<Positions />} />
          <Route path="/trade" element={<ManualTrade />} />
          <Route path="/strategies" element={<Strategies />} />
          <Route path="/ai-screener" element={<AIScreener />} />
          <Route path="/limit-up" element={<LimitUp />} />
          <Route path="/stock/:symbol" element={<StockDetail />} />
          <Route path="/risk" element={<RiskMonitor />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}

function NavItem({ to, end, icon: Icon, label }: {
  to: string; end?: boolean; icon: any; label: string;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
          isActive ? 'bg-blue-600/20 text-blue-400' : 'text-gray-400 hover:text-white hover:bg-gray-800'
        }`
      }
    >
      <Icon className="w-4 h-4" />
      {label}
    </NavLink>
  );
}

function StatusBar() {
  // 检测 WebSocket 和服务状态
  const account = usePositionStore((s) => s.account);
  const wsConnected = useConnectionStore((s) => s.connected);

  const handleLogout = () => {
    localStorage.removeItem('token');
    window.location.reload();
  };

  return (
    <div className="p-3 border-t border-gray-800 space-y-2 text-xs">
      <div className="flex items-center gap-2 text-gray-500">
        {wsConnected ? (
          <Wifi className="w-3 h-3 text-green-400" />
        ) : (
          <WifiOff className="w-3 h-3 text-red-400" />
        )}
        系统运行中
      </div>
      {account && (
        <div className="text-gray-500">
          资产: <span className="text-white">¥{account.total_equity?.toLocaleString() || '---'}</span>
        </div>
      )}
      <button
        onClick={handleLogout}
        className="w-full flex items-center gap-2 text-gray-500 hover:text-white transition-colors"
      >
        <LogOut className="w-3 h-3" /> 退出登录
      </button>
    </div>
  );
}
