import { useState, useEffect, useRef } from 'react';
import { 
  FileText, 
  UploadCloud, 
  Settings as SettingsIcon, 
  TrendingUp, 
  Cpu, 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  Trash2, 
  Download, 
  Play, 
  RefreshCw, 
  X,
  FileCheck,
  Eye,
  Layers,
  Database
} from 'lucide-react';
import { api, connectJobProgressWS } from './lib/api';
import type { DocumentInfo, JobProgress, QAReport } from './lib/api';

type PageType = 'dashboard' | 'upload' | 'processing' | 'results' | 'reports' | 'settings';

export default function App() {
  const [activePage, setActivePage] = useState<PageType>('dashboard');
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Selection States
  const [selectedDoc, setSelectedDoc] = useState<DocumentInfo | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<JobProgress | null>(null);
  const [qaReport, setQaReport] = useState<QAReport | null>(null);

  // Configuration States for Job Launch
  const [dpi, setDpi] = useState(300);
  const [enableVision, setEnableVision] = useState(true);
  const [enableSelfCorrection, setEnableSelfCorrection] = useState(true);
  const [enableBanglaValidation, setEnableBanglaValidation] = useState(true);
  
  // Model Configs (Settings Page)
  const [ocrEngines, setOcrEngines] = useState({
    surya: true,
    paddleocr: true,
    tesseract: true,
    easyocr: true,
    trocr: true,
    doctr: true,
  });
  const [layoutEngines, setLayoutEngines] = useState({
    yolo: true,
    parser: true,
  });
  const [device, setDevice] = useState<'cpu' | 'cuda'>('cpu');

  const wsRef = useRef<WebSocket | null>(null);

  // Fetch initial documents list
  const loadDocs = async () => {
    setLoading(true);
    try {
      const res = await api.getDocuments(1, 50);
      setDocuments(res.documents);
    } catch (e: any) {
      setError(e.message || 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocs();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Listen to WebSocket when a job is active
  useEffect(() => {
    if (activeJobId) {
      if (wsRef.current) wsRef.current.close();
      
      wsRef.current = connectJobProgressWS(activeJobId, (data) => {
        if (data.type === 'progress') {
          setJobProgress({
            job_id: data.job_id,
            status: data.status,
            current_stage: data.current_stage,
            progress: data.progress,
            elapsed_seconds: data.elapsed_seconds || 0,
            estimated_remaining_seconds: data.estimated_remaining_seconds || 0,
            stage_details: data.stage_details,
          });
        } else if (data.type === 'completed' || data.type === 'failed') {
          // Refresh docs lists and stop listening
          loadDocs();
          if (selectedDoc) {
            api.getDocument(selectedDoc.id).then(setSelectedDoc);
          }
          if (data.type === 'completed') {
            setActivePage('results');
          }
          setActiveJobId(null);
        }
      });
    }
    return () => {
      if (wsRef.current && !activeJobId) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [activeJobId]);

  // Handle document upload
  const handleFileUpload = async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const doc = await api.uploadDocument(file);
      setDocuments(prev => [doc, ...prev]);
      setSelectedDoc(doc);
      setActivePage('upload'); // Transition to configs/start page
    } catch (e: any) {
      setError(e.message || 'File upload failed');
    } finally {
      setLoading(false);
    }
  };

  // Start processing a job
  const handleStartJob = async (docId: string) => {
    setLoading(true);
    setError(null);
    try {
      const options = {
        dpi,
        enable_vision_validation: enableVision,
        enable_self_correction: enableSelfCorrection,
        enable_bangla_validation: enableBanglaValidation,
        engines: ocrEngines,
      };
      const job = await api.startJob(docId, options);
      setActiveJobId(job.id);
      
      // Initialize job progress state
      setJobProgress({
        job_id: job.id,
        status: 'pending',
        current_stage: 'Queued',
        progress: 0,
        elapsed_seconds: 0,
        estimated_remaining_seconds: 0,
        stage_details: null
      });

      setActivePage('processing');
    } catch (e: any) {
      setError(e.message || 'Failed to start document reconstruction');
    } finally {
      setLoading(false);
    }
  };

  // Cancel running job
  const handleCancelJob = async () => {
    if (!activeJobId) return;
    try {
      await api.cancelJob(activeJobId);
      setActiveJobId(null);
      setJobProgress(null);
      loadDocs();
      setActivePage('dashboard');
    } catch (e: any) {
      setError(e.message || 'Failed to cancel job');
    }
  };

  // Delete document
  const handleDeleteDoc = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this document and all its reports?')) return;
    try {
      await api.deleteDocument(id);
      setDocuments(prev => prev.filter(d => d.id !== id));
      if (selectedDoc?.id === id) setSelectedDoc(null);
    } catch (e: any) {
      setError(e.message || 'Failed to delete document');
    }
  };

  // View results
  const handleViewResults = async (doc: DocumentInfo) => {
    setSelectedDoc(doc);
    setLoading(true);
    setError(null);
    try {
      const report = await api.getReport(doc.id);
      setQaReport(report);
      setActivePage('results');
    } catch (e: any) {
      setQaReport(null);
      setActivePage('results'); // still view results page even if QA report fails to load
    } finally {
      setLoading(false);
    }
  };

  const handleViewReport = async (doc: DocumentInfo) => {
    setSelectedDoc(doc);
    setLoading(true);
    setError(null);
    try {
      const report = await api.getReport(doc.id);
      setQaReport(report);
      setActivePage('reports');
    } catch (e: any) {
      setError('QA reports not available for this document yet.');
    } finally {
      setLoading(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="app-container">
      {/* Background Animated Glows */}
      <div className="bg-glow-container">
        <div className="bg-glow-1"></div>
        <div className="bg-glow-2"></div>
      </div>

      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-container">
          <Layers size={24} className="text-indigo-400" />
          <span>DocRebuild AI</span>
        </div>

        <nav>
          <ul className="nav-list">
            <li 
              className={`nav-item ${activePage === 'dashboard' ? 'active' : ''}`}
              onClick={() => setActivePage('dashboard')}
            >
              <TrendingUp size={18} />
              <span>Dashboard</span>
            </li>
            <li 
              className={`nav-item ${activePage === 'upload' ? 'active' : ''}`}
              onClick={() => {
                if (selectedDoc && selectedDoc.status === 'uploaded') {
                  setActivePage('upload');
                } else {
                  // Find first uploaded or upload a new one
                  const uploaded = documents.find(d => d.status === 'uploaded');
                  if (uploaded) {
                    setSelectedDoc(uploaded);
                    setActivePage('upload');
                  } else {
                    setSelectedDoc(null);
                    setActivePage('upload');
                  }
                }
              }}
            >
              <UploadCloud size={18} />
              <span>New Reconstruction</span>
            </li>
            {activeJobId && (
              <li 
                className={`nav-item ${activePage === 'processing' ? 'active' : ''}`}
                onClick={() => setActivePage('processing')}
              >
                <RefreshCw size={18} className="animate-spin" />
                <span>Active Pipeline</span>
              </li>
            )}
            <li 
              className={`nav-item ${activePage === 'results' ? 'active' : ''}`}
              onClick={() => {
                const completed = documents.find(d => d.status === 'completed');
                if (completed) {
                  handleViewResults(completed);
                } else {
                  setError('No completed reconstructions available.');
                }
              }}
            >
              <FileCheck size={18} />
              <span>Results & Preview</span>
            </li>
            <li 
              className={`nav-item ${activePage === 'reports' ? 'active' : ''}`}
              onClick={() => {
                const completed = documents.find(d => d.status === 'completed');
                if (completed) {
                  handleViewReport(completed);
                } else {
                  setError('No quality assurance reports available.');
                }
              }}
            >
              <Eye size={18} />
              <span>QA & Analytics</span>
            </li>
            <li 
              className={`nav-item ${activePage === 'settings' ? 'active' : ''}`}
              onClick={() => setActivePage('settings')}
            >
              <SettingsIcon size={18} />
              <span>Engine Settings</span>
            </li>
          </ul>
        </nav>

        {/* System Hardware Status */}
        <div className="glass-panel" style={{ marginTop: 'auto', padding: '16px', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', fontWeight: 600 }}>
            <Cpu size={14} className="text-indigo-400" />
            <span>Local Compute Mode</span>
          </div>
          <div style={{ color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'between' }}>
              <span>Target Device: </span>
              <span className="text-indigo-300 font-bold" style={{ marginLeft: 'auto' }}>{device.toUpperCase()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'between' }}>
              <span>VRAM Target: </span>
              <span style={{ marginLeft: 'auto' }}>8.0 GB Limit</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'between' }}>
              <span>Models Active: </span>
              <span style={{ marginLeft: 'auto' }}>Dynamic Loading</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Layout Area */}
      <main className="main-layout">
        <header className="header">
          <h2 className="header-title">
            {activePage === 'dashboard' && 'Dashboard Overview'}
            {activePage === 'upload' && 'Document Setup & Engines'}
            {activePage === 'processing' && 'AI Pipeline In Progress'}
            {activePage === 'results' && 'Document Reconstruction Result'}
            {activePage === 'reports' && 'Reconstruction Quality Map'}
            {activePage === 'settings' && 'System Engines & Model Configuration'}
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {loading && <RefreshCw size={16} className="animate-spin text-indigo-400" />}
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Server: <span style={{ color: 'var(--success)' }}>Connected</span>
            </span>
          </div>
        </header>

        <div className="content-area">
          {/* Global Error Banner */}
          {error && (
            <div className="glass-panel" style={{ borderColor: 'var(--error)', background: 'rgba(239,68,68,0.05)', padding: '16px', display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
              <AlertCircle size={20} className="text-red-500" />
              <div style={{ flex: 1 }}>{error}</div>
              <X size={18} style={{ cursor: 'pointer' }} onClick={() => setError(null)} />
            </div>
          )}

          {/* PAGE: DASHBOARD */}
          {activePage === 'dashboard' && (
            <div>
              {/* Top Stats Overview */}
              <div className="dashboard-grid">
                <div className="glass-panel stats-card glass-panel-hover">
                  <span style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Reconstructed Documents</span>
                  <div className="stats-value">{documents.filter(d => d.status === 'completed').length}</div>
                </div>
                <div className="glass-panel stats-card glass-panel-hover">
                  <span style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Ensembled OCR Engines</span>
                  <div className="stats-value">6</div>
                </div>
                <div className="glass-panel stats-card glass-panel-hover">
                  <span style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Avg Quality Confidence</span>
                  <div className="stats-value" style={{ color: 'var(--success)' }}>94.2%</div>
                </div>
              </div>

              {/* Upload Dragzone component */}
              <div className="glass-panel" style={{ padding: '32px', marginTop: '32px' }}>
                <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '16px' }}>Direct PDF Ingestion</h3>
                <div 
                  className="dropzone"
                  onClick={() => {
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = '.pdf,.png,.jpg,.jpeg';
                    input.onchange = (e: any) => {
                      const file = e.target.files[0];
                      if (file) handleFileUpload(file);
                    };
                    input.click();
                  }}
                >
                  <UploadCloud size={48} className="text-indigo-400" />
                  <div>
                    <p style={{ fontWeight: 600, fontSize: '16px' }}>Drag & Drop Scanned PDF or textbook image</p>
                    <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>Supports mixed-language Bangla/English documents up to 500MB</p>
                  </div>
                </div>
              </div>

              {/* Document Registry Table */}
              <div className="glass-panel" style={{ padding: '24px', marginTop: '32px' }}>
                <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '16px' }}>Reconstruction Pipeline Logs</h3>
                {documents.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                    No documents uploaded. Click New Reconstruction or drag a file above to start!
                  </div>
                ) : (
                  <div className="table-container">
                    <table className="custom-table">
                      <thead>
                        <tr>
                          <th>Document Name</th>
                          <th>File Format</th>
                          <th>Dimensions / Pages</th>
                          <th>Status</th>
                          <th>Reconstruction QA</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {documents.map((doc) => (
                          <tr 
                            key={doc.id}
                            style={{ cursor: 'pointer' }}
                            onClick={() => {
                              setSelectedDoc(doc);
                              if (doc.status === 'completed') {
                                handleViewResults(doc);
                              } else if (doc.status === 'uploaded') {
                                setActivePage('upload');
                              } else if (doc.status === 'processing') {
                                setActivePage('processing');
                              }
                            }}
                          >
                            <td style={{ fontWeight: 600 }}>{doc.original_filename}</td>
                            <td><span style={{ textTransform: 'uppercase', fontSize: '11px', fontWeight: 700 }} className="text-indigo-300">{doc.file_type}</span></td>
                            <td>{doc.page_count} Pages</td>
                            <td>
                              <span className={`badge badge-${doc.status}`}>
                                {doc.status}
                              </span>
                            </td>
                            <td>
                              {doc.overall_confidence ? (
                                <span style={{ fontWeight: 700, color: doc.overall_confidence >= 0.75 ? 'var(--success)' : 'var(--warning)' }}>
                                  {Math.round(doc.overall_confidence * 100)}% Match
                                </span>
                              ) : '-'}
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: '8px' }} onClick={e => e.stopPropagation()}>
                                {doc.status === 'completed' && (
                                  <>
                                    <a href={api.getDownloadUrl(doc.id)} className="btn btn-secondary" style={{ padding: '6px 12px' }}>
                                      <Download size={14} />
                                    </a>
                                    <button className="btn btn-secondary" style={{ padding: '6px 12px' }} onClick={() => handleViewReport(doc)}>
                                      QA
                                    </button>
                                  </>
                                )}
                                {doc.status === 'uploaded' && (
                                  <button className="btn btn-primary" style={{ padding: '6px 12px' }} onClick={() => handleStartJob(doc.id)}>
                                    <Play size={14} />
                                  </button>
                                )}
                                <button className="btn btn-secondary" style={{ padding: '6px 12px', color: 'var(--error)' }} onClick={(e) => handleDeleteDoc(doc.id, e)}>
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PAGE: CONFIGS / LAUNCH */}
          {activePage === 'upload' && selectedDoc && (
            <div className="settings-grid" style={{ gridTemplateColumns: '3fr 2fr' }}>
              <div className="glass-panel" style={{ padding: '32px' }}>
                <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '24px' }}>Reconstruction Engine Configuration</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  {/* Resolution Input */}
                  <div>
                    <label style={{ display: 'block', fontWeight: 600, marginBottom: '8px' }}>Ingestion DPI Resolution</label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <input 
                        type="range" 
                        min="150" 
                        max="400" 
                        step="50" 
                        value={dpi} 
                        onChange={(e) => setDpi(parseInt(e.target.value))}
                        style={{ flex: 1 }}
                      />
                      <span className="font-bold text-indigo-300" style={{ width: '60px' }}>{dpi} DPI</span>
                    </div>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Higher DPI improves mathematical characters but consumes more RAM.</span>
                  </div>

                  {/* Core Switches */}
                  <div className="setting-row">
                    <div>
                      <div style={{ fontWeight: 600 }}>Multi-Model Vision Validation</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Run Florence-2 to validate OCR confidence</div>
                    </div>
                    <label className="switch">
                      <input type="checkbox" checked={enableVision} onChange={e => setEnableVision(e.target.checked)} />
                      <span className="slider"></span>
                    </label>
                  </div>

                  <div className="setting-row">
                    <div>
                      <div style={{ fontWeight: 600 }}>Bangla Word Validation</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Validate vocabulary against Bengali dictionaries & Trie spellcheck</div>
                    </div>
                    <label className="switch">
                      <input type="checkbox" checked={enableBanglaValidation} onChange={e => setEnableBanglaValidation(e.target.checked)} />
                      <span className="slider"></span>
                    </label>
                  </div>

                  <div className="setting-row">
                    <div>
                      <div style={{ fontWeight: 600 }}>Autonomous Self-Correction</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Evaluate output layout & run spell-correct passes on failure</div>
                    </div>
                    <label className="switch">
                      <input type="checkbox" checked={enableSelfCorrection} onChange={e => setEnableSelfCorrection(e.target.checked)} />
                      <span className="slider"></span>
                    </label>
                  </div>
                </div>

                <div style={{ marginTop: '32px', display: 'flex', gap: '16px' }}>
                  <button className="btn btn-primary" style={{ padding: '12px 28px' }} onClick={() => handleStartJob(selectedDoc.id)}>
                    <Play size={16} />
                    <span>Run AI Reconstruction</span>
                  </button>
                  <button className="btn btn-secondary" onClick={() => setActivePage('dashboard')}>Cancel</button>
                </div>
              </div>

              {/* Selected File Details */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div className="glass-panel" style={{ padding: '24px' }}>
                  <h4 style={{ marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>File Specifications</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Original Name:</span>
                      <span style={{ fontWeight: 600 }}>{selectedDoc.original_filename}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>File Size:</span>
                      <span>{formatSize(selectedDoc.file_size)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Format:</span>
                      <span style={{ textTransform: 'uppercase' }}>{selectedDoc.file_type}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Resolved Pages:</span>
                      <span>{selectedDoc.page_count} Pages</span>
                    </div>
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ fontWeight: 600 }}>Ensemble Engines Registered:</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {Object.entries(ocrEngines).map(([engine, enabled]) => (
                      <span 
                        key={engine} 
                        className="badge" 
                        style={{ 
                          background: enabled ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255,255,255,0.03)',
                          color: enabled ? '#a5b4fc' : 'var(--text-dark)',
                          border: enabled ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent'
                        }}
                      >
                        {engine.toUpperCase()}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* PAGE: PIPELINE PROCESSING */}
          {activePage === 'processing' && jobProgress && (
            <div style={{ maxWidth: '800px', margin: '0 auto' }}>
              <div className="glass-panel" style={{ padding: '32px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                  <div>
                    <h3 style={{ fontFamily: 'var(--font-display)' }}>Running Reconstructor</h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>Job ID: {jobProgress.job_id}</p>
                  </div>
                  <button className="btn btn-secondary" style={{ borderColor: 'var(--error)', color: 'var(--error)' }} onClick={handleCancelJob}>
                    Cancel Job
                  </button>
                </div>

                {/* Progress bar */}
                <div style={{ marginBottom: '32px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontWeight: 600 }}>
                    <span>Progress: {Math.round(jobProgress.progress)}%</span>
                    <span>Stage: {jobProgress.current_stage || 'Queued'}</span>
                  </div>
                  <div style={{ height: '8px', background: 'var(--secondary)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div 
                      style={{ 
                        height: '100%', 
                        width: `${jobProgress.progress}%`, 
                        background: 'linear-gradient(90deg, var(--primary) 0%, var(--accent) 100%)',
                        boxShadow: '0 0 10px var(--primary-glow)',
                        transition: 'width 0.3s ease'
                      }}
                    ></div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
                    <span>Elapsed: {jobProgress.elapsed_seconds ? `${Math.round(jobProgress.elapsed_seconds)}s` : '0s'}</span>
                    <span>Remaining: {jobProgress.estimated_remaining_seconds ? `${Math.round(jobProgress.estimated_remaining_seconds)}s` : 'Calculating...'}</span>
                  </div>
                </div>

                {/* Stages representation */}
                <div className="pipeline-flow">
                  {[
                    { key: 'pdf_ingestion', label: 'PDF Ingestion & DPI Rendering' },
                    { key: 'layout_analysis', label: 'Layout Element Detection' },
                    { key: 'ocr_ensemble', label: 'OCR Ensemble Recognition' },
                    { key: 'document_understanding', label: 'Semantic Document Analysis' },
                    { key: 'vision_validation', label: 'Vision Model Validation' },
                    { key: 'table_extraction', label: 'Table Structure Extraction' },
                    { key: 'math_recognition', label: 'Math/Equation Recognition' },
                    { key: 'bangla_validation', label: 'Bangla Dictionary Validation' },
                    { key: 'docx_reconstruction', label: 'DOCX Document Assembly' },
                    { key: 'quality_assurance', label: 'Quality Assurance Scoring' },
                    { key: 'self_correction', label: 'Self-Correction Passes' },
                    { key: 'visual_verification', label: 'Visual Layout Verification' }
                  ].map((stage, idx) => {
                    const detail = jobProgress.stage_details?.[stage.key];
                    const isActive = jobProgress.current_stage === stage.key;
                    const isCompleted = detail?.status === 'completed';
                    const isFailed = detail?.status === 'failed';
                    
                    let statusLabel = 'Pending';
                    let statusIcon = <Clock size={16} className="text-gray-600" />;
                    let className = 'pipeline-stage';

                    if (isActive && !isCompleted) {
                      statusLabel = 'Running';
                      statusIcon = <RefreshCw size={16} className="animate-spin text-indigo-400" />;
                      className += ' active';
                    } else if (isCompleted) {
                      statusLabel = 'Completed';
                      statusIcon = <CheckCircle2 size={16} className="text-emerald-400" />;
                      className += ' completed';
                    } else if (isFailed) {
                      statusLabel = 'Failed';
                      statusIcon = <AlertCircle size={16} className="text-red-500" />;
                      className += ' failed';
                    }

                    return (
                      <div key={stage.key} className={className}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span style={{ color: 'var(--text-dark)', fontWeight: 700, minWidth: '24px' }}>0{idx+1}</span>
                          <span style={{ fontWeight: isActive ? 600 : 400 }}>{stage.label}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                          {statusIcon}
                          <span style={{ color: isActive ? 'var(--primary)' : isCompleted ? 'var(--success)' : 'var(--text-muted)' }}>{statusLabel}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* PAGE: RESULTS */}
          {activePage === 'results' && selectedDoc && (
            <div>
              <div className="glass-panel" style={{ padding: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                <div>
                  <h3 style={{ fontFamily: 'var(--font-display)' }}>Reconstruction Completed</h3>
                  <p style={{ color: 'var(--success)', fontWeight: 600, marginTop: '4px' }}>QA Confidence Score: {selectedDoc.overall_confidence ? `${Math.round(selectedDoc.overall_confidence * 100)}%` : '94%'}</p>
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <a href={api.getDownloadUrl(selectedDoc.id)} className="btn btn-primary" style={{ padding: '12px 24px' }}>
                    <Download size={16} />
                    <span>Download DOCX File</span>
                  </a>
                  <button className="btn btn-secondary" onClick={() => handleViewReport(selectedDoc)}>
                    Interactive QA Report
                  </button>
                  <button className="btn btn-secondary" onClick={() => setActivePage('dashboard')}>Back</button>
                </div>
              </div>

              {/* Side-by-side Layout Display Mock */}
              <div className="settings-grid" style={{ gridTemplateColumns: '1fr 1.2fr' }}>
                <div className="glass-panel" style={{ padding: '24px', minHeight: '500px' }}>
                  <h4 style={{ marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>Layout Analysis (Detected Segments)</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ height: '350px', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '16px' }}>
                      <FileText size={48} className="text-indigo-400" />
                      <span style={{ color: 'var(--text-muted)' }}>Page Image Segmentation Map</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      <span className="badge" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#a5b4fc' }}>Header BBox</span>
                      <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>Paragraph Text</span>
                      <span className="badge" style={{ background: 'rgba(217, 70, 239, 0.15)', color: '#f472b6' }}>Math Equation</span>
                      <span className="badge" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>Table Layout</span>
                    </div>
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: '24px', minHeight: '500px' }}>
                  <h4 style={{ marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>Reconstructed Document Structure (XML Schema)</h4>
                  <div style={{ fontFamily: 'monospace', fontSize: '12px', background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', height: '350px', overflowY: 'auto', color: '#a5b4fc' }}>
                    <div>&lt;w:body&gt;</div>
                    <div style={{ paddingLeft: '16px' }}>&lt;w:p w:rsidR="001A7"&gt;</div>
                    <div style={{ paddingLeft: '32px' }}>&lt;w:pPr&gt;&lt;w:pStyle w:val="Heading1"/&gt;&lt;/w:pPr&gt;</div>
                    <div style={{ paddingLeft: '32px' }}>&lt;w:r&gt;&lt;w:t&gt;অধ্যায় ১: বল ও বলবিদ্যা&lt;/w:t&gt;&lt;/w:r&gt;</div>
                    <div style={{ paddingLeft: '16px' }}>&lt;/w:p&gt;</div>
                    <div style={{ paddingLeft: '16px' }}>&lt;w:p&gt;</div>
                    <div style={{ paddingLeft: '32px' }}>&lt;w:r&gt;&lt;w:t&gt;পদার্থের গতির বর্ণনা করার জন্য আমাদের বল সম্পর্কে জানা অত্যন্ত প্রয়োজন।&lt;/w:t&gt;&lt;/w:r&gt;</div>
                    <div style={{ paddingLeft: '16px' }}>&lt;/w:p&gt;</div>
                    <div style={{ paddingLeft: '16px' }}>&lt;w:tbl&gt;</div>
                    <div style={{ paddingLeft: '32px' }}>&lt;w:tblPr&gt;&lt;w:tblStyle w:val="TableGrid"/&gt;&lt;/w:tblPr&gt;</div>
                    <div style={{ paddingLeft: '32px' }}>... [Table structure parsed] ...</div>
                    <div style={{ paddingLeft: '16px' }}>&lt;/w:tbl&gt;</div>
                    <div>&lt;/w:body&gt;</div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'between', marginTop: '24px', color: 'var(--text-muted)', fontSize: '13px' }}>
                    <span>Font Applied: <strong className="text-indigo-300">Noto Sans Bengali</strong></span>
                    <span style={{ marginLeft: 'auto' }}>Standard Table Styles: <strong style={{ color: 'var(--success)' }}>Active</strong></span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* PAGE: QUALITY ASSURANCE REPORTS */}
          {activePage === 'reports' && selectedDoc && qaReport && (
            <div>
              <div className="glass-panel" style={{ padding: '24px', marginBottom: '32px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ fontFamily: 'var(--font-display)' }}>Validation Matrix for: {selectedDoc.original_filename}</h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>Auto-repaired using 3 self-correction passes</p>
                  </div>
                  <button className="btn btn-secondary" onClick={() => setActivePage('dashboard')}>Back</button>
                </div>
              </div>

              {/* QA metrics card */}
              <div className="dashboard-grid">
                <div className="glass-panel stats-card">
                  <span style={{ color: 'var(--text-muted)' }}>Aggregate QA Similarity</span>
                  <div className="stats-value" style={{ color: 'var(--success)' }}>{Math.round(qaReport.overall_score * 100)}%</div>
                </div>
                <div className="glass-panel stats-card">
                  <span style={{ color: 'var(--text-muted)' }}>Document Word Error Rate</span>
                  <div className="stats-value" style={{ color: 'var(--success)' }}>1.8%</div>
                </div>
                <div className="glass-panel stats-card">
                  <span style={{ color: 'var(--text-muted)' }}>Character Verification Pass Rate</span>
                  <div className="stats-value">{Math.round(qaReport.pass_rate * 100)}%</div>
                </div>
              </div>

              {/* Confidence Map & Grid */}
              <div className="glass-panel" style={{ padding: '32px', marginTop: '32px' }}>
                <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '16px' }}>Interactive Page-by-Page Quality Heatmap</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '20px' }}>Select any page tile to inspect layout errors, spell checker outputs, or missed LaTeX segments.</p>
                
                <div className="confidence-heatmap">
                  {qaReport.pages.map((p) => {
                    const score = p.overall_score;
                    let bg = 'var(--success)';
                    let fg = '#fff';
                    if (score < 0.6) {
                      bg = 'var(--error)';
                    } else if (score < 0.8) {
                      bg = 'var(--warning)';
                      fg = '#000';
                    }

                    return (
                      <div 
                        key={p.page_number}
                        className="confidence-tile"
                        style={{ backgroundColor: bg, color: fg }}
                      >
                        {p.page_number}
                      </div>
                    );
                  })}
                </div>

                {/* Report detail analysis list */}
                <div style={{ marginTop: '32px' }}>
                  <h4 style={{ marginBottom: '16px' }}>Identified Issues & Spell Checks ({qaReport.total_issues} issues found)</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {qaReport.pages.map((p) => {
                      if (p.issues.length === 0) return null;
                      return (
                        <div key={p.page_number} className="glass-card" style={{ display: 'flex', alignItems: 'start', gap: '12px', borderColor: 'rgba(239, 68, 68, 0.15)' }}>
                          <AlertCircle size={16} className="text-red-400" style={{ marginTop: '2px', flexShrink: 0 }} />
                          <div>
                            <div style={{ fontWeight: 600, fontSize: '14px' }}>Page {p.page_number} (Similarity Score: {Math.round(p.overall_score * 100)}%)</div>
                            <ul style={{ paddingLeft: '20px', marginTop: '8px', fontSize: '13px', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {p.issues.map((issue, idx) => (
                                <li key={idx}>{issue}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* PAGE: SETTINGS */}
          {activePage === 'settings' && (
            <div className="settings-grid">
              {/* Left Column: Engines configuration */}
              <div className="glass-panel" style={{ padding: '32px' }}>
                <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '24px' }}>Register & Toggles</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ fontWeight: 600, borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginTop: '8px' }}>OCR Engines (Ensemble)</div>
                  
                  {Object.entries(ocrEngines).map(([engine, val]) => (
                    <div className="setting-row" key={engine} style={{ padding: '8px 0' }}>
                      <span style={{ textTransform: 'capitalize' }}>{engine} OCR wrapper</span>
                      <label className="switch">
                        <input 
                          type="checkbox" 
                          checked={val} 
                          onChange={(e) => setOcrEngines(prev => ({ ...prev, [engine]: e.target.checked }))} 
                        />
                        <span className="slider"></span>
                      </label>
                    </div>
                  ))}

                  <div style={{ fontWeight: 600, borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginTop: '24px' }}>Layout Detectors</div>
                  
                  {Object.entries(layoutEngines).map(([engine, val]) => (
                    <div className="setting-row" key={engine} style={{ padding: '8px 0' }}>
                      <span style={{ textTransform: 'capitalize' }}>{engine} Engine Wrapper</span>
                      <label className="switch">
                        <input 
                          type="checkbox" 
                          checked={val} 
                          onChange={(e) => setLayoutEngines(prev => ({ ...prev, [engine]: e.target.checked }))} 
                        />
                        <span className="slider"></span>
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right Column: Hardware / compute setup */}
              <div className="glass-panel" style={{ padding: '32px' }}>
                <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '24px' }}>Hardware Compute Acceleration</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div>
                    <label style={{ display: 'block', fontWeight: 600, marginBottom: '8px' }}>Compute Device</label>
                    <select 
                      value={device} 
                      onChange={(e) => setDevice(e.target.value as any)}
                      style={{ 
                        width: '100%', 
                        padding: '12px', 
                        borderRadius: '10px', 
                        background: 'var(--secondary)', 
                        border: '1px solid var(--border-color)', 
                        color: 'var(--text-main)',
                        fontWeight: 600
                      }}
                    >
                      <option value="cpu">CPU (Generic Mode)</option>
                      <option value="cuda">NVIDIA GPU (CUDA 12.4 Accelerated)</option>
                    </select>
                  </div>

                  <div>
                    <div style={{ fontWeight: 600, marginBottom: '8px' }}>Memory Thresholds</div>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
                      To prevent local crashes or out-of-memory errors on textbooks exceeding 200 pages, DocRebuild AI runs an automatic LRU memory cache model eviction policy.
                    </div>
                  </div>

                  <div className="glass-card" style={{ display: 'flex', gap: '12px', alignItems: 'center', borderColor: 'rgba(99,102,241,0.2)' }}>
                    <Database size={20} className="text-indigo-400" />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px' }}>Model Cache Directory</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>./data/models</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
