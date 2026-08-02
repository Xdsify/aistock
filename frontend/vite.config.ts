import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // 策略相关 → strategy-engine
      '/api/strategies': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace('/api/strategies', '/api/strategy'),
      },
      '/api/strategy': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      // AI相关 → ai-service
      '/api/ai': {
        target: 'http://localhost:8003',
        changeOrigin: true,
      },
      // 风控相关 → risk-manager
      '/api/risk': {
        target: 'http://localhost:8004',
        changeOrigin: true,
      },
      // 行情数据 → data-service
      '/api/stocks': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace('/api/stocks', '/api/data'),
      },
      '/api/market': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace('/api/market', '/api/data/market'),
      },
      '/api/data': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      // 订单/持仓/账户 → execution-engine
      '/api/orders': {
        target: 'http://localhost:9001',
        changeOrigin: true,
      },
      '/api/order': {
        target: 'http://localhost:9001',
        changeOrigin: true,
      },
      '/api/positions': {
        target: 'http://localhost:9001',
        changeOrigin: true,
      },
      '/api/account': {
        target: 'http://localhost:9001',
        changeOrigin: true,
      },
      '/api/emergency-stop': {
        target: 'http://localhost:9001',
        changeOrigin: true,
      },
      // 信号相关 → strategy-engine
      '/api/signals': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace('/api/signals', '/api/strategy/signal'),
      },
      // 其余API → 默认到 strategy-engine
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
    },
  },
});
