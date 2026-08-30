import React from 'react';
import { Sparkles, Activity, ShieldCheck, Truck, Database, Layers, Terminal, Compass, CheckCircle2 } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, systemStatus }) {
  const navItems = [
    { id: 'brain', label: "Rajender's Brain", tag: 'COPILOT', icon: Sparkles },
    { id: 'cockpit', label: 'Resolution Cockpit', count: systemStatus?.counts?.work_orders || 0, icon: Activity },
    { id: 'approval', label: 'Approval Gate', count: systemStatus?.counts?.comms_pending || 0, alert: (systemStatus?.counts?.comms_pending || 0) > 0, icon: ShieldCheck },
    { id: 'fleet', label: 'Fleet & Topology', count: systemStatus?.context_store?.vehicles_loaded || 100, icon: Truck },
    { id: 'audit', label: 'Audit Ledger', tag: 'SHA-256', icon: Database },
    { id: 'sandbox', label: 'Sandbox & Tests', tag: '92 TESTS', icon: Layers },
  ];

  return (
    <header className="border-b border-[#e8e8e6] bg-[#ffffff] sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-14">
          {/* Logo / Workspace Title */}
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-[#242424] text-white flex items-center justify-center text-xs font-bold font-serif">
              M
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-semibold text-sm tracking-tight text-[#242424]">Meridian Freight</span>
              <span className="text-[11px] text-[#787774] hidden sm:inline">/ Dispatch Intelligence</span>
            </div>
          </div>

          {/* Clean Notion Menu */}
          <nav className="flex items-center gap-1 overflow-x-auto py-1 scrollbar-none">
            {navItems.map(item => {
              const isActive = activeTab === item.id;
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 shrink-0 ${
                    isActive
                      ? 'bg-[#242424] text-white shadow-sm'
                      : 'text-[#5a5a58] hover:bg-[#f1f1ef] hover:text-[#242424]'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-[#787774]'}`} />
                  <span>{item.label}</span>
                  {item.tag && (
                    <span className={`text-[9px] font-mono uppercase px-1 py-0.2 rounded ${
                      isActive ? 'bg-white/20 text-white' : 'bg-[#e8e8e6] text-[#787774]'
                    }`}>
                      {item.tag}
                    </span>
                  )}
                  {item.count !== undefined && (
                    <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                      isActive
                        ? 'bg-white/20 text-white'
                        : item.alert
                        ? 'bg-[#e11d48] text-white font-bold'
                        : 'bg-[#ededeb] text-[#787774]'
                    }`}>
                      {item.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Status */}
          <div className="hidden lg:flex items-center gap-2 text-[11px] text-[#787774]">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
            <span className="font-mono">Epsilon Grounded</span>
          </div>
        </div>
      </div>
    </header>
  );
}
