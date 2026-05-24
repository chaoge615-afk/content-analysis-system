import { useState, FormEvent } from 'react';

interface QueryInputProps {
  onSubmit: (question: string) => void;
  loading: boolean;
}

export default function QueryInput({ onSubmit, loading }: QueryInputProps) {
  const [question, setQuestion] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (question.trim() && !loading) {
      onSubmit(question);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="输入你的问题... (例如: 今天我吃了多少蛋白质？)"
        className="w-full p-4 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
        rows={3}
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !question.trim()}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? '处理中...' : '提交'}
      </button>
    </form>
  );
}
