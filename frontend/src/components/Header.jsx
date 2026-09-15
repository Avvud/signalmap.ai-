import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Radar, ShieldCheck, Activity } from 'lucide-react';

export default function Header() {
  const location = useLocation();

  return (
    <header className="navbar">
      <Link to="/" className="logo-brand">
        <div className="logo-icon">
          <Radar size={22} />
        </div>
        <span>SignalMap AI</span>
      </Link>

      <nav className="nav-links">
        <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
          New Research
        </Link>
        <div className="nav-link" style={{ opacity: 0.7, cursor: 'default' }}>
          <Activity size={14} style={{ marginRight: 6, display: 'inline' }} />
          Live Engine v1.0
        </div>
      </nav>
    </header>
  );
}
