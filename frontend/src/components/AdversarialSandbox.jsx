import React, { useState } from 'react';
import { Upload, Play, Terminal, FileCode, CheckCircle2 } from 'lucide-react';

export default function AdversarialSandbox({ apiBase = 'http://127.0.0.1:8000' }) {
  const [testOutput, setTestOutput] = useState(null);
  const [runningTests, setRunningTests] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploading, setUploading] = useState(false);

  const handleRunAllTests = async () => {
    setRunningTests(true);
    setTestOutput(null);
    try {
      const res = await fetch(`${apiBase}/api/tests/run`, { method: 'POST' });
      const data = await res.json();
      setTestOutput(data);
    } catch (err) {
      setTestOutput({ passed: false, stdout: `Failed to execute tests: ${err.message}` });
    } finally {
      setRunningTests(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setUploadResult(null);

    try {
      const res = await fetch(`${apiBase}/api/surprise/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      setUploadResult(data);
    } catch (err) {
      alert(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-2">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#e8e8e6]">
        <div>
          <span className="notion-tag font-mono text-[10px] uppercase tracking-wider">
            DRIFT ADAPTER & SANDBOX
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[#191919] serif-heading mt-1">
            Adversarial File Simulator & Automated Tests
          </h1>
          <p className="text-xs text-[#787774] mt-1">
            Test unexpected schema drift (TSV, CSV, Excel, BOM UTF-8) and execute the 92 automated test suites in real-time.
          </p>
        </div>

        <button
          onClick={handleRunAllTests}
          disabled={runningTests}
          className="px-4 py-1.5 rounded-md bg-[#242424] hover:bg-[#111111] disabled:opacity-40 text-white text-xs font-medium flex items-center gap-1.5 transition-all shadow-sm"
        >
          <Play className={`w-3.5 h-3.5 ${runningTests ? 'animate-spin' : ''}`} />
          <span>{runningTests ? 'Running 92 Suites...' : 'Run 92 Automated Tests'}</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Box */}
        <div className="notion-card p-5 space-y-3">
          <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase">
            SURPRISE FORMAT DROPZONE
          </div>
          <p className="text-xs text-[#787774]">
            Upload any unannounced ticket queue format (.json, .jsonl, .csv, .tsv, .xlsx). The Drift Adapter normalizes keys and executes resolution.
          </p>

          <label className="border border-dashed border-[#d3d3d0] hover:border-[#242424] rounded-lg p-6 flex flex-col items-center justify-center gap-2 cursor-pointer bg-[#fbfbfa] hover:bg-[#f7f6f3] transition-all text-center">
            <input
              type="file"
              onChange={handleFileUpload}
              className="hidden"
              accept=".json,.jsonl,.csv,.tsv,.xlsx"
            />
            <FileCode className="w-6 h-6 text-[#787774]" />
            <div>
              <div className="text-xs font-medium text-[#191919]">
                {uploading ? 'Adapting format...' : 'Choose or drop surprise queue file'}
              </div>
              <div className="text-[10px] text-[#9b9a97] mt-0.5">JSON, JSONL, CSV, TSV, XLSX (BOM & CRLF safe)</div>
            </div>
          </label>

          {uploadResult && (
            <div className="bg-[#f7f6f3] p-3 rounded-lg border border-[#ededeb] text-xs space-y-2">
              <div className="flex items-center justify-between font-medium text-[#191919]">
                <span>{uploadResult.filename}</span>
                <span className="text-[#15803d]">Parsed {uploadResult.records_parsed} record(s)</span>
              </div>

              {uploadResult.drift_alerts && uploadResult.drift_alerts.length > 0 && (
                <div className="bg-[#fef3c7] p-2 rounded text-[#92400e] text-[10px] font-mono">
                  <div className="font-bold mb-0.5">Drift Normalizations:</div>
                  <ul className="list-disc pl-3">
                    {uploadResult.drift_alerts.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Test Output Terminal */}
        <div className="notion-card p-5 space-y-3 flex flex-col">
          <div className="flex items-center justify-between">
            <div className="text-[11px] font-mono font-semibold tracking-wider text-[#787774] uppercase">
              PYTEST EXECUTION CONSOLE
            </div>
            {testOutput && (
              <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                testOutput.passed ? 'bg-[#dcfce7] text-[#166534]' : 'bg-[#fee2e2] text-[#991b1b]'
              }`}>
                {testOutput.passed ? '92/92 PASSING' : 'FAILED'}
              </span>
            )}
          </div>

          <div className="flex-1 bg-[#191919] rounded-lg p-3.5 font-mono text-[11px] text-[#ededeb] overflow-y-auto max-h-[300px] whitespace-pre-wrap leading-relaxed">
            {runningTests && (
              <div className="text-amber-400">
                Running 92 tests (Epsilon Engine, Drift Adapter, PII Scrubber, Idempotency, Validator, Rules)...
              </div>
            )}
            {!runningTests && !testOutput && (
              <div className="text-[#787774]">
                Click "Run 92 Automated Tests" above to execute verification suite in real time.
              </div>
            )}
            {!runningTests && testOutput && (
              <div>
                {testOutput.stdout || testOutput.stderr || 'Tests completed.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
