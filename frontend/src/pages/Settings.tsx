import { useState } from 'react';
import { Save, Key, Server, Bell, Shield, CheckCircle } from 'lucide-react';

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    deepseekApiKey: '',
    brokerAccount: '',
    tushareToken: '',
    maxSingleStock: 20,
    maxSector: 40,
    dailyLossLimit: 5,
    maxDrawdown: 8,
    aiConfidenceThreshold: 60,
  });

  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const updateSetting = (key: string, value: any) =>
    setSettings((s) => ({ ...s, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      // 保存到后端 (通过环境变量配置更新 — 实际生产环境需要安全API)
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_single_stock_pct: settings.maxSingleStock / 100,
          max_sector_pct: settings.maxSector / 100,
          daily_loss_limit_pct: settings.dailyLossLimit / 100,
          max_drawdown_pct: settings.maxDrawdown / 100,
          ai_confidence_threshold: settings.aiConfidenceThreshold / 100,
        }),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } catch (e) {
      console.error('保存设置失败:', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">系统设置</h1>

      {/* API配置 */}
      <Section title="API配置" icon={Key}>
        <FormField label="DeepSeek API Key" type="password"
          value={settings.deepseekApiKey}
          onChange={(v) => updateSetting('deepseekApiKey', v)}
          placeholder="sk-..." />
        <FormField label="Tushare Token" type="password"
          value={settings.tushareToken}
          onChange={(v) => updateSetting('tushareToken', v)}
          placeholder="输入Tushare token" />
      </Section>

      {/* 券商配置 */}
      <Section title="券商配置" icon={Server}>
        <FormField label="华泰账户"
          value={settings.brokerAccount}
          onChange={(v) => updateSetting('brokerAccount', v)}
          placeholder="输入证券公司账号" />
        <FormField label="交易密码" type="password"
          value=""
          onChange={() => {}}
          placeholder="输入交易密码" />
      </Section>

      {/* 风控参数 */}
      <Section title="风控参数" icon={Shield}>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="单股仓位上限(%)" type="number"
            value={settings.maxSingleStock}
            onChange={(v) => updateSetting('maxSingleStock', Number(v))} />
          <FormField label="单行业仓位上限(%)" type="number"
            value={settings.maxSector}
            onChange={(v) => updateSetting('maxSector', Number(v))} />
          <FormField label="日亏损上限(%)" type="number"
            value={settings.dailyLossLimit}
            onChange={(v) => updateSetting('dailyLossLimit', Number(v))} />
          <FormField label="最大回撤(%)" type="number"
            value={settings.maxDrawdown}
            onChange={(v) => updateSetting('maxDrawdown', Number(v))} />
        </div>
      </Section>

      {/* AI参数 */}
      <Section title="AI参数" icon={Bell}>
        <FormField label="信号置信度阈值(%)" type="number"
          value={settings.aiConfidenceThreshold}
          onChange={(v) => updateSetting('aiConfidenceThreshold', Number(v))} />
        <div className="text-xs text-gray-500">
          AI置信度低于此阈值的信号将自动拒绝
        </div>
      </Section>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition-colors"
        >
          {saving ? (
            <>保存中...</>
          ) : (
            <>
              <Save className="w-4 h-4" />
              保存设置
            </>
          )}
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-green-400">
            <CheckCircle className="w-4 h-4" />
            保存成功
          </span>
        )}
      </div>
    </div>
  );
}

function Section({ title, icon: Icon, children }: { title: string; icon: any; children: any }) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <h3 className="font-semibold mb-4 flex items-center gap-2 text-blue-400">
        <Icon className="w-4 h-4" />
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function FormField({ label, type = 'text', value, onChange, placeholder }: {
  label: string; type?: string; value: string | number;
  onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm
                   focus:outline-none focus:border-blue-500 transition-colors"
      />
    </div>
  );
}
