import { useState } from 'react';
import { Brain, Lock, User } from 'lucide-react';

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || '登录失败');
        return;
      }
      localStorage.setItem('token', data.token);
      onLogin();
    } catch {
      setError('请求失败，请检查服务是否运行');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center">
      <form onSubmit={submit} className="bg-gray-900 border border-gray-800 rounded-2xl p-8 w-96 space-y-5">
        <div className="text-center">
          <Brain className="w-10 h-10 text-blue-400 mx-auto mb-2" />
          <h1 className="text-2xl font-bold">AIStock</h1>
          <p className="text-sm text-gray-500">AI量化交易系统</p>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">用户名</label>
          <div className="relative">
            <User className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">密码</label>
          <div className="relative">
            <Lock className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg font-bold transition-colors"
        >
          {loading ? '登录中...' : '登录'}
        </button>
        <p className="text-xs text-gray-600 text-center">默认账号 admin / admin123 (可通过 ADMIN_PASSWORD 环境变量修改)</p>
      </form>
    </div>
  );
}
