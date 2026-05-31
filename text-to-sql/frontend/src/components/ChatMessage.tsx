import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';
import ResultTable from './ResultTable';
import QuickView from './QuickView';

// 引用来源类型
export interface SourceItem {
  bvid: string;
  title: string;
  up_name: string;
  category: string;
  url: string;
}

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  routeType?: string;
  sql?: string;
  sqlResult?: any[];
  reasoning?: string;
  responseTime?: number;
  quickView?: { type: 'status' | 'up_list' | 'recent' | 'categories'; data: any };
  sources?: SourceItem[];
}

// 路由类型标签颜色和文字
const ROUTE_LABELS: Record<string, { label: string; color: string }> = {
  structured: { label: '结构化查询', color: 'bg-purple-100 text-purple-800' },
  semantic: { label: '语义检索', color: 'bg-green-100 text-green-800' },
  hybrid: { label: '混合查询', color: 'bg-orange-100 text-orange-800' },
  error: { label: '错误', color: 'bg-red-100 text-red-800' },
};

// 复制按钮组件
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="p-1 rounded hover:bg-gray-200 transition-colors text-gray-400 hover:text-gray-600"
      title="复制"
    >
      {copied ? (
        <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  );
}

// 引用来源卡片组件
function SourcesCard({ sources }: { sources: SourceItem[] }) {
  if (!sources || sources.length === 0) return null;

  return (
    <details className="mt-3 pt-3 border-t border-gray-100">
      <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1">
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
        引用来源 ({sources.length})
      </summary>
      <div className="mt-2 space-y-1.5">
        {sources.map((s, i) => (
          <a
            key={s.bvid + i}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block p-2 bg-gray-50 hover:bg-blue-50 rounded-lg text-xs transition-colors group"
          >
            <div className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5 shrink-0">▶</span>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-700 group-hover:text-blue-700 truncate">
                  {s.title || s.bvid}
                </div>
                <div className="flex items-center gap-2 mt-0.5 text-gray-400">
                  {s.up_name && <span>{s.up_name}</span>}
                  {s.category && <span>· {s.category}</span>}
                  <span className="text-blue-400 group-hover:underline">{s.bvid}</span>
                </div>
              </div>
              <svg className="w-3.5 h-3.5 text-gray-300 group-hover:text-blue-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </div>
          </a>
        ))}
      </div>
    </details>
  );
}

export default function ChatMessage({
  role,
  content,
  routeType,
  sql,
  sqlResult,
  reasoning,
  responseTime,
  quickView,
  sources,
}: ChatMessageProps) {
  const isUser = role === 'user';
  const routeInfo = routeType ? ROUTE_LABELS[routeType] : null;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`${isUser ? 'max-w-[60%]' : 'max-w-[85%]'} ${isUser ? 'order-2' : ''}`}>
        {/* 消息气泡 */}
        <div
          className={`rounded-2xl px-5 py-4 relative ${
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
          {isUser ? (
            <div className="text-sm whitespace-pre-wrap leading-relaxed">
              {content}
            </div>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  // 链接新窗口打开
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {children}
                    </a>
                  ),
                  // 代码块样式
                  code: ({ className, children, ...props }) => {
                    const isInline = !className;
                    if (isInline) {
                      return (
                        <code className="bg-gray-100 text-pink-600 px-1.5 py-0.5 rounded text-[13px] font-mono">
                          {children}
                        </code>
                      );
                    }
                    return (
                      <code className={`${className || ''} text-[13px] font-mono`} {...props}>
                        {children}
                      </code>
                    );
                  },
                  pre: ({ children }) => (
                    <pre className="bg-gray-50 p-3 rounded-lg overflow-x-auto border border-gray-200 my-3">
                      {children}
                    </pre>
                  ),
                  // 列表样式 — 宽松间距
                  ul: ({ children }) => <ul className="list-disc pl-6 my-3 space-y-2.5">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-6 my-3 space-y-3">{children}</ol>,
                  // 列表项 — 增加内部间距
                  li: ({ children }) => (
                    <li className="leading-7 pl-0.5">
                      {children}
                    </li>
                  ),
                  // 标题样式
                  h1: ({ children }) => <h1 className="text-lg font-bold mt-4 mb-2 text-gray-900">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-base font-bold mt-3.5 mb-1.5 text-gray-900">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-[15px] font-bold mt-3 mb-1 text-gray-900">{children}</h3>,
                  // 粗体 — 在列表项内作为小标题更突出
                  strong: ({ children }) => (
                    <strong className="font-bold text-gray-900">{children}</strong>
                  ),
                  // 引用
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-blue-200 pl-4 py-1 my-3 text-gray-600 italic bg-blue-50/50 rounded-r-lg">
                      {children}
                    </blockquote>
                  ),
                  // 段落 — 宽松段间距
                  p: ({ children }) => <p className="my-2.5 leading-7">{children}</p>,
                  // 水平线
                  hr: () => <hr className="my-4 border-gray-200" />,
                  // 分隔线样式
                  br: () => <br />,
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}

          {/* 复制按钮（仅 assistant 消息，且内容足够长） */}
          {!isUser && content.length > 50 && (
            <div className="absolute top-2 right-2">
              <CopyButton text={content} />
            </div>
          )}

          {/* 快捷指令结构化视图 */}
          {!isUser && quickView && quickView.data && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <QuickView type={quickView.type} data={quickView.data} />
            </div>
          )}

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

          {/* 引用来源 */}
          {!isUser && <SourcesCard sources={sources || []} />}
        </div>

        {/* SQL 展示（仅 assistant 消息） */}
        {!isUser && sql && (
          <details className="mt-2 ml-2">
            <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              查看 SQL
            </summary>
            <div className="mt-1 relative">
              <pre className="bg-gray-50 p-3 pr-10 rounded-lg overflow-x-auto text-xs font-mono text-gray-700 border border-gray-200">
                <code className="language-sql">{sql}</code>
              </pre>
              <div className="absolute top-1.5 right-1.5">
                <CopyButton text={sql} />
              </div>
            </div>
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
