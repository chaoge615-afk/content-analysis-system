import { useState, useRef, useEffect } from 'react';

interface ChatInputProps {
  onSend: (message: string, domain?: string) => void;
  loading: boolean;
}

export default function ChatInput({ onSend, loading }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [domain, setDomain] = useState<string | undefined>(undefined);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动调整 textarea 高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !loading) {
      onSend(input.trim(), domain);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end">
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-gray-500">领域:</span>
          <select
            value={domain || ''}
            onChange={(e) => setDomain(e.target.value || undefined)}
            className="px-2 py-1 text-xs border border-gray-200 rounded bg-white"
          >
            <option value="">全部</option>
            <option value="emotional">情感/两性</option>
            <option value="career">求职/职场</option>
          </select>
        </div>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"
          rows={1}
          disabled={loading}
          className="w-full resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                     disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
      </div>
      <button
        type="submit"
        disabled={!input.trim() || loading}
        className="px-5 py-3 rounded-xl bg-blue-600 text-white font-medium text-sm
                   hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
                   transition-colors whitespace-nowrap"
      >
        {loading ? (
          <span className="flex items-center gap-1">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            处理中
          </span>
        ) : (
          '发送'
        )}
      </button>
    </form>
  );
}
