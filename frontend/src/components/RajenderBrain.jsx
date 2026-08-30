import React, { useState, useRef, useEffect } from 'react';
import { Send, ArrowRight, BookOpen, FileText, ShieldAlert, Sparkles, CheckCircle2, CornerDownLeft } from 'lucide-react';

const TOPIC_CHIPS = [
  { tag: 'S L A', title: 'Shakti Cement Protocol', query: "What is Shakti Cement's delivery window protocol?" },
  { tag: 'W I N T E R', title: 'Delhi NCR BS Stage', query: "What is the policy for Delhi NCR winter operations regarding BS4 and BS6?" },
  { tag: 'H I L L S', title: 'Rudrapur / Nainital Route', query: "What are the rules for hill routes to Rudrapur and Nainital regarding heaters and brakes?" },
  { tag: 'J U G A A D', title: 'Guddu 7-Day Boundary', query: "Explain the 7-day Guddu jugaad temporary patch boundary rule." },
  { tag: 'P H A R M A', title: 'Orion Pharma Audit Rules', query: "What are Orion Pharma's vehicle age requirements and temperature rules?" },
  { tag: 'H U B', title: '50km Origin Hub Heuristic', query: "How does the 50km origin vs nearest hub selection rule work?" },
];

export default function RajenderBrain({ apiBase = 'http://127.0.0.1:8000' }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: "Namaste. I am **Rajender's Dispatch Brain**.\n\nAfter 18 years leading Meridian Freight's North India operations, all my heuristic notes, unwritten client agreements, mechanic logs, and fleet rules have been ingested into this grounded context layer. Ask me any question regarding dispatch precedence, vehicle eligibility, or client constraints. I will only answer factually with verified source citations.",
      citations: ["dispatcher_interview.txt", "fleet_master.csv", "maintenance_log.xlsx"],
      is_sufficient: true,
      timestamp: 'Active'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (queryText = input) => {
    const text = queryText.trim();
    if (!text || loading) return;

    const userMsg = {
      id: Date.now().toString(),
      sender: 'user',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${apiBase}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text })
      });
      const data = await res.json();

      const botMsg = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: data.answer || "No response received.",
        citations: data.citations || [],
        is_sufficient: data.is_sufficient !== false,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'assistant',
          text: `Unable to connect to Epsilon Engine: ${err.message}. Please verify the API backend is running.`,
          citations: [],
          is_sufficient: false,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-2">
      {/* Notion Avatar & Welcome Section (Matching provided image) */}
      <div className="space-y-4">
        {/* Hand-drawn minimalist Avatar SVG */}
        <div className="w-16 h-16 rounded-full bg-[#f1f1ef] border border-[#e8e8e6] flex items-center justify-center text-2xl">
          👨🏽‍💼
        </div>

        <div>
          <h1 className="text-3xl font-bold tracking-tight text-[#191919] serif-heading">
            Hi, there!
          </h1>
          <p className="text-base text-[#2f2f2f] mt-2 font-normal leading-relaxed">
            I'm <strong className="font-semibold text-[#111827]">Rajender's Dispatch Brain</strong>, preserving 18 years of unwritten freight logistics heuristics, dispatcher interview transcripts, client SLA protocols, and vehicle maintenance memory for Meridian Freight.
          </p>
          <p className="text-xs text-[#787774] mt-1 leading-relaxed">
            Whenever junior dispatchers need guidance on complex breakdown transshipments or route bans, I search the ingested corpus and provide grounded answers with exact line citations.
          </p>
        </div>
      </div>

      {/* Quick Knowledge Topics Grid (Notion styled like 'LATEST POST' / 'PROJECTS') */}
      <div>
        <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase mb-3">
          QUICK OPERATIONAL KNOWLEDGE & DISPATCH POLICIES
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {TOPIC_CHIPS.map((chip, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(chip.query)}
              className="notion-card p-3.5 text-left flex items-start justify-between group hover:border-[#9b9a97] transition-all"
            >
              <div className="space-y-1">
                <span className="notion-tag text-[10px] font-mono uppercase tracking-wider">
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
        <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase">
          GROUNDED CONVERSATION
        </div>

        <div className="space-y-4">
          {messages.map(msg => (
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

              <div className="text-xs text-[#2f2f2f] leading-relaxed whitespace-pre-wrap font-sans">
                {msg.text}
              </div>

              {/* Citations block */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-[#ededeb] flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] font-mono font-semibold text-[#787774] uppercase tracking-wider mr-1">
                    Citations:
                  </span>
                  {msg.citations.map((c, i) => (
                    <span
                      key={i}
                      className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#f7f6f3] border border-[#e8e8e6] text-[#242424]"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              )}

              {/* Insufficient Evidence Warning */}
              {msg.sender === 'assistant' && !msg.is_sufficient && (
                <div className="mt-2.5 pt-2 border-t border-amber-200 flex items-center gap-1 text-[11px] text-amber-700">
                  <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                  <span>Insufficient evidence in corpus to answer factually. Confident guessing is forbidden.</span>
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="p-4 rounded-lg bg-[#fbfbfa] border border-[#ededeb] mr-8 text-xs text-[#787774] flex items-center gap-3 animate-pulse">
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-[#191919] animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span className="font-mono text-[11px] text-[#242424]">
                Rajender's Brain is analyzing operational records & verifying citations...
              </span>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input Field (Notion minimalist) */}
      <div className="sticky bottom-4 bg-[#ffffff]/90 backdrop-blur-md pt-2">
        <div className="border border-[#d3d3d0] focus-within:border-[#242424] rounded-lg p-1.5 bg-[#ffffff] shadow-sm flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="Ask Rajender's Brain anything (e.g. 'Why was UP40IM3144 grounded?')..."
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
    </div>
  );
}
