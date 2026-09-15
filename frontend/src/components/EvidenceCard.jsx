import React from 'react';
import { ExternalLink, Hash, Globe, Youtube, MessageSquare, Code } from 'lucide-react';

const sourceIcons = {
  website: Globe,
  youtube: Youtube,
  reddit: MessageSquare,
  github: Code,
};

export default function EvidenceCard({ evidence }) {
  const Icon = sourceIcons[evidence.source] || Globe;

  return (
    <div className="evidence-card" id={`evidence-${evidence.evidence_id}`}>
      <div className="evidence-header">
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon size={14} />
          <strong>{evidence.evidence_id}</strong> ({evidence.source})
        </span>
        {evidence.url && (
          <a href={evidence.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-secondary)' }}>
            <ExternalLink size={14} />
          </a>
        )}
      </div>

      <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--text-main)' }}>
        {evidence.title || 'Untitled Evidence Item'}
      </div>

      <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
        {evidence.snippet || (typeof evidence.content === 'string' ? evidence.content.slice(0, 150) + '...' : 'No preview standard text.')}
      </p>

      {evidence.confidence_score !== undefined && (
        <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--text-dim)', textAlign: 'right' }}>
          Confidence: {(evidence.confidence_score * 100).toFixed(0)}%
        </div>
      )}
    </div>
  );
}
