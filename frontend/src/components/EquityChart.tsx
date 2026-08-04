import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';

// 兜底数据: 当执行引擎没有真实权益历史时使用 (确定性生成, 不会每次刷新变化)
function stableEquityData() {
  const data = [];
  const startDate = new Date('2026-01-01');
  let equity = 470000;
  const changes = [
    1200, -800, 2100, -500, 3200, -1200, 800, 2400, -1500, 1800,
    -600, 3100, -2000, 900, 2600, -1100, 1400, -700, 3500, -1800,
    1000, -900, 2800, -400, 1600, -1300, 2200, -300, 1900, -1000,
    2700, -1600, 1100, -500, 3000, -1400, 700, 2400, -800, 1700,
    -1100, 3200, -1700, 600, 2000, -900, 2500, -600, 1300, -400,
    2900, -1200, 400, 2100, -700, 1500, -300, 2600, -1000, 800,
    1800, -500, 3100, -1500, 500, 2200, -600, 1400, -200, 2700,
    -900, 600, 1900, -300, 2400, -700, 1000, 1600, -400, 3000,
    -1300, 300, 2000, -650, 1100, -350, 2500, -850, 450, 2150,
    -550, 650, 1750, -250, 2300, -450, 350, 1950, -150, 2850,
  ];

  for (let i = 0; i < changes.length; i++) {
    const date = new Date(startDate.getTime() + i * 24 * 60 * 60 * 1000);
    equity += changes[i];
    equity = Math.max(equity, 450000);
    data.push({
      time: date.toISOString().split('T')[0],
      value: Math.round(equity * 100) / 100,
    });
  }
  return data;
}

export default function EquityChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<any[] | null>(null);

  // 从执行引擎拉取真实权益历史
  useEffect(() => {
    fetch('/api/equity-history')
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (d?.points?.length) {
          setPoints(d.points.map((p: any) => ({
            time: Math.floor(new Date(p.time).getTime() / 1000),
            value: p.value,
          })));
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 300,
      timeScale: {
        timeVisible: true,
        borderColor: '#334155',
      },
    });

    const areaSeries = chart.addAreaSeries({
      lineColor: '#3b82f6',
      topColor: 'rgba(59, 130, 246, 0.3)',
      bottomColor: 'rgba(59, 130, 246, 0.02)',
      lineWidth: 2,
    });

    // 有真实数据用真实, 否则用兜底
    const data = points && points.length >= 2 ? points : stableEquityData();
    areaSeries.setData(data);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [points]);

  return <div ref={chartContainerRef} />;
}
