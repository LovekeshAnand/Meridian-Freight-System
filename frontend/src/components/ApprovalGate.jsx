import React, { useState, useEffect } from 'react';
import { ShieldCheck, Check, X, Edit3, Send, CheckCheck, Clock, Mail, RefreshCw } from 'lucide-react';

export default function ApprovalGate({ apiBase = 'http://127.0.0.1:8000' }) {
  const [pending, setPending] = useState([]);
  const [sent, setSent] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editingMsg, setEditingMsg] = useState(null);
  const [editText, setEditText] = useState('');
  const [approverName, setApproverName] = useState('Senior Dispatcher');

  const fetchData = async () => {
    try {
      const res = await fetch(`${apiBase}/api/pipeline/results`);
      const data = await res.json();
      setPending(data.comms_pending || []);
      setSent(data.comms_sent || []);
    } catch (err) {
      console.error('Failed to fetch approval gate data:', err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleApproveSingle = async (messageId) => {
    setLoading(true);
    try {
      await fetch(`${apiBase}/api/comms/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, approved_by: approverName })
      });
      await fetchData();
    } catch (err) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAll = async () => {
    if (!confirm(`Confirm dispatch of all ${pending.length} pending client notifications?`)) {
      return;
    }
    setLoading(true);
    try {
      await fetch(`${apiBase}/api/comms/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approve_all: true, approved_by: approverName })
      });
      await fetchData();
    } catch (err) {
      alert(`Bulk approval error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async (messageId) => {
    const reason = prompt('Please enter reason for rejecting draft:') || 'Dispatcher rejected draft.';
    setLoading(true);
    try {
      await fetch(`${apiBase}/api/comms/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, reason, rejected_by: approverName })
      });
      await fetchData();
    } catch (err) {
      alert(`Reject error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingMsg) return;
    setLoading(true);
    try {
      await fetch(`${apiBase}/api/comms/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: editingMsg.message_id, edited_body: editText })
      });
      setEditingMsg(null);
      await fetchData();
    } catch (err) {
      alert(`Save edit error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-2">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#e8e8e6]">
        <div>
          <span className="notion-tag font-mono text-[10px] uppercase tracking-wider">
            HUMAN-IN-THE-LOOP CONTROL
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[#191919] serif-heading mt-1">
            Outbound Communication Approval Gate
          </h1>
          <p className="text-xs text-[#787774] mt-1">
            Strict safety requirement: Zero outbound client communications are sent without explicit human approval.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-xs text-[#787774] flex items-center gap-1.5 font-mono">
            <span>Approver:</span>
            <input
              type="text"
              value={approverName}
              onChange={e => setApproverName(e.target.value)}
              className="bg-[#fbfbfa] border border-[#d3d3d0] rounded px-2 py-1 text-xs text-[#191919] font-sans"
            />
          </div>
          <button
            onClick={handleApproveAll}
            disabled={loading || pending.length === 0}
            className="px-4 py-1.5 rounded-md bg-[#242424] hover:bg-[#111111] disabled:opacity-30 text-white text-xs font-medium flex items-center gap-1.5 transition-all shadow-sm"
          >
            <CheckCheck className="w-3.5 h-3.5" />
            <span>Approve All ({pending.length})</span>
          </button>
        </div>
      </div>

      {/* Pending Items Grid */}
      <div className="space-y-3">
        <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase flex items-center justify-between">
          <span>PENDING DRAFTS AWAITING SIGN-OFF ({pending.length})</span>
          <span className="text-[10px] font-normal">outputs/comms_pending.jsonl</span>
        </div>

        {pending.length === 0 ? (
          <div className="notion-card p-8 text-center text-xs text-[#787774]">
            All communications approved or queue is clear.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {pending.map((msg, idx) => (
              <div key={idx} className="notion-card p-4 flex flex-col justify-between space-y-3">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="notion-pill-black text-[10px] font-mono">
                      {msg.message_id}
                    </span>
                    <span className="notion-tag font-medium">
                      {msg.client}
                    </span>
                  </div>

                  <div className="mt-2 text-xs text-[#787774] font-mono flex items-center gap-1">
                    <Mail className="w-3 h-3 text-[#9b9a97]" />
                    <span>To: {msg.recipient}</span>
                  </div>

                  <div className="mt-1.5 text-xs font-semibold text-[#191919]">
                    Subject: {msg.subject}
                  </div>

                  <div className="mt-2.5 bg-[#fbfbfa] p-3 rounded border border-[#ededeb] text-xs text-[#2f2f2f] whitespace-pre-wrap leading-relaxed">
                    {msg.body}
                  </div>

                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1">
                      {msg.citations.map((c, i) => (
                        <span key={i} className="text-[9px] font-mono px-1.5 py-0.2 bg-[#f1f1ef] text-[#787774] rounded">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="pt-2.5 border-t border-[#ededeb] flex items-center justify-between gap-2">
                  <button
                    onClick={() => {
                      setEditingMsg(msg);
                      setEditText(msg.body);
                    }}
                    className="px-2.5 py-1 rounded bg-[#ffffff] border border-[#d3d3d0] hover:bg-[#f1f1ef] text-[11px] font-medium text-[#242424] flex items-center gap-1"
                  >
                    <Edit3 className="w-3 h-3" /> Edit
                  </button>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleReject(msg.message_id)}
                      disabled={loading}
                      className="px-2.5 py-1 rounded bg-[#fff1f2] border border-[#fecdd3] hover:bg-[#ffe4e6] text-[11px] font-medium text-[#be123c] flex items-center gap-1"
                    >
                      <X className="w-3 h-3" /> Reject
                    </button>
                    <button
                      onClick={() => handleApproveSingle(msg.message_id)}
                      disabled={loading}
                      className="px-3 py-1 rounded bg-[#242424] hover:bg-[#111111] text-[11px] font-medium text-white flex items-center gap-1"
                    >
                      <Check className="w-3 h-3" /> Approve
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Dispatched History Table */}
      <div className="space-y-3 pt-4 border-t border-[#e8e8e6]">
        <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase flex items-center justify-between">
          <span>APPROVED & COMMITTED OUTBOX ({sent.length})</span>
          <span className="text-[10px] font-normal">outputs/comms_sent.jsonl</span>
        </div>

        {sent.length === 0 ? (
          <div className="notion-card p-6 text-center text-xs text-[#787774]">
            No dispatched notifications yet.
          </div>
        ) : (
          <div className="notion-card overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#fbfbfa] text-[#787774] font-mono text-[10px] uppercase border-b border-[#e8e8e6]">
                <tr>
                  <th className="p-3">Message ID</th>
                  <th className="p-3">Client</th>
                  <th className="p-3">Recipient</th>
                  <th className="p-3">Approved By</th>
                  <th className="p-3">Dispatched Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ededeb]">
                {sent.map((s, idx) => (
                  <tr key={idx} className="hover:bg-[#fbfbfa]">
                    <td className="p-3 font-mono font-semibold text-[#191919]">{s.message_id}</td>
                    <td className="p-3 text-[#242424]">{s.client}</td>
                    <td className="p-3 font-mono text-[#787774]">{s.recipient}</td>
                    <td className="p-3 text-[#15803d] font-medium">{s.approved_by || 'Senior Dispatcher'}</td>
                    <td className="p-3 text-[#787774] font-mono">{new Date(s.dispatched_at || s.approved_at || Date.now()).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editingMsg && (
        <div className="fixed inset-0 z-50 bg-[#191919]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#ffffff] rounded-lg border border-[#d3d3d0] max-w-lg w-full p-6 shadow-xl relative">
            <h3 className="text-base font-bold text-[#191919] serif-heading">
              Edit Notification Draft ({editingMsg.message_id})
            </h3>
            <p className="text-xs text-[#787774] mt-1 font-mono">
              To: {editingMsg.recipient}
            </p>

            <textarea
              value={editText}
              onChange={e => setEditText(e.target.value)}
              rows={8}
              className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded p-3 text-xs text-[#191919] mt-3 focus:outline-none focus:border-[#242424] font-sans"
            />

            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setEditingMsg(null)}
                className="px-3 py-1.5 rounded text-xs text-[#787774] hover:text-[#191919]"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={loading}
                className="px-4 py-1.5 rounded bg-[#242424] hover:bg-[#111111] text-white text-xs font-medium"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
