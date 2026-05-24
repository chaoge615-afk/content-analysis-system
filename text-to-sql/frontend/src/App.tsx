import { useState } from 'react';
import QueryInput from './components/QueryInput';
import ResultTable from './components/ResultTable';
import { query, QueryResult } from './services/api';

function App() {
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (question: string) => {
    setLoading(true);
    setResult(null);

    try {
      const response = await query(question);
      setResult(response);
    } catch (error) {
      setResult({
        success: false,
        error: '网络错误',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Text-to-SQL 查询系统
          </h1>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {/* Query Input Section */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">
            输入问题
          </h2>
          <QueryInput onSubmit={handleSubmit} loading={loading} />
        </section>

        {/* Result Section */}
        {result && (
          <section className="bg-white rounded-lg shadow p-6 space-y-6">
            {/* Status */}
            <div>
              <h2 className="text-lg font-semibold text-gray-700 mb-2">
                结果
              </h2>
              {result.success ? (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                  成功
                </span>
              ) : (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                  失败
                </span>
              )}
            </div>

            {/* SQL */}
            {result.sql && (
              <div>
                <h3 className="text-sm font-medium text-gray-600 mb-2">
                  生成的 SQL
                </h3>
                <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto text-sm font-mono text-gray-800">
                  {result.sql}
                </pre>
              </div>
            )}

            {/* Answer */}
            {result.answer && (
              <div>
                <h3 className="text-sm font-medium text-gray-600 mb-2">
                  回答
                </h3>
                <p className="text-gray-800">{result.answer}</p>
              </div>
            )}

            {/* Table */}
            {result.result && result.result.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-600 mb-2">
                  数据表格
                </h3>
                <ResultTable data={result.result} />
              </div>
            )}

            {/* Error */}
            {result.error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-red-800">{result.error}</p>
              </div>
            )}

            {/* Iterations */}
            {result.iterations && (
              <p className="text-sm text-gray-500">
                迭代次数: {result.iterations}
              </p>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
