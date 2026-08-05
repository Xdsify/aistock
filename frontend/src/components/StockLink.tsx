import { Link } from 'react-router-dom';

/** 可点击的股票链接 → 个股详情页 (K线等) */
export default function StockLink({
  symbol, name, className,
}: {
  symbol: string;
  name?: string;
  className?: string;
}) {
  return (
    <Link
      to={`/stock/${encodeURIComponent(symbol)}`}
      className={`hover:text-blue-400 transition-colors ${className || ''}`}
      title="查看K线详情"
    >
      {name || symbol}
    </Link>
  );
}
