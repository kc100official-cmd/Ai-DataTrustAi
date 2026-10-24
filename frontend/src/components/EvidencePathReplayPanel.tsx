import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  XOctagon,
  Play,
  RotateCcw,
  Database,
  FileText,
  GitBranch,
  ExternalLink,
  CheckCircle2,
} from 'lucide-react';
import { EvidencePath, EvidenceHop, ClaimValidation } from '../api';

interface EvidencePathReplayPanelProps {
  question: string;
  answerClaim: string;
  verificationStatus: string;
  verificationRationale: string;
  paths: EvidencePath[];
  claims: ClaimValidation[];
  missingOrConflictingNotes: string[];
  onNavigateToGraphEntity?: (entityId: string) => void;
}

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  switch (status) {
    case 'Supported':
      return (
        <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/40">
          <ShieldCheck className="w-4 h-4" />
          Supported
        </span>
      );
    case 'Partially supported':
      return (
        <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/40">
          <AlertTriangle className="w-4 h-4" />
          Partially Supported
        </span>
      );
    case 'Conflicting evidence':
      return (
        <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/40">
          <XOctagon className="w-4 h-4" />
          Conflicting Evidence
        </span>
      );
    case 'Needs clarification':
      return (
        <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold bg-violet-500/15 text-violet-300 border border-violet-500/40">
          <HelpCircle className="w-4 h-4" />
          Needs Clarification
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold bg-slate-700/60 text-slate-200 border border-slate-600">
          <XOctagon className="w-4 h-4" />
          Insufficient Evidence
        </span>
      );
  }
};

