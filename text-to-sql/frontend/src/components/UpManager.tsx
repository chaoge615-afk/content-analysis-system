import { useState, useEffect } from 'react';
import {
  listUps,
  resolveUpUrl,
  addUp,
  removeUp,
  exportUp,
  importUp,
  UpInfoDetailed,
  UpResolveResult,
  UpImportResult,
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

  // 导出/导入状态
  const [exporting, setExporting] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<UpImportResult | null>(null);
  const [importOverwrite, setImportOverwrite] = useState(false);

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

  const handleExport = async (uid: string, name: string) => {
    setExporting(uid);
    setError('');
    try {
      const blob = await exportUp(uid);
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `up_export_${uid}_${name}.zip`;
        a.click();
        URL.revokeObjectURL(url);
        setSuccess(`✅ 已导出 UP主: ${name}`);
        setTimeout(() => setSuccess(''), 3000);
      } else {
        setError('导出失败');
      }
    } catch (e: any) {
      setError(e.message || '导出失败');
    }
    setExporting(null);
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    setImportResult(null);
    setError('');

    try {
      const result = await importUp(file, importOverwrite);
      setImportResult(result);
      if (result.success) {
        setSuccess(`✅ 已导入 UP主: ${result.imported?.name} (${result.imported?.videos_written} 个视频)`);
        fetchUps();
        setTimeout(() => setSuccess(''), 5000);
      } else {
        setError(result.error || '导入失败');
      }
    } catch (err: any) {
      setError(err.message || '导入失败');
    }

    setImporting(false);
    e.target.value = ''; // 重置文件输入
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
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={() => handleExport(up.uid, up.name)}
                  disabled={exporting === up.uid}
                  className="px-2 py-1 text-xs bg-blue-50 text-blue-600 rounded hover:bg-blue-100 disabled:opacity-50"
                  title="导出"
                >
                  {exporting === up.uid ? '...' : '📦'}
                </button>
                <button
                  onClick={() => handleRemove(up.uid, up.name)}
                  className="px-2 py-1 text-xs text-red-600 hover:text-red-800"
                  title="删除"
                >
                  ✕
                </button>
              </div>
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

      {/* 导入 UP主 */}
      <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
        <div className="text-sm font-medium text-gray-700">导入 UP主</div>
        <div className="text-xs text-gray-500">
          从 ZIP 文件导入 UP主 完整数据（配置、视频元数据、向量、转写文本）
        </div>

        <div className="flex items-center gap-3">
          <label className="flex-1">
            <input
              type="file"
              accept=".zip"
              onChange={handleImport}
              disabled={importing}
              className="block w-full text-sm text-gray-500
                file:mr-3 file:py-1.5 file:px-4
                file:rounded file:border-0
                file:text-sm file:font-medium
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100
                disabled:opacity-50"
            />
          </label>
          <label className="flex items-center gap-1.5 text-xs text-gray-600 whitespace-nowrap">
            <input
              type="checkbox"
              checked={importOverwrite}
              onChange={(e) => setImportOverwrite(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            覆盖已有
          </label>
        </div>

        {importing && (
          <div className="text-xs text-blue-600">导入中...</div>
        )}

        {importResult && importResult.success && importResult.imported && (
          <div className="p-2 bg-green-50 border border-green-200 rounded text-xs">
            <div className="font-medium text-green-800">
              {importResult.imported.name} (UID: {importResult.imported.uid})
            </div>
            <div className="text-green-700 mt-1 space-y-0.5">
              <div>视频: {importResult.imported.videos_written} 条</div>
              <div>ChromaDB: {importResult.imported.chromadb_written} 个文档</div>
              <div>转写文件: {importResult.imported.transcripts_written} 个</div>
              {importResult.imported.checkpoints_written > 0 && (
                <div>检查点: {importResult.imported.checkpoints_written} 个</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
