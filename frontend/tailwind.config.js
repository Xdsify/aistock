/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        buy: '#ef4444',    // 红色=涨 (A股习惯)
        sell: '#22c55e',   // 绿色=跌 (A股习惯)
        profit: '#ef4444',
        loss: '#22c55e',
        dark: {
          900: '#0f172a',
          800: '#1e293b',
          700: '#334155',
          600: '#475569',
        },
      },
    },
  },
  plugins: [],
};
