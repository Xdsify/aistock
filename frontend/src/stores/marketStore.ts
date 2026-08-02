import { create } from 'zustand';

interface Quote {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  change: number;
  volume: number;
  amount: number;
  high: number;
  low: number;
  open: number;
  pre_close: number;
  timestamp: string;
}

interface MarketState {
  quotes: Record<string, Quote>;
  sentiment: {
    advance_decline_ratio: number;
    limit_up_count: number;
    limit_down_count: number;
    avg_change_pct: number;
  } | null;
  updateQuote: (quote: Quote) => void;
  updateSentiment: (data: any) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  quotes: {},
  sentiment: null,

  updateQuote: (quote) =>
    set((state) => ({
      quotes: { ...state.quotes, [quote.symbol]: quote },
    })),

  updateSentiment: (data) =>
    set({ sentiment: data }),
}));
