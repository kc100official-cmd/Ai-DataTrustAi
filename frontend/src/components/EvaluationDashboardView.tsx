import React, { useState, useEffect } from 'react';
import {
  Award,
  Play,
  Download,
  ShieldAlert,
  CheckCircle2,
  XOctagon,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { api } from '../api';

export const EvaluationDashboardView: React.FC = () => {
  const [evalMeta, setEvalMeta] = useState<any>(null);
  const [modelName, setModelName] = useState<string>('llama3.1:8b-instruct-q4_K_M');
  const [paramBillions, setParamBillions] = useState<number>(8.0);
  const [activeRun, setActiveRun] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadEvaluations = async () => {
    try {
      const data = await api.getEvaluations();
      setEvalMeta(data);
      if (data.runs && data.runs.length > 0 && !activeRun) {
        setActiveRun(data.runs[0]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadEvaluations();
  }, []);

  const handleRunEvaluation = async (overrideModel?: string, overrideParams?: number) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const run = await api.runEvaluation({
        dataset_mode: 'bird_smoke_synthetic',
        model_name: overrideModel ?? modelName,
        model_param_billions: overrideParams ?? paramBillions,
        max_questions: 6,
      });
      setActiveRun(run);
      await loadEvaluations();
    } catch (err: any) {
      setErrorMsg(err.message || 'Evaluation failed');
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = (content: string, filename: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-[1180px] mx-auto space-y-10">
      {/* Clean Header & Run Bar */}
      <div className="rounded-3xl glass-panel-elevated p-8 sm:p-10 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="eye-label block">RESTRICTED ≤ 8B BENCHMARK</span>
            <h2 className="text-2xl sm:text-3xl font-display font-bold text-white">
              BIRD Text-to-SQL Evaluation
            </h2>
            <p className="text-base text-blue-100/75 font-light">
              Verifies SQL Execution Accuracy (EX) while strictly enforcing the ≤ 8.0B parameter open-weight model limit.
            </p>
          </div>

          <button
            type="button"
            onClick={() => handleRunEvaluation('llama3.1:70b-instruct', 70.0)}
            className="px-4 py-2.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 border border-rose-400/35 text-xs font-mono transition"
          >
            Test &gt;8B Rejection (70B Model)
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-xs font-mono uppercase text-blue-200/75 block mb-2">
              Open-Weight Model (≤ 8B)
            </label>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full px-4 py-3.5 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-white font-mono"
            />
          </div>

          <div>
            <label className="text-xs font-mono uppercase text-blue-200/75 block mb-2">
              Parameter Count (Billions)
            </label>
            <input
              type="number"
              step="0.5"
              value={paramBillions}
              onChange={(e) => setParamBillions(parseFloat(e.target.value) || 8.0)}
              className="w-full px-4 py-3.5 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-white font-mono"
            />
          </div>

          <div className="flex items-end">
            <button
              type="button"
              disabled={loading}
              onClick={() => handleRunEvaluation()}
              className="btn-nexus w-full flex items-center justify-center gap-2.5 !py-3.5"
            >
              <Play className="w-4 h-4" />
              <span>{loading ? 'Running Benchmark...' : 'Run Benchmark Suite'}</span>
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="p-4 rounded-2xl bg-rose-950/35 border border-rose-500/40 text-sm font-mono text-rose-200 flex items-center gap-2.5">
            <ShieldAlert className="w-5 h-5 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {/* Clean Results Summary */}
      {activeRun && (
        <div className="space-y-8">
          {/* 3 Big KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="rounded-3xl glass-panel p-7 space-y-2">
              <span className="text-xs font-mono uppercase text-blue-200/70">
                Execution Accuracy (EX)
              </span>
              <div className="text-4xl font-display font-black text-emerald-400">
                {activeRun.execution_accuracy_pct}%
              </div>
              <div className="text-sm font-mono text-slate-300">
                {activeRun.correct_count} / {activeRun.total_questions} exact result matches
              </div>
            </div>

            <div className="rounded-3xl glass-panel p-7 space-y-2">
              <span className="text-xs font-mono uppercase text-blue-200/70">
                Mean Query Latency
              </span>
              <div className="text-4xl font-display font-black text-cyan-300">
                {activeRun.avg_latency_ms} ms
              </div>
              <div className="text-sm font-mono text-slate-300">Read-Only SQLite Execution</div>
            </div>

            <div className="rounded-3xl glass-panel p-7 space-y-3 flex flex-col justify-between">
              <div>
                <span className="text-xs font-mono uppercase text-blue-200/70">
                  Model Policy Status
                </span>
                <div className="text-lg font-display font-bold text-white mt-1">
                  {activeRun.model_name} ({activeRun.model_param_billions}B)
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() =>
                    downloadFile(
                      JSON.stringify(activeRun, null, 2),
                      `${activeRun.run_id}.json`,
                      'application/json'
                    )
                  }
                  className="px-3.5 py-2 rounded-xl bg-[#030d2b] border border-blue-400/30 text-xs font-mono text-cyan-300 flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" /> JSON
                </button>
                <button
                  type="button"
                  onClick={() =>
                    downloadFile(
                      activeRun.csv_export || '',
                      `${activeRun.run_id}.csv`,
                      'text/csv'
                    )
                  }
                  className="px-3.5 py-2 rounded-xl bg-[#030d2b] border border-blue-400/30 text-xs font-mono text-emerald-300 flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" /> CSV
                </button>
              </div>
            </div>
          </div>

          {/* Question Results List */}
          <div className="rounded-3xl glass-panel p-8 space-y-6">
            <h3 className="text-xl font-display font-bold text-white">
              Benchmark Queries ({activeRun.question_results?.length || 0})
            </h3>
            <div className="space-y-4">
              {(activeRun.question_results || []).map((q: any) => (
                <div
                  key={q.question_id}
                  className="p-5 rounded-2xl bg-[#030d2b] border border-blue-400/20 space-y-2.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-sm font-bold text-cyan-300">
                      {q.question_id} · {q.db_id}
                    </span>
                    {q.execution_match ? (
                      <span className="text-xs font-mono text-emerald-400 flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4" /> MATCH ({q.latency_ms} ms)
                      </span>
                    ) : (
                      <span className="text-xs font-mono text-rose-400 flex items-center gap-1.5">
                        <XOctagon className="w-4 h-4" /> {q.status}
                      </span>
                    )}
                  </div>
                  <div className="text-base text-white">{q.question}</div>
                  <div className="p-3 rounded-xl bg-[#01040d] border border-blue-400/15 font-mono text-xs text-cyan-200">
                    {q.predicted_sql}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
