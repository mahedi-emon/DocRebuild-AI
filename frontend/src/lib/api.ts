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

export interface JobInfo {
  id: string;
  document_id: string;
  status: JobProgress['status'];
  current_stage: string | null;
  progress: number;
  stage_details: JobProgress['stage_details'];
  created_at: string;
}

export interface JobStartOptions {
  dpi: number;
  enable_vision_validation: boolean;
  enable_self_correction: boolean;
  enable_bangla_validation: boolean;
  ocr_engines?: string[];
}

export interface JobEvent {
  type: 'progress' | 'completed' | 'failed' | string;
  job_id?: string;
  status?: JobProgress['status'];
  current_stage?: string | null;
  progress?: number;
  elapsed_seconds?: number | null;
  estimated_remaining_seconds?: number | null;
  stage_details?: JobProgress['stage_details'];
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

interface ReportInfo {
  report_type: string;
  data: QAReport;
}

const API_URL = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE;
const WS_URL = import.meta.env.VITE_WS_URL;

// Use relative paths if API_URL is not explicitly set, 
// relying on Vite proxy in dev and Nginx proxy in prod.
const API_BASE = API_URL ? API_URL.replace(/\/$/, '') : '';

async function readApiError(res: Response, fallback: string): Promise<Error> {
  const body = await res.json().catch(() => null) as { detail?: string } | null;
  return new Error(body?.detail || fallback);
}

export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    if (error.message === 'Failed to fetch') {
      return 'Cannot reach backend API. Please make sure the server is running.';
    }
    return error.message;
  }
  return fallback;
}

export const api = {
  health: async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      return res.ok;
    } catch {
      return false;
    }
  },

  getDocuments: async (page = 1, pageSize = 20, status?: string): Promise<{ documents: DocumentInfo[]; total: number }> => {
    let url = `${API_BASE}/api/documents?page=${page}&page_size=${pageSize}`;
    if (status) url += `&status=${status}`;
    const res = await fetch(url);
    if (!res.ok) throw await readApiError(res, 'Failed to fetch documents');
    return res.json();
  },

  getDocument: async (id: string): Promise<DocumentInfo> => {
    const res = await fetch(`${API_BASE}/api/documents/${id}`);
    if (!res.ok) throw await readApiError(res, 'Failed to fetch document details');
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
      throw await readApiError(res, 'Failed to upload document');
    }
    return res.json();
  },

  deleteDocument: async (id: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/api/documents/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw await readApiError(res, 'Failed to delete document');
  },

  startJob: async (documentId: string, options: JobStartOptions): Promise<{ id: string; status: string }> => {
    const res = await fetch(`${API_BASE}/api/jobs/start/${documentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options),
    });
    if (!res.ok) {
      throw await readApiError(res, 'Failed to start job');
    }
    return res.json();
  },

  getJobProgress: async (jobId: string): Promise<JobProgress> => {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}/progress`);
    if (!res.ok) throw await readApiError(res, 'Failed to get job progress');
    return res.json();
  },

  getDocumentJobs: async (documentId: string): Promise<JobInfo[]> => {
    const res = await fetch(`${API_BASE}/api/jobs/document/${documentId}`);
    if (!res.ok) throw await readApiError(res, 'Failed to fetch jobs for document');
    return res.json();
  },

  cancelJob: async (jobId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
    if (!res.ok) throw await readApiError(res, 'Failed to cancel job');
  },

  getReport: async (documentId: string): Promise<QAReport> => {
    const res = await fetch(`${API_BASE}/api/reports/${documentId}`);
    if (!res.ok) throw await readApiError(res, 'Failed to fetch QA report');
    // Reports API returns a list of reports, find the 'qa' type
    const data = await res.json() as { reports?: ReportInfo[] };
    const reports = data.reports || [];
    const qaReport = reports.find((r) => r.report_type === 'qa');
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

export function connectJobProgressWS(jobId: string, onMessage: (data: JobEvent) => void): WebSocket {
  const ws_protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // Use relative path equivalent for websockets by constructing from window.location
  const defaultWsBase = `${ws_protocol}//${window.location.host}`;
  const wsBase = WS_URL ? WS_URL.replace(/\/$/, '') : defaultWsBase;
  const ws = new WebSocket(`${wsBase}/ws/jobs/${jobId}`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as JobEvent;
      onMessage(data);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  };
  ws.onerror = (err) => {
    console.error('WebSocket error:', err);
  };
  return ws;
}
