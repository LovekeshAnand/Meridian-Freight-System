import React, { useState, useRef, useEffect } from 'react';
import { Send, ArrowRight, CornerDownLeft, X, ShieldAlert, Truck, Info, RotateCcw, MessageSquare, Plus, Trash2, CheckCircle2, FileText, Database } from 'lucide-react';

const KNOWLEDGE_TEST_PROMPTS = [
  { group: 'GREETINGS & INTRO', query: 'hi', desc: 'Assistant introduction & capabilities' },
  { group: 'VEHICLE DIAGNOSTIC', query: 'Why was UP40IM3144 grounded?', desc: 'Overdue service grounding check (>30d)' },
  { group: 'CLIENT SLA OVERRIDE', query: "What is Shakti Cement's delivery window protocol?", desc: '36h operational vs 48h paper contract' },
  { group: 'WINTER POLLUTION BAN', query: 'Can a BS4 truck homed in Jaipur take a load to Gurgaon or Noida during December?', desc: 'Delhi NCR winter GRAP BS6 restriction' },
  { group: 'HILL ROUTE & BRAKES', query: 'Can we dispatch a truck to Rudrapur in January if it had brake work 12 days ago?', desc: 'Engine heater + 30-day flat running rule' },
  { group: 'MECHANIC PATCH LOCK', query: 'If mechanic Guddu did a temporary patch on a vehicle in Lucknow, can it be dispatched to Ambala?', desc: '7-day timer & home region restriction' },
  { group: 'GATE CLOSING PROTOCOL', query: 'What happens if a Vertex Retail consignment will reach the Ludhiana warehouse gate at 6:30 PM?', desc: '6:00 PM gate hold & penalty prevention' },
  { group: 'INCIDENT ROTATION', query: 'If a vehicle breaks down on an Apex Chemicals run, can we assign the same vehicle on their next shipment?', desc: 'Mandatory vehicle plate rotation' },
  { group: 'COLD CHAIN & AGE', query: 'Can a 2018 model Tata Prima truck carry an Orion Pharma pharmaceutical consignment?', desc: '2020+ model year & cold chain rule' },
];

const INITIAL_MESSAGE = {
  id: 'welcome',
  sender: 'assistant',
  text: "Namaste! I am **Rajender's Dispatch Brain**.\n\nI have ingested all 18 years of operational rules, client SLAs, mechanic logs, and fleet registers. Ask me any question or pick a verified test query from the sidebar.",
  citations: ["dispatcher_interview.txt", "fleet_master.csv", "maintenance_log.xlsx"],
  is_sufficient: true,
  timestamp: 'Active'
};

