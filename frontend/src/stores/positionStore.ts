import { create } from 'zustand';

interface Position {
  symbol: string;
  total_qty: number;
  available_sell: number;
  locked_qty: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  updated_at: string;
}

interface AccountInfo {
  total_equity: number;
  available_cash: number;
  market_value: number;
}

interface PositionState {
  positions: Record<string, Position>;
  account: AccountInfo | null;
  totalPnL: number;
  totalPnLPct: number;
  winRate: number;
  profitFactor: number;

  updatePosition: (pos: Position) => void;
  setPositions: (positions: Position[]) => void;
  setAccount: (account: AccountInfo) => void;
}

export const usePositionStore = create<PositionState>((set) => ({
  positions: {},
  account: null,
  totalPnL: 0,
  totalPnLPct: 0,
  winRate: 0,
  profitFactor: 0,

  updatePosition: (pos) =>
    set((state) => ({
      positions: { ...state.positions, [pos.symbol]: pos },
    })),

  setPositions: (positions) =>
    set(() => ({
      positions: Object.fromEntries(positions.map((p) => [p.symbol, p])),
    })),

  setAccount: (account) =>
    set({ account }),
}));
