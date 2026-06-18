import { useState, useEffect, useRef } from 'react';
import {
  checkGpu,
  triggerGpuTranscribe,
  getAsrStatus,
  updateAsrSettings,
  triggerAsrTranscribe,
  GpuStatusResponse,
  AsrSettings,
  AsrUsage,
  AsrBudget,
  AsrUsageRecord,
} from '../services/api';

export default function GpuTranscribe() {
  const [gpuStatus, setGpuStatus] = useState<GpuStatusResponse | null>(null);
  const [checking, setChecking] = useState(true);
  const [downloadsDir, setDownloadsDir] = useState('/sync/downloads');
  const [transcriptsDir, setTranscriptsDir] = useState('/sync/transcripts');
  const [modelSize, setModelSize] = useState('small');
  const [device, setDevice] = useState('cuda');
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState('');

  // ASR 状态
  const [asrSettings, setAsrSettings] = useState<AsrSettings | null>(null);
  const [asrUsage, setAsrUsage] = useState<AsrUsage | null>(null);
  const [asrBudget, setAsrBudget] = useState<AsrBudget | null>(null);
  const [asrBudgetInput, setAsrBudgetInput] = useState('');
  const [asrTriggering, setAsrTriggering] = useState(false);
  const [asrMsg, setAsrMsg] = useState('');
  const [asrMsgType, setAsrMsgType] = useState<'ok' | 'err'>('ok');

  const logRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 初始检测 GPU
  useEffect(() => {
    fetchStatus();
    fetchAsrStatus();
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
      const result = await triggerGpuTranscribe(downloadsDir, transcriptsDir, modelSize, device);
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

  // ──── ASR 操作 ────
  const fetchAsrStatus = async () => {
    const data = await getAsrStatus();
    if (data?.success) {
      setAsrSettings(data.data.settings);
      setAsrUsage(data.data.usage);
      setAsrBudget(data.data.budget);
      setAsrBudgetInput(String(data.data.settings.monthly_budget_minutes));
    }
  };

  const handleAsrToggle = async () => {
    if (!asrSettings) return;
    const newEnabled = !asrSettings.enabled;
    const result = await updateAsrSettings({ enabled: newEnabled });
    if (result.success) {
      setAsrMsg(newEnabled ? 'ASR 已开启' : 'ASR 已关闭');
      setAsrMsgType('ok');
      fetchAsrStatus();
    } else {
      setAsrMsg(result.error || '操作失败');
      setAsrMsgType('err');
    }
    setTimeout(() => setAsrMsg(''), 3000);
  };

  const handleBudgetSave = async () => {
    const minutes = parseFloat(asrBudgetInput);
    if (isNaN(minutes) || minutes < 0) {
      setAsrMsg('请输入有效的分钟数');
      setAsrMsgType('err');
    } else {
      const result = await updateAsrSettings({ monthly_budget_minutes: minutes });
      if (result.success) {
        setAsrMsg('预算已更新');
        setAsrMsgType('ok');
        fetchAsrStatus();
      } else {
        setAsrMsg(result.error || '保存失败');
        setAsrMsgType('err');
      }
    }
    setTimeout(() => setAsrMsg(''), 3000);
  };

  const handleAsrTrigger = async () => {
    setAsrTriggering(true);
    setAsrMsg('');
    const result = await triggerAsrTranscribe();
    if (result.success) {
      setAsrMsg('ASR 转写任务已触发');
      setAsrMsgType('ok');
    } else {
      setAsrMsg(result.error || '触发失败');
      setAsrMsgType('err');
    }
    setAsrTriggering(false);
    setTimeout(() => setAsrMsg(''), 5000);
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

  // ──── GPU 已连接 ────

  return (
    <div className="space-y-4">
      {/* ──────────── GPU 转录（开发机） ──────────── */}
      <h3 className="text-sm font-medium text-gray-700">GPU 转录（开发机）</h3>

      {/* GPU 服务不可达 */}
      {!gpuStatus && (
        <div className="max-w-lg mx-auto py-8 text-center">
          <div className="text-4xl mb-4">🖥️</div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">此功能仅限开发机使用</h3>
          <p className="text-sm text-gray-500 mb-4">
            GPU 转录服务需要 NVIDIA 显卡（RTX 4060），<br />
            请确认 docker compose 已启动 gpu-service 容器。
          </p>
          <code className="text-xs bg-gray-100 px-3 py-1.5 rounded">
            docker compose --profile dev --profile gpu up -d gpu-service
          </code>
          <button
            onClick={fetchStatus}
            className="block mx-auto mt-4 text-sm text-blue-600 hover:text-blue-800"
          >
            🔄 重新检测
          </button>
        </div>
      )}

      {/* GPU 已连接 - 显示详细配置 */}
      {gpuStatus && (() => {
        const gpu = gpuStatus.gpu;
        const task = gpuStatus.task;
        const taskRunning = task?.status === 'running';
        return (
        <>
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
                placeholder="/sync/downloads"
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
                placeholder="/sync/transcripts"
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                disabled={taskRunning}
              />
            </div>
          </div>

          {/* 模型选择 + 设备选择 + 触发按钮 */}
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

            <select
              value={device}
              onChange={(e) => setDevice(e.target.value)}
              className="px-2.5 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
              disabled={taskRunning}
            >
              <option value="cuda">CUDA (GPU)</option>
              <option value="cpu">CPU</option>
            </select>

            <button
              onClick={handleTrigger}
              disabled={(device === 'cuda' && !gpu.cuda_available) || taskRunning || triggering}
              className={`px-4 py-1.5 text-sm font-medium rounded text-white transition-colors ${
                (device === 'cuda' && !gpu.cuda_available) || taskRunning
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

          {/* 刷新按钮 */}
          <button
            onClick={fetchStatus}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            🔄 刷新状态
          </button>
        </>
        );
      })()}

      {/* ──────────── 云 ASR 转写（NAS） ──────────── */}
      <div className="mt-6 pt-6 border-t border-gray-200 space-y-4">
        <h3 className="text-sm font-medium text-gray-700">云 ASR 转写（NAS）</h3>

        {/* 模式开关 + 模型说明 */}
        <div className="p-3 bg-white border border-gray-200 rounded-lg space-y-3">
          {/* 开关 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">模式</span>
              <button
                onClick={handleAsrToggle}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  asrSettings?.enabled ? 'bg-blue-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    asrSettings?.enabled ? 'translate-x-5' : ''
                  }`}
                />
              </button>
              <span className={`text-sm font-medium ${asrSettings?.enabled ? 'text-blue-600' : 'text-gray-500'}`}>
                {asrSettings?.enabled ? '已开启' : '已关闭'}
              </span>
            </div>
            <span className="text-xs text-gray-400">
              模型: FunAudioLLM/SenseVoiceSmall（免费）
            </span>
          </div>

          {/* 月度预算 */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 whitespace-nowrap">月度预算</label>
            <input
              type="number"
              value={asrBudgetInput}
              onChange={(e) => setAsrBudgetInput(e.target.value)}
              placeholder="60"
              className="w-20 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
            />
            <span className="text-xs text-gray-400">分钟</span>
            <button
              onClick={handleBudgetSave}
              className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
            >
              保存
            </button>
          </div>

          {/* 用量进度条 */}
          {asrUsage && asrBudget && (
            <div>
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>本月已用</span>
                <span>
                  {asrUsage.total_minutes.toFixed(1)} / {asrBudget.budget_minutes} 分钟
                  {asrBudget.budget_minutes > 0 && (
                    <span className="ml-1 text-gray-400">
                      ({Math.round((asrUsage.total_minutes / asrBudget.budget_minutes) * 100)}%)
                    </span>
                  )}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    asrBudget.ok ? 'bg-blue-500' : 'bg-red-500'
                  }`}
                  style={{
                    width: `${Math.min(
                      asrBudget.budget_minutes > 0
                        ? (asrUsage.total_minutes / asrBudget.budget_minutes) * 100
                        : 0,
                      100
                    )}%`,
                  }}
                />
              </div>
              {!asrBudget.ok && (
                <div className="text-xs text-red-500 mt-1">{asrBudget.message}</div>
              )}
            </div>
          )}

          {/* 手动触发 */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleAsrTrigger}
              disabled={asrTriggering || !asrSettings?.enabled}
              className={`px-4 py-1.5 text-sm font-medium rounded text-white transition-colors ${
                asrTriggering || !asrSettings?.enabled
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-green-600 hover:bg-green-700'
              }`}
            >
              {asrTriggering ? '触发中...' : '▶ 手动触发 ASR 转写'}
            </button>
            <button
              onClick={fetchAsrStatus}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              🔄 刷新用量
            </button>
          </div>

          {/* 操作反馈 */}
          {asrMsg && (
            <div
              className={`text-xs px-2 py-1.5 rounded ${
                asrMsgType === 'ok' ? 'text-green-700 bg-green-50' : 'text-red-700 bg-red-50'
              }`}
            >
              {asrMsg}
            </div>
          )}
        </div>

        {/* 最近转写记录 */}
        {asrUsage && asrUsage.records && asrUsage.records.length > 0 && (
          <div className="p-3 bg-white border border-gray-200 rounded-lg">
            <div className="text-xs text-gray-500 mb-2">最近转写记录（{asrUsage.month}）</div>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {asrUsage.records.slice(0, 10).map((rec: AsrUsageRecord, i: number) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-xs py-1 border-b border-gray-100 last:border-b-0"
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="text-gray-400 whitespace-nowrap">{rec.date}</span>
                    <span className="text-gray-700 truncate">{rec.up_name} - {rec.title}</span>
                  </div>
                  <div className="flex items-center gap-2 ml-2 whitespace-nowrap">
                    <span className="text-gray-400">{rec.duration_minutes.toFixed(1)}分钟</span>
                    <span className="text-green-500">✓</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}