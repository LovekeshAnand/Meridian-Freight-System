import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, ArrowRight, CornerDownLeft, X, ShieldAlert, Truck, Info, RotateCcw, 
  MessageSquare, Plus, Trash2, CheckCircle2, FileText, Database, Paperclip, 
  UploadCloud, Check, FileCode, AlertTriangle, Layers, Clock, ShieldCheck, Mail
} from 'lucide-react';

const KNOWLEDGE_TEST_PROMPTS = [
  { group: 'GREETINGS & INTRO', query: 'hi', desc: 'Assistant introduction & capabilities' },
  { group: 'HILL ROUTE DILEMMA', query: 'We need to dispatch an emergency transshipment to Nainital in mid-January. We have two trucks at Ambala: Truck A is a 2021 BS6 with an engine heater installed, but had brake pad work done 18 days ago. Truck B is a 2020 BS6 with no engine heater and 60 days since its last brake service. Which truck, if either, is eligible for dispatch under our hill route policy, and why?', desc: 'Engine heater + 30-day flat running rule' },
  { group: 'ORION PHARMA AUDIT', query: 'An Orion Pharma audit team is reviewing our vehicle selection for a temperature-sensitive vaccine batch. A dispatcher proposed a 2019 BharatBenz truck with active refrigeration and up-to-date maintenance. Will this pass the Orion Pharma audit, and what specific documentation is required?', desc: '2020+ model year & cold chain rule' },
  { group: 'APEX ROTATION & BS4', query: 'A BS4 truck suffered a breakdown on an Apex Chemicals run from Delhi to Jaipur. After repairs at Jaipur, operations wants to dispatch this same truck on an Apex Chemicals load returning to Delhi in November. What two independent operational policies prohibit this dispatch?', desc: 'Incident rotation + Winter GRAP ban' },
  { group: '50KM ORIGIN BOUNDARY', query: 'A breakdown occurs on the highway between Gurgaon and Jaipur, exactly 54 km away from Gurgaon origin hub and 180 km away from Jaipur. The supervisor argues we should dispatch from Gurgaon because it is the closest hub in distance, but what does our 50km dispatch rule mandate?', desc: 'Origin lock (<=50km) vs Nearest hub (>50km)' },
  { group: 'DRIVER NIGHT ROSTER', query: 'Can a newly hired driver with 3 months of tenure drive a solo morning dispatch from Delhi to Ambala departing at 7:00 AM, if the return leg involves driving back to Delhi at 9:30 PM?', desc: '<6 months solo night driving ban' },
  { group: 'GATE CLOSING PROTOCOL', query: 'What happens if a Vertex Retail consignment will reach the Ludhiana warehouse gate at 6:30 PM?', desc: '6:00 PM gate hold & penalty prevention' },
];

const INITIAL_MESSAGE = {
  id: 'welcome',
  sender: 'assistant',
  text: "Namaste! I am **Rajender's Dispatch Brain**.\n\nI have ingested all 18 years of operational rules, client SLAs, mechanic logs, and fleet registers.\n\nAsk me any operational question, pick a test prompt from the left, or **click the `+` button in the prompt bar to attach and process incident tickets in ANY format (JSON, CSV, TXT, Excel)**.",
  citations: ["dispatcher_interview.txt", "fleet_master.csv", "maintenance_log.xlsx"],
  is_sufficient: true,
  timestamp: 'Active'
};