export default function RajenderBrain({ apiBase = 'http://127.0.0.1:8000' }) {
  // Chat threads stored in state & localStorage
  const [threads, setThreads] = useState(() => {
    try {
      const saved = localStorage.getItem('meridian_threads_v2');
      return saved ? JSON.parse(saved) : [{ id: 'default', title: 'Main Dispatch Session', messages: [INITIAL_MESSAGE], updatedAt: Date.now() }];
    } catch {
      return [{ id: 'default', title: 'Main Dispatch Session', messages: [INITIAL_MESSAGE], updatedAt: Date.now() }];
    }
  });

  const [activeThreadId, setActiveThreadId] = useState('default');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamingMsgId, setStreamingMsgId] = useState(null);
  const [displayedTexts, setDisplayedTexts] = useState({});
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [selectedRule, setSelectedRule] = useState(null);
  const chatEndRef = useRef(null);

  const activeThread = threads.find(t => t.id === activeThreadId) || threads[0];

  useEffect(() => {
    localStorage.setItem('meridian_threads_v2', JSON.stringify(threads));
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [threads, displayedTexts]);

  const handleCreateNewThread = () => {
    const newId = `thread_${Date.now()}`;
    const newThread = {
      id: newId,
      title: `Session ${threads.length + 1}`,
      messages: [INITIAL_MESSAGE],
      updatedAt: Date.now()
    };
    setThreads(prev => [newThread, ...prev]);
    setActiveThreadId(newId);
    setDisplayedTexts({});
  };

  const handleDeleteThread = (threadId, e) => {
    e.stopPropagation();
    if (threads.length <= 1) {
      handleCreateNewThread();
      return;
    }
    const remaining = threads.filter(t => t.id !== threadId);
    setThreads(remaining);
    if (activeThreadId === threadId) {
      setActiveThreadId(remaining[0].id);
    }
  };

  const streamText = (msgId, fullText) => {
    setStreamingMsgId(msgId);
    setDisplayedTexts(prev => ({ ...prev, [msgId]: '' }));

    const words = fullText.split(' ');
    let currentWordIdx = 0;

    const interval = setInterval(() => {
      if (currentWordIdx < words.length) {
        currentWordIdx++;
        const partial = words.slice(0, currentWordIdx).join(' ');
        setDisplayedTexts(prev => ({ ...prev, [msgId]: partial }));
      } else {
        clearInterval(interval);
        setStreamingMsgId(null);
        setDisplayedTexts(prev => ({ ...prev, [msgId]: fullText }));
      }
    }, 35); // Smooth word stream
  };

  const handleSend = async (queryText = input) => {
    const text = queryText.trim();
    if (!text || loading) return;

    const userMsg = {
      id: Date.now().toString(),
      sender: 'user',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    const currentMessages = activeThread.messages || [];
    const updatedMessages = [...currentMessages, userMsg];

    // Update thread in state
    setThreads(prev => prev.map(t => {
      if (t.id === activeThread.id) {
        return {
          ...t,
          title: t.title === 'Main Dispatch Session' || t.title.startsWith('Session') ? (text.slice(0, 24) + (text.length > 24 ? '...' : '')) : t.title,
          messages: updatedMessages,
          updatedAt: Date.now()
        };
      }
      return t;
    }));

    setInput('');
    setLoading(true);

    try {
      const historyPayload = updatedMessages.slice(-6).map(m => ({
        sender: m.sender,
        text: m.text
      }));

      const fetchPromise = fetch(`${apiBase}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, history: historyPayload })
      }).then(r => r.json());

      // 1.8s realistic typing indicator
      const minDelayPromise = new Promise(resolve => setTimeout(resolve, 1800));

      const [data] = await Promise.all([fetchPromise, minDelayPromise]);

      const botMsgId = (Date.now() + 1).toString();
      const botMsg = {
        id: botMsgId,
        sender: 'assistant',
        text: data.answer || "No response received.",
        citations: data.citations || [],
        is_sufficient: data.is_sufficient !== false,
        rule_code: data.rule_code,
        rule_name: data.rule_name,
        vehicle_data: data.vehicle_data,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setThreads(prev => prev.map(t => {
        if (t.id === activeThread.id) {
          return {
            ...t,
            messages: [...updatedMessages, botMsg],
            updatedAt: Date.now()
          };
        }
        return t;
      }));

      setLoading(false);
      streamText(botMsgId, botMsg.text);

    } catch (err) {
      await new Promise(r => setTimeout(r, 1000));
      setLoading(false);
      const errorMsg = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `Unable to connect to backend: ${err.message}. Please ensure the server is running on port 8000.`,
        citations: [],
        is_sufficient: false,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setThreads(prev => prev.map(t => {
        if (t.id === activeThread.id) {
          return { ...t, messages: [...updatedMessages, errorMsg] };
        }
        return t;
      }));
    }
  };

  return (
    <div className="max-w-7xl mx-auto flex flex-col md:flex-row gap-6 py-2">
      {/* ── Left Sidebar (Sessions & Knowledge Test Explorer) ────────────────── */}
      <aside className="w-full md:w-72 shrink-0 space-y-4">
        {/* New Session Button */}
        <button
          onClick={handleCreateNewThread}
          className="w-full py-2 px-3 rounded-md bg-[#242424] hover:bg-[#111111] text-white text-xs font-medium flex items-center justify-between transition-all shadow-xs"
        >
          <span className="flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5" />
            <span>New Dispatch Thread</span>
          </span>
          <span className="text-[10px] font-mono text-slate-400">Ctrl+N</span>
        </button>

        {/* Sessions List */}
        <div className="notion-card p-3 space-y-2">
          <div className="text-[10px] font-mono font-semibold tracking-wider text-[#787774] uppercase flex items-center justify-between">
            <span>SAVED SESSIONS</span>
            <span className="text-[9px]">{threads.length}</span>
          </div>

          <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
            {threads.map(t => {
              const isSelected = t.id === activeThreadId;
              return (
                <div
                  key={t.id}
                  onClick={() => {
                    setActiveThreadId(t.id);
                    setDisplayedTexts({});
                  }}
                  className={`p-2 rounded-md text-xs cursor-pointer flex items-center justify-between group transition-all ${
                    isSelected
                      ? 'bg-[#f1f1ef] text-[#191919] font-medium'
                      : 'text-[#5a5a58] hover:bg-[#fbfbfa] hover:text-[#191919]'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate pr-1">
                    <MessageSquare className="w-3.5 h-3.5 text-[#787774] shrink-0" />
                    <span className="truncate">{t.title}</span>
                  </div>
                  {threads.length > 1 && (
                    <button
                      onClick={(e) => handleDeleteThread(t.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-[#be123c] rounded transition-opacity"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Verified Knowledge Test Prompts (1-Click Test Sandbox) */}
        <div className="notion-card p-3 space-y-2">
          <div className="text-[10px] font-mono font-semibold tracking-wider text-[#787774] uppercase">
            VERIFIED GROUNDING PROMPTS
          </div>
          <p className="text-[11px] text-[#787774] leading-relaxed">
            Click any operational test below to test Rajender's Brain over the ingested corpus:
          </p>

          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {KNOWLEDGE_TEST_PROMPTS.map((item, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(item.query)}
                className="w-full text-left p-2 rounded-md hover:bg-[#fbfbfa] border border-transparent hover:border-[#ededeb] transition-all group"
              >
                <div className="text-[9px] font-mono uppercase font-semibold text-[#787774] group-hover:text-[#191919]">
                  {item.group}
                </div>
                <div className="text-xs text-[#242424] font-medium line-clamp-1 mt-0.5 group-hover:underline">
                  {item.query}
                </div>
                <div className="text-[10px] text-[#9b9a97] line-clamp-1">
                  {item.desc}
                </div>
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* ── Main Chat Area ─────────────────────────────────────────────────── */}
      <main className="flex-1 space-y-6">
        {/* Header Intro Banner */}
        <div className="pb-4 border-b border-[#e8e8e6] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#f1f1ef] border border-[#e8e8e6] flex items-center justify-center text-lg">
              👨🏽‍💼
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-[#191919] serif-heading">
                  Rajender's Dispatch Brain
                </h2>
                <span className="notion-tag font-mono text-[9px] uppercase">
                  Active Thread
                </span>
              </div>
              <p className="text-xs text-[#787774]">
                Multi-turn context retention active. Pronouns and follow-ups resolve automatically.
              </p>
            </div>
          </div>
        </div>

        {/* Conversation Feed */}
        <div className="space-y-3.5 min-h-[360px]">
          {(activeThread.messages || []).map(msg => {
            const isStreamingThis = streamingMsgId === msg.id;
            const textToRender = displayedTexts[msg.id] !== undefined ? displayedTexts[msg.id] : msg.text;

            return (
              <div
                key={msg.id}
                className={`p-4 rounded-lg transition-all ${
                  msg.sender === 'user'
                    ? 'bg-[#f7f6f3] border border-[#ededeb] ml-6'
                    : 'bg-[#ffffff] border border-[#e8e8e6] mr-6 shadow-2xs'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-0.5 rounded ${
                    msg.sender === 'user'
                      ? 'bg-[#242424] text-white'
                      : 'bg-[#f1f1ef] text-[#5a5a58]'
                  }`}>
                    {msg.sender === 'user' ? 'DISPATCHER QUERY' : "RAJENDER'S BRAIN"}
                  </span>
                  <span className="text-[10px] font-mono text-[#9b9a97]">{msg.timestamp}</span>
                </div>

                {/* Direct Concise Answer with Typewriter stream */}
                <div className="text-xs text-[#2f2f2f] leading-relaxed whitespace-pre-wrap font-sans">
                  {textToRender}
                  {isStreamingThis && (
                    <span className="inline-block w-1.5 h-3 bg-[#191919] ml-0.5 animate-pulse" />
                  )}
                </div>

                {/* Interactive Rule Button & Vehicle Info Button (Appears once stream finishes) */}
                {!isStreamingThis && (msg.rule_code || msg.vehicle_data) && (
                  <div className="mt-3 pt-2.5 border-t border-[#ededeb] flex flex-wrap items-center gap-2">
                    {msg.rule_code && (
                      <button
                        onClick={() => setSelectedRule({ code: msg.rule_code, name: msg.rule_name })}
                        className="px-2.5 py-1 rounded bg-[#242424] hover:bg-[#111111] text-white font-mono text-[10px] font-semibold flex items-center gap-1.5 transition-all shadow-xs"
                      >
                        <span>{msg.rule_code}</span>
                        <Info className="w-3 h-3 opacity-70" />
                      </button>
                    )}

                    {msg.vehicle_data && (
                      <button
                        onClick={() => setSelectedVehicle(msg.vehicle_data)}
                        className="px-2.5 py-1 rounded bg-[#ffffff] border border-[#d3d3d0] hover:bg-[#f1f1ef] text-[#242424] font-medium text-[11px] flex items-center gap-1.5 transition-all shadow-xs"
                      >
                        <Truck className="w-3 h-3 text-[#787774]" />
                        <span>More Info on {msg.vehicle_data.reg}</span>
                      </button>
                    )}
                  </div>
                )}

                {/* Citations block */}
                {!isStreamingThis && msg.citations && msg.citations.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                    <span className="text-[9px] font-mono font-semibold text-[#787774] uppercase tracking-wider mr-1">
                      Citations:
                    </span>
                    {msg.citations.map((c, i) => (
                      <span
                        key={i}
                        className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#f7f6f3] border border-[#e8e8e6] text-[#242424]"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}

                {/* Insufficient Evidence Warning */}
                {!isStreamingThis && msg.sender === 'assistant' && !msg.is_sufficient && (
                  <div className="mt-2.5 pt-2 border-t border-amber-200 flex items-center gap-1 text-[11px] text-amber-700">
                    <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                    <span>Insufficient evidence in corpus to answer factually. Confident guessing is forbidden.</span>
                  </div>
                )}
              </div>
            );
          })}

          {/* Clean 3-Dot Typing Animation */}
          {loading && (
            <div className="p-3.5 rounded-lg bg-[#fbfbfa] border border-[#ededeb] mr-6 w-fit flex items-center gap-1.5 shadow-xs">
              <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input Bar */}
        <div className="sticky bottom-4 bg-[#ffffff]/90 backdrop-blur-md pt-2">
          <div className="border border-[#d3d3d0] focus-within:border-[#242424] rounded-lg p-1.5 bg-[#ffffff] shadow-sm flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder="Ask Rajender's Brain anything (or follow up on previous answers)..."
              className="flex-1 px-3 py-2 text-xs text-[#191919] placeholder-[#9b9a97] bg-transparent focus:outline-none"
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="px-3.5 py-1.5 rounded bg-[#242424] hover:bg-[#111111] disabled:opacity-30 text-white text-xs font-medium flex items-center gap-1.5 transition-all"
            >
              <span>Ask</span>
              <CornerDownLeft className="w-3 h-3" />
            </button>
          </div>
        </div>
      </main>

      {/* Vehicle Info Modal */}
      {selectedVehicle && (
        <div className="fixed inset-0 z-50 bg-[#191919]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#ffffff] rounded-lg border border-[#d3d3d0] max-w-md w-full p-6 shadow-xl relative max-h-[85vh] overflow-y-auto">
            <button
              onClick={() => setSelectedVehicle(null)}
              className="absolute top-4 right-4 p-1.5 text-[#787774] hover:text-[#191919] rounded hover:bg-[#f1f1ef]"
            >
              <X className="w-4 h-4" />
            </button>

            <span className="notion-pill-black font-mono text-[10px]">
              {selectedVehicle.reg}
            </span>

            <h3 className="text-lg font-bold text-[#191919] serif-heading mt-2">
              Vehicle Specifications & Maintenance Profile
            </h3>

            <div className="mt-4 space-y-2.5 text-xs">
              <div className="grid grid-cols-2 gap-2 bg-[#f7f6f3] p-3 rounded-lg border border-[#ededeb]">
                <div>
                  <div className="text-[10px] text-[#787774] uppercase font-mono">Model</div>
                  <div className="font-semibold text-[#191919] mt-0.5">{selectedVehicle.model}</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#787774] uppercase font-mono">Manufacturing Year</div>
                  <div className="font-semibold text-[#191919] mt-0.5">{selectedVehicle.year}</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#787774] uppercase font-mono">Emission Standard</div>
                  <div className="font-semibold text-[#191919] mt-0.5">{selectedVehicle.bs_stage}</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#787774] uppercase font-mono">Home Hub</div>
                  <div className="font-semibold text-[#191919] mt-0.5">{selectedVehicle.home_hub}</div>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[#ffffff] border border-[#e8e8e6] space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-[#787774]">Engine Heater:</span>
                  <span className="font-medium text-[#191919]">{selectedVehicle.engine_heater === 'Yes' ? 'Installed (Cold Start Capable)' : 'None'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[#787774]">Latest Routine Service:</span>
                  <span className="font-mono text-[#191919]">{selectedVehicle.latest_service_date}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[#787774]">Maintenance Status:</span>
                  {selectedVehicle.is_overdue ? (
                    <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-[#fee2e2] text-[#991b1b] border border-[#fecaca]">
                      Overdue (&gt;30d) - Grounded
                    </span>
                  ) : (
                    <span className="text-[#15803d] font-medium">Up to Date</span>
                  )}
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[#787774]">Guddu Jugaad Temporary Patch:</span>
                  {selectedVehicle.has_active_jugaad ? (
                    <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
                      Active (7-Day Clock)
                    </span>
                  ) : (
                    <span className="text-[#787774]">None</span>
                  )}
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[#787774]">Recent Brake Work:</span>
                  {selectedVehicle.brake_work_in_last_30d ? (
                    <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
                      &lt;30 Days (Hill Restricted)
                    </span>
                  ) : (
                    <span className="text-[#787774]">None in 30d</span>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                onClick={() => setSelectedVehicle(null)}
                className="px-4 py-1.5 rounded bg-[#242424] text-white text-xs font-medium"
              >
                Close Profile
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rule Detail Modal */}
      {selectedRule && (
        <div className="fixed inset-0 z-50 bg-[#191919]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#ffffff] rounded-lg border border-[#d3d3d0] max-w-md w-full p-6 shadow-xl relative">
            <button
              onClick={() => setSelectedRule(null)}
              className="absolute top-4 right-4 p-1.5 text-[#787774] hover:text-[#191919] rounded hover:bg-[#f1f1ef]"
            >
              <X className="w-4 h-4" />
            </button>

            <span className="notion-pill-black font-mono text-[10px]">
              {selectedRule.code}
            </span>

            <h3 className="text-lg font-bold text-[#191919] serif-heading mt-2">
              {selectedRule.name}
            </h3>

            <p className="text-xs text-[#2f2f2f] mt-3 leading-relaxed bg-[#f7f6f3] p-3 rounded border border-[#ededeb]">
              This dispatch heuristic is sourced directly from Rajender's lead dispatcher operational interview and internal fleet maintenance logbooks. It is strictly enforced by the automated breakdown pipeline.
            </p>

            <div className="mt-5 flex justify-end">
              <button
                onClick={() => setSelectedRule(null)}
                className="px-4 py-1.5 rounded bg-[#242424] text-white text-xs font-medium"
              >
                Close Rule Info
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
