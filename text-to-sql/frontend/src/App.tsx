import { useState, useRef, useEffect } from 'react';
import ChatInput from './components/ChatInput';
import ChatMessage from './components/ChatMessage';
import StatusPanel from './components/StatusPanel';
import AdminPanel from './components/AdminPanel';
import { chat, getUpList, getRecent, getCategories, getStatus } from './services/api';

// 消息类型
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  routeType?: string;
  sql?: string;
  sqlResult?: any[];
  reasoning?: string;
  responseTime?: number;
  quickView?: { type: 'status' | 'up_list' | 'recent' | 'categories'; data: any };
  timestamp: Date;
}

type MainTab = 'chat' | 'admin';

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<MainTab>('chat');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // 滚动到最新消息
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 处理发送消息
  const handleSend = async (input: string) => {
    // 添加用户消息
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      // 处理斜杠命令
      if (input.startsWith('/')) {
        const response = await handleSlashCommand(input);
        setMessages((prev) => [...prev, response]);
      } else {
        // 普通问答
        const result = await chat(input);
        const assistantMsg: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: result.answer,
          routeType: result.route_type,
          sql: result.sql,
          sqlResult: result.sql_result,
          reasoning: result.reasoning,
          responseTime: result.response_time,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }
    } catch (error: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `请求失败: ${error.message || '未知错误'}`,
          routeType: 'error',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // 处理斜杠命令
  const handleSlashCommand = async (input: string): Promise<Message> => {
    const parts = input.split(/\s+/);
    const cmd = parts[0].toLowerCase();

    switch (cmd) {
      case '/status': {
        const status = await getStatus();
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content: status
            ? `系统状态: Router ${status.router} · Text-to-SQL ${status.text_to_sql} · RAG ${status.rag}`
            : '无法获取系统状态',
          quickView: { type: 'status', data: status },
          timestamp: new Date(),
        };
      }

      case '/up_list': {
        const data = await getUpList();
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content: data.length > 0 ? `UP主列表 (${data.length} 位)` : '暂无 UP 主数据',
          quickView: { type: 'up_list', data },
          timestamp: new Date(),
        };
      }

      case '/recent': {
        const data = await getRecent();
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content: data.length > 0 ? `最近采集 (${data.length} 个视频)` : '暂无视频数据',
          quickView: { type: 'recent', data },
          timestamp: new Date(),
        };
      }

      case '/categories': {
        const data = await getCategories();
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content: data.length > 0 ? `分类统计 (${data.length} 个分类)` : '暂无分类数据',
          quickView: { type: 'categories', data },
          timestamp: new Date(),
        };
      }

      case '/sql': {
        const question = parts.slice(1).join(' ');
        if (!question) {
          return {
            id: `cmd-${Date.now()}`,
            role: 'assistant',
            content: '用法: /sql [问题]\n示例: /sql 桃姐有几个视频？',
            timestamp: new Date(),
          };
        }
        const result = await chat(question, 'structured');
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content: result.answer,
          routeType: result.route_type,
          sql: result.sql,
          sqlResult: result.sql_result,
          reasoning: '强制走 Text-to-SQL',
          responseTime: result.response_time,
          timestamp: new Date(),
        };
      }

      case '/rag': {
        const question = parts.slice(1).join(' ');
        if (!question) {
          return {
            id: `cmd-${Date.now()}`,
            role: 'assistant',
            content: '用法: /rag [问题]\n示例: /rag 博主们对冷暴力怎么看？',
            timestamp: new Date(),
          };
        }
        const result = await chat(question, 'semantic');
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content: result.answer,
          routeType: result.route_type,
          reasoning: '强制走 RAG',
          responseTime: result.response_time,
          timestamp: new Date(),
        };
      }

      case '/clear': {
        setMessages([]);
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content: '对话已清空',
          timestamp: new Date(),
        };
      }

      case '/help': {
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content:
            '可用命令:\n' +
            '  /status      - 查看系统状态\n' +
            '  /up_list     - 查看 UP 主列表\n' +
            '  /recent      - 查看最近采集视频\n' +
            '  /categories  - 查看分类统计\n' +
            '  /sql [问题]  - 强制走 Text-to-SQL\n' +
            '  /rag [问题]  - 强制走 RAG\n' +
            '  /clear       - 清空对话\n' +
            '  /help        - 显示帮助\n\n' +
            '直接输入问题即可智能问答，系统会自动判断走 SQL 还是 RAG。',
          timestamp: new Date(),
        };
      }

      default: {
        return {
          id: `cmd-${Date.now()}`,
          role: 'assistant',
          content: `未知命令: ${cmd}\n输入 /help 查看可用命令`,
          timestamp: new Date(),
        };
      }
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-gray-800">
            智能内容分析系统
          </h1>
          <span className="text-xs text-gray-400">
            B站视频 · 精炼 · 智能问答
          </span>
        </div>

        {/* 顶部 Tab 切换 */}
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
          <button
            onClick={() => setActiveTab('chat')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'chat'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            对话
          </button>
          <button
            onClick={() => setActiveTab('admin')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'admin'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            管理面板
          </button>
        </div>

        {/* 侧边栏切换（仅对话模式） */}
        {activeTab === 'chat' && (
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="px-3 py-1.5 rounded-lg text-xs text-gray-500 border border-gray-200
                       hover:bg-gray-50 transition-colors"
          >
            {sidebarOpen ? '隐藏面板' : '显示面板'}
          </button>
        )}
        {activeTab === 'admin' && <div className="w-20" />}
      </header>

      {/* Main Content */}
      {activeTab === 'chat' ? (
        <div className="flex flex-1 overflow-hidden">
          {/* Chat Area */}
          <div className="flex-1 flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center space-y-4">
                    <div className="text-4xl">💬</div>
                    <h2 className="text-xl font-semibold text-gray-600">
                      智能内容问答
                    </h2>
                    <p className="text-sm text-gray-400 max-w-md">
                      输入问题，系统会自动判断走结构化查询（SQL）还是语义检索（RAG）。
                      也可以试试右侧的示例问题。
                    </p>
                    <p className="text-xs text-gray-300">
                      输入 /help 查看所有命令
                    </p>
                  </div>
                </div>
              ) : (
                <div className="max-w-3xl mx-auto">
                  {messages.map((msg) => (
                    <ChatMessage
                      key={msg.id}
                      role={msg.role}
                      content={msg.content}
                      routeType={msg.routeType}
                      sql={msg.sql}
                      sqlResult={msg.sqlResult}
                      reasoning={msg.reasoning}
                      responseTime={msg.responseTime}
                      quickView={msg.quickView}
                    />
                  ))}
                  {loading && (
                    <div className="flex justify-start mb-4">
                      <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                        <div className="flex items-center gap-2 text-gray-400 text-sm">
                          <div className="flex gap-1">
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                          </div>
                          <span>思考中...</span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="border-t border-gray-200 bg-white px-4 py-3 shrink-0">
              <div className="max-w-3xl mx-auto">
                <ChatInput onSend={handleSend} loading={loading} />
              </div>
            </div>
          </div>

          {/* Sidebar */}
          {sidebarOpen && (
            <div className="w-64 border-l border-gray-200 bg-gray-50 p-3 overflow-y-auto shrink-0">
              <StatusPanel onQuickQuestion={handleSend} />
            </div>
          )}
        </div>
      ) : (
        /* 管理面板 */
        <div className="flex-1 overflow-hidden">
          <div className="max-w-4xl mx-auto h-full p-6 overflow-y-auto">
            <AdminPanel />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
