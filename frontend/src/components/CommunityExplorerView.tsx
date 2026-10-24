import React, { useState, useEffect } from 'react';
import {
  Network,
  Users,
  GitBranch,
  Send,
  Sparkles,
} from 'lucide-react';
import { api } from '../api';

interface CommunityExplorerViewProps {
  activeSourceId: string;
  onAskCommunityQuestion: (question: string, communityId: string, sourceId: string) => void;
}

export const CommunityExplorerView: React.FC<CommunityExplorerViewProps> = ({
  activeSourceId,
  onAskCommunityQuestion,
}) => {
  const [sourceFilter, setSourceFilter] = useState<string>(activeSourceId);
  const [communities, setCommunities] = useState<any[]>([]);
  const [selectedComm, setSelectedComm] = useState<any>(null);
  const [communityQuestion, setCommunityQuestion] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    setSourceFilter(activeSourceId);
  }, [activeSourceId]);

  useEffect(() => {
    setLoading(true);
    api
      .getCommunities(sourceFilter === 'ALL' ? undefined : sourceFilter)
      .then((res) => {
        const list = res.communities || [];
        setCommunities(list);
        if (list.length > 0) {
          setSelectedComm(list[0]);
          setCommunityQuestion(
            `What are the key companies, facilities, and relationships in ${list[0].theme_label}?`
          );
        } else {
          setSelectedComm(null);
        }
      })
      .finally(() => setLoading(false));
  }, [sourceFilter]);

  return (
    <div className="space-y-10">
      {/* Clean Header */}
      <div className="rounded-3xl glass-panel p-8 flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-1.5">
          <span className="eye-label block">THEMATIC GRAPH CLUSTERS</span>
          <h2 className="text-2xl sm:text-3xl font-display font-bold text-white">
            Regional & Industrial Communities
          </h2>
          <p className="text-base text-blue-100/75 font-light">
            Automatically groups connected Indian companies and city facilities into regional themes using Louvain modularity.
          </p>
        </div>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="px-4 py-3 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-white font-mono"
        >
          <option value="enterprise_supply_ops">Indian Corporate Supply DB</option>
          <option value="california_schools_bird_demo">Regional STEM Schools</option>
          <option value="ALL">All Connected Sources</option>
        </select>
      </div>

      {loading ? (
        <div className="p-12 text-center text-sm font-mono text-cyan-300 animate-pulse">
          Detecting Graph Communities...
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left: Clean Community Cards (5 cols) */}
          <div className="lg:col-span-5 space-y-5">
            {communities.map((comm) => {
              const isSelected = selectedComm?.community_id === comm.community_id;
              return (
                <div
                  key={comm.community_id}
                  onClick={() => {
                    setSelectedComm(comm);
                    setCommunityQuestion(
                      `What are the key companies, facilities, and relationships in ${comm.theme_label}?`
                    );
                  }}
                  className={`rounded-3xl p-7 transition border space-y-4 ${
                    isSelected
                      ? 'glass-panel-elevated border-cyan-300/70'
                      : 'glass-panel hover:border-blue-400/40'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-cyan-300 font-semibold">
                      {comm.community_id}
                    </span>
                    <span className="px-3 py-1 rounded-full text-xs font-mono bg-[#030d2b] text-blue-200 border border-blue-400/25">
                      {comm.entity_count} Entities · {comm.edge_count} Links
                    </span>
                  </div>

                  <h3 className="text-lg font-display font-bold text-white leading-snug">
                    {comm.theme_label}
                  </h3>

                  <p className="text-sm text-blue-100/80 font-light leading-relaxed">
                    {comm.evidence_summary}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Right: Clean Selected Community Overview (7 cols) */}
          <div className="lg:col-span-7">
            {selectedComm ? (
              <div className="rounded-3xl glass-panel-elevated p-8 space-y-8">
                <div className="border-b border-blue-400/20 pb-6 space-y-3">
                  <span className="px-3 py-1 rounded-full text-xs font-mono bg-cyan-500/15 text-cyan-300 border border-cyan-400/30">
                    {selectedComm.community_id} · Modularity Q: {selectedComm.quality_metrics?.graph_modularity_q}
                  </span>
                  <h3 className="text-2xl font-display font-bold text-white">
                    {selectedComm.theme_label}
                  </h3>
                  <p className="text-base text-blue-100/85 font-light leading-relaxed">
                    {selectedComm.evidence_summary}
                  </p>
                </div>

                {/* Ask Scoped Question */}
                <div className="p-6 rounded-2xl bg-[#030d2b] border border-blue-400/30 space-y-3">
                  <label className="text-xs font-mono uppercase tracking-wider text-cyan-300 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    Ask a Question About This Cluster
                  </label>
                  <div className="flex flex-col sm:flex-row gap-3">
                    <input
                      type="text"
                      value={communityQuestion}
                      onChange={(e) => setCommunityQuestion(e.target.value)}
                      className="flex-1 px-4 py-3 rounded-xl bg-[#01040d] border border-blue-400/30 text-sm text-white focus:border-cyan-300 outline-none"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        onAskCommunityQuestion(
                          communityQuestion,
                          selectedComm.community_id,
                          sourceFilter === 'ALL' ? 'enterprise_supply_ops' : sourceFilter
                        )
                      }
                      className="btn-nexus flex items-center justify-center gap-2 !py-3 !px-6 shrink-0"
                    >
                      <Send className="w-4 h-4" />
                      <span>Verify</span>
                    </button>
                  </div>
                </div>

                {/* Member Entities */}
                <div className="space-y-4">
                  <h4 className="text-sm font-mono uppercase tracking-wider text-cyan-200 flex items-center gap-2">
                    <Users className="w-4 h-4 text-cyan-300" />
                    Cluster Members ({selectedComm.entities?.length || 0})
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {(selectedComm.entities || []).map((ent: any) => (
                      <div
                        key={ent.id}
                        className="p-4 rounded-2xl bg-[#030d2b] border border-blue-400/20 flex items-center justify-between gap-3"
                      >
                        <div>
                          <div className="text-base font-semibold text-white">{ent.name}</div>
                          <div className="text-xs font-mono text-slate-400 mt-0.5">
                            {ent.provenance?.source_record}
                          </div>
                        </div>
                        <span className="px-2.5 py-1 rounded-lg text-xs font-mono bg-blue-500/15 text-cyan-300">
                          {ent.entity_type}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Key Relationships */}
                <div className="space-y-4 pt-2 border-t border-blue-400/15">
                  <h4 className="text-sm font-mono uppercase tracking-wider text-cyan-200 flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-cyan-300" />
                    Key Connections ({selectedComm.relationships?.length || 0})
                  </h4>
                  <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                    {(selectedComm.relationships || []).map((rel: any) => (
                      <div
                        key={rel.id}
                        className="p-4 rounded-2xl bg-[#030d2b] border border-blue-400/20 text-sm flex flex-wrap items-center justify-between gap-2"
                      >
                        <span className="font-mono text-slate-100">
                          {rel.source_name}{' '}
                          <span className="text-cyan-300 font-bold">→ {rel.rel_type} →</span>{' '}
                          {rel.target_name}
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          {rel.provenance?.source_record}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};
