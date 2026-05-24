import { useState, useEffect } from 'react';
import { getStatus, getUpList, getRecent, SystemStatus } from '../services/api';

interface StatusPanelProps {
  onQuickQuestion: (question: string) => void;
}

// 快捷问题推荐
const QUICK_QUESTIONS = [
  { label: '系统状态', question: '/status' },
  { label: 'UP主列表', question: '/up_list' },
  { label: '最近视频', question: '/recent' },
];

const SAMPLE_QUESTIONS = [
  '一共有多少个视频？',
  '桃姐最近发了几个视频？',
  '各分类有多少视频？',
  '博主们对冷暴力怎么看？',
  '最近一周有什么新内容？',
  '关于改善沟通有什么建议？',
];

export default function StatusPanel({ onQuickQuestion }: StatusPanelProps) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [upCount, setUpCount] = useState(0);
  const [recentCount, setRecentCount] = useState(0);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    const s = await getStatus();
    setStatus(s);

    // 获取统计数据
    try {
      const upList = await getUpList();
      setUpCount(upList.length);
      const recent = await getRecent();
      setRecentCount(recent.length);
    } catch {
      // 忽略
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 space-y-4">
      {/* 系统状态 */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          系统状态
        </h3>
        <div className="space-y-1.5">
          <StatusRow
            label="Router"
            status={status?.router === 'ok' ? 'ok' : 'unknown'}
          />
          <StatusRow
            label="Text-to-SQL"
            status={status?.text_to_sql === 'ok' ? 'ok' : 'unavailable'}
          />
          <StatusRow
            label="RAG"
            status={status?.rag === 'ok' ? 'ok' : 'unavailable'}
          />
        </div>
      </div>

      {/* 数据概览 */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          数据概览
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <StatCard label="UP主" value={upCount} />
          <StatCard label="最近视频" value={recentCount} />
        </div>
      </div>

      {/* 快捷指令 */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          快捷指令
        </h3>
        <div className="flex flex-wrap gap-1.5">
          {QUICK_QUESTIONS.map((q) => (
            <button
              key={q.question}
              onClick={() => onQuickQuestion(q.question)}
              className="px-2.5 py-1 rounded-full text-xs bg-gray-100 text-gray-700
                         hover:bg-blue-100 hover:text-blue-700 transition-colors"
            >
              {q.label}
            </button>
          ))}
        </div>
      </div>

      {/* 示例问题 */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          试试这样问
        </h3>
        <div className="space-y-1">
          {SAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => onQuickQuestion(q)}
              className="block w-full text-left px-2.5 py-1.5 rounded text-xs text-gray-600
                         hover:bg-blue-50 hover:text-blue-700 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* 刷新按钮 */}
      <button
        onClick={fetchStatus}
        className="w-full px-3 py-1.5 rounded text-xs text-gray-500 border border-gray-200
                   hover:bg-gray-50 transition-colors"
      >
        刷新状态
      </button>
    </div>
  );
}

function StatusRow({
  label,
  status,
}: {
  label: string;
  status: 'ok' | 'unavailable' | 'unknown';
}) {
  const colors = {
    ok: 'bg-green-400',
    unavailable: 'bg-red-400',
    unknown: 'bg-gray-400',
  };

  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${colors[status]}`} />
      <span className="text-xs text-gray-600">{label}</span>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-gray-50 rounded-lg p-2 text-center">
      <div className="text-lg font-bold text-gray-800">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
