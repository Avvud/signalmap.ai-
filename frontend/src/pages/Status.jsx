import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getResearchStatus } from '../services/api';
import PipelineStepper from '../components/PipelineStepper';
import { Loader2, AlertCircle, FileText } from 'lucide-react';

export default function Status() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let intervalId;

    const fetchStatus = async () => {
      try {
        const res = await getResearchStatus(runId);
        setData(res);

        if (res.status === 'completed') {
          clearInterval(intervalId);
          setTimeout(() => navigate(`/report/${runId}`), 1200);
        } else if (res.status === 'failed') {
          clearInterval(intervalId);
        }
      } catch (err) {
        setError(err.response?.data?.detail || 'Error fetching status');
        clearInterval(intervalId);
      }
    };

    fetchStatus();
    intervalId = setInterval(fetchStatus, 2000);

    return () => clearInterval(intervalId);
  }, [runId, navigate]);

  if (error) {
    return (
      <div className="glass-card" style={{ maxWidth: 600, margin: '60px auto', textAlign: 'center' }}>
        <AlertCircle size={40} color="var(--accent-danger)" style={{ marginBottom: 16 }} />
        <h2>Pipeline Failed</h2>
        <p style={{ color: 'var(--text-muted)', margin: '12px 0 24px' }}>{error}</p>
        <button onClick={() => navigate('/')} className="btn-primary">Return Home</button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 880, margin: '40px auto' }}>
      <div className="glass-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 700 }}>Researching: {data?.company_name || 'Target'}</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>Run ID: {runId}</p>
          </div>

          <div className={`status-badge ${data?.status || 'queued'}`}>
            {data?.status === 'running' && <Loader2 size={14} className="spin" style={{ animation: 'spin 1s linear infinite' }} />}
            {data?.status || 'queued'}
          </div>
        </div>

        <PipelineStepper currentStatus={data?.status || 'queued'} />

        <div style={{ marginTop: 30, padding: 20, background: 'var(--bg-input)', borderRadius: 10, fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          <div style={{ fontWeight: 600, marginBottom: 8, color: 'var(--text-main)' }}>Pipeline Progress Details:</div>
          <div>• Created At: {data?.created_at ? new Date(data.created_at).toLocaleTimeString() : 'Just now'}</div>
          <div>• Mode: {data?.mode || 'full'}</div>
          {data?.status === 'running' && <div>• Processing 4 external data sources in parallel...</div>}
          {data?.status === 'completed' && <div style={{ color: 'var(--accent-neon)', fontWeight: 600, marginTop: 8 }}>✓ Research complete! Redirecting to report...</div>}
        </div>

        {data?.status === 'completed' && (
          <button onClick={() => navigate(`/report/${runId}`)} className="btn-primary" style={{ marginTop: 24, width: '100%' }}>
            <FileText size={18} /> View Final Intelligence Report
          </button>
        )}
      </div>
    </div>
  );
}
