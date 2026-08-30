import React, { useState, useEffect } from 'react';
import { Play, Plus, RefreshCw, AlertCircle, CheckCircle, ChevronRight, X, Clock, MapPin, Truck, FileText, ShieldCheck } from 'lucide-react';

export default function BreakdownCockpit({ apiBase = 'http://127.0.0.1:8000', setActiveTab }) {
  const [results, setResults] = useState({ work_orders: [], comms_pending: [], comms_sent: [], quarantine: [] });
  const [loading, setLoading] = useState(false);
  const [selectedWO, setSelectedWO] = useState(null);
  const [showManualModal, setShowManualModal] = useState(false);
  
  const [manualTicket, setManualTicket] = useState({
    ticket_id: `TKT-${Math.floor(1000 + Math.random() * 9000)}`,
    vehicle: 'UP40IM3144',
    origin_hub: 'Gurgaon',
    km_from_origin_hub: '25',
    client: 'Shakti Cement',
    destination: 'Lucknow',
    issue: 'radiator hose burst and coolant leak',
    severity: 'HIGH'
  });

  const fetchResults = async () => {
    try {
      const res = await fetch(`${apiBase}/api/pipeline/results`);
      const data = await res.json();
      setResults(data);
    } catch (err) {
      console.error('Failed to fetch pipeline results:', err);
    }
  };

  useEffect(() => {
    fetchResults();
  }, []);

  const handleRunPipeline = async () => {
    setLoading(true);
    try {
      await fetch(`${apiBase}/api/pipeline/run`, { method: 'POST' });
      await fetchResults();
    } catch (err) {
      alert(`Pipeline execution error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = {
        ...manualTicket,
        km_from_origin_hub: parseFloat(manualTicket.km_from_origin_hub) || 0
      };
      await fetch(`${apiBase}/api/pipeline/submit_ticket`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      setShowManualModal(false);
      await fetchResults();
    } catch (err) {
      alert(`Failed to submit ticket: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-2">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#e8e8e6]">
        <div>
          <span className="notion-tag font-mono text-[10px] uppercase tracking-wider">
            AUTOMATION PIPELINE
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[#191919] serif-heading mt-1">
            Breakdown Resolution Cockpit
          </h1>
          <p className="text-xs text-[#787774] mt-1">
            Consumes breakdown queue, enriches records, enforces 12 dispatch heuristics, and allocates replacement units.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {results.comms_pending.length > 0 && setActiveTab && (
            <button
              onClick={() => setActiveTab('approval')}
              className="px-3.5 py-1.5 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Review Drafts ({results.comms_pending.length}) →</span>
            </button>
          )}
          <button
            onClick={() => setShowManualModal(true)}
            className="px-3 py-1.5 rounded-md bg-[#ffffff] border border-[#d3d3d0] hover:bg-[#f1f1ef] text-xs font-medium text-[#242424] flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Simulate Ticket</span>
          </button>
          <button
            onClick={handleRunPipeline}
            disabled={loading}
            className="px-4 py-1.5 rounded-md bg-[#242424] hover:bg-[#111111] disabled:opacity-40 text-white text-xs font-medium flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Play className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Processing...' : 'Run Queue (tickets.json)'}</span>
          </button>
        </div>
      </div>

      {/* Metrics Row (Notion Clean Cards) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="notion-card p-3.5">
          <div className="text-[10px] font-mono text-[#787774] uppercase tracking-wider">WORK ORDERS</div>
          <div className="text-xl font-bold text-[#191919] mt-1">{results.work_orders.length}</div>
          <div className="text-[10px] text-[#787774] font-mono mt-0.5">outputs/work_orders.jsonl</div>
        </div>

        <div
          onClick={() => setActiveTab && setActiveTab('approval')}
          className={`notion-card p-3.5 transition-all group ${
            setActiveTab ? 'cursor-pointer hover:border-indigo-300 hover:bg-indigo-50/40' : ''
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-mono text-indigo-700 font-bold uppercase tracking-wider">PENDING GATE</div>
            <span className="text-[9px] font-mono text-indigo-600 opacity-0 group-hover:opacity-100 transition-opacity">CLICK TO OPEN →</span>
          </div>
          <div className="text-xl font-bold text-indigo-700 mt-1">{results.comms_pending.length}</div>
          <div className="text-[10px] text-[#787774] font-mono mt-0.5">Awaiting Human Sign-off</div>
        </div>

        <div className="notion-card p-3.5">
          <div className="text-[10px] font-mono text-[#787774] uppercase tracking-wider">DISPATCHED</div>
          <div className="text-xl font-bold text-[#15803d] mt-1">{results.comms_sent.length}</div>
          <div className="text-[10px] text-[#787774] font-mono mt-0.5">outputs/comms_sent.jsonl</div>
        </div>

        <div className="notion-card p-3.5">
          <div className="text-[10px] font-mono text-[#787774] uppercase tracking-wider">QUARANTINED</div>
          <div className="text-xl font-bold text-[#be123c] mt-1">{results.quarantine.length}</div>
          <div className="text-[10px] text-[#787774] font-mono mt-0.5">outputs/quarantine.jsonl</div>
        </div>
      </div>

      {/* Two Column Layout: Work Orders & Quarantine */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Work Orders (2 Cols) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase flex items-center justify-between">
            <span>RESOLVED WORK ORDERS ({results.work_orders.length})</span>
            <span className="text-[10px] font-normal">Click card for audit trail</span>
          </div>

          {results.work_orders.length === 0 ? (
            <div className="notion-card p-8 text-center text-xs text-[#787774]">
              No work orders in queue. Click "Run Queue (tickets.json)" to process breakdowns.
            </div>
          ) : (
            <div className="space-y-2.5">
              {results.work_orders.map((wo, idx) => (
                <div
                  key={idx}
                  onClick={() => setSelectedWO(wo)}
                  className="notion-card p-3.5 cursor-pointer hover:border-[#9b9a97] transition-all"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="notion-pill-black text-[10px] font-mono">
                          {wo.work_order_id}
                        </span>
                        <span className="text-[11px] font-mono text-[#787774]">
                          Ticket: {wo.ticket_id}
                        </span>
                      </div>

                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                        <div>
                          <span className="text-[#787774]">Broken: </span>
                          <span className="font-mono font-semibold text-[#be123c]">{wo.vehicle_reg}</span>
                        </div>
                        <span className="text-[#9b9a97]">➔</span>
                        <div>
                          <span className="text-[#787774]">Replacement: </span>
                          <span className="font-mono font-semibold text-[#15803d]">{wo.replacement_vehicle_reg}</span>
                        </div>
                        {wo.hub_used && (
                          <span className="notion-tag font-mono text-[10px]">
                            Hub: {wo.hub_used}
                          </span>
                        )}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-[#9b9a97] mt-1" />
                  </div>

                  {wo.citations && wo.citations.length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-[#ededeb] flex flex-wrap gap-1">
                      {wo.citations.slice(0, 3).map((c, i) => (
                        <span key={i} className="text-[9px] font-mono px-1.5 py-0.2 bg-[#f7f6f3] border border-[#e8e8e6] text-[#5a5a58] rounded">
                          {c}
                        </span>
                      ))}
                      {wo.citations.length > 3 && (
                        <span className="text-[9px] text-[#787774]">+{wo.citations.length - 3}</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Quarantine List (1 Col) */}
        <div className="space-y-3">
          <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase">
            QUARANTINED TICKETS ({results.quarantine.length})
          </div>

          {results.quarantine.length === 0 ? (
            <div className="notion-card p-6 text-center text-xs text-[#787774]">
              Zero quarantined records. All tickets safely coerced or valid.
            </div>
          ) : (
            <div className="space-y-2">
              {results.quarantine.map((q, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-[#fff1f2] border border-[#fecdd3] text-xs">
                  <div className="flex items-center justify-between font-mono font-bold text-[#be123c]">
                    <span>{q.ticket_id || 'CORRUPT_RECORD'}</span>
                    <span className="text-[9px] text-[#9f1239] font-normal">
                      {new Date(q.quarantined_at || Date.now()).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="mt-1.5 text-[11px] text-[#881337] leading-relaxed">
                    {q.quarantine_reason}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Decision Detail Drawer */}
      {selectedWO && (
        <div className="fixed inset-0 z-50 bg-[#191919]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#ffffff] rounded-lg border border-[#d3d3d0] max-w-lg w-full p-6 shadow-xl relative max-h-[85vh] overflow-y-auto">
            <button
              onClick={() => setSelectedWO(null)}
              className="absolute top-4 right-4 p-1.5 text-[#787774] hover:text-[#191919] rounded hover:bg-[#f1f1ef]"
            >
              <X className="w-4 h-4" />
            </button>

            <span className="notion-pill-black font-mono text-[10px]">
              {selectedWO.work_order_id}
            </span>

            <h3 className="text-lg font-bold text-[#191919] serif-heading mt-2">
              Resolution Audit Trail
            </h3>

            <div className="mt-4 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2 bg-[#f7f6f3] p-3 rounded-lg border border-[#ededeb]">
                <div>
                  <div className="text-[10px] text-[#787774] uppercase font-mono">Ticket ID</div>
                  <div className="font-mono font-semibold text-[#191919] mt-0.5">{selectedWO.ticket_id}</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#787774] uppercase font-mono">Dispatch Hub</div>
                  <div className="font-semibold text-[#191919] mt-0.5">{selectedWO.hub_used || 'Origin Hub'}</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#787774] uppercase font-mono">Broken Vehicle</div>
                  <div className="font-mono font-semibold text-[#be123c] mt-0.5">{selectedWO.vehicle_reg}</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#787774] uppercase font-mono">Replacement Allocated</div>
                  <div className="font-mono font-semibold text-[#15803d] mt-0.5">{selectedWO.replacement_vehicle_reg}</div>
                </div>
              </div>

              {selectedWO.hub_strategy && (
                <div className="p-3 rounded-lg bg-[#ffffff] border border-[#e8e8e6]">
                  <div className="text-[10px] text-[#787774] uppercase font-mono font-semibold">Hub Search Precedence</div>
                  <div className="text-xs text-[#2f2f2f] mt-1 font-mono">{selectedWO.hub_strategy}</div>
                </div>
              )}

              <div className="p-3 rounded-lg bg-[#ffffff] border border-[#e8e8e6]">
                <div className="text-[10px] text-[#787774] uppercase font-mono font-semibold mb-1.5">Governing Citations</div>
                <div className="flex flex-wrap gap-1">
                  {selectedWO.citations && selectedWO.citations.map((c, i) => (
                    <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#f7f6f3] border border-[#e8e8e6] text-[#242424]">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                onClick={() => setSelectedWO(null)}
                className="px-4 py-1.5 rounded bg-[#242424] text-white text-xs font-medium"
              >
                Close Audit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Simulation Modal */}
      {showManualModal && (
        <div className="fixed inset-0 z-50 bg-[#191919]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <form onSubmit={handleManualSubmit} className="bg-[#ffffff] rounded-lg border border-[#d3d3d0] max-w-md w-full p-6 shadow-xl relative">
            <button
              type="button"
              onClick={() => setShowManualModal(false)}
              className="absolute top-4 right-4 p-1.5 text-[#787774] hover:text-[#191919] rounded hover:bg-[#f1f1ef]"
            >
              <X className="w-4 h-4" />
            </button>

            <span className="notion-tag font-mono text-[10px]">SIMULATOR</span>
            <h3 className="text-lg font-bold text-[#191919] serif-heading mt-1">
              Simulate Breakdown Ticket
            </h3>

            <div className="mt-4 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-[#787774] uppercase font-mono font-semibold">Ticket ID</label>
                  <input
                    type="text"
                    value={manualTicket.ticket_id}
                    onChange={e => setManualTicket({ ...manualTicket, ticket_id: e.target.value })}
                    className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded p-2 text-[#191919] font-mono mt-1"
                    required
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#787774] uppercase font-mono font-semibold">Vehicle Reg</label>
                  <input
                    type="text"
                    value={manualTicket.vehicle}
                    onChange={e => setManualTicket({ ...manualTicket, vehicle: e.target.value })}
                    className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded p-2 text-[#191919] font-mono mt-1"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-[#787774] uppercase font-mono font-semibold">Client</label>
                  <select
                    value={manualTicket.client}
                    onChange={e => setManualTicket({ ...manualTicket, client: e.target.value })}
                    className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded p-2 text-[#191919] mt-1"
                  >
                    <option value="Shakti Cement">Shakti Cement</option>
                    <option value="Apex Chemicals">Apex Chemicals</option>
                    <option value="Vertex Retail">Vertex Retail</option>
                    <option value="Orion Pharma">Orion Pharma</option>
                    <option value="Internal">Internal</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-[#787774] uppercase font-mono font-semibold">Origin Hub</label>
                  <input
                    type="text"
                    value={manualTicket.origin_hub}
                    onChange={e => setManualTicket({ ...manualTicket, origin_hub: e.target.value })}
                    className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded p-2 text-[#191919] mt-1"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-[#787774] uppercase font-mono font-semibold">KM from Origin</label>
                  <input
                    type="number"
                    value={manualTicket.km_from_origin_hub}
                    onChange={e => setManualTicket({ ...manualTicket, km_from_origin_hub: e.target.value })}
                    className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded p-2 text-[#191919] mt-1"
                    required
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#787774] uppercase font-mono font-semibold">Destination</label>
                  <input
                    type="text"
                    value={manualTicket.destination}
                    onChange={e => setManualTicket({ ...manualTicket, destination: e.target.value })}
                    className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded p-2 text-[#191919] mt-1"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-[#787774] uppercase font-mono font-semibold">Breakdown Description</label>
                <input
                  type="text"
                  value={manualTicket.issue}
                  onChange={e => setManualTicket({ ...manualTicket, issue: e.target.value })}
                  className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded p-2 text-[#191919] mt-1"
                />
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowManualModal(false)}
                className="px-3 py-1.5 rounded text-xs text-[#787774] hover:text-[#191919]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-1.5 rounded bg-[#242424] hover:bg-[#111111] text-white text-xs font-medium"
              >
                {loading ? 'Processing...' : 'Ingest & Resolve'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
