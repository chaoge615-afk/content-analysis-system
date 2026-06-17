import { useState, useEffect, useRef } from 'react';
import {
  triggerMonitor,
  getTriggerStatus,
  getUpList,
  saveCookie,
  deleteCookie,
  testCookie,
  TriggerStatusResponse,
  UpInfo,
} from '../services/api';
import UpManager from './UpManager';

export default function MonitorTrigger() {
  const [status, setStatus] = useState<TriggerStatusResponse | null>(null);
  const [maxVideos, setMaxVideos] = useState('');
  const [selectedUps, setSelectedUps] = useState<string[]>([]);
  const [upList, setUpList] = useState<UpInfo[]>([]);
  const [upListLoading, setUpListLoading] = useState(true);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [fullScan, setFullScan] = useState(false);
  const [error, setError] = useState('');

  // Cookie 管理
  const [cookieOpen, setCookieOpen] = useState(false);
  const [cookieInput, setCookieInput] = useState('');
  const [cookieSaving, setCookieSaving] = useState(false);
  const [cookieMsg, setCookieMsg] = useState('');
  const [cookieMsgType, setCookieMsgType] = useState<'ok' | 'err'>('ok');
  const [cookieTesting, setCookieTesting] = useState(false);
  const [cookieTestResult, setCookieTestResult] = useState<{
    valid: boolean;
    message?: string;
    error?: string;
    uname?: string;
  } | null>(null);

  const logEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 加载 UP主 列表（可被 UpManager 触发刷新）
  const fetchUpList = () => {
    setUpListLoading(true);
    getUpList()
      .then((list) => {
        setUpList(list);
        // 清理已不存在的选中项
        const validNames = new Set(list.map((u) => u.name));
        setSelectedUps((prev) => prev.filter((n) => validNames.has(n)));
      })
      .catch(() => setUpList([]))
      .finally(() => setUpListLoading(false));
  };

  useEffect(() => { fetchUpList(); }, []);

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

  // Cookie 未配置时自动展开
  useEffect(() => {
    if (status && status.cookie_ok === false && !cookieOpen) {
      setCookieOpen(true);
    }
  }, [status?.cookie_ok]);

  const fetchStatus = async () => {
    const data = await getTriggerStatus();
    setStatus(data);
  };

  const toggleUp = (name: string) => {
    setSelectedUps((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const handleSaveCookie = async () => {
    if (!cookieInput.trim()) {
      setCookieMsg('请输入 Cookie 内容');
      setCookieMsgType('err');
      return;
    }
    setCookieSaving(true);
    setCookieMsg('');
    const result = await saveCookie(cookieInput);
    if (result.success) {
      setCookieMsg(result.message || 'Cookie 已保存');
      setCookieMsgType('ok');
      setCookieInput('');
      setCookieTestResult(null);  // 清除旧的测试结果（可能已过期）
      fetchStatus();
    } else {
      setCookieMsg(result.error || '保存失败');
      setCookieMsgType('err');
    }
    setCookieSaving(false);
  };

  const handleDeleteCookie = async () => {
    setCookieSaving(true);
    const result = await deleteCookie();
    if (result.success) {
      setCookieMsg(result.message || 'Cookie 已删除');
      setCookieMsgType('ok');
      setCookieTestResult(null);
      fetchStatus();
    } else {
      setCookieMsg(result.error || '删除失败');
      setCookieMsgType('err');
    }
    setCookieSaving(false);
  };

  const handleTestCookie = async () => {
    setCookieTesting(true);
    setCookieTestResult(null);
    const result = await testCookie();
    if (result.success) {
      setCookieTestResult({
        valid: result.valid ?? false,
        message: result.message,
        error: result.error,
        uname: result.uname,
      });
    } else {
      setCookieTestResult({
        valid: false,
        error: result.error || '测试请求失败',
      });
    }
    setCookieTesting(false);
    // 测试完成后刷新状态，更新 Cookie 状态指示器（绿/红）
    fetchStatus();
  };

  const handleTrigger = async () => {
    setTriggering(true);
    setError('');
    const params: Record<string, any> = {};
    if (maxVideos) params.max_videos = parseInt(maxVideos, 10);
    if (selectedUps.length > 0) params.up_names = selectedUps;
    if (fullScan) params.full_scan = true;

    const result = await triggerMonitor(params);
    if (!result.success) {
      setError(result.error || '触发失败');
    }
    setTriggering(false);
    fetchStatus();
  };

  const isRunning = status?.status === 'running';
  const task = status?.task;

  // Cookie 状态：测试结果为"过期"时覆盖后端判断（后端只检查文件存在，不检查是否过期）
  const cookieEffectiveOk = cookieTestResult
    ? cookieTestResult.valid
    : (status?.cookie_ok ?? false);

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

      {/* Docker 不可用提示 */}
      {status && !status.docker_available && (
        <div className="text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded">
          Docker 不可用，请确认 Docker socket 已正确挂载
        </div>
      )}

      {/* Cookie 管理区域 */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <button
          onClick={() => setCookieOpen(!cookieOpen)}
          className="w-full px-3 py-2 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                cookieEffectiveOk ? 'bg-green-400' : 'bg-red-400'
              }`}
            />
            <span className="text-sm font-medium text-gray-700">
              Cookie 设置
            </span>
            {cookieEffectiveOk && (
              <span className="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                已配置
              </span>
            )}
            {!cookieEffectiveOk && status?.cookie_ok && (
              <span className="text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                已过期
              </span>
            )}
            {!cookieEffectiveOk && !status?.cookie_ok && (
              <span className="text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                未配置
              </span>
            )}
          </div>
          <span className="text-gray-400 text-xs">{cookieOpen ? '收起' : '展开'}</span>
        </button>

        {cookieOpen && (
          <div className="px-3 py-3 space-y-2 border-t border-gray-200">
            {/* Cookie 状态描述 */}
            {status?.cookie_message && (
              <div
                className={`text-xs px-2 py-1.5 rounded ${
                  status.cookie_ok
                    ? 'text-green-700 bg-green-50'
                    : 'text-red-700 bg-red-50'
                }`}
              >
                {status.cookie_message}
              </div>
            )}

            {/* Cookie 输入 */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs text-gray-500">
                  粘贴 B站 Cookie（Netscape 格式）
                </label>
                <button
                  onClick={() =>
                    window.open(
                      'https://www.bilibili.com',
                      '_blank'
                    )
                  }
                  className="text-xs text-blue-500 hover:text-blue-700"
                >
                  打开 B站 ↗
                </button>
              </div>
              <textarea
                value={cookieInput}
                onChange={(e) => setCookieInput(e.target.value)}
                placeholder={"从浏览器开发者工具 → Application → Cookies → 导出 Netscape 格式\n或直接粘贴包含 SESSDATA、bili_jct 等字段的 Cookie 内容"}
                rows={5}
                className="w-full px-2.5 py-1.5 border border-gray-200 rounded text-xs font-mono
                           focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
              />
              <div className="text-xs text-gray-400 mt-0.5">
                获取方式：B站页面 → F12 → Application → Cookies → 用浏览器插件导出 Netscape 格式
              </div>
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleSaveCookie}
                disabled={cookieSaving || !cookieInput.trim()}
                className="px-3 py-1.5 bg-blue-600 text-white rounded text-xs font-medium
                           hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
                           transition-colors"
              >
                {cookieSaving ? '保存中...' : '保存 Cookie'}
              </button>
              {status?.cookie_ok && status?.cookie_source === 'file' && (
                <>
                  <button
                    onClick={handleTestCookie}
                    disabled={cookieTesting}
                    className="px-3 py-1.5 bg-green-600 text-white rounded text-xs font-medium
                               hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed
                               transition-colors"
                  >
                    {cookieTesting ? '测试中...' : '测试 Cookie'}
                  </button>
                  <button
                    onClick={handleDeleteCookie}
                    disabled={cookieSaving}
                    className="px-3 py-1.5 border border-red-300 text-red-600 rounded text-xs
                               hover:bg-red-50 disabled:opacity-50 transition-colors"
                  >
                    删除已保存的 Cookie
                  </button>
                </>
              )}
            </div>

            {/* 测试结果 */}
            {cookieTestResult && (
              <div
                className={`text-xs px-2 py-1.5 rounded ${
                  cookieTestResult.valid
                    ? 'text-green-700 bg-green-50'
                    : 'text-red-700 bg-red-50'
                }`}
              >
                {cookieTestResult.valid && cookieTestResult.uname && (
                  <span>✓ 登录用户: {cookieTestResult.uname}</span>
                )}
                {cookieTestResult.valid && !cookieTestResult.uname && (
                  <span>✓ {cookieTestResult.message || 'Cookie 有效'}</span>
                )}
                {!cookieTestResult.valid && (
                  <span>✗ {cookieTestResult.error || cookieTestResult.message || 'Cookie 无效'}</span>
                )}
              </div>
            )}

            {/* 操作反馈 */}
            {cookieMsg && (
              <div
                className={`text-xs px-2 py-1.5 rounded ${
                  cookieMsgType === 'ok'
                    ? 'text-green-700 bg-green-50'
                    : 'text-red-700 bg-red-50'
                }`}
              >
                {cookieMsg}
              </div>
            )}
          </div>
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
                      setSelectedUps([]);
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
            disabled={isRunning || triggering || !status?.docker_available || !cookieEffectiveOk}
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
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={fullScan}
              onChange={(e) => setFullScan(e.target.checked)}
              disabled={isRunning}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-xs text-gray-600">全量扫描（拉取所有历史视频）</span>
          </label>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
          {error}
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

      {/* UP主管理 */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <UpManager onChanged={fetchUpList} />
      </div>
    </div>
  );
}
