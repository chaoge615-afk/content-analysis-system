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
export async function getUpList(): Promise<any[]> {
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
