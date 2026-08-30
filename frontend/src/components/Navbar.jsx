import React, { useState } from 'react';
import { 
  Sparkles, Activity, ShieldCheck, Truck, Database, Layers, Menu, X, 
  ChevronRight, CheckCircle2, ArrowUpRight, Bell, AlertOctagon, FileText, 
  AlertTriangle, ArrowRight 
} from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, systemStatus }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const pendingCount = systemStatus?.counts?.comms_pending || 0;
  const quarantineCount = systemStatus?.counts?.quarantined || 0;
  const totalAlerts = pendingCount + quarantineCount;

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
                  <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-[#ffffff] border border-[#e8e8e6] rounded-xl shadow-2xl z-50 p-4 animate-slide-in-right">
                    <div className="flex items-center justify-between pb-3 border-b border-[#ededeb]">
                      <div className="flex items-center gap-2">
                        <Bell className="w-4 h-4 text-[#191919]" />
                        <span className="text-xs font-bold font-mono text-[#191919] uppercase tracking-wider">
                          NOTIFICATION CENTER
                        </span>
                      </div>
                      <span className="text-[10px] font-mono bg-[#f1f1ef] text-[#787774] px-2 py-0.5 rounded">
                        {totalAlerts} Active Item(s)
                      </span>
                    </div>

                    <div className="mt-3 space-y-2 max-h-80 overflow-y-auto pr-1">
                      {/* 1. Pending Approvals */}
                      {pendingCount > 0 ? (
                        <div
                          onClick={() => handleSelectTab('approval')}
                          className="p-3 rounded-lg border border-indigo-200 bg-indigo-50/70 hover:bg-indigo-100/70 cursor-pointer transition-all group"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <FileText className="w-4 h-4 text-indigo-600 shrink-0" />
                              <span className="text-xs font-semibold text-indigo-950">
                                {pendingCount} Draft(s) Waiting for Human Approval
                              </span>
                            </div>
                            <span className="text-[9px] font-mono bg-indigo-200 text-indigo-800 font-bold px-1.5 py-0.2 rounded">
                              GATE OPEN
                            </span>
                          </div>
                          <p className="text-[11px] text-indigo-800 mt-1 leading-snug">
                            Outbound client notification letters are staged in outbox. Click to review and 1-click dispatch.
                          </p>
                          <div className="text-[10px] font-mono text-indigo-600 font-semibold mt-2 flex items-center gap-1 group-hover:underline">
                            <span>Open Approval Gate Desk</span>
                            <ArrowRight className="w-3 h-3" />
                          </div>
                        </div>
                      ) : null}

                      {/* 2. Quarantined Tickets */}
                      {quarantineCount > 0 ? (
                        <div
                          onClick={() => handleSelectTab('cockpit')}
                          className="p-3 rounded-lg border border-rose-200 bg-rose-50/70 hover:bg-rose-100/70 cursor-pointer transition-all group"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <AlertOctagon className="w-4 h-4 text-rose-600 shrink-0" />
                              <span className="text-xs font-semibold text-rose-950">
                                {quarantineCount} Ticket(s) Quarantined
                              </span>
                            </div>
                            <span className="text-[9px] font-mono bg-rose-200 text-rose-800 font-bold px-1.5 py-0.2 rounded">
                              CORRUPT INPUT
                            </span>
                          </div>
                          <p className="text-[11px] text-rose-800 mt-1 leading-snug">
                            Missing origin hubs or invalid telemetry isolated safely. Click to inspect reasons in Cockpit.
                          </p>
                          <div className="text-[10px] font-mono text-rose-600 font-semibold mt-2 flex items-center gap-1 group-hover:underline">
                            <span>Open Resolution Cockpit</span>
                            <ArrowRight className="w-3 h-3" />
                          </div>
                        </div>
                      ) : null}

                      {/* 3. P2 Gate Rule / SLA Standing Notice */}
                      <div className="p-3 rounded-lg border border-amber-200 bg-amber-50/70">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                          <span className="text-xs font-semibold text-amber-950">
                            P2 Standing Policies Active
                          </span>
                        </div>
                        <div className="text-[11px] text-amber-800 mt-1 space-y-0.5">
                          <div>• <strong>Vertex Retail</strong>: 6:00 PM gate closing hold active.</div>
                          <div>• <strong>Shakti Cement</strong>: 36-hour operational window enforced.</div>
                          <div>• <strong>Delhi NCR</strong>: GRAP BS4 commercial vehicle ban enforced.</div>
                        </div>
                      </div>

                      {totalAlerts === 0 && (
                        <div className="p-4 text-center text-xs text-[#787774] font-mono">
                          <CheckCircle2 className="w-5 h-5 text-emerald-600 mx-auto mb-1" />
                          <span>All queues clear. Zero pending approvals.</span>
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
