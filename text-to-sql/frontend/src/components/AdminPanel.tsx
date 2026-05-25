import { useState } from 'react';
import MonitorTrigger from './MonitorTrigger';
import QueryLog from './QueryLog';
import SystemMetrics from './SystemMetrics';

type AdminTab = 'monitor' | 'query_log' | 'metrics';

const TABS: { key: AdminTab; label: string; icon: string }[] = [
  { key: 'monitor', label: '采集触发', icon: '📡' },
  { key: 'query_log', label: '查询日志', icon: '📋' },
  { key: 'metrics', label: '服务监控', icon: '📊' },
];

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState<AdminTab>('monitor');

  return (
    <div className="h-full flex flex-col">
      {/* 子 Tab 切换 */}
      <div className="flex border-b border-gray-200 mb-4">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 px-3 py-2.5 text-sm font-medium transition-colors border-b-2 ${
              activeTab === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <span className="mr-1.5">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'monitor' && <MonitorTrigger />}
        {activeTab === 'query_log' && <QueryLog />}
        {activeTab === 'metrics' && <SystemMetrics />}
      </div>
    </div>
  );
}
