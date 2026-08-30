import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import NotificationToast from './components/NotificationToast';
import RajenderBrain from './components/RajenderBrain';
import BreakdownCockpit from './components/BreakdownCockpit';
import ApprovalGate from './components/ApprovalGate';
import FleetExplorer from './components/FleetExplorer';
import AuditLedger from './components/AuditLedger';
import AdversarialSandbox from './components/AdversarialSandbox';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState('brain');
  const [systemStatus, setSystemStatus] = useState(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      const data = await res.json();
      setSystemStatus(data);
    } catch (err) {
      console.warn('API offline or polling:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-[#ffffff] text-[#2f2f2f] flex flex-col font-sans">
      <NotificationToast />
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        systemStatus={systemStatus}
      />

      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto w-full">
        {activeTab === 'brain' && <RajenderBrain apiBase={API_BASE} setActiveTab={setActiveTab} />}
        {activeTab === 'cockpit' && <BreakdownCockpit apiBase={API_BASE} setActiveTab={setActiveTab} />}
        {activeTab === 'approval' && <ApprovalGate apiBase={API_BASE} setActiveTab={setActiveTab} />}
        {activeTab === 'fleet' && <FleetExplorer apiBase={API_BASE} setActiveTab={setActiveTab} />}
        {activeTab === 'audit' && <AuditLedger apiBase={API_BASE} setActiveTab={setActiveTab} />}
        {activeTab === 'sandbox' && <AdversarialSandbox apiBase={API_BASE} setActiveTab={setActiveTab} />}
      </main>

      <footer className="border-t border-[#e8e8e6] py-5 text-center text-xs text-[#787774] font-mono">
        Meridian Freight System • Rajender's Grounded Dispatch Brain • Notion Minimalist Theme v2.0
      </footer>
    </div>
  );
}