export const EvidencePathReplayPanel: React.FC<EvidencePathReplayPanelProps> = ({
  verificationRationale,
  paths,
  claims,
  missingOrConflictingNotes,
  onNavigateToGraphEntity,
}) => {
  const [selectedPathIdx, setSelectedPathIdx] = useState(0);
  const [activeHopIdx, setActiveHopIdx] = useState<number>(0);
  const [isReplaying, setIsReplaying] = useState(false);

  const currentPath: EvidencePath | undefined = paths[selectedPathIdx] || paths[0];

  useEffect(() => {
    setSelectedPathIdx(0);
    setActiveHopIdx(0);
  }, [paths]);

  useEffect(() => {
    if (!isReplaying || !currentPath) return;
    const totalHops = currentPath.hops.length;
    const timer = setInterval(() => {
      setActiveHopIdx((prev) => {
        if (prev + 1 < totalHops) {
          return prev + 1;
        } else {
          setIsReplaying(false);
          return prev;
        }
      });
    }, 1100);
    return () => clearInterval(timer);
  }, [isReplaying, currentPath]);

  const startReplay = () => {
    if (!currentPath || currentPath.hops.length === 0) return;
    setActiveHopIdx(0);
    setIsReplaying(true);
  };

  return (
    <div className="rounded-3xl glass-panel-elevated spotlight-card p-8 sm:p-10 space-y-8">
      {/* Spacious Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-blue-400/20 pb-6">
        <div className="space-y-1.5">
          <div className="flex items-center gap-3">
            <GitBranch className="w-6 h-6 text-cyan-300" />
            <h3 className="text-xl sm:text-2xl font-display font-bold text-white">
              Evidence Path Replay
            </h3>
          </div>
          <p className="text-sm sm:text-base text-blue-100/75 font-light">
            {verificationRationale}
          </p>
        </div>

        {currentPath && currentPath.hops.length > 0 && (
          <button
            type="button"
            onClick={startReplay}
            className="btn-nexus flex items-center gap-2.5"
          >
            {isReplaying ? (
              <RotateCcw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            <span>{isReplaying ? 'Replaying Path...' : 'Replay Evidence Path'}</span>
          </button>
        )}
      </div>

      {/* Path Switcher (Only if multiple paths exist) */}
      {paths.length > 1 && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-mono text-blue-200/70">Supporting Paths:</span>
          {paths.map((p, idx) => (
            <button
              key={p.path_id}
              type="button"
              onClick={() => {
                setSelectedPathIdx(idx);
                setActiveHopIdx(0);
              }}
              className={`px-4 py-2 rounded-xl text-sm font-mono transition border ${
                selectedPathIdx === idx
                  ? 'bg-blue-500/25 text-white border-cyan-300/70 shadow-md'
                  : 'bg-[#030d2b] text-blue-200/70 border-blue-400/20 hover:text-white'
              }`}
            >
              Path {idx + 1} · {p.all_confirmed ? 'Confirmed Direct' : 'Includes Inferred Step'}
            </button>
          ))}
        </div>
      )}

      {/* Visual Step-by-Step Graph Path Chain */}
      {currentPath ? (
        <div className="space-y-6">
          {/* Clean Path Banner */}
          <div className="p-5 rounded-2xl bg-[#030d2b] border border-blue-400/30 flex flex-wrap items-center justify-between gap-4">
            <span className="font-mono text-sm sm:text-base text-[#88ccff] font-semibold">
              {currentPath.summary_chain}
            </span>
            <span
              className={`px-3.5 py-1 rounded-full text-xs font-mono font-semibold ${
                currentPath.all_confirmed
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                  : 'bg-violet-500/15 text-violet-300 border border-violet-500/30'
              }`}
            >
              {currentPath.all_confirmed ? '100% Confirmed Facts' : 'Includes Inferred Link'}
            </span>
          </div>

          {/* Spacious Hop Cards */}
          <div className="grid grid-cols-1 gap-5">
            {currentPath.hops.map((hop, idx) => {
              const isSelected = activeHopIdx === idx;
              return (
                <div
                  key={`${hop.step_index}-${hop.rel_type}`}
                  onClick={() => setActiveHopIdx(idx)}
                  className={`cursor-pointer rounded-2xl p-6 transition-all border ${
                    isSelected
                      ? hop.is_inferred
                        ? 'bg-violet-950/30 border-violet-400/70 shadow-xl'
                        : 'bg-blue-950/45 border-cyan-300/70 shadow-xl'
                      : 'bg-[#041034]/75 border-blue-400/20 hover:border-blue-300/40'
                  }`}
                >
                  {/* Hop Top Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
                    <div className="flex items-center gap-3">
                      <span className="px-3 py-1 rounded-lg text-xs font-mono font-bold bg-blue-500/20 text-cyan-200 border border-blue-400/30">
                        STEP {hop.step_index}
                      </span>
                      {hop.is_inferred ? (
                        <span className="px-3.5 py-1 rounded-full text-xs font-mono bg-violet-500/20 text-violet-200 border border-dashed border-violet-400">
                          Inferred Relationship
                        </span>
                      ) : (
                        <span className="px-3.5 py-1 rounded-full text-xs font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                          Confirmed Database Fact
                        </span>
                      )}
                    </div>

                    {onNavigateToGraphEntity && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onNavigateToGraphEntity(hop.from_entity_id);
                        }}
                        className="text-xs font-mono text-[#88ccff] hover:text-white flex items-center gap-1.5 transition"
                      >
                        <span>Inspect in Graph</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  {/* Large Readable Entity -> Relationship -> Entity Flow */}
                  <div className="flex flex-wrap items-center gap-4 my-4">
                    <div className="px-5 py-3 rounded-xl bg-[#020c28] border border-blue-400/35 text-base font-semibold text-white">
                      {hop.from_entity_name}
                      <span className="ml-2 text-xs font-mono text-blue-200/60 font-normal">
                        {hop.from_entity_type}
                      </span>
                    </div>

                    <div className="px-4 py-2 rounded-lg bg-blue-500/15 border border-cyan-300/35 font-mono text-sm font-bold text-[#88ccff]">
                      {hop.direction === '<-' ? `← ${hop.rel_type}` : `${hop.rel_type} →`}
                    </div>

                    <div className="px-5 py-3 rounded-xl bg-[#020c28] border border-blue-400/35 text-base font-semibold text-white">
                      {hop.to_entity_name}
                      <span className="ml-2 text-xs font-mono text-blue-200/60 font-normal">
                        {hop.to_entity_type}
                      </span>
                    </div>
                  </div>

                  {/* Clean Source Record Citation */}
                  <div className="mt-4 pt-4 border-t border-blue-400/15 flex flex-wrap items-center gap-3 text-sm text-blue-100/85">
                    {hop.source_type === 'database_record' ? (
                      <Database className="w-4 h-4 text-cyan-300 shrink-0" />
                    ) : (
                      <FileText className="w-4 h-4 text-violet-300 shrink-0" />
                    )}
                    <span className="font-mono text-cyan-200 font-semibold">
                      {hop.source_record}:
                    </span>
                    <span className="text-blue-100/90 font-light">“{hop.excerpt}”</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="p-6 rounded-2xl bg-[#030d2b]/80 border border-blue-400/20 text-base text-blue-100/80 font-light">
          This question was answered directly from structured SQL records without requiring a multi-hop graph traversal.
        </div>
      )}

      {/* Clean Claim Verification Summary */}
      {claims.length > 0 && (
        <div className="space-y-4 pt-4 border-t border-blue-400/20">
          <h4 className="text-sm font-mono uppercase tracking-[0.2em] text-[#88ccff] flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            Verified Claims ({claims.length})
          </h4>
          <div className="grid grid-cols-1 gap-4">
            {claims.map((c) => (
              <div
                key={c.claim_id}
                className="p-5 rounded-2xl bg-[#030d2b]/90 border border-blue-400/20 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="text-base font-medium text-white leading-relaxed">
                    {c.claim_text}
                  </span>
                  <StatusBadge status={c.status} />
                </div>
                <div className="text-sm text-blue-200/75 font-mono">
                  Source: {c.supporting_sources.join(', ')}
                </div>
                {c.conflict_note && (
                  <div className="text-sm text-rose-200 bg-rose-950/35 border border-rose-500/40 px-4 py-3 rounded-xl">
                    ⚠️ {c.conflict_note}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conflict / Caveat Notice (Only if present) */}
      {missingOrConflictingNotes.length > 0 && (
        <div className="p-5 rounded-2xl bg-amber-950/25 border border-amber-400/35 space-y-2">
          <div className="text-sm font-semibold text-amber-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Data Quality Notes
          </div>
          <ul className="list-disc list-inside text-sm text-amber-100/90 space-y-1.5 leading-relaxed">
            {missingOrConflictingNotes.map((note, idx) => (
              <li key={idx}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
