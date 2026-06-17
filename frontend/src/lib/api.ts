/* DocRebuild AI — API Client */

export interface DocumentInfo {
  id: string;
  filename: string;
  original_filename: string;
  file_path: string;
  output_path: string | null;
  file_size: number;
  file_type: string;
  page_count: number;
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  error_message: string | null;
  overall_confidence: number | null;
  created_at: string;
}

export interface JobProgress {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  current_stage: string | null;
  progress: number;
  elapsed_seconds: number | null;
  estimated_remaining_seconds: number | null;
  stage_details: Record<string, {
    status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
    progress: number;
    started_at: string | null;
    completed_at: string | null;
    error_message: string | null;
  }> | null;
}

export interface QAReport {
  overall_score: number;
  total_pages: number;
  total_issues: number;
  pass_rate: number;
  passed: boolean;
  pages: Array<{
    page_number: number;
    text_similarity: number;
    layout_similarity: number;
    image_similarity: number;
    table_similarity: number;
    equation_similarity: number;
    reading_order_score: number;
    overall_score: number;
    issues: string[];
    pass: boolean;
  }>;
}

const API_HOST = import.meta.env.VITE_API_BASE 
  ? import.meta.env.VITE_API_BASE.replace(/^https?:\/\//, '') 
  : `${window.location.hostname}:8000`;

const API_BASE = `${window.location.protocol}//${API_HOST}`;

export const api = {
  getDocuments: async (page = 1, pageSize = 20, status?: string): Promise<{ documents: DocumentInfo[]; total: number }> => {
    let url = `${API_BASE}/api/documents?page=${page}&page_size=${pageSize}`;
    if (status) url += `&status=${status}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  getDocument: async (id: string): Promise<DocumentInfo> => {
    const res = await fetch(`${API_BASE}/api/documents/${id}`);
    if (!res.ok) throw new Error('Failed to fetch document details');
    return res.json();
  },

  uploadDocument: async (file: File): Promise<DocumentInfo> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to upload document');
    }
    return res.json();
  },

  deleteDocument: async (id: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/api/documents/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete document');
  },

  startJob: async (documentId: string, options: any = {}): Promise<{ id: string; status: string }> => {
    const res = await fetch(`${API_BASE}/api/jobs/start/${documentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to start job');
    }
    return res.json();
  },

  getJobProgress: async (jobId: string): Promise<JobProgress> => {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}/progress`);
    if (!res.ok) throw new Error('Failed to get job progress');
    return res.json();
  },

  cancelJob: async (jobId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to cancel job');
  },

  getReport: async (documentId: string): Promise<QAReport> => {
    const res = await fetch(`${API_BASE}/api/reports/${documentId}`);
    if (!res.ok) throw new Error('Failed to fetch QA report');
    // Reports API returns a list of reports, find the 'qa' type
    const data = await res.json();
    const reports = data.reports || [];
    const qaReport = reports.find((r: any) => r.report_type === 'qa');
    if (!qaReport) throw new Error('QA Report not found');
    return qaReport.data;
  },

  getDownloadUrl: (documentId: string): string => {
    return `${API_BASE}/api/documents/${documentId}/download`;
  },
  
  getStaticUrl: (path: string): string => {
    // Convert relative data path to API static path
    // e.g. ./data/uploads/123/pages/page_0001.png -> http://localhost:8000/static/uploads/...
    if (!path) return '';
    const cleanPath = path.replace(/\\/g, '/');
    if (cleanPath.includes('data/uploads/')) {
      const parts = cleanPath.split('data/uploads/');
      return `${API_BASE}/static/uploads/${parts[parts.length - 1]}`;
    }
    if (cleanPath.includes('data/outputs/')) {
      const parts = cleanPath.split('data/outputs/');
      return `${API_BASE}/static/outputs/${parts[parts.length - 1]}`;
    }
    return `${API_BASE}/${cleanPath}`;
  }
};

export function connectJobProgressWS(jobId: string, onMessage: (data: any) => void): WebSocket {
  const ws_protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${ws_protocol}//${API_HOST}/ws/jobs/${jobId}`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  };
  ws.onerror = (err) => {
    console.error('WebSocket error:', err);
  };
  return ws;
}
