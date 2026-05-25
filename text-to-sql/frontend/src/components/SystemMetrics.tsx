import { useState, useEffect, useRef } from 'react';
import { getSystemMetrics, SystemMetricsResponse, ContainerMetric } from '../services/api';

// 容器显示名称和内存限制映射
const CONTAINER_INFO: Record<string, { label: string; memLimit: string }> = {
  chromadb: { label: 'ChromaDB', memLimit: '1 GB' },
  'text-to-sql': { label: 'Text-to-SQL', memLimit: '2 GB' },
  rag: { label: 'RAG', memLimit: '2 GB' },
  'router-agent': { label: 'Router Agent', memLimit: '1 GB' },
  frontend: { label: 'Frontend', memLimit: '256 MB' },
};

export default function SystemMetrics() {
  const [metrics, setMetrics] = useState<SystemMetricsResponse | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchMetrics();
  }, []);

  useEffect(() => {
    if (autoRefresh) {
      pollRef.current = setInterval(fetchMetrics, 30000);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [autoRefresh]);

  const fetchMetrics = async () => {
    const data = await getSystemMetrics();
    setMetrics(data);
  };

  return (
    <div className="space-y-5">
      {/* 顶部信息栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {metrics?.uptime && (
            <span className="text-xs text-gray-500">
              运行时间: {metrics.uptime}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-3.5 h-3.5 rounded"
            />
            自动刷新 (30s)
          </label>
          <button
            onClick={fetchMetrics}
            className="px-3 py-1 text-xs border border-gray-200 rounded
                       hover:bg-gray-50 transition-colors"
          >
            刷新
          </button>
        </div>
      </div>

      {!metrics ? (
        <div className="text-center py-8 text-sm text-gray-400">加载中...</div>
      ) : (
        <>
          {/* 容器状态卡片 */}
          <div>
            <h4 className="text-sm font-medium text-gray-600 mb-2">容器状态</h4>
            <div className="grid grid-cols-1 gap-3">
              {Object.entries(CONTAINER_INFO).map(([name, info]) => {
                const metric = metrics.containers?.[name];
                return (
                  <ContainerCard
                    key={name}
                    name={name}
                    label={info.label}
                    memLimit={info.memLimit}
                    metric={metric}
                  />
                );
              })}
            </div>
          </div>

          {/* 知识库指标 */}
          <div>
            <h4 className="text-sm font-medium text-gray-600 mb-2">知识库</h4>
            <div className="grid grid-cols-3 gap-3">
              <MetricCard
                label="文档块数"
                value={metrics.rag_stats?.video_chunks ?? '—'}
              />
              <MetricCard
                label="视频总数"
                value={extractVideoCount(metrics.sql_stats) ?? '—'}
              />
              <MetricCard
                label="总查询数"
                value={metrics.query_stats?.total_queries ?? 0}
              />
            </div>
          </div>

          {/* 查询类型分布 */}
          {metrics.query_stats?.by_route_type &&
            Object.keys(metrics.query_stats.by_route_type).length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-600 mb-2">
                  查询类型分布
                </h4>
                <div className="flex items-center gap-3">
                  <RouteTypeBar data={metrics.query_stats.by_route_type} />
                  <div className="text-xs text-gray-500">
                    平均响应: {metrics.query_stats?.avg_response_time ?? 0}s
                  </div>
                </div>
              </div>
            )}
        </>
      )}
    </div>
  );
}

function ContainerCard({
  name,
  label,
  memLimit,
  metric,
}: {
  name: string;
  label: string;
  memLimit: string;
  metric?: ContainerMetric;
}) {
  const isRunning = metric?.status === 'running';
  const memPercent = metric?.memory_percent ?? 0;
  const memUsage = metric ? formatBytes(metric.memory_usage) : '—';

  // 内存条颜色
  const barColor =
    memPercent > 90
      ? 'bg-red-500'
      : memPercent > 70
        ? 'bg-yellow-500'
        : 'bg-blue-500';

  return (
    <div className="border rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isRunning ? 'bg-green-400' : 'bg-gray-300'
            }`}
          />
          <span className="text-sm font-medium text-gray-700">{label}</span>
          <span className="text-xs text-gray-400">{name}</span>
        </div>
        <div className="flex items-center gap-2">
          {metric?.ports && metric.ports.length > 0 && (
            <span className="text-xs text-gray-400">
              {metric.ports[0]}
            </span>
          )}
          <span
            className={`text-xs px-1.5 py-0.5 rounded ${
              isRunning
                ? 'bg-green-50 text-green-600'
                : 'bg-gray-100 text-gray-500'
            }`}
          >
            {isRunning ? '运行中' : '未运行'}
          </span>
        </div>
      </div>

      {/* 内存使用条 */}
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${barColor}`}
            style={{ width: `${Math.min(memPercent, 100)}%` }}
          />
        </div>
        <span className="text-xs text-gray-500 whitespace-nowrap tabular-nums w-32 text-right">
          {isRunning ? `${memUsage} / ${memLimit}` : `限制: ${memLimit}`}
        </span>
      </div>

      {/* CPU */}
      {isRunning && (
        <div className="text-xs text-gray-400 mt-1 text-right tabular-nums">
          CPU: {metric?.cpu_percent ?? 0}%
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="bg-gray-50 rounded-lg p-3 text-center">
      <div className="text-xl font-bold text-gray-800 tabular-nums">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

function RouteTypeBar({ data }: { data: Record<string, number> }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const colors: Record<string, string> = {
    structured: 'bg-blue-500',
    semantic: 'bg-green-500',
    hybrid: 'bg-purple-500',
  };

  const labels: Record<string, string> = {
    structured: '结构化',
    semantic: '语义',
    hybrid: '混合',
  };

  return (
    <div className="flex-1">
      {/* 横条图 */}
      <div className="flex h-4 rounded-full overflow-hidden">
        {Object.entries(data).map(([type, count]) => {
          const percent = (count / total) * 100;
          return (
            <div
              key={type}
              className={`${colors[type] || 'bg-gray-400'} transition-all`}
              style={{ width: `${percent}%` }}
              title={`${labels[type] || type}: ${count} (${percent.toFixed(1)}%)`}
            />
          );
        })}
      </div>
      {/* 图例 */}
      <div className="flex gap-3 mt-1.5">
        {Object.entries(data).map(([type, count]) => (
          <div key={type} className="flex items-center gap-1 text-xs text-gray-500">
            <div
              className={`w-2.5 h-2.5 rounded-sm ${colors[type] || 'bg-gray-400'}`}
            />
            <span>
              {labels[type] || type}: {count} (
              {((count / total) * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function extractVideoCount(sqlStats: any): number | string {
  if (!sqlStats) return '—';
  if (typeof sqlStats.total_videos === 'number') return sqlStats.total_videos;
  // 尝试从 tables 数据中提取
  if (Array.isArray(sqlStats.tables)) {
    const videoTable = sqlStats.tables.find(
      (t: any) =>
        t &&
        typeof t === 'object' &&
        JSON.stringify(t).toLowerCase().includes('video_meta')
    );
    if (videoTable) return JSON.stringify(videoTable);
  }
  return '—';
}
