import { create } from 'zustand';

interface Signal {
  signal_id: string;
  strategy_name: string;
  symbol: string;
  action: 'BUY' | 'SELL';
  strength: number;
  price: number;
  volume: number;
  position_pct: number;
  stop_loss: number;
  take_profit: number;
  reason: string;
  ai_confidence: number;
  ai_notes: string;
  risk_approved: boolean;
  requires_confirmation: boolean;
  timestamp: string;
}

interface SignalState {
  signals: Signal[];
  addSignal: (signal: Signal) => void;
  approveSignal: (signalId: string) => void;
  rejectSignal: (signalId: string) => void;
  clearSignals: () => void;
}

export const useSignalStore = create<SignalState>((set) => ({
  signals: [],

  addSignal: (signal) =>
    set((state) => ({
      signals: [signal, ...state.signals].slice(0, 50),
    })),

  approveSignal: (signalId) =>
    set((state) => ({
      signals: state.signals.filter((s) => s.signal_id !== signalId),
    })),

  rejectSignal: (signalId) =>
    set((state) => ({
      signals: state.signals.filter((s) => s.signal_id !== signalId),
    })),

  clearSignals: () => set({ signals: [] }),
}));
