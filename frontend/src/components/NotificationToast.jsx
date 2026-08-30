import React, { useState, useEffect } from 'react';
import { AlertOctagon, FileText, AlertTriangle, RefreshCw, ShieldCheck, X } from 'lucide-react';

let toastListeners = [];

export const showToast = (toast) => {
  const newToast = {
    id: Date.now() + Math.random(),
    type: toast.type || 'info',
    title: toast.title,
    message: toast.message,
    details: toast.details,
    duration: toast.duration || 6000,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  };
  toastListeners.forEach(listener => listener(newToast));
};

if (typeof window !== 'undefined') {
  window.showToast = showToast;
}

export default function NotificationToast() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    const handleNewToast = (toast) => {
      setToasts(prev => [toast, ...prev.slice(0, 6)]);
      if (toast.duration > 0) {
        setTimeout(() => {
          setToasts(prev => prev.filter(t => t.id !== toast.id));
        }, toast.duration);
      }
    };

    toastListeners.push(handleNewToast);
    return () => {
      toastListeners = toastListeners.filter(l => l !== handleNewToast);
    };
  }, []);

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const getToastConfig = (type) => {
    switch (type) {
      case 'quarantine':
        return {
          icon: AlertOctagon,
          bg: 'bg-rose-50',
          border: 'border-rose-300',
          text: 'text-rose-900',
          badgeBg: 'bg-rose-100 text-rose-800',
          iconColor: 'text-rose-600'
        };
      case 'draft_ready':
        return {
          icon: FileText,
          bg: 'bg-indigo-50',
          border: 'border-indigo-300',
          text: 'text-indigo-900',
          badgeBg: 'bg-indigo-100 text-indigo-800',
          iconColor: 'text-indigo-600'
        };
      case 'gate_breach':
      case 'sla_breach':
        return {
          icon: AlertTriangle,
          bg: 'bg-amber-50',
          border: 'border-amber-300',
          text: 'text-amber-900',
          badgeBg: 'bg-amber-100 text-amber-800',
          iconColor: 'text-amber-600'
        };
      case 'deduplication':
        return {
          icon: RefreshCw,
          bg: 'bg-sky-50',
          border: 'border-sky-300',
          text: 'text-sky-900',
          badgeBg: 'bg-sky-100 text-sky-800',
          iconColor: 'text-sky-600'
        };
      case 'schema_drift':
      default:
        return {
          icon: ShieldCheck,
          bg: 'bg-emerald-50',
          border: 'border-emerald-300',
          text: 'text-emerald-900',
          badgeBg: 'bg-emerald-100 text-emerald-800',
          iconColor: 'text-emerald-600'
        };
    }
  };

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-16 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => {
        const config = getToastConfig(toast.type);
        const IconComponent = config.icon;

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 rounded-lg border shadow-lg ${config.bg} ${config.border} animate-slide-in-right transition-all flex items-start gap-3 relative`}
          >
            <div className={`p-1.5 rounded-md ${config.badgeBg} shrink-0 mt-0.5`}>
              <IconComponent className={`w-4 h-4 ${config.iconColor}`} />
            </div>

            <div className="flex-1 min-w-0 pr-4">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-mono font-bold tracking-tight uppercase text-[#191919]">
                  {toast.title}
                </span>
                <span className="text-[10px] font-mono text-[#787774]">
                  {toast.timestamp}
                </span>
              </div>

              <div className={`text-xs font-medium mt-0.5 ${config.text} leading-snug`}>
                {toast.message}
              </div>

              {toast.details && (
                <div className="text-[11px] font-mono text-[#5a5a58] mt-1 bg-white/70 px-2 py-1 rounded border border-black/5 truncate">
                  {toast.details}
                </div>
              )}
            </div>

            <button
              onClick={() => removeToast(toast.id)}
              className="text-[#787774] hover:text-[#191919] p-1 rounded hover:bg-black/5 transition-all shrink-0 absolute top-2 right-2"
              aria-label="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
