import { useState, useEffect } from 'react';
import { getQueryStats, QueryStatsResponse, QueryLogItem } from '../services/api';

const ROUTE_TYPES = [
  { value: '', label: '全部' },
  { value: 'structured', label: '结构化' },
  { value: 'semantic', label: '语义' },
  { value: 'hybrid', label: '混合' },
];

const ROUTE_COLORS: Record<string, string> = {
  structured: 'bg-blue-100 text-blue-700',
  semantic: 'bg-green-100 text-green-700',
  hybrid: 'bg-purple-100 text-purple-700',
};

export default function QueryLog() {
  const [data, setData] = useState<QueryStatsResponse | null>(null);
  const [page, setPage] = useState(1);
  const [routeFilter, setRouteFilter] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const pageSize = 15;

  useEffect(() => {
    fetchData();
  }, [page, routeFilter]);

  const fetchData = async () => {
    const result = await getQueryStats(page, pageSize, routeFilter || undefined);
    setData(result);
  };

  const queries = data?.queries;
  const stats = data?.stats;

  return (
    <div className="space-y-4">
      {/* 聚合统计 */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          <StatCard label="总查询数" value={stats.total_queries} />
          <StatCard
            label="平均响应"
            value={`${stats.avg_response_time}s`}
          />
          {Object.entries(stats.by_route_type).map(([type, count]) => (
            <StatCard
              key={type}
              label={type === 'structured' ? '结构化' : type === 'semantic' ? '语义' : type === 'hybrid' ? '混合' : type}
              value={count as number}
            />
          ))}
        </div>
      )}

      {/* 过滤 + 分页控制 */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          {ROUTE_TYPES.map((rt) => (
            <button
              key={rt.value}
              onClick={() => {
                setRouteFilter(rt.value);
                setPage(1);
              }}
              className={`px-3 py-1 rounded text-xs transition-colors ${
                routeFilter === rt.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {rt.label}
            </button>
          ))}
        </div>

        {queries && queries.total_pages > 1 && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-gray-50"
            >
              上一页
            </button>
            <span>
              {page} / {queries.total_pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(queries.total_pages, p + 1))}
              disabled={page >= queries.total_pages}
              className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-gray-50"
            >
              下一页
            </button>
          </div>
        )}
      </div>

      {/* 查询记录表格 */}
      {!queries || queries.items.length === 0 ? (
        <div className="text-center py-8 text-sm text-gray-400">
          暂无查询记录
        </div>
      ) : (
        <div className="border rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">
                  问题
                </th>
                <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 w-20">
                  类型
                </th>
                <th className="text-right px-3 py-2 text-xs font-medium text-gray-500 w-20">
                  耗时
                </th>
                <th className="text-right px-3 py-2 text-xs font-medium text-gray-500 w-40">
                  时间
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {queries.items.map((item: QueryLogItem) => (
                <QueryRow
                  key={item.id}
                  item={item}
                  expanded={expandedId === item.id}
                  onToggle={() =>
                    setExpandedId(expandedId === item.id ? null : item.id)
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 总数 */}
      {queries && (
        <div className="text-xs text-gray-400 text-right">
          共 {queries.total} 条记录
        </div>
      )}
    </div>
  );
}

function QueryRow({
  item,
  expanded,
  onToggle,
}: {
  item: QueryLogItem;
  expanded: boolean;
  onToggle: () => void;
}) {
  const badge = ROUTE_COLORS[item.route_type] || 'bg-gray-100 text-gray-600';
  const typeLabel =
    item.route_type === 'structured'
      ? '结构化'
      : item.route_type === 'semantic'
        ? '语义'
        : item.route_type === 'hybrid'
          ? '混合'
          : item.route_type;

  return (
    <>
      <tr
        className="hover:bg-gray-50 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="px-3 py-2 max-w-xs truncate text-gray-700">
          {expanded ? item.question : item.question.slice(0, 50)}
          {!expanded && item.question.length > 50 && '...'}
        </td>
        <td className="px-3 py-2">
          <span className={`px-2 py-0.5 rounded text-xs ${badge}`}>
            {typeLabel}
          </span>
        </td>
        <td className="px-3 py-2 text-right text-gray-500 tabular-nums">
          {item.response_time}s
        </td>
        <td className="px-3 py-2 text-right text-gray-400 text-xs">
          {formatDate(item.created_at)}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={4} className="px-3 py-2 bg-gray-50">
            <div className="text-xs text-gray-600 space-y-1">
              <div>
                <span className="font-medium">完整问题：</span>
                {item.question}
              </div>
              <div>
                <span className="font-medium">ID：</span>
                {item.id}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="bg-gray-50 rounded-lg p-3 text-center">
      <div className="text-lg font-bold text-gray-800 tabular-nums">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}
