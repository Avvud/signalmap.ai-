import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createResearchRun } from '../services/api';
import { Sparkles, ArrowRight, ShieldCheck, Zap, Database, Cpu } from 'lucide-react';

export default function Home() {
  const [companyName, setCompanyName] = useState('');
  const [mode, setMode] = useState('full');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!companyName.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const data = await createResearchRun(companyName.trim(), mode);
      navigate(`/status/${data.run_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to trigger research run. Make sure backend is running.');
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 760, margin: '40px auto 0' }}>
      <div style={{ textAlign: 'center', marginBottom: 40 }}>
        <div className="status-badge running" style={{ marginBottom: 16 }}>
          <Sparkles size={14} /> Stage 2 Dual-Groq Synthesis
        </div>
        <h1 style={{ fontSize: '2.8rem', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 16 }}>
          Autonomous Market Intelligence <br />
          <span style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Rooted in Hard Evidence
          </span>
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem' }}>
          Concurrently crawls Web, YouTube, Reddit, & GitHub. Every finding is mathematically traceable to source citations.
        </p>
      </div>

      <div className="glass-card">
        {error && (
          <div style={{ padding: '12px 16px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid var(--accent-danger)', borderRadius: 8, color: '#fca5a5', marginBottom: 20 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Target Company or Topic</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. FastAPI, Supabase, Vercel..."
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              disabled={loading}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Execution Mode</label>
            <select
              className="form-select"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              disabled={loading}
            >
              <option value="full">Full Pipeline (Concurrent Web, YT, Reddit, GitHub + Groq Stage A & B)</option>
              <option value="content">Content Focus (Web & YouTube focus)</option>
              <option value="developer">Developer Focus (GitHub & Tech docs focus)</option>
              <option value="messaging">Messaging & Social Focus (Reddit & Sentiment focus)</option>
            </select>
          </div>

          <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: 10 }} disabled={loading}>
            {loading ? 'Initializing Pipeline...' : 'Launch Intelligence Engine'}
            {!loading && <ArrowRight size={18} />}
          </button>
        </form>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20, marginTop: 40 }}>
        <div style={{ textAlignment: 'center' }}>
          <ShieldCheck size={24} color="var(--accent-neon)" style={{ marginBottom: 8 }} />
          <h4 style={{ fontWeight: 700, fontSize: '0.95rem' }}>Strict Citations</h4>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>Zero hallucination policy. Every claim links to evidence IDs.</p>
        </div>
        <div style={{ textAlignment: 'center' }}>
          <Database size={24} color="var(--accent-secondary)" style={{ marginBottom: 8 }} />
          <h4 style={{ fontWeight: 700, fontSize: '0.95rem' }}>Multi-Source Fetch</h4>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>Concurrent pipeline fetching across web, YouTube, Reddit & GitHub.</p>
        </div>
        <div style={{ textAlignment: 'center' }}>
          <Cpu size={24} color="var(--accent-primary)" style={{ marginBottom: 8 }} />
          <h4 style={{ fontWeight: 700, fontSize: '0.95rem' }}>Groq AI Synthesis</h4>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>Two-stage synthesis extracting strengths, risks & sentiment.</p>
        </div>
      </div>
    </div>
  );
}
