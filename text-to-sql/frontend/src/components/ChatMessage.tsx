import ResultTable from './ResultTable';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  routeType?: string;
  sql?: string;
  sqlResult?: any[];
  reasoning?: string;
  responseTime?: number;
}

// 路由类型标签颜色和文字
const ROUTE_LABELS: Record<string, { label: string; color: string }> = {
  structured: { label: '结构化查询', color: 'bg-purple-100 text-purple-800' },
  semantic: { label: '语义检索', color: 'bg-green-100 text-green-800' },
  hybrid: { label: '混合查询', color: 'bg-orange-100 text-orange-800' },
  error: { label: '错误', color: 'bg-red-100 text-red-800' },
};

export default function ChatMessage({
  role,
  content,
  routeType,
  sql,
  sqlResult,
  reasoning,
  responseTime,
}: ChatMessageProps) {
  const isUser = role === 'user';
  const routeInfo = routeType ? ROUTE_LABELS[routeType] : null;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[80%] ${isUser ? 'order-2' : ''}`}>
        {/* 消息气泡 */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-md'
              : 'bg-white border border-gray-200 text-gray-800 rounded-bl-md shadow-sm'
          }`}
        >
          {/* 路由标签（仅 assistant 消息） */}
          {!isUser && routeInfo && (
            <div className="flex items-center gap-2 mb-2">
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${routeInfo.color}`}
              >
                {routeInfo.label}
              </span>
              {responseTime !== undefined && (
                <span className="text-xs text-gray-400">
                  {responseTime.toFixed(1)}s
                </span>
              )}
            </div>
          )}

          {/* 消息内容 */}
          <div className="text-sm whitespace-pre-wrap leading-relaxed">
            {content}
          </div>

          {/* 推理过程（可折叠） */}
          {!isUser && reasoning && (
            <details className="mt-2 text-xs text-gray-500">
              <summary className="cursor-pointer hover:text-gray-700">
                分类理由
              </summary>
              <p className="mt-1 pl-2 border-l-2 border-gray-200">
                {reasoning}
              </p>
            </details>
          )}
        </div>

        {/* SQL 展示（仅 assistant 消息） */}
        {!isUser && sql && (
          <details className="mt-2 ml-2">
            <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
              查看 SQL
            </summary>
            <pre className="mt-1 bg-gray-50 p-3 rounded-lg overflow-x-auto text-xs font-mono text-gray-700 border border-gray-200">
              {sql}
            </pre>
          </details>
        )}

        {/* 数据表格（仅 assistant 消息） */}
        {!isUser && sqlResult && sqlResult.length > 0 && (
          <details className="mt-2 ml-2">
            <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
              查看数据表格 ({sqlResult.length} 条)
            </summary>
            <div className="mt-2 overflow-x-auto">
              <ResultTable data={sqlResult} />
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