export default function RajenderBrain({ apiBase = 'http://127.0.0.1:8000' }) {
  // Chat threads stored in state & localStorage
  const [threads, setThreads] = useState(() => {
    try {
      const saved = localStorage.getItem('meridian_threads_v3');
      return saved ? JSON.parse(saved) : [{ id: 'default', title: 'Main Dispatch Session', messages: [INITIAL_MESSAGE], updatedAt: Date.now() }];
    } catch {
      return [{ id: 'default', title: 'Main Dispatch Session', messages: [INITIAL_MESSAGE], updatedAt: Date.now() }];
    }
  });

  const [activeThreadId, setActiveThreadId] = useState(() => {
    return threads[0]?.id || 'default';
  });

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedRule, setSelectedRule] = useState(null);
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [displayedTexts, setDisplayedTexts] = useState({});
  const [approvedComms, setApprovedComms] = useState({});
  
  // Document Attachment State
  const [attachedFile, setAttachedFile] = useState(null);
  const fileInputRef = useRef(null);

  const chatEndRef = useRef(null);
  const streamingTimersRef = useRef({});

  // Sync threads to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('meridian_threads_v3', JSON.stringify(threads));
    } catch (e) {
      console.error("Failed to save threads", e);
    }
  }, [threads]);

  const activeThread = threads.find(t => t.id === activeThreadId) || threads[0];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeThread?.messages, displayedTexts, loading, attachedFile]);

  // Clean Typewriter streaming animation
  const streamText = (msgId, fullText) => {
    if (!fullText) return;
    
    if (streamingTimersRef.current[msgId]) {
      clearInterval(streamingTimersRef.current[msgId]);
    }

    const words = fullText.split(' ');
    let currentIndex = 0;
    
    setDisplayedTexts(prev => ({ ...prev, [msgId]: '' }));

    const timer = setInterval(() => {
      currentIndex += 2;
      if (currentIndex >= words.length) {
        setDisplayedTexts(prev => ({ ...prev, [msgId]: fullText }));
        clearInterval(timer);
        delete streamingTimersRef.current[msgId];
      } else {
        setDisplayedTexts(prev => ({
          ...prev,
          [msgId]: words.slice(0, currentIndex).join(' ')
        }));
      }
    }, 28);

    streamingTimersRef.current[msgId] = timer;
  };

  const handleCreateNewThread = () => {
    const newId = `thread_${Date.now()}`;
    const newThread = {
      id: newId,
      title: `Dispatch Thread #${threads.length + 1}`,
      messages: [INITIAL_MESSAGE],
      updatedAt: Date.now()
    };
    setThreads(prev => [newThread, ...prev]);
    setActiveThreadId(newId);
    setDisplayedTexts({});
    setAttachedFile(null);
  };

  const handleDeleteThread = (id, e) => {
    e.stopPropagation();
    if (threads.length <= 1) return;
    const remaining = threads.filter(t => t.id !== id);
    setThreads(remaining);
    if (activeThreadId === id) {
      setActiveThreadId(remaining[0].id);
      setDisplayedTexts({});
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setAttachedFile(file);
    }
  };

  const handleApproveComms = async (msgId, messageId) => {
    try {
      await fetch(`${apiBase}/api/comms/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, approved_by: 'Lead Dispatcher' })
      });
      setApprovedComms(prev => ({ ...prev, [messageId]: true }));
    } catch (e) {
      alert(`Approval error: ${e.message}`);
    }
  };

  const handleSend = async (customPrompt) => {
    const text = customPrompt !== undefined ? customPrompt : input;
    if (!text.trim() && !attachedFile) return;

    const userMsgId = Date.now().toString();
    const userMsg = {
      id: userMsgId,
      sender: 'user',
      text: text || (attachedFile ? `Attached file for processing: ${attachedFile.name}` : ''),
      attached_filename: attachedFile ? attachedFile.name : null,
      attached_filesize: attachedFile ? `${(attachedFile.size / 1024).toFixed(1)} KB` : null,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    const updatedMessages = [...activeThread.messages, userMsg];

    // Auto update thread title if first query
    const threadTitle = activeThread.messages.length <= 1 
      ? (text ? (text.slice(0, 32) + (text.length > 32 ? '...' : '')) : (attachedFile?.name || 'Document Analysis'))
      : activeThread.title;

    setThreads(prev => prev.map(t => {
      if (t.id === activeThread.id) {
        return {
          ...t,
          title: threadTitle,
          messages: updatedMessages,
          updatedAt: Date.now()
        };
      }
      return t;
    }));

    const fileToUpload = attachedFile;
    setInput('');
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setLoading(true);

    try {
      let data;
      const minDelayPromise = new Promise(resolve => setTimeout(resolve, 1500));

      if (fileToUpload) {
        // Document analysis endpoint
        const formData = new FormData();
        formData.append('file', fileToUpload);
        if (text) formData.append('question', text);

        const fetchPromise = fetch(`${apiBase}/api/tickets/analyze-document`, {
          method: 'POST',
          body: formData
        }).then(r => r.json());

        const [res] = await Promise.all([fetchPromise, minDelayPromise]);
        data = res;

        const botMsgId = (Date.now() + 1).toString();
        const primaryAnalysis = data.analyses?.[0];

        const botMsg = {
          id: botMsgId,
          sender: 'assistant',
          is_document_analysis: true,
          filename: data.filename,
          total_tickets: data.total_tickets,
          drift_alerts: data.drift_alerts,
          analyses: data.analyses || [],
          text: primaryAnalysis?.llm_analysis || `Processed ${data.total_tickets} ticket(s) from ${data.filename}.`,
          citations: primaryAnalysis?.citations || ["dispatcher_interview.txt", "fleet_master.csv"],
          is_sufficient: true,
          model_used: primaryAnalysis?.model_used || 'qwen2.5:3b',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };

        setThreads(prev => prev.map(t => {
          if (t.id === activeThread.id) {
            return { ...t, messages: [...updatedMessages, botMsg], updatedAt: Date.now() };
          }
          return t;
        }));

        setLoading(false);
        streamText(botMsgId, botMsg.text);

      } else {
        // Natural language query endpoint
        const historyPayload = updatedMessages.slice(-6).map(m => ({
          sender: m.sender,
          text: m.text
        }));

        const fetchPromise = fetch(`${apiBase}/api/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: text, history: historyPayload })
        }).then(r => r.json());

        const [res] = await Promise.all([fetchPromise, minDelayPromise]);
        data = res;

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
          model_used: data.model_used,
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
      }

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

  // Sample Ticket Injector for 1-Click Testing
  const handleLoadSampleTicket = (format) => {
    let sampleContent, sampleFilename;
    if (format === 'json') {
      sampleFilename = 'sample_breakdown_tkt.json';
      sampleContent = JSON.stringify([{
        ticket_id: "TKT-EMERG-801",
        client: "Shakti Cement",
        vehicle: "UP17GN7381",
        origin_hub: "Gurgaon",
        destination: "Ludhiana",
        km_from_origin_hub: 42,
        issue: "Severe radiator leakage and engine overheating on NH44",
        severity: "HIGH"
      }], null, 2);
    } else {
      sampleFilename = 'sample_tickets_batch.csv';
      sampleContent = "ticket_id,client,vehicle,origin_hub,destination,km_from_origin_hub,issue\nTKT-901,Vertex Retail,HR55GV5088,Ludhiana,Delhi,68,Alternator malfunction at highway toll\nTKT-902,Apex Chemicals,RJ43DD3546,Jaipur,Kanpur,14,Brake failure on slip road";
    }

    const blob = new Blob([sampleContent], { type: format === 'json' ? 'application/json' : 'text/csv' });
    const file = new File([blob], sampleFilename, { type: format === 'json' ? 'application/json' : 'text/csv' });
    setAttachedFile(file);
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

        {/* 1-Click Sample Ticket Attachment Tools */}
        <div className="notion-card p-3 space-y-2">
          <div className="text-[10px] font-mono font-semibold tracking-wider text-[#787774] uppercase flex items-center gap-1.5">
            <Paperclip className="w-3 h-3 text-[#242424]" />
            <span>TICKET INGESTION SANDBOX</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 pt-1">
            <button
              onClick={() => handleLoadSampleTicket('json')}
              className="px-2 py-1.5 rounded bg-[#f7f6f3] hover:bg-[#ebeae6] border border-[#e8e8e6] text-[11px] font-mono text-[#242424] flex items-center gap-1 transition-all"
            >
              <FileCode className="w-3 h-3 text-indigo-600" />
              <span>Sample JSON</span>
            </button>
            <button
              onClick={() => handleLoadSampleTicket('csv')}
              className="px-2 py-1.5 rounded bg-[#f7f6f3] hover:bg-[#ebeae6] border border-[#e8e8e6] text-[11px] font-mono text-[#242424] flex items-center gap-1 transition-all"
            >
              <FileText className="w-3 h-3 text-emerald-600" />
              <span>Sample CSV</span>
            </button>
          </div>
        </div>

        {/* Verified Knowledge Test Prompts */}
        <div className="notion-card p-3 space-y-2">
          <div className="text-[10px] font-mono font-semibold tracking-wider text-[#787774] uppercase flex items-center justify-between">
            <span>VERIFIED TEST BENCH</span>
            <span className="text-[9px] text-[#059669] font-semibold">100% Grounded</span>
          </div>

          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {KNOWLEDGE_TEST_PROMPTS.map((p, i) => (
              <div
                key={i}
                onClick={() => handleSend(p.query)}
                className="p-2 rounded border border-[#f0efe9] bg-[#ffffff] hover:bg-[#f7f6f3] cursor-pointer transition-all group"
              >
                <div className="text-[9px] font-mono font-semibold text-[#0284c7] uppercase">
                  {p.group}
                </div>
                <div className="text-xs text-[#242424] font-medium line-clamp-2 mt-0.5 group-hover:text-[#000000]">
                  {p.query}
                </div>
                <div className="text-[10px] text-[#787774] mt-0.5 truncate">
                  {p.desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* ── Main Chat Area ───────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col h-[82vh] notion-card overflow-hidden">
        {/* Chat Stream Viewport */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {activeThread.messages.map((msg) => {
            const isStreamingThis = displayedTexts[msg.id] !== undefined && displayedTexts[msg.id] !== msg.text;
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
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-0.5 rounded ${
                      msg.sender === 'user'
                        ? 'bg-[#242424] text-white'
                        : 'bg-[#f1f1ef] text-[#5a5a58]'
                    }`}>
                      {msg.sender === 'user' ? 'DISPATCHER QUERY' : "RAJENDER'S BRAIN"}
                    </span>
                    {msg.sender === 'assistant' && msg.model_used && (
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        <span>{msg.model_used}</span>
                      </span>
                    )}
                    {msg.is_document_analysis && (
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center gap-1">
                        <FileText className="w-3 h-3" />
                        <span>{msg.filename}</span>
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] font-mono text-[#9b9a97]">{msg.timestamp}</span>
                </div>

                {/* User Attached Document Preview */}
                {msg.attached_filename && (
                  <div className="mb-2 p-2 rounded bg-white border border-[#e8e8e6] flex items-center justify-between text-xs w-fit">
                    <div className="flex items-center gap-1.5 font-mono text-[#242424]">
                      <Paperclip className="w-3.5 h-3.5 text-indigo-600" />
                      <span>{msg.attached_filename}</span>
                    </div>
                    {msg.attached_filesize && (
                      <span className="text-[10px] text-[#787774] ml-3">{msg.attached_filesize}</span>
                    )}
                  </div>
                )}

                {/* Document Multi-Ticket Detailed Analysis Cards */}
                {msg.is_document_analysis && msg.analyses && msg.analyses.length > 0 && (
                  <div className="space-y-4 my-3">
                    {msg.analyses.map((analysis, idx) => {
                      const t = analysis.ticket;
                      const wo = analysis.work_order;
                      const quar = analysis.quarantine;
                      const comms = analysis.comms_pending;
                      const isApproved = comms && approvedComms[comms.message_id];

                      return (
                        <div key={idx} className="p-3.5 rounded-lg border border-[#e2e1dc] bg-[#faf9f6] space-y-3">
                          {/* Ticket Header & Status */}
                          <div className="flex items-center justify-between border-b border-[#ededeb] pb-2">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-[#191919]">{t.ticket_id}</span>
                              <span className="text-xs px-2 py-0.5 rounded bg-white border border-[#d3d3d0] font-medium text-[#242424]">
                                {t.client}
                              </span>
                              <span className="text-xs font-mono text-[#787774]">
                                {t.origin_hub} → {t.destination} ({t.km_from_origin_hub || 0} km)
                              </span>
                            </div>
                            <div>
                              {wo ? (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3" />
                                  <span>WORK ORDER GENERATED</span>
                                </span>
                              ) : quar ? (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-300 flex items-center gap-1">
                                  <AlertTriangle className="w-3 h-3" />
                                  <span>QUARANTINED</span>
                                </span>
                              ) : null}
                            </div>
                          </div>

                          {/* Breakdown Decision Grid */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                            <div className="p-2.5 rounded bg-white border border-[#ededeb]">
                              <div className="text-[10px] font-mono text-[#787774] uppercase">BROKEN VEHICLE & INCIDENT</div>
                              <div className="font-mono font-semibold text-[#be123c] mt-0.5">{t.vehicle}</div>
                              <div className="text-[#5a5a58] text-[11px] mt-0.5">{t.issue}</div>
                            </div>

                            <div className="p-2.5 rounded bg-white border border-[#ededeb]">
                              <div className="text-[10px] font-mono text-[#787774] uppercase">ASSIGNED REPLACEMENT</div>
                              {wo ? (
                                <>
                                  <div className="font-mono font-semibold text-[#15803d] mt-0.5">
                                    {wo.replacement_vehicle_reg || wo.replacement_vehicle} ({wo.hub_used || wo.assigned_hub})
                                  </div>
                                  <div className="text-[#5a5a58] text-[11px] mt-0.5 truncate">{wo.hub_strategy || wo.selection_rationale}</div>
                                </>
                              ) : (
                                <div className="text-rose-700 font-medium text-[11px] mt-0.5">{quar?.quarantine_reason || quar?.reason || 'No vehicle assigned'}</div>
                              )}
                            </div>
                          </div>

                          {/* Client Comms Notification Box with 1-Click Approve */}
                          {comms && (
                            <div className="p-2.5 rounded bg-white border border-[#ededeb] space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] font-mono font-semibold text-[#787774] uppercase flex items-center gap-1">
                                  <Mail className="w-3 h-3 text-indigo-600" />
                                  <span>DRAFTED CLIENT NOTIFICATION</span>
                                </span>
                                {isApproved ? (
                                  <span className="text-[10px] font-semibold text-emerald-700 flex items-center gap-1">
                                    <Check className="w-3 h-3" />
                                    <span>APPROVED & SENT</span>
                                  </span>
                                ) : (
                                  <button
                                    onClick={() => handleApproveComms(msg.id, comms.message_id)}
                                    className="px-2 py-0.5 rounded bg-[#242424] hover:bg-[#111111] text-white font-medium text-[10px] flex items-center gap-1 transition-all"
                                  >
                                    <Check className="w-3 h-3" />
                                    <span>Approve & Send</span>
                                  </button>
                                )}
                              </div>
                              <div className="text-[11px] font-sans text-[#242424] bg-[#fbfbfa] p-2 rounded border border-[#f0efe9] whitespace-pre-wrap">
                                {comms.body}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Direct Concise Answer with Typewriter stream */}
                <div className="text-xs text-[#2f2f2f] leading-relaxed whitespace-pre-wrap font-sans">
                  {textToRender}
                  {isStreamingThis && (
                    <span className="inline-block w-1.5 h-3 bg-[#191919] ml-0.5 animate-pulse" />
                  )}
                </div>

                {/* Interactive Rule Button & Vehicle Info Button */}
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

        {/* Input Bar with Document Attachment Plus Button */}
        <div className="sticky bottom-4 bg-[#ffffff]/90 backdrop-blur-md pt-2 px-3 pb-3 border-t border-[#f0efe9]">
          {/* File Attachment Pill Preview */}
          {attachedFile && (
            <div className="mb-2 px-2.5 py-1.5 rounded-md bg-indigo-50 border border-indigo-200 flex items-center justify-between text-xs text-indigo-900 w-fit animate-in fade-in">
              <div className="flex items-center gap-2">
                <FileCode className="w-3.5 h-3.5 text-indigo-600" />
                <span className="font-medium">{attachedFile.name}</span>
                <span className="text-[10px] text-indigo-600 font-mono">({(attachedFile.size / 1024).toFixed(1)} KB)</span>
              </div>
              <button 
                onClick={() => setAttachedFile(null)}
                className="ml-3 p-0.5 hover:bg-indigo-100 rounded text-indigo-700"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <div className="border border-[#d3d3d0] focus-within:border-[#242424] rounded-lg p-1.5 bg-[#ffffff] shadow-sm flex items-center gap-2">
            {/* Hidden File Input */}
            <input 
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept=".json,.csv,.txt,.xlsx,.tsv,.log"
              className="hidden"
            />

            {/* Document Plus Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              title="Attach ticket document (JSON, CSV, TXT, Excel, Logs)"
              className="p-1.5 rounded-md text-[#787774] hover:text-[#191919] hover:bg-[#f1f1ef] transition-all shrink-0 flex items-center gap-1 border border-transparent hover:border-[#e8e8e6]"
            >
              <Plus className="w-4 h-4 text-[#242424]" />
              <Paperclip className="w-3.5 h-3.5 text-[#787774]" />
            </button>

            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder={attachedFile ? `Add prompt instruction for ${attachedFile.name} (optional)...` : "Ask Rajender's Brain anything or attach ticket document (JSON/CSV)..."}
              className="w-full text-xs text-[#191919] placeholder-[#9b9a97] outline-none bg-transparent"
            />

            <button
              onClick={() => handleSend()}
              disabled={loading || (!input.trim() && !attachedFile)}
              className="p-1.5 bg-[#242424] hover:bg-[#111111] disabled:opacity-40 text-white rounded-md transition-all shrink-0 flex items-center gap-1 text-xs font-medium"
            >
              <span>Ask</span>
              <CornerDownLeft className="w-3 h-3" />
            </button>
          </div>
        </div>
      </main>

      {/* ── Rule Details Slide-Over Drawer ───────────────────────────────────── */}
      {selectedRule && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-[#ffffff] border border-[#d3d3d0] rounded-xl max-w-lg w-full p-6 shadow-xl relative animate-in zoom-in-95">
            <button
              onClick={() => setSelectedRule(null)}
              className="absolute top-4 right-4 text-[#787774] hover:text-[#191919] p-1 rounded-md"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="text-[10px] font-mono text-[#0284c7] font-semibold uppercase">
              OPERATIONAL RULE ARTIFACT
            </div>
            <h3 className="text-base font-bold text-[#191919] serif-heading mt-1">
              {selectedRule.code}: {selectedRule.name}
            </h3>

            <div className="mt-4 space-y-3 text-xs text-[#5a5a58]">
              <div className="p-3 bg-[#f7f6f3] rounded-lg border border-[#ededeb]">
                <div className="text-[10px] text-[#787774] uppercase font-mono">Governing Citation</div>
                <div className="font-mono text-[#191919] font-medium mt-0.5">
                  dispatcher_interview.txt & emails/
                </div>
              </div>
              <div className="p-3 bg-[#f7f6f3] rounded-lg border border-[#ededeb]">
                <div className="text-[10px] text-[#787774] uppercase font-mono">Precedence Level</div>
                <div className="font-semibold text-emerald-700 mt-0.5">
                  Level 1 - Active Operational Agreement
                </div>
              </div>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                onClick={() => setSelectedRule(null)}
                className="px-4 py-1.5 rounded bg-[#242424] text-white text-xs font-medium"
              >
                Close Rule
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Vehicle Info Slide-Over Drawer ───────────────────────────────────── */}
      {selectedVehicle && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-[#ffffff] border border-[#d3d3d0] rounded-xl max-w-lg w-full p-6 shadow-xl relative animate-in zoom-in-95">
            <button
              onClick={() => setSelectedVehicle(null)}
              className="absolute top-4 right-4 text-[#787774] hover:text-[#191919] p-1 rounded-md"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="text-[10px] font-mono text-[#059669] font-semibold uppercase flex items-center gap-1.5">
              <Truck className="w-3.5 h-3.5" />
              <span>LIVE FLEET TELEMETRY</span>
            </div>
            <h3 className="text-lg font-bold text-[#191919] serif-heading mt-2">
              {selectedVehicle.reg} ({selectedVehicle.model})
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
    </div>
  );
}
