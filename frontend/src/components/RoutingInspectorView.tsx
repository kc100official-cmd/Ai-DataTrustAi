import React, { useState, useEffect } from 'react';
import {
  Compass,
  Play,
  Database,
  HelpCircle,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import { api, RoutingDecision } from '../api';

interface RoutingInspectorViewProps {
  activeSourceId: string;
  onExecuteInAskWorkspace: (question: string, sourceId: string) => void;
}

const PRESET_ROUTING_PROBES = [
  {
    label: 'SQL Strategy (Budgets)',
    source_id: 'enterprise_supply_ops',
    question: 'What is the total facility budget and contract value by region?',
  },
  {
    label: 'Graph Strategy (Gwalior Path)',
    source_id: 'california_schools_bird_demo',
    question: 'Show the relationship path connecting School A (Scindia STEM Academy Gwalior) to Region North.',
  },
  {
    label: 'Hybrid Strategy (Adani Audit)',
    source_id: 'enterprise_supply_ops',
    question: 'Verify the contract status and compliance audit status for Adani Green Energy at Morena.',
  },
  {
    label: 'Clarification Gate (Ambiguous)',
    source_id: 'enterprise_supply_ops',
    question: 'Tell me about Mercury.',
  },
  {
    label: 'Abstention (Out-of-Domain)',
    source_id: 'enterprise_supply_ops',
    question: 'What was the Bitcoin cryptocurrency trading volume in Atlantis?',
  },
];

export const RoutingInspectorView: React.FC<RoutingInspectorViewProps> = ({
  activeSourceId,
  onExecuteInAskWorkspace,
}) => {
  const [sourceId, setSourceId] = useState<string>(activeSourceId);
  const [question, setQuestion] = useState<string>(PRESET_ROUTING_PROBES[2].question);
  const [decision, setDecision] = useState<RoutingDecision | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const runInspection = async (q: string, src: string) => {
    setLoading(true);
    try {
      const res = await api.inspectRouting(q, src);
      setDecision(res);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runInspection(question, sourceId);
  }, []);

  return (
    <div className="max-w-[1120px] mx-auto space-y-10">
      {/* Spacious Routing Input Card */}
      <div className="rounded-3xl glass-panel-elevated p-8 sm:p-10 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="eye-label block">STRATEGY ROUTER</span>
            <h2 className="text-2xl sm:text-3xl font-display font-bold text-white">
              Intelligent Question Routing
            </h2>
            <p className="text-base text-blue-100/75 font-light">
              See how DataTrust AI chooses between SQL, Knowledge Graph, Hybrid, Clarification, or Abstention.
            </p>
          </div>
          <select
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            className="px-4 py-3 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-white font-mono"
          >
            <option value="enterprise_supply_ops">Indian Corporate Supply DB</option>
            <option value="california_schools_bird_demo">Regional STEM Schools</option>
          </select>
        </div>

        {/* Preset Strategy Buttons */}
        <div className="flex flex-wrap gap-3">
          {PRESET_ROUTING_PROBES.map((probe, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setSourceId(probe.source_id);
                setQuestion(probe.question);
                runInspection(probe.question, probe.source_id);
              }}
              className="px-4 py-2 rounded-xl bg-[#030d2b] hover:bg-blue-900/50 border border-blue-400/25 hover:border-cyan-300/60 text-xs sm:text-sm text-blue-100 transition"
            >
              {probe.label}
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            runInspection(question, sourceId);
          }}
          className="flex flex-col sm:flex-row gap-4"
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Type any question to test routing..."
            className="flex-1 px-6 py-4 rounded-2xl bg-[#030d2b] border border-blue-400/35 text-base text-white focus:border-cyan-300 outline-none"
          />
          <button
            type="submit"
            disabled={loading}
            className="btn-nexus flex items-center justify-center gap-2 !py-4 !px-7 shrink-0"
          >
            <Play className="w-4 h-4" />
            <span>Inspect Route</span>
          </button>
        </form>
      </div>

      {/* Clean Decision Summary */}
      {decision && (
        <div className="rounded-3xl glass-panel p-8 sm:p-10 space-y-8">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-blue-400/20 pb-6">
            <div>
              <span className="text-xs font-mono uppercase tracking-wider text-cyan-300 block">
                Selected Strategy
              </span>
              <h3 className="text-2xl font-display font-bold text-white mt-1">
                {decision.strategy_label}
              </h3>
            </div>

            <div className="flex items-center gap-4">
              <div className="px-4 py-2 rounded-xl bg-[#030d2b] border border-cyan-400/35 font-mono text-sm text-cyan-200">
                Evidence Coverage: {Math.round(decision.evidence_coverage_score * 100)}%
              </div>
              <button
                type="button"
                onClick={() => onExecuteInAskWorkspace(question, sourceId)}
                className="btn-nexus-outline flex items-center gap-2 !py-3 !px-5"
              >
                <span>Run Full Verification</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          <p className="text-base sm:text-lg text-slate-100 bg-[#030d2b] p-6 rounded-2xl border border-blue-400/20 font-light leading-relaxed">
            {decision.selection_rationale}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <h4 className="text-sm font-mono uppercase tracking-wider text-cyan-200">
                Execution Steps
              </h4>
              <div className="space-y-2.5">
                {decision.retrieval_steps.map((step, i) => (
                  <div
                    key={i}
                    className="p-4 rounded-xl bg-[#030d2b] border border-blue-400/20 text-sm text-slate-200 flex items-center gap-3"
                  >
                    <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" />
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-mono uppercase tracking-wider text-cyan-200">
                Data Sources Consulted
              </h4>
              <div className="space-y-2.5">
                {decision.sources_consulted.map((src, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl bg-[#030d2b] border border-blue-400/20 text-sm font-mono text-slate-200 flex items-center gap-3"
                  >
                    <Database className="w-4 h-4 text-cyan-400 shrink-0" />
                    <span>{src}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {decision.clarification_needed && (
            <div className="p-6 rounded-2xl bg-violet-950/30 border border-violet-400/40 space-y-3">
              <div className="text-base font-semibold text-violet-200 flex items-center gap-2">
                <HelpCircle className="w-5 h-5" />
                {decision.ambiguity_detected}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {decision.clarification_options.map((opt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onExecuteInAskWorkspace(opt, sourceId)}
                    className="text-left p-4 rounded-xl bg-[#030d2b] hover:bg-blue-950 border border-violet-400/35 text-sm text-violet-100 flex items-center justify-between"
                  >
                    <span>{opt}</span>
                    <ArrowRight className="w-4 h-4 shrink-0 ml-2" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
