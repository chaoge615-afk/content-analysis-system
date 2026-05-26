import { useState, useEffect, useRef } from 'react';
import {
  checkGpu,
  triggerGpuTranscribe,
  GpuStatusResponse,
} from '../services/api';

export default function GpuTranscribe() {
  const [gpuStatus, setGpuStatus] = useState<GpuStatusResponse | null>(null);
  const [checking, setChecking] = useState(true);
  const [downloadsDir, setDownloadsDir] = useState('D:\\sync\\downloads');
  const [transcriptsDir, setTranscriptsDir] = useState('D:\\sync\\transcripts');
  const [modelSize, setModelSize] = useState('small');
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState('');

  const logRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 初始检测 GPU
  useEffect(() => {
    fetchStatus();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // 运行中自动轮询
  const isRunning = gpuStatus?.task?.status === 'running';
  useEffect(() => {
    if (isRunning) {
      pollRef.current = setInterval(fetchStatus, 3000);
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [isRunning]);

  // 日志自动滚动
  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [gpuStatus?.task?.logs?.length]);

  const fetchStatus = async () => {
    const status = await checkGpu();
    setGpuStatus(status);
    setChecking(false);
  };

  const handleTrigger = async () => {
    if (!downloadsDir || !transcriptsDir) {
      setError('请填写 downloads 和 transcripts 目录路径');
      return;
    }
    setError('');
    setTriggering(true);
    try {
      const result = await triggerGpuTranscribe(downloadsDir, transcriptsDir, modelSize);
      if (!result.success) {
        setError(result.error || '启动失败');
      } else {
        await fetchStatus();  // 立即刷新状态
      }
    } catch (e: any) {
      setError(e.message || '请求失败');
    } finally {
      setTriggering(false);
    }
  };

  // ──── 加载中 ────
  if (checking) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex items-center gap-2 text-gray-500">
          <span className="w-4 h-4 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
          正在检测 GPU 服务...
        </div>
      </div>
    );
  }

  // ──── GPU 服务不可达 ────
  if (!gpuStatus) {
    return (
      <div className="max-w-lg mx-auto py-16 text-center">
        <div className="text-4xl mb-4">🖥️</div>
        <h3 className="text-lg font-semibold text-gray-700 mb-2">此功能仅限开发机使用</h3>
        <p className="text-sm text-gray-500 mb-4">
          GPU 转录服务需要 NVIDIA 显卡（RTX 4060），<br />
          请在开发机上启动 GPU 服务后再访问此页面。
        </p>
        <code className="text-xs bg-gray-100 px-3 py-1.5 rounded">
          python bilibili-monitor/scripts/gpu_service.py --port 8011
        </code>
        <button
          onClick={fetchStatus}
          className="block mx-auto mt-4 text-sm text-blue-600 hover:text-blue-800"
        >
          🔄 重新检测
        </button>
      </div>
    );
  }

  // ──── GPU 已连接 ────
  const { gpu, task } = gpuStatus;
  const taskRunning = task?.status === 'running';

  return (
    <div className="space-y-4">
      {/* GPU 信息卡片 */}
      <div className={`p-3 rounded-lg border ${gpu.cuda_available ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'}`}>
        <div className="flex items-center gap-2">
          <span className="text-lg">{gpu.cuda_available ? '✅' : '⚠️'}</span>
          <div>
            <span className="font-medium text-sm">
              {gpu.cuda_available ? gpu.gpu_name : 'GPU 不可用'}
            </span>
            {gpu.gpu_memory_mb && (
              <span className="text-xs text-gray-500 ml-2">{gpu.gpu_memory_mb} MB</span>
            )}
          </div>
        </div>
        {gpu.torch_version && (
          <div className="text-xs text-gray-400 mt-1">PyTorch {gpu.torch_version}</div>
        )}
        {gpu.error && (
          <div className="text-xs text-red-500 mt-1">{gpu.error}</div>
        )}
      </div>

      {/* 配置区域 */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">downloads 目录</label>
          <input
            type="text"
            value={downloadsDir}
            onChange={(e) => setDownloadsDir(e.target.value)}
            placeholder="D:\sync\downloads"
            className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
            disabled={taskRunning}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">transcripts 目录</label>
          <input
            type="text"
            value={transcriptsDir}
            onChange={(e) => setTranscriptsDir(e.target.value)}
            placeholder="D:\sync\transcripts"
            className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
            disabled={taskRunning}
          />
        </div>
      </div>

      {/* 模型选择 + 触发按钮 */}
      <div className="flex items-center gap-3">
        <select
          value={modelSize}
          onChange={(e) => setModelSize(e.target.value)}
          className="px-2.5 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
          disabled={taskRunning}
        >
          <option value="tiny">tiny (最快)</option>
          <option value="base">base</option>
          <option value="small">small (推荐)</option>
          <option value="medium">medium (更高精度)</option>
        </select>

        <button
          onClick={handleTrigger}
          disabled={!gpu.cuda_available || taskRunning || triggering}
          className={`px-4 py-1.5 text-sm font-medium rounded text-white transition-colors ${
            !gpu.cuda_available || taskRunning
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
          }`}
        >
          {triggering ? (
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              启动中...
            </span>
          ) : taskRunning ? (
            '运行中...'
          ) : (
            '🚀 开始GPU转录'
          )}
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">{error}</div>
      )}

      {/* 进度条 */}
      {task && task.status !== 'idle' && (
        <div className="p-3 bg-white border border-gray-200 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">
              {taskRunning ? '⏳ 转录中...' : task.status === 'done' ? '✅ 转录完成' : '❌ 转录异常'}
            </span>
            <span className="text-xs text-gray-400">
              {task.progress && `${task.progress.success || 0}/${task.progress.found || 0}`}
            </span>
          </div>

          {taskRunning && task.progress && task.progress.found > 0 && (
            <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{
                  width: `${((task.progress.success + task.progress.failed) / task.progress.found) * 100}%`,
                }}
              />
            </div>
          )}

          {/* 实时日志 */}
          {task.logs && task.logs.length > 0 && (
            <div
              ref={logRef}
              className="bg-gray-900 text-green-400 text-xs font-mono p-3 rounded max-h-60 overflow-y-auto"
            >
              {task.logs.map((line, i) => (
                <div key={i} className="leading-relaxed">
                  {line}
                </div>
              ))}
            </div>
          )}

          {task.message && task.status !== 'running' && (
            <div className="text-sm text-gray-600 mt-1">{task.message}</div>
          )}
        </div>
      )}

      {/* 重试按钮 */}
      <button
        onClick={fetchStatus}
        className="text-xs text-gray-400 hover:text-gray-600"
      >
        🔄 刷新状态
      </button>
    </div>
  );
}