import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Home from './pages/Home';
import Status from './pages/Status';
import Report from './pages/Report';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-container">
        <Header />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/status/:runId" element={<Status />} />
            <Route path="/report/:runId" element={<Report />} />
          </Routes>
        </main>
        <footer className="footer">
          SignalMap AI © 2026 — Multi-source Autonomous Market Intelligence Engine
        </footer>
      </div>
    </BrowserRouter>
  );
}
