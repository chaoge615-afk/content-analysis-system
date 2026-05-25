import axios from 'axios';

// ============ Router Agent 接口 ============

export interface ChatResponse {
  answer: string;
  route_type: string;       // "structured" | "semantic" | "hybrid"
  sql?: string;
  sql_result?: any[];
  sources?: any[];
  reasoning?: string;
  response_time?: number;
}

export interface SystemStatus {
  router: string;
  text_to_sql: string;
  rag: string;
  sql_url: string;
  rag_url: string;
}

export interface TriggerParams {
  max_videos?: number;
  up_names?: string[];
}

export interface UpInfo {
  uid: string;
  name: string;
  total_videos: number;
  last_update?: string | null;
}

export interface TriggerTask {
  status: string;           // "running" | "completed" | "failed"
  container_id?: string;
  container_name?: string;
  started_at?: string;
  finished_at?: string | null;
  error?: string | null;
  logs?: string[];
  exit_code?: number;
  params?: TriggerParams;
}

export interface TriggerStatusResponse {
  status: string;           // "idle" | "running" | "completed" | "failed"
  task: TriggerTask | null;
  docker_available: boolean;
  cookie_ok?: boolean;
  cookie_message?: string;
  cookie_source?: string;   // "file" | "env_file" | "env_content" | "env" | "none"
}

export interface QueryLogItem {
  id: number;
  question: string;
  route_type: string;
  response_time: number;
  created_at: string;
}

export interface QueryLogPage {
  items: QueryLogItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface QueryStatsResponse {
  success: boolean;
  stats: {
    total_queries: number;
    by_route_type: Record<string, number>;
    avg_response_time: number;
  };
  queries: QueryLogPage;
}

export interface ContainerMetric {
  name: string;
  status: string;
  image: string;
  memory_usage: number;
  memory_limit: number;
  memory_percent: number;
  cpu_percent: number;
  ports: string[];
}

export interface SystemMetricsResponse {
  uptime: string;
  containers: Record<string, ContainerMetric>;
  rag_stats: any;
  sql_stats: any;
  query_stats: {
    total_queries: number;
    by_route_type: Record<string, number>;
    avg_response_time: number;
  };
}

// 保留旧接口向后兼容
export interface QueryResult {
  success: boolean;
  sql?: string;
  result?: any[];
  answer?: string;
  error?: string;
  iterations?: number;
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/',
  timeout: 120000,
});

// ============ Router Agent API ============

/** 统一问答（对接 Router Agent） */
export async function chat(
  question: string,
  forceRoute?: string
): Promise<ChatResponse> {
  try {
    const response = await api.post<ChatResponse>('/api/chat', {
      question,
      force_route: forceRoute || null,
    });
    return response.data;
  } catch (error: any) {
    return {
      answer: `请求失败: ${error.message || '网络错误'}`,
      route_type: 'error',
    };
  }
}

/** 获取系统状态 */
export async function getStatus(): Promise<SystemStatus | null> {
  try {
    const response = await api.get<SystemStatus>('/api/status');
    return response.data;
  } catch {
    return null;
  }
}

/** 获取 UP 主列表 */
export async function getUpList(): Promise<UpInfo[]> {
  try {
    const response = await api.get('/api/up_list');
    return response.data?.data || [];
  } catch {
    return [];
  }
}

/** 获取最近采集视频 */
export async function getRecent(): Promise<any[]> {
  try {
    const response = await api.get('/api/recent');
    return response.data?.data || [];
  } catch {
    return [];
  }
}

/** 获取分类列表 */
export async function getCategories(): Promise<any[]> {
  try {
    const response = await api.get('/api/categories');
    return response.data?.data || [];
  } catch {
    return [];
  }
}

// ============ 采集触发 API ============

/** 触发 bilibili-monitor 采集 */
export async function triggerMonitor(params?: TriggerParams): Promise<any> {
  try {
    const response = await api.post('/api/trigger_monitor', params || {});
    return response.data;
  } catch (error: any) {
    return { success: false, error: error.message || '请求失败' };
  }
}

/** 获取采集任务状态 */
export async function getTriggerStatus(): Promise<TriggerStatusResponse> {
  try {
    const response = await api.get<TriggerStatusResponse>('/api/trigger_status');
    return response.data;
  } catch {
    return { status: 'idle', task: null, docker_available: false };
  }
}

// ============ 查询日志 API ============

/** 获取查询统计（分页） */
export async function getQueryStats(
  page: number = 1,
  pageSize: number = 20,
  routeType?: string
): Promise<QueryStatsResponse | null> {
  try {
    const params: Record<string, any> = { page, page_size: pageSize };
    if (routeType) params.route_type = routeType;
    const response = await api.get<QueryStatsResponse>('/api/query_stats', { params });
    return response.data;
  } catch {
    return null;
  }
}

// ============ 系统监控 API ============

/** 获取系统指标 */
export async function getSystemMetrics(): Promise<SystemMetricsResponse | null> {
  try {
    const response = await api.get<SystemMetricsResponse>('/api/system_metrics');
    return response.data;
  } catch {
    return null;
  }
}

// ============ Cookie 管理 API ============

/** Cookie 状态响应 */
export interface CookieStatusResponse {
  ok: boolean;
  message: string;
  source?: string;
}

/** 获取 Cookie 状态 */
export async function getCookieStatus(): Promise<CookieStatusResponse> {
  try {
    const response = await api.get<CookieStatusResponse>('/api/cookie');
    return response.data;
  } catch {
    return { ok: false, message: '无法获取 Cookie 状态', source: 'none' };
  }
}

/** 保存 Cookie */
export async function saveCookie(content: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const response = await api.post('/api/cookie', { content });
    return response.data;
  } catch (error: any) {
    return { success: false, error: error.message || '请求失败' };
  }
}

/** 删除 Cookie */
export async function deleteCookie(): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const response = await api.delete('/api/cookie');
    return response.data;
  } catch (error: any) {
    return { success: false, error: error.message || '请求失败' };
  }
}

/** 测试 Cookie 有效性 */
export interface CookieTestResult {
  success: boolean;
  valid?: boolean;
  message?: string;
  error?: string;
  uname?: string;
  mid?: string;
  is_login?: boolean;
  code?: number;
}

export async function testCookie(): Promise<CookieTestResult> {
  try {
    const response = await api.post<CookieTestResult>('/api/cookie/test');
    return response.data;
  } catch (error: any) {
    return { success: false, error: error.message || '请求失败' };
  }
}

// ============ 旧接口（向后兼容） ============

export async function query(question: string): Promise<QueryResult> {
  try {
    const response = await api.post<QueryResult>('/query', { question });
    return response.data;
  } catch (error: any) {
    return {
      success: false,
      error: error.message || 'Request failed',
    };
  }
}

export default api;
