import { useState, useEffect, useRef } from 'react';
import {
  triggerMonitor,
  getTriggerStatus,
  getUpList,
  TriggerStatusResponse,
  UpInfo,
} from '../services/api';

export default function MonitorTrigger() {
  const [status, setStatus] = useState<TriggerStatusResponse | null>(null);
  const [maxVideos, setMaxVideos] = useState('');
  const [selectedUps, setSelectedUps] = useState<string[]>([]);
  const [upList, setUpList] = useState<UpInfo[]>([]);
  const [upListLoading, setUpListLoading] = useState(true);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState('');
  const logEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 加载 UP主 列表
  useEffect(() => {
    setUpListLoading(true);
    getUpList()
      .then((data) => {
        console.log('[MonitorTrigger] UP主列表:', data);
        setUpList(data);
      })
      .catch((err) => {
        console.error('[MonitorTrigger] 加载UP主列表失败:', err);
        setUpList([]);
      })
      .finally(() => setUpListLoading(false));
  }, []);

  useEffect(() => {
    fetchStatus();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // 运行中时自动轮询
  useEffect(() => {
    if (status?.status === 'running') {
      pollRef.current = setInterval(fetchStatus, 5000);
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [status?.status]);

  // 日志自动滚动
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [status?.task?.logs?.length]);

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchStatus = async () => {
    const data = await getTriggerStatus();
    setStatus(data);
  };

  const toggleUp = (name: string) => {
    setSelectedUps((prev) =>
      prev.includes(name)
        ? prev.filter((n) => n !== name)
        : [...prev, name]
    );
  };

  const clearSelection = () => {
    setSelectedUps([]);
  };

  const handleTrigger = async () => {
    setTriggering(true);
    setError('');
    const params: Record<string, any> = {};
    if (maxVideos) params.max_videos = parseInt(maxVideos, 10);
    if (selectedUps.length > 0) params.up_names = selectedUps;

    const result = await triggerMonitor(params);
    if (!result.success) {
      setError(result.error || '触发失败');
    }
    setTriggering(false);
    fetchStatus();
  };

  const isRunning = status?.status === 'running';
  const task = status?.task;

  return (
    <div className="space-y-4">
      {/* 状态指示器 */}
      <div className="flex items-center gap-3">
        <div
          className={`w-3 h-3 rounded-full ${
            isRunning
              ? 'bg-yellow-400 animate-pulse'
              : task?.status === 'completed'
                ? 'bg-green-400'
                : task?.status === 'failed'
                  ? 'bg-red-400'
                  : 'bg-gray-300'
          }`}
        />
        <span className="text-sm font-medium text-gray-700">
          {isRunning
            ? '采集运行中...'
            : task?.status === 'completed'
              ? '上次采集成功'
              : task?.status === 'failed'
                ? '上次采集失败'
                : '空闲'}
        </span>
        {task?.started_at && (
          <span className="text-xs text-gray-400">
            {new Date(task.started_at).toLocaleString('zh-CN')}
          </span>
        )}
      </div>

      {/* 触发参数 */}
      <div className="space-y-3">
        {/* 最大视频数 */}
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">
              最大视频数（可选）
            </label>
            <input
              type="number"
              value={maxVideos}
              onChange={(e) => setMaxVideos(e.target.value)}
              placeholder="不限制"
              disabled={isRunning}
              className="w-full px-2.5 py-1.5 border border-gray-200 rounded text-sm
                         focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
            />
          </div>
        </div>

        {/* UP主多选 */}
        <div className="relative" ref={dropdownRef}>
          <label className="block text-xs text-gray-500 mb-1">
            指定 UP主（可选，不选则全部）
          </label>

          {/* 选中项展示区 */}
          <div
            onClick={() => !isRunning && setDropdownOpen(!dropdownOpen)}
            className={`min-h-[38px] px-2.5 py-1.5 border rounded text-sm flex flex-wrap gap-1.5 items-center cursor-pointer
              ${dropdownOpen ? 'border-blue-400 ring-1 ring-blue-400' : 'border-gray-200'}
              ${isRunning ? 'bg-gray-50 cursor-not-allowed' : 'hover:border-gray-300'}`}
          >
            {selectedUps.length === 0 ? (
              <span className="text-gray-400">全部 UP主</span>
            ) : (
              <>
                {selectedUps.map((name) => (
                  <span
                    key={name}
                    className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs"
                  >
                    {name}
                    {!isRunning && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleUp(name);
                        }}
                        className="hover:text-blue-900 font-bold"
                      >
                        ×
                      </button>
                    )}
                  </span>
                ))}
                {!isRunning && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      clearSelection();
                    }}
                    className="text-xs text-gray-400 hover:text-gray-600 ml-1"
                  >
                    清空
                  </button>
                )}
              </>
            )}
          </div>

          {/* 下拉选项 */}
          {dropdownOpen && !isRunning && (
            <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded shadow-lg max-h-52 overflow-y-auto">
              {upListLoading ? (
                <div className="px-3 py-4 text-sm text-gray-400 text-center">
                  加载中...
                </div>
              ) : upList.length === 0 ? (
                <div className="px-3 py-4 text-sm text-gray-400 text-center">
                  暂无 UP主 数据
                </div>
              ) : (
                upList.map((up) => (
                  <label
                    key={up.uid}
                    className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedUps.includes(up.name)}
                      onChange={() => toggleUp(up.name)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="flex-1">{up.name}</span>
                    <span className="text-xs text-gray-400">
                      {up.total_videos} 个视频
                    </span>
                  </label>
                ))
              )}
            </div>
          )}
        </div>

        {/* 触发按钮 */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleTrigger}
            disabled={isRunning || triggering || !status?.docker_available}
            className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm font-medium
                       hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
                       transition-colors whitespace-nowrap"
          >
            {triggering ? '启动中...' : isRunning ? '运行中' : '开始采集'}
          </button>
          {selectedUps.length > 0 && (
            <span className="text-xs text-gray-500">
              已选 {selectedUps.length} 个 UP主
            </span>
          )}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
          {error}
        </div>
      )}

      {/* Docker 不可用提示 */}
      {status && !status.docker_available && (
        <div className="text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded">
          Docker 不可用，请确认 Docker socket 已正确挂载
        </div>
      )}

      {/* 运行详情 */}
      {task && (
        <div className="space-y-2">
          {/* 元信息 */}
          <div className="flex gap-4 text-xs text-gray-500">
            {task.container_name && (
              <span>容器: {task.container_name}</span>
            )}
            {task.exit_code !== undefined && task.exit_code !== null && (
              <span>
                退出码:{' '}
                <span className={task.exit_code === 0 ? 'text-green-600' : 'text-red-600'}>
                  {task.exit_code}
                </span>
              </span>
            )}
            {task.finished_at && (
              <span>完成于: {new Date(task.finished_at).toLocaleString('zh-CN')}</span>
            )}
          </div>

          {/* 错误信息 */}
          {task.error && (
            <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
              {task.error}
            </div>
          )}

          {/* 日志区域 */}
          {task.logs && task.logs.length > 0 && (
            <div>
              <div className="text-xs text-gray-500 mb-1">运行日志</div>
              <div
                className="bg-gray-900 text-green-400 rounded p-3 text-xs font-mono
                           max-h-64 overflow-y-auto"
              >
                {task.logs.map((line, i) => (
                  <div key={i} className="whitespace-pre-wrap break-all leading-5">
                    {line}
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
