import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getResearchReport, getResearchSources } from '../services/api';
import EvidenceCard from '../components/EvidenceCard';
import { ArrowLeft, ShieldCheck, Sparkles, Layers, TrendingUp, AlertTriangle, Download, Target } from 'lucide-react';

export default function Report() {
  const { runId } = useParams();
  const [report, setReport] = useState(null);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [repRes, srcRes] = await Promise.all([
          getResearchReport(runId),
          getResearchSources(runId)
        ]);
        setReport(repRes);
        setSources(srcRes.evidence || []);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load research report');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [runId]);

  const highlightEvidence = (evId) => {
    setSelectedEvidenceId(evId);
    const el = document.getElementById(`evidence-${evId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <div className="status-badge running" style={{ padding: '12px 24px', fontSize: '1rem' }}>
          Loading Intelligence Report...
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="glass-card" style={{ maxWidth: 600, margin: '60px auto', textAlign: 'center' }}>
        <AlertTriangle size={40} color="var(--accent-warning)" style={{ marginBottom: 16 }} />
        <h2>Report Unavailable</h2>
        <p style={{ color: 'var(--text-muted)', margin: '12px 0 24px' }}>{error || 'No report found.'}</p>
        <Link to="/" className="btn-primary">Return Home</Link>
      </div>
    );
  }

  const {
    company_name = 'Target Company',
    executive_summary = 'No summary generated.',
    findings = [],
    cross_platform_findings = [],
    opportunity,
    created_at
  } = report;

  return (
    <div style={{ maxWidth: 1150, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Link to="/" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)', fontWeight: 600 }}>
          <ArrowLeft size={16} /> Back to Search
        </Link>
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="btn-primary" style={{ padding: '8px 16px', fontSize: '0.88rem' }} onClick={() => window.print()}>
            <Download size={14} /> Export Report
          </button>
        </div>
      </div>

      {/* Header Banner */}
      <div className="glass-card" style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div className="status-badge completed" style={{ marginBottom: 12 }}>
              <ShieldCheck size={14} /> Verified Evidence Report
            </div>
            <h1 style={{ fontSize: '2.4rem', fontWeight: 800 }}>{company_name}</h1>
            <p style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
              Run ID: {runId} • Generated: {created_at ? new Date(created_at).toLocaleString() : 'Just now'}
            </p>
          </div>
          <div style={{ background: 'var(--bg-input)', padding: '12px 18px', borderRadius: 10, textAlign: 'right' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Evidence Items</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--accent-secondary)' }}>
              {sources.length} Items
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.1fr', gap: 28 }}>
        {/* Main Intelligence Report Content */}
        <div>
          {/* Executive Summary */}
          <div className="glass-card" style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={18} color="var(--accent-primary)" /> Executive Summary
            </h3>
            <p style={{ color: 'var(--text-main)', lineHeight: 1.7, fontSize: '1.02rem' }}>
              {executive_summary}
            </p>
          </div>

          {/* Key Findings with Citation Tags */}
          <div className="glass-card" style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: 16 }}>Key Evidence-Backed Findings</h3>
            {findings.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>No key findings synthesized.</p>
            ) : (
              findings.map((f, i) => (
                <div key={f.id || i} className="finding-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--accent-secondary)', fontWeight: 700, textTransform: 'uppercase' }}>
                      {f.claim_type || 'Observation'} • Confidence: {((f.confidence || 0.9) * 100).toFixed(0)}%
                    </span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>{f.source_category || 'general'}</span>
                  </div>

                  <p style={{ color: 'var(--text-main)', fontSize: '0.98rem', marginBottom: 10, lineHeight: 1.5 }}>
                    {typeof f === 'string' ? f : (f.claim || 'Observation finding')}
                  </p>

                  <div>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontWeight: 600 }}>Citations:</span>
                    {(f.evidence_ids || []).map((id) => (
                      <span key={id} className="evidence-tag" onClick={() => highlightEvidence(id)}>
                        [{id}]
                      </span>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Strategic Opportunity */}
          {opportunity && (
            <div className="glass-card" style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Target size={18} color="var(--accent-neon)" /> Strategic Opportunity
              </h3>
              <p style={{ color: 'var(--text-main)', lineHeight: 1.6 }}>{opportunity}</p>
            </div>
          )}

          {/* Cross Platform Synthesis & Insights */}
          {cross_platform_findings && cross_platform_findings.length > 0 && (
            <div className="glass-card">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                <TrendingUp size={18} color="var(--accent-secondary)" /> Cross-Platform Insights
              </h3>
              {cross_platform_findings.map((cpf, idx) => {
                const claimText = typeof cpf === 'string' ? cpf : (cpf.claim || JSON.stringify(cpf));
                const evidenceIds = typeof cpf === 'object' && cpf.evidence_ids ? cpf.evidence_ids : [];
                const claimType = typeof cpf === 'object' && cpf.claim_type ? cpf.claim_type : 'cross_platform';

                return (
                  <div key={idx} className="finding-card" style={{ borderLeftColor: 'var(--accent-secondary)', marginBottom: 12 }}>
                    <div style={{ fontSize: '0.78rem', color: 'var(--accent-secondary)', fontWeight: 700, textTransform: 'uppercase', marginBottom: 4 }}>
                      {claimType}
                    </div>
                    <p style={{ color: 'var(--text-main)', fontSize: '0.95rem', marginBottom: 6 }}>{claimText}</p>
                    {evidenceIds.length > 0 && (
                      <div>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)', fontWeight: 600 }}>Citations: </span>
                        {evidenceIds.map(id => (
                          <span key={id} className="evidence-tag" onClick={() => highlightEvidence(id)}>
                            [{id}]
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Evidence Lineage Drawer */}
        <div>
          <div className="glass-card" style={{ position: 'sticky', top: 20 }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Layers size={18} color="var(--accent-neon)" /> Evidence Store ({sources.length})
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)', marginBottom: 16 }}>
              Click any citation tag to jump to its raw evidence item below.
            </p>

            <div style={{ maxHeight: '75vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {sources.map((item) => (
                <div
                  key={item.evidence_id}
                  style={{
                    border: selectedEvidenceId === item.evidence_id ? '2px solid var(--accent-primary)' : 'none',
                    borderRadius: 8,
                    transition: 'all 0.2s ease'
                  }}
                >
                  <EvidenceCard evidence={item} />
                </div>
              ))}

              {sources.length === 0 && (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: 20 }}>
                  No evidence items found for this run.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
