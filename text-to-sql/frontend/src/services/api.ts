import axios from 'axios';

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
