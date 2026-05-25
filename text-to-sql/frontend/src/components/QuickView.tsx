import { SystemStatus, UpInfo } from '../services/api';

interface QuickViewProps {
  type: 'status' | 'up_list' | 'recent' | 'categories';
  data: any;
}

export default function QuickView({ type, data }: QuickViewProps) {
  switch (type) {
    case 'status':
      return <StatusView data={data as SystemStatus} />;
    case 'up_list':
      return <UpListView data={data as UpInfo[]} />;
    case 'recent':
      return <RecentView data={data as any[]} />;
    case 'categories':
      return <CategoriesView data={data as any[]} />;
    default:
      return null;
  }
}

// ============ /status ============

function StatusView({ data }: { data: SystemStatus | null }) {
  if (!data) {
    return (
      <div className="flex items-center gap-2 text-sm text-red-500">
        <span className="w-2 h-2 rounded-full bg-red-400" />
        无法获取系统状态
      </div>
    );
  }

  const items = [
    { name: 'Router Agent', status: data.router, icon: 'R' },
    { name: 'Text-to-SQL', status: data.text_to_sql, icon: 'S' },
    { name: 'RAG', status: data.rag, icon: 'R' },
  ];

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-gray-500 mb-2">系统状态</div>
      <div className="grid grid-cols-3 gap-2">
        {items.map((item) => {
          const ok = item.status === 'ok';
          return (
            <div
              key={item.name}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${
                ok
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                  ok ? 'bg-green-500' : 'bg-red-500'
                }`}
              >
                {item.icon}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-medium text-gray-700 truncate">
                  {item.name}
                </div>
                <div
                  className={`text-xs ${ok ? 'text-green-600' : 'text-red-600'}`}
                >
                  {ok ? '正常' : '不可用'}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============ /up_list ============

function UpListView({ data }: { data: UpInfo[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="text-sm text-gray-400 py-2">暂无 UP主 数据</div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs font-medium text-gray-500">
          UP主列表
        </div>
        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
          共 {data.length} 位
        </span>
      </div>
      <div className="space-y-1.5">
        {data.map((up, i) => (
          <div
            key={up.uid || i}
            className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold shrink-0">
                {(up.name || '?').charAt(0)}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-800 truncate">
                  {up.name}
                </div>
                {up.last_update && (
                  <div className="text-xs text-gray-400">
                    更新于 {up.last_update}
                  </div>
                )}
              </div>
            </div>
            <div className="text-xs text-gray-500 bg-white px-2 py-0.5 rounded border border-gray-200 whitespace-nowrap ml-2">
              {up.total_videos} 视频
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============ /recent ============

function RecentView({ data }: { data: any[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="text-sm text-gray-400 py-2">暂无视频数据</div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs font-medium text-gray-500">最近采集</div>
        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
          {data.length} 个视频
        </span>
      </div>
      <div className="space-y-1.5">
        {data.map((v, i) => (
          <div
            key={i}
            className="px-3 py-2.5 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-gray-800 truncate" title={v.title}>
                  {v.title}
                </div>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <span className="inline-flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                    {v.up_name || '未知'}
                  </span>
                  {v.category && (
                    <span className="text-xs text-gray-500 bg-white px-1.5 py-0.5 rounded border border-gray-200">
                      {v.category}
                    </span>
                  )}
                  {v.duration && (
                    <span className="text-xs text-gray-400">
                      {v.duration}
                    </span>
                  )}
                </div>
              </div>
              {v.publish_date && (
                <div className="text-xs text-gray-400 whitespace-nowrap shrink-0">
                  {v.publish_date}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============ /categories ============

function CategoriesView({ data }: { data: any[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="text-sm text-gray-400 py-2">暂无分类数据</div>
    );
  }

  const maxCount = Math.max(...data.map((d) => d.count || 0));

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs font-medium text-gray-500">分类统计</div>
        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
          {data.length} 个分类
        </span>
      </div>
      <div className="space-y-1">
        {data.map((d, i) => {
          const percent = maxCount > 0 ? ((d.count || 0) / maxCount) * 100 : 0;
          return (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 rounded"
            >
              <div className="w-20 text-xs text-gray-700 truncate shrink-0" title={d.category}>
                {d.category}
              </div>
              <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-blue-400 h-full rounded-full"
                  style={{ width: `${percent}%` }}
                />
              </div>
              <div className="text-xs text-gray-500 w-8 text-right tabular-nums">
                {d.count}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
