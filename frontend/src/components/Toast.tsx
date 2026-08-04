import { AlertTriangle, X, Info } from 'lucide-react';
import { useToastStore } from '../stores/toastStore';

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const remove = useToastStore((s) => s.remove);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2 w-80">
      {toasts.map((t) => {
        const Icon = t.type === 'info' ? Info : AlertTriangle;
        const color =
          t.type === 'error'
            ? 'text-red-400 border-red-500/40'
            : t.type === 'warning'
              ? 'text-yellow-400 border-yellow-500/40'
              : 'text-blue-400 border-blue-500/40';
        return (
          <div key={t.id} className={`bg-gray-900 border ${color} rounded-lg p-3 flex items-start gap-2 shadow-lg`}>
            <Icon className="w-4 h-4 mt-0.5 shrink-0" />
            <span className="text-sm text-gray-200 flex-1">{t.message}</span>
            <button onClick={() => remove(t.id)} className="text-gray-500 hover:text-white shrink-0">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
