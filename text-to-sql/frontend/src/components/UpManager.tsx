import { useState, useEffect } from 'react';
import {
  listUps,
  resolveUpUrl,
  addUp,
  removeUp,
  UpInfoDetailed,
  UpResolveResult,
} from '../services/api';

export default function UpManager() {
  const [ups, setUps] = useState<UpInfoDetailed[]>([]);
  const [loading, setLoading] = useState(true);
  const [addUrl, setAddUrl] = useState('');
  const [whisperModel, setWhisperModel] = useState('small');
  const [resolving, setResolving] = useState(false);
  const [resolved, setResolved] = useState<UpResolveResult | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchUps();
  }, []);

  const fetchUps = async () => {
    setLoading(true);
    const data = await listUps();
    setUps(data);
    setLoading(false);
  };

  const handleResolve = async () => {
    if (!addUrl.trim()) {
      setError('请输入 B站链接');
      return;
    }
    setError('');
    setResolved(null);
    setResolving(true);

    const result = await resolveUpUrl(addUrl.trim());
    if (result.success) {
      setResolved(result);
    } else {
      setError(result.error || '解析失败');
    }
    setResolving(false);
  };

  const handleAdd = async () => {
    if (!resolved || !resolved.uid) return;

    setAdding(true);
    setError('');
    const result = await addUp(addUrl.trim(), whisperModel);

    if (result.success) {
      setSuccess(`✅ 已添加 UP主: ${resolved.name}`);
      setAddUrl('');
      setResolved(null);
      fetchUps();
      setTimeout(() => setSuccess(''), 3000);
    } else {
      setError(result.error || '添加失败');
    }
    setAdding(false);
  };

  const handleRemove = async (uid: string, name: string) => {
    if (!confirm(`确认删除 UP主 "${name}"？\n（配置文件将被删除，已入库的视频数据保留）`)) {
      return;
    }

    const result = await removeUp(uid);
    if (result.success) {
      setSuccess(`✅ 已删除 UP主: ${name}`);
      fetchUps();
      setTimeout(() => setSuccess(''), 3000);
    } else {
      setError(result.error || '删除失败');
    }
  };

  return (
    <div className="space-y-4">
      {/* 标题 */}
      <h3 className="text-sm font-medium text-gray-700">UP主管理</h3>

      {/* 当前 UP主列表 */}
      {loading ? (
        <div className="text-sm text-gray-500">加载中...</div>
      ) : ups.length === 0 ? (
        <div className="text-sm text-gray-500">暂无 UP主配置</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {ups.map((up) => (
            <div
              key={up.uid}
              className="flex items-center justify-between p-2.5 bg-white border border-gray-200 rounded-lg hover:border-gray-300"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                {up.face ? (
                  <img
                    src={up.face}
                    alt={up.name}
                    className="w-8 h-8 rounded-full flex-shrink-0"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs text-gray-500">{up.name[0]}</span>
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-gray-900 truncate">{up.name}</div>
                  <div className="text-xs text-gray-500">
                    {up.video_count ?? 0} 个视频 · {up.whisper_model}
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleRemove(up.uid, up.name)}
                className="ml-2 text-xs text-red-600 hover:text-red-800 flex-shrink-0"
                title="删除"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 添加新 UP主 */}
      <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
        <div className="text-sm font-medium text-gray-700">添加新 UP主</div>

        <div className="flex gap-2">
          <input
            type="text"
            value={addUrl}
            onChange={(e) => setAddUrl(e.target.value)}
            placeholder="粘贴 B站主页或视频链接"
            className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
            onKeyDown={(e) => e.key === 'Enter' && handleResolve()}
          />
          <select
            value={whisperModel}
            onChange={(e) => setWhisperModel(e.target.value)}
            className="px-2.5 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
          >
            <option value="small">small</option>
            <option value="medium">medium</option>
          </select>
          <button
            onClick={handleResolve}
            disabled={resolving || !addUrl.trim()}
            className={`px-4 py-1.5 text-sm font-medium rounded text-white transition-colors ${
              resolving || !addUrl.trim()
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {resolving ? '解析中...' : '解析'}
          </button>
        </div>

        {/* 解析预览 */}
        {resolved && resolved.success && (
          <div className="p-3 bg-white border border-green-200 rounded">
            <div className="flex items-center gap-3">
              {resolved.face ? (
                <img
                  src={resolved.face}
                  alt={resolved.name}
                  className="w-12 h-12 rounded-full"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="w-12 h-12 rounded-full bg-gray-200 flex items-center justify-center">
                  <span className="text-lg text-gray-500">{resolved.name?.[0]}</span>
                </div>
              )}
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-900">{resolved.name}</div>
                <div className="text-xs text-gray-500">UID: {resolved.uid}</div>
                {resolved.video_title && (
                  <div className="text-xs text-gray-400 mt-0.5">
                    视频: {resolved.video_title}
                  </div>
                )}
              </div>
              <button
                onClick={handleAdd}
                disabled={adding}
                className={`px-4 py-1.5 text-sm font-medium rounded text-white transition-colors ${
                  adding ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700'
                }`}
              >
                {adding ? '添加中...' : '确认添加'}
              </button>
            </div>
          </div>
        )}

        {/* 错误/成功提示 */}
        {error && <div className="text-xs text-red-600">{error}</div>}
        {success && <div className="text-xs text-green-600">{success}</div>}
      </div>
    </div>
  );
}
