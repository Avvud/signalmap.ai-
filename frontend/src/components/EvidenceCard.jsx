import React from 'react';
import { ExternalLink, Globe, Youtube, MessageSquare, Code } from 'lucide-react';

const sourceIcons = {
  website: Globe,
  youtube: Youtube,
  reddit: MessageSquare,
  github: Code,
};

export default function EvidenceCard({ evidence }) {
  const Icon = sourceIcons[evidence.source] || Globe;
  const targetUrl = evidence.source_url || evidence.url;
  const contentSnippet = evidence.normalized_content || evidence.raw_content || evidence.snippet || 'No text preview available.';

  return (
    <div className="evidence-card" id={`evidence-${evidence.evidence_id}`}>
      <div className="evidence-header">
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--accent-secondary)' }}>
          <Icon size={14} />
          <strong>{evidence.evidence_id}</strong> ({evidence.source})
        </span>

        {targetUrl && (
          <a
            href={targetUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="Visit external source"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              color: 'var(--accent-primary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              background: 'rgba(99, 102, 241, 0.12)',
              padding: '2px 8px',
              borderRadius: 4,
              transition: 'all 0.2s ease'
            }}
          >
            Visit <ExternalLink size={12} />
          </a>
        )}
      </div>

      <div style={{ fontWeight: 700, marginBottom: 6, fontSize: '0.92rem', color: 'var(--text-main)' }}>
        {targetUrl ? (
          <a
            href={targetUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--text-main)', textDecoration: 'none' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
          >
            {evidence.title || 'Untitled Evidence Source'}
          </a>
        ) : (
          evidence.title || 'Untitled Evidence Source'
        )}
      </div>

      <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: '1.45', maxHeight: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {typeof contentSnippet === 'string' ? contentSnippet.slice(0, 180) + (contentSnippet.length > 180 ? '...' : '') : 'No preview standard text.'}
      </p>
    </div>
  );
}
