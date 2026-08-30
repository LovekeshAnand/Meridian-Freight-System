import React, { useState } from 'react';
import { 
  Sparkles, Activity, ShieldCheck, Truck, Database, Layers, Menu, X, 
  ChevronRight, CheckCircle2, ArrowUpRight, Bell, AlertOctagon, FileText, 
  AlertTriangle, ArrowRight 
} from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, systemStatus }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifFilter, setNotifFilter] = useState('all'); // 'all' | 'drafts' | 'quarantine'
  const [pendingItems, setPendingItems] = useState([]);
  const [quarantineItems, setQuarantineItems] = useState([]);
  const [approvingId, setApprovingId] = useState(null);

  const pendingCount = systemStatus?.counts?.comms_pending || 0;
  const quarantineCount = systemStatus?.counts?.quarantined || 0;
  const totalAlerts = pendingCount + quarantineCount;

  // Fetch detailed list of pending and quarantined items when notification center opens
  React.useEffect(() => {
    if (notifOpen) {
      fetch('http://127.0.0.1:8000/api/comms/pending')
        .then(r => r.json())
        .then(data => setPendingItems(Array.isArray(data) ? data : []))
        .catch(() => {});

      fetch('http://127.0.0.1:8000/api/quarantine')
        .then(r => r.json())
        .then(data => setQuarantineItems(Array.isArray(data) ? data : []))
        .catch(() => {});
    }
  }, [notifOpen]);

  const handleQuickApprove = async (msgId, e) => {
    e.stopPropagation();
    setApprovingId(msgId);
    try {
      await fetch('http://127.0.0.1:8000/api/comms/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: msgId, approved_by: 'Lead Dispatcher' })
      });
      setPendingItems(prev => prev.filter(p => p.message_id !== msgId));
    } catch (err) {
      alert(`Approval failed: ${err.message}`);
    } finally {
      setApprovingId(null);
    }
  };

  const navItems = [
    { id: 'brain', label: "Rajender's Brain", desc: '18-year grounded heuristic context layer & AI copilot', tag: 'COPILOT', icon: Sparkles },
    { id: 'cockpit', label: 'Resolution Cockpit', desc: 'Automated 7-step breakdown resolution & candidate allocator', count: systemStatus?.counts?.work_orders || 0, icon: Activity },
    { id: 'approval', label: 'Approval Gate', desc: 'Human-in-the-loop review & dispatch sign-off desk', count: pendingCount, alert: pendingCount > 0, icon: ShieldCheck },
    { id: 'fleet', label: 'Fleet & Topology', desc: '100 commercial vehicles, Guddu 7d timers & BS stage map', count: systemStatus?.context_store?.vehicles_loaded || 100, icon: Truck },
    { id: 'audit', label: 'Audit Ledger', desc: 'Cryptographic SHA-256 hash-chained decision trail', tag: 'SHA-256', icon: Database },
    { id: 'sandbox', label: 'Sandbox & Tests', desc: 'Surprise format drift adapter & 92 live automated tests', tag: '92 TESTS', icon: Layers },
  ];

  const currentItem = navItems.find(i => i.id === activeTab) || navItems[0];

  const handleSelectTab = (id) => {
    setActiveTab(id);
    setDrawerOpen(false);
    setNotifOpen(false);
  };

  return (
    <>
      <header className="border-b border-[#e8e8e6] bg-[#ffffff] sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14">
            {/* Left: Brand Logo & Current View */}
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-md bg-[#242424] text-white flex items-center justify-center text-xs font-bold font-serif shadow-xs">
                M
              </div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm tracking-tight text-[#191919]">Meridian</span>
                <span className="text-slate-300">/</span>
                <span className="text-xs font-medium text-[#242424]">{currentItem.label}</span>
              </div>
            </div>

            {/* Right: Status Pill, Notification Bell & Menu Button */}
            <div className="flex items-center gap-2.5">
              <div className="hidden sm:flex items-center gap-2 text-[11px] text-[#787774] font-mono mr-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                <span>Epsilon Grounded</span>
              </div>

              {/* Top-Right Notification Bell Button */}
              <div className="relative">
                <button
                  onClick={() => {
                    setNotifOpen(!notifOpen);
                    setDrawerOpen(false);
                  }}
                  className={`relative p-2 rounded-md transition-all flex items-center gap-1.5 border ${
                    notifOpen || totalAlerts > 0
                      ? 'bg-[#f7f6f3] border-[#d3d3d0] text-[#191919]'
                      : 'hover:bg-[#f1f1ef] border-[#ededeb] text-[#5a5a58]'
                  }`}
                  aria-label="Toggle Notification Center"
                >
                  <Bell className="w-4 h-4" />
                  {totalAlerts > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full bg-[#e11d48] text-white text-[10px] font-mono font-bold">
                      {totalAlerts}
                    </span>
                  )}
                </button>

                {/* Interactive Notification Dropdown */}
                {notifOpen && (
                  <div className="absolute right-0 mt-2 w-80 sm:w-[420px] bg-[#ffffff] border border-[#e8e8e6] rounded-xl shadow-2xl z-50 p-4 animate-slide-in-right">
                    {/* Header */}
                    <div className="flex items-center justify-between pb-3 border-b border-[#ededeb]">
                      <div className="flex items-center gap-2">
                        <Bell className="w-4 h-4 text-[#191919]" />
                        <span className="text-xs font-bold font-mono text-[#191919] uppercase tracking-wider">
                          NOTIFICATION CENTER
                        </span>
                      </div>
                      <span className="text-[10px] font-mono bg-[#f1f1ef] text-[#787774] px-2 py-0.5 rounded">
                        {totalAlerts} Total Active
                      </span>
                    </div>

                    {/* Filter Tabs */}
                    <div className="flex gap-1 mt-2.5 pb-2 border-b border-[#f1f1ef]">
                      <button
                        onClick={() => setNotifFilter('all')}
                        className={`px-2 py-1 rounded text-[11px] font-mono transition-all ${
                          notifFilter === 'all'
                            ? 'bg-[#242424] text-white font-semibold'
                            : 'text-[#787774] hover:bg-[#f1f1ef]'
                        }`}
                      >
                        All ({pendingItems.length + quarantineItems.length})
                      </button>
                      <button
                        onClick={() => setNotifFilter('drafts')}
                        className={`px-2 py-1 rounded text-[11px] font-mono transition-all ${
                          notifFilter === 'drafts'
                            ? 'bg-indigo-600 text-white font-semibold'
                            : 'text-[#787774] hover:bg-indigo-50 hover:text-indigo-700'
                        }`}
                      >
                        Drafts ({pendingItems.length})
                      </button>
                      <button
                        onClick={() => setNotifFilter('quarantine')}
                        className={`px-2 py-1 rounded text-[11px] font-mono transition-all ${
                          notifFilter === 'quarantine'
                            ? 'bg-rose-600 text-white font-semibold'
                            : 'text-[#787774] hover:bg-rose-50 hover:text-rose-700'
                        }`}
                      >
                        Quarantined ({quarantineItems.length})
                      </button>
                    </div>

                    {/* Scrollable Items Container */}
                    <div className="mt-3 space-y-2.5 max-h-[60vh] overflow-y-auto pr-1">
                      {/* 1. Pending Draft Items */}
                      {(notifFilter === 'all' || notifFilter === 'drafts') && pendingItems.map((item) => (
                        <div
                          key={item.message_id || item.ticket_id}
                          onClick={() => handleSelectTab('approval')}
                          className="p-3 rounded-lg border border-indigo-200 bg-indigo-50/60 hover:bg-indigo-100/60 cursor-pointer transition-all group"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-1.5">
                              <FileText className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                              <span className="font-mono text-[11px] font-bold text-indigo-950">
                                {item.ticket_id || 'TICKET DRAFT'}
                              </span>
                            </div>
                            <span className="text-[9px] font-mono bg-indigo-200 text-indigo-800 font-bold px-1.5 py-0.2 rounded">
                              DRAFT READY
                            </span>
                          </div>

                          <div className="text-xs font-semibold text-[#191919] mt-1">
                            Client: {item.recipient || item.client || 'Shakti Cement'}
                          </div>

                          <p className="text-[11px] text-[#5a5a58] mt-0.5 line-clamp-2 leading-relaxed font-sans">
                            {item.body || item.text || 'Client notification letter drafted and waiting for human dispatcher authorization.'}
                          </p>

                          <div className="mt-2 pt-2 border-t border-indigo-100 flex items-center justify-between">
                            <div className="text-[10px] font-mono text-[#787774] flex items-center gap-1">
                              <span>Assigned:</span>
                              <span className="font-semibold text-emerald-700">
                                {item.replacement_vehicle || item.replacement_vehicle_reg || 'Eligible Truck'}
                              </span>
                            </div>
                            <button
                              onClick={(e) => handleQuickApprove(item.message_id, e)}
                              disabled={approvingId === item.message_id}
                              className="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-700 text-white text-[10px] font-mono font-semibold transition-all shadow-2xs"
                            >
                              {approvingId === item.message_id ? 'Sending...' : 'Approve & Send'}
                            </button>
                          </div>
                        </div>
                      ))}

                      {/* 2. Quarantined Items */}
                      {(notifFilter === 'all' || notifFilter === 'quarantine') && quarantineItems.map((item, idx) => (
                        <div
                          key={item.ticket_id || idx}
                          onClick={() => handleSelectTab('cockpit')}
                          className="p-3 rounded-lg border border-rose-200 bg-rose-50/60 hover:bg-rose-100/60 cursor-pointer transition-all group"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-1.5">
                              <AlertOctagon className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                              <span className="font-mono text-[11px] font-bold text-rose-950">
                                {item.ticket_id || 'CORRUPT RECORD'}
                              </span>
                            </div>
                            <span className="text-[9px] font-mono bg-rose-200 text-rose-800 font-bold px-1.5 py-0.2 rounded">
                              QUARANTINED
                            </span>
                          </div>

                          <div className="text-xs font-semibold text-rose-900 mt-1">
                            Reason: {item.quarantine_reason || item.reason || 'Missing required fields or invalid telemetry.'}
                          </div>

                          <div className="mt-2 pt-2 border-t border-rose-100 flex items-center justify-between text-[10px] font-mono">
                            <span className="text-rose-700 font-medium">Safe Isolation</span>
                            <span className="text-rose-600 font-semibold group-hover:underline flex items-center gap-1">
                              <span>Inspect in Cockpit</span>
                              <ArrowRight className="w-3 h-3" />
                            </span>
                          </div>
                        </div>
                      ))}

                      {/* 3. P2 Standing Policy Banner */}
                      {notifFilter === 'all' && (
                        <div className="p-3 rounded-lg border border-amber-200 bg-amber-50/60">
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                            <span className="text-xs font-semibold text-amber-950">
                              P2 Standing Dispatch Policies Active
                            </span>
                          </div>
                          <div className="text-[11px] text-amber-900 mt-1 space-y-0.5 font-sans">
                            <div>• <strong>Vertex Retail</strong>: 6:00 PM gate hold (overnight hold until 8:00 AM).</div>
                            <div>• <strong>Shakti Cement</strong>: 36-hour delivery window strictly enforced.</div>
                            <div>• <strong>Delhi NCR</strong>: GRAP BS4 commercial vehicle ban enforced.</div>
                          </div>
                        </div>
                      )}

                      {pendingItems.length === 0 && quarantineItems.length === 0 && (
                        <div className="p-6 text-center text-xs text-[#787774] font-mono">
                          <CheckCircle2 className="w-6 h-6 text-emerald-600 mx-auto mb-1.5" />
                          <span>All queues clear. Zero pending actions.</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Hamburger Button */}
              <button
                onClick={() => {
                  setDrawerOpen(true);
                  setNotifOpen(false);
                }}
                className="relative p-2 rounded-md hover:bg-[#f1f1ef] text-[#191919] transition-all flex items-center gap-2 border border-[#ededeb]"
                aria-label="Open Navigation Menu"
              >
                <Menu className="w-4 h-4" />
                <span className="text-xs font-medium hidden sm:inline">Menu</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Animated Slide-Over Drawer Backdrop & Panel */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop */}
          <div
            onClick={() => setDrawerOpen(false)}
            className="absolute inset-0 bg-[#191919]/30 backdrop-blur-xs transition-opacity duration-300 ease-in-out"
          />

          {/* Slide-Over Menu Panel (Right Side) */}
          <div className="absolute inset-y-0 right-0 max-w-sm w-full bg-[#ffffff] border-l border-[#e8e8e6] shadow-2xl flex flex-col justify-between transform transition-transform duration-300 ease-in-out">
            <div className="p-5 overflow-y-auto">
              {/* Drawer Header */}
              <div className="flex items-center justify-between pb-4 border-b border-[#ededeb]">
                <div>
                  <span className="notion-tag font-mono text-[9px] uppercase tracking-wider">
                    OPERATIONS WORKSPACE
                  </span>
                  <h2 className="text-base font-bold text-[#191919] serif-heading mt-0.5">
                    Meridian Dispatch Hub
                  </h2>
                </div>
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="p-1.5 text-[#787774] hover:text-[#191919] rounded-md hover:bg-[#f1f1ef] transition-all"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Navigation Items List */}
              <div className="mt-4 space-y-1.5">
                {navItems.map(item => {
                  const isActive = activeTab === item.id;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => handleSelectTab(item.id)}
                      className={`w-full p-3 rounded-lg text-left transition-all flex items-start justify-between group ${
                        isActive
                          ? 'bg-[#f7f6f3] border border-[#d3d3d0]'
                          : 'hover:bg-[#fbfbfa] border border-transparent hover:border-[#ededeb]'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-md shrink-0 mt-0.5 ${
                          isActive ? 'bg-[#242424] text-white' : 'bg-[#f1f1ef] text-[#787774] group-hover:text-[#191919]'
                        }`}>
                          <Icon className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-[#191919]">{item.label}</span>
                            {item.tag && (
                              <span className="text-[9px] font-mono px-1 py-0.2 bg-[#ededeb] text-[#5a5a58] rounded">
                                {item.tag}
                              </span>
                            )}
                            {item.count !== undefined && (
                              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                                item.alert
                                  ? 'bg-[#e11d48] text-white font-bold'
                                  : 'bg-[#ededeb] text-[#787774]'
                              }`}>
                                {item.count}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-[#787774] mt-0.5 leading-relaxed">
                            {item.desc}
                          </p>
                        </div>
                      </div>
                      <ChevronRight className="w-3.5 h-3.5 text-[#9b9a97] group-hover:text-[#191919] shrink-0 mt-2" />
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Bottom Drawer Footer */}
            <div className="p-4 border-t border-[#ededeb] bg-[#fbfbfa] text-xs text-[#787774] space-y-1 font-mono text-[11px]">
              <div className="flex justify-between">
                <span>Fleet Ingested:</span>
                <span className="text-[#191919] font-semibold">{systemStatus?.context_store?.vehicles_loaded || 100} vehicles</span>
              </div>
              <div className="flex justify-between">
                <span>Email Threads:</span>
                <span className="text-[#191919] font-semibold">{systemStatus?.context_store?.emails_loaded || 40} threads</span>
              </div>
              <div className="flex justify-between">
                <span>Audit Ledger:</span>
                <span className="text-[#15803d] font-semibold">Verified SHA-256</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
