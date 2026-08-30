import React, { useState, useRef, useEffect } from 'react';
import { Send, ArrowRight, CornerDownLeft, X, ShieldAlert, Truck, Info, RotateCcw } from 'lucide-react';

const TOPIC_CHIPS = [
  { tag: 'S L A', title: 'Shakti Cement Protocol', query: "What is Shakti Cement's delivery window protocol?" },
  { tag: 'W I N T E R', title: 'Delhi NCR BS Stage', query: "Can a BS4 truck homed in Jaipur take a load to Gurgaon or Noida during December?" },
  { tag: 'H I L L S', title: 'Rudrapur / Nainital Route', query: "Can we dispatch a truck to Rudrapur in January if it had brake work 12 days ago?" },
  { tag: 'J U G A A D', title: 'Guddu 7-Day Boundary', query: "If mechanic Guddu did a temporary patch on a vehicle in Lucknow, can it be dispatched to Ambala?" },
  { tag: 'V E H I C L E', title: 'Vehicle UP40IM3144', query: "Why was UP40IM3144 grounded?" },
  { tag: 'P H A R M A', title: 'Orion Pharma Audit Rules', query: "Can a 2018 model Tata Prima truck carry an Orion Pharma pharmaceutical consignment?" },
];

const INITIAL_MESSAGE = {
  id: 'welcome',
  sender: 'assistant',
  text: "Namaste. I am **Rajender's Dispatch Brain**.\n\nAsk me any question regarding dispatch precedence, vehicle eligibility, or client constraints. I provide concise, grounded answers with citations.",
  citations: ["dispatcher_interview.txt", "fleet_master.csv", "maintenance_log.xlsx"],
  is_sufficient: true,
  timestamp: 'Active'
};

export default function RajenderBrain({ apiBase = 'http://127.0.0.1:8000' }) {
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem('meridian_chat_history');
      return saved ? JSON.parse(saved) : [INITIAL_MESSAGE];
    } catch {
      return [INITIAL_MESSAGE];
    }
  });

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamingMsgId, setStreamingMsgId] = useState(null);
  const [displayedTexts, setDisplayedTexts] = useState({});
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [selectedRule, setSelectedRule] = useState(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('meridian_chat_history', JSON.stringify(messages));
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, displayedTexts]);

  const handleClearHistory = () => {
    setMessages([INITIAL_MESSAGE]);
    setDisplayedTexts({});
    localStorage.removeItem('meridian_chat_history');
  };

  const streamText = (msgId, fullText) => {
    let index = 0;
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
    }, 45); // Smooth ChatGPT-style word streaming
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

    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput('');
    setLoading(true);

    const startTime = Date.now();

    try {
      // Build conversation history payload for contextual resolution
      const historyPayload = updatedMessages.slice(-6).map(m => ({
        sender: m.sender,
        text: m.text
      }));

      const fetchPromise = fetch(`${apiBase}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, history: historyPayload })
      }).then(r => r.json());

      // Ensure minimum 1.8 second typing animation delay
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

      setMessages(prev => [...prev, botMsg]);
      setLoading(false);

      // Start ChatGPT-style stream
      streamText(botMsgId, botMsg.text);

    } catch (err) {
      await new Promise(r => setTimeout(r, 1200));
      setLoading(false);
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'assistant',
          text: `Unable to connect to backend: ${err.message}.`,
          citations: [],
          is_sufficient: false,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-2">
      {/* Notion Avatar & Welcome Section */}
      <div className="flex items-start justify-between">
        <div className="space-y-3">
          <div className="w-14 h-14 rounded-full bg-[#f1f1ef] border border-[#e8e8e6] flex items-center justify-center text-2xl shadow-xs">
            👨🏽‍💼
          </div>

          <div>
            <h1 className="text-3xl font-bold tracking-tight text-[#191919] serif-heading">
              Hi, there!
            </h1>
            <p className="text-sm text-[#2f2f2f] mt-1 font-normal leading-relaxed">
              I'm <strong className="font-semibold text-[#111827]">Rajender's Dispatch Brain</strong>, preserving 18 years of unwritten freight logistics heuristics, dispatcher interview transcripts, and fleet maintenance memory.
            </p>
          </div>
        </div>

        {messages.length > 1 && (
          <button
            onClick={handleClearHistory}
            className="px-2.5 py-1 rounded bg-[#fbfbfa] border border-[#d3d3d0] hover:bg-[#f1f1ef] text-[#787774] hover:text-[#191919] text-xs font-mono flex items-center gap-1.5 transition-all mt-2"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset Context</span>
          </button>
        )}
      </div>

      {/* Quick Knowledge Topics Grid */}
      <div>
        <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase mb-3">
          QUICK OPERATIONAL KNOWLEDGE
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {TOPIC_CHIPS.map((chip, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(chip.query)}
              className="notion-card p-3 text-left flex items-start justify-between group hover:border-[#9b9a97] transition-all"
            >
              <div className="space-y-1">
                <span className="notion-tag text-[9px] font-mono uppercase tracking-wider">
                  {chip.tag}
                </span>
                <div className="text-xs font-semibold text-[#242424] group-hover:underline">
                  {chip.title}
                </div>
                <div className="text-[11px] text-[#787774] line-clamp-1">
                  {chip.query}
                </div>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-[#9b9a97] group-hover:text-[#242424] group-hover:translate-x-0.5 transition-all shrink-0 mt-1" />
            </button>
          ))}
        </div>
      </div>

      {/* Main Conversation Feed */}
      <div className="space-y-4 pt-2 border-t border-[#e8e8e6]">
        <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase flex items-center justify-between">
          <span>GROUNDED CONVERSATION WITH CONTEXT RETENTION</span>
          <span className="text-[10px] font-normal text-[#9b9a97]">{messages.length} messages</span>
        </div>

        <div className="space-y-3.5">
          {messages.map(msg => {
            const isStreamingThis = streamingMsgId === msg.id;
            const textToRender = displayedTexts[msg.id] !== undefined ? displayedTexts[msg.id] : msg.text;

            return (
              <div
                key={msg.id}
                className={`p-4 rounded-lg transition-all ${
                  msg.sender === 'user'
                    ? 'bg-[#f7f6f3] border border-[#ededeb] ml-8'
                    : 'bg-[#ffffff] border border-[#e8e8e6] mr-8'
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
                  <div className="mt-3 pt-2.5 border-t border-[#ededeb] flex flex-wrap items-center gap-2 animate-fade-in">
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

          {/* Clean 3-Dot Typing Animation (Shows for 2 seconds) */}
          {loading && (
            <div className="p-3.5 rounded-lg bg-[#fbfbfa] border border-[#ededeb] mr-8 w-fit flex items-center gap-1.5 shadow-xs">
              <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input Field */}
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

      {/* Vehicle Info Drawer/Modal */}
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
