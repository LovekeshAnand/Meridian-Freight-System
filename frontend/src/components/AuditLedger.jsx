import React, { useState, useEffect } from 'react';
import { Database, Link2, CheckCircle2, Search, RefreshCw } from 'lucide-react';

export default function AuditLedger({ apiBase = 'http://127.0.0.1:8000' }) {
  const [auditData, setAuditData] = useState({ total_records: 0, records: [] });
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');

  const fetchAudit = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/audit`);
      const data = await res.json();
      setAuditData(data);
    } catch (err) {
      console.error('Failed to load audit ledger:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudit();
  }, []);

  const filteredRecords = (auditData.records || []).filter(r => {
    const q = search.toLowerCase();
    return (
      (r.ticket_id && r.ticket_id.toLowerCase().includes(q)) ||
      (r.step && r.step.toLowerCase().includes(q)) ||
      (r.rule_cited && r.rule_cited.toLowerCase().includes(q)) ||
      (r.state_hash && r.state_hash.toLowerCase().includes(q))
    );
  });

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-2">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#e8e8e6]">
        <div>
          <span className="notion-tag font-mono text-[10px] uppercase tracking-wider">
            IMMUTABLE AUDIT LEDGER
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[#191919] serif-heading mt-1">
            Cryptographic Decision Chain (SHA-256)
          </h1>
          <p className="text-xs text-[#787774] mt-1">
            Single source of truth in <span className="font-mono text-[#191919]">audit/audit.jsonl</span>. Every step decision is hash-chained.
          </p>
        </div>

        <button
          onClick={fetchAudit}
          disabled={loading}
          className="px-3.5 py-1.5 rounded-md bg-[#ffffff] border border-[#d3d3d0] hover:bg-[#f1f1ef] text-xs font-medium text-[#242424] flex items-center gap-1.5 transition-all shadow-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Ledger</span>
        </button>
      </div>

      {/* Search Input */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 text-[#9b9a97] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Filter audit ledger by ticket ID, step (VALIDATE, ENRICH, RULE_EVAL), or hash..."
            className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded-md pl-8 pr-3 py-1.5 text-xs text-[#191919] placeholder-[#9b9a97] focus:outline-none focus:border-[#242424]"
          />
        </div>
        <div className="text-[11px] font-mono text-[#787774]">
          Showing {filteredRecords.length} / {auditData.total_records} events
        </div>
      </div>

      {/* Audit Log Cards (Monochrome Feed) */}
      <div className="space-y-2.5">
        {filteredRecords.length === 0 ? (
          <div className="notion-card p-8 text-center text-xs text-[#787774]">
            No audit ledger entries found.
          </div>
        ) : (
          filteredRecords.slice().reverse().map((entry, idx) => (
            <div key={idx} className="notion-card p-3.5 hover:border-[#9b9a97] transition-all text-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="notion-pill-black font-mono text-[10px]">
                    {entry.audit_id || `AUD-${idx}`}
                  </span>
                  <span className="notion-tag font-mono text-[10px]">
                    {entry.step}
                  </span>
                  <span className="font-mono font-bold text-[#191919]">
                    {entry.ticket_id}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-[#9b9a97]">{entry.ts || 'Recorded'}</span>
              </div>

              <div className="mt-2 bg-[#fbfbfa] p-2.5 rounded border border-[#ededeb] text-[#2f2f2f] font-sans text-xs">
                {entry.decision}
              </div>

              <div className="mt-2 pt-2 border-t border-[#ededeb] flex flex-wrap items-center justify-between gap-2 text-[10px]">
                <div className="flex items-center gap-1 text-[#787774]">
                  <span className="font-semibold uppercase">Rule Cited:</span>
                  <span className="font-mono text-[#242424]">{entry.rule_cited || 'Standard SOP'}</span>
                </div>

                <div className="flex items-center gap-1 font-mono text-[#787774]">
                  <Link2 className="w-3 h-3 text-[#15803d]" />
                  <span>State Hash:</span>
                  <span className="text-[#15803d]">{entry.state_hash ? `${entry.state_hash.substring(0, 16)}...` : 'N/A'}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
