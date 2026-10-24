import React, { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ShieldCheck,
  Sparkles,
  Database,
  GitBranch,
  Network,
  Compass,
  Award,
  LayoutDashboard,
  MessageSquare,
  Terminal,
  HelpCircle,
  ArrowRight,
  FileText,
  MousePointer,
  Code2,
  PlusCircle,
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
import { api, AskResponse, DataSourceInfo, HealthStatus } from './api';
import { Hero3DCore } from './components/Hero3DCore';
import { EvidencePathReplayPanel, StatusBadge } from './components/EvidencePathReplayPanel';
import { GraphExplorerView } from './components/GraphExplorerView';
import { CommunityExplorerView } from './components/CommunityExplorerView';
import { RoutingInspectorView } from './components/RoutingInspectorView';
import { DatabaseExplorerView } from './components/DatabaseExplorerView';
import { EvaluationDashboardView } from './components/EvaluationDashboardView';
import { DataStudioView } from './components/DataStudioView';
import { InteractiveAtmosphere, NexusIntroLoader } from './components/InteractiveAtmosphere';

type ScreenId =
  | 'overview'
  | 'ask'
  | 'studio'
  | 'graph'
  | 'communities'
  | 'routing'
  | 'database'
  | 'evaluation';

const EXAMPLE_QUESTIONS = [
  {
    badge: 'Gwalior STEM Replay',
    source_id: 'california_schools_bird_demo',
    question: 'How is School A (Scindia STEM Academy Gwalior) connected to Region North and what are its SAT math scores?',
    bullets: [
      'Traces Scindia STEM Academy → Gwalior → Region North',
      'Verifies SAT Math score (642) from SQLite records',
    ],
  },
  {
    badge: 'Adani Morena Conflict',
    source_id: 'enterprise_supply_ops',
    question: 'Verify the contract status and compliance audit status for Adani Green Energy at Morena.',
    bullets: [
      'Compares ERP Active status ($5.4M) vs. Audit Hold',
      'Flags conflicting evidence automatically',
    ],
  },
  {
    badge: 'Hindi Cross-Lingual (P2)',
    source_id: 'enterprise_supply_ops',
    question: 'अडानी ग्रीन एनर्जी की स्थिति क्या है?',
    bullets: [
      'Answers in Hindi over English documents with quotes',
      'Replays verified multi-hop Knowledge Graph path',
    ],
  },
  {
    badge: 'Doc Contradiction (P2)',
    source_id: 'enterprise_supply_ops',
    question: 'What is Apex Labs status?',
    bullets: [
      'Detects conflicting audit memos across documents',
      'Presents both active & suspended claims with sources',
    ],
  },
  {
    badge: 'Regional Budget Chart',
    source_id: 'enterprise_supply_ops',
    question: 'What is the total facility budget and contract value by region?',
    bullets: [
      'Aggregates budgets across North, West & Central hubs',
      'Renders live visual comparison bar chart',
    ],
  },
  {
    badge: 'L&T Supply Chain Path',
    source_id: 'enterprise_supply_ops',
    question: 'Trace the supply chain path from Larsen & Toubro (L&T) to Region North and Project Mercury.',
    bullets: [
      'Finds multi-hop path from L&T Gwalior to Project Mercury',
      'Distinguishes confirmed facts from inferred links',
    ],
  },
  {
    badge: 'Indian Corporate Roster',
    source_id: 'enterprise_supply_ops',
    question: 'Show all Indian companies, their compliance scores, and total contract values.',
    bullets: [
      'Lists L&T, Bharat Forge, Adani, Mahindra, Reliance & TCS',
      'Ranks compliance scores & contract values',
    ],
  },
  {
    badge: 'Ambiguity Gate',
    source_id: 'enterprise_supply_ops',
    question: 'Tell me about Mercury.',
    bullets: [
      'Detects multiple "Mercury" entities across tables',
      'Pauses to ask user for 1-click clarification',
    ],
  },
];

const PLATFORM_FUNCTIONS: {
  id: ScreenId;
  title: string;
  tag: string;
  bullets: string[];
}[] = [
  {
    id: 'ask',
    title: 'Ask Workspace',
    tag: 'Natural Language Q&A',
    bullets: [
      'Ask questions in plain English',
      'Auto-generates safe read-only SQL',
      'Replays step-by-step evidence paths',
    ],
  },
  {
    id: 'studio',
    title: '+ Add Your Data',
    tag: 'Live Data Builder',
    bullets: [
      'Add Indian companies & city hubs',
      'Connect custom 3D graph relationships',
      'Updates SQL & Graph instantaneously',
    ],
  },
  {
    id: 'graph',
    title: '3D Knowledge Graph',
    tag: 'Interactive Space',
    bullets: [
      'Click any city or company to expand',
      'Inspect exact source record excerpts',
      'Merge or unmerge duplicate aliases',
    ],
  },
  {
    id: 'communities',
    title: 'Community Clusters',
    tag: 'Thematic Grouping',
    bullets: [
      'Auto-groups Gwalior, Morena, Jaipur & Mumbai',
      'Shows key entities & cluster density',
      'Run questions scoped to 1 cluster',
    ],
  },
  {
    id: 'routing',
    title: 'Smart Question Router',
    tag: '6-Strategy Engine',
    bullets: [
      'Routes between SQL, Graph & Hybrid',
      'Scores evidence coverage %',
      'Abstains when evidence is missing',
    ],
  },
  {
    id: 'database',
    title: 'Database & SQL Studio',
    tag: 'Read-Only Guard',
    bullets: [
      'Browse tables, keys & row counts',
      'Blocks destructive SQL at C-level',
      'Auto-repairs broken column names',
    ],
  },
];

export const App: React.FC = () => {
  const [activeScreen, setActiveScreen] = useState<ScreenId>('overview');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [sources, setSources] = useState<DataSourceInfo[]>([]);
  const [activeSourceId, setActiveSourceId] = useState<string>('enterprise_supply_ops');
  const [customCursorEnabled, setCustomCursorEnabled] = useState<boolean>(true);
  const [showIntroLoader, setShowIntroLoader] = useState<boolean>(() => {
    try {
      return sessionStorage.getItem('datatrustNexusLoaded') !== '1';
    } catch {
      return false;
    }
  });

  // Ask Workspace state
  const [questionInput, setQuestionInput] = useState<string>(EXAMPLE_QUESTIONS[1].question);
  const [scopedCommunityId, setScopedCommunityId] = useState<string | undefined>(undefined);
  const [askResult, setAskResult] = useState<AskResponse | null>(null);
  const [askLoading, setAskLoading] = useState<boolean>(false);
  const [askError, setAskError] = useState<string | null>(null);

  // Collapsible SQL editor toggle so Ask Workspace stays clean & spacious
  const [showSqlEditor, setShowSqlEditor] = useState<boolean>(false);
  const [editableSql, setEditableSql] = useState<string>('');
  const [sqlReexecLoading, setSqlReexecLoading] = useState<boolean>(false);

  // Graph deep-link state
  const [graphTargetEntityId, setGraphTargetEntityId] = useState<string | null>(null);

  useEffect(() => {
    api.getHealth().then(setHealth).catch(console.error);
    api
      .getSources()
      .then((res) => setSources(res.sources || []))
      .catch(console.error);
    handleRunAsk(EXAMPLE_QUESTIONS[1].question, EXAMPLE_QUESTIONS[1].source_id);
  }, []);

  const handleLoaderComplete = () => {
    try {
      sessionStorage.setItem('datatrustNexusLoaded', '1');
    } catch {}
    setShowIntroLoader(false);
  };

  const handleRunAsk = async (
    q: string,
    srcId: string = activeSourceId,
    commId?: string
  ) => {
    setAskLoading(true);
    setAskError(null);
    try {
      const res = await api.ask(q, srcId, commId);
      setAskResult(res);
      if (res.sql_result?.executed_sql) {
        setEditableSql(res.sql_result.executed_sql);
      } else {
        setEditableSql('');
      }
    } catch (err: any) {
      setAskError(err.message || 'Failed to process question.');
    } finally {
      setAskLoading(false);
    }
  };

  const handleInspectAndRerunSql = async () => {
    if (!editableSql.trim() || !askResult) return;
    setSqlReexecLoading(true);
    try {
      const newSqlRes = await api.executeSql(
        askResult.source_id,
        editableSql,
        askResult.question,
        true
      );
      setAskResult({
        ...askResult,
        sql_result: newSqlRes,
      });
    } catch (err: any) {
      setAskError(err.message || 'SQL execution failed');
    } finally {
      setSqlReexecLoading(false);
    }
  };

  const navItems: { id: ScreenId; label: string; icon: React.ReactNode }[] = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: 'ask', label: 'Ask Workspace', icon: <MessageSquare className="w-4 h-4" /> },
    { id: 'studio', label: '+ Add Your Data', icon: <PlusCircle className="w-4 h-4 text-emerald-300" /> },
    { id: 'graph', label: 'Knowledge Graph', icon: <GitBranch className="w-4 h-4" /> },
    { id: 'communities', label: 'Communities', icon: <Network className="w-4 h-4" /> },
    { id: 'routing', label: 'Routing', icon: <Compass className="w-4 h-4" /> },
    { id: 'database', label: 'Database', icon: <Database className="w-4 h-4" /> },
    { id: 'evaluation', label: 'BIRD Eval', icon: <Award className="w-4 h-4" /> },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-[#10162f] text-[#F8FAFC] relative">
      {/* Liquid Black Cosmos + Shooting Stars + Custom Dual-Ring Cursor (Hides Native Arrow 100%) */}
      <InteractiveAtmosphere cursorEnabled={customCursorEnabled} />

      {/* Session Conic-Ring Intro Loader */}
      {showIntroLoader && <NexusIntroLoader onFinish={handleLoaderComplete} />}

      {/* VERTICAL RIGHT-SIDE DASHBOARD NAVIGATION DOCK (Dark-Bright Frosted Pearl) */}
      <aside
        className="fixed right-4 top-5 bottom-5 z-50 w-16 lg:w-60 rounded-3xl border border-white/20 backdrop-blur-2xl flex flex-col justify-between p-3 lg:p-5 transition-all duration-300"
        style={{
          background:
            'linear-gradient(180deg, rgba(255, 255, 255, 0.12) 0%, rgba(99, 102, 241, 0.08) 55%, rgba(25, 34, 72, 0.85) 100%)',
          boxShadow: '0 24px 60px rgba(8, 12, 32, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.35)',
        }}
      >
        {/* Top Brand Identity in Vertical Right Dock */}
        <div className="space-y-4">
          <div
            onClick={() => setActiveScreen('overview')}
            className="flex items-center gap-3 p-1.5 rounded-2xl group transition"
          >
            <div
              className="w-10 h-10 rounded-2xl border border-white/40 flex items-center justify-center font-display font-bold text-xs text-white shrink-0 transition group-hover:scale-105"
              style={{
                background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                boxShadow: '0 8px 22px rgba(99, 102, 241, 0.5)',
              }}
            >
              DT
            </div>
            <div className="hidden lg:block overflow-hidden">
              <div className="flex items-center gap-1.5">
                <span className="font-display font-bold text-base tracking-tight text-white truncate">
                  DataTrust AI
                </span>
              </div>
              <p className="text-[10px] font-medium tracking-wider text-amber-200/90 uppercase truncate">
                Verify Every Answer
              </p>
            </div>
          </div>

          <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-white/25 to-transparent" />

          {/* Vertical Navigation Stack with Fluid Spring Indicator */}
          <nav className="flex flex-col gap-1.5">
            {navItems.map((item) => {
              const active = activeScreen === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveScreen(item.id)}
                  title={item.label}
                  className={`w-full px-3 lg:px-4 py-3 rounded-2xl text-xs font-semibold tracking-wide flex items-center justify-center lg:justify-start gap-3 transition-colors duration-300 relative overflow-hidden ${
                    active
                      ? 'text-white'
                      : 'text-slate-200/80 hover:text-white hover:bg-white/10'
                  }`}
                >
                  {active && (
                    <motion.div
                      layoutId="rightNavActive"
                      transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                      className="absolute inset-0 rounded-2xl bg-gradient-to-r from-indigo-500/45 via-violet-500/40 to-sky-500/35 border border-white/35 shadow-[0_8px_24px_rgba(99,102,241,0.35)]"
                    />
                  )}
                  <span className={`relative z-10 ${active ? 'text-amber-300' : 'text-indigo-200/85'}`}>
                    {item.icon}
                  </span>
                  <span className="relative z-10 hidden lg:inline truncate">{item.label}</span>
                  {active && (
                    <span className="relative z-10 hidden lg:block ml-auto w-2 h-2 rounded-full bg-amber-300 shadow-[0_0_10px_#fde68a]" />
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom Controls in Vertical Right Dock */}
        <div className="space-y-3 pt-3 border-t border-white/15">
          <button
            type="button"
            onClick={() => setCustomCursorEnabled((prev) => !prev)}
            className="w-full px-3 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 border border-white/20 text-[11px] font-medium text-white flex items-center justify-center lg:justify-start gap-2.5 transition"
            title="Toggle Custom Animated Halo Cursor"
          >
            <MousePointer className="w-3.5 h-3.5 text-amber-300 shrink-0" />
            <span className="hidden lg:inline truncate">
              {customCursorEnabled ? 'Custom Cursor Active' : 'Enable Custom Cursor'}
            </span>
          </button>

          {health && (
            <div className="hidden lg:flex items-center justify-between px-3 py-2 rounded-xl bg-white/[0.07] border border-white/15 text-[11px] font-medium text-emerald-200">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                60 FPS Locked
              </span>
              <span className="text-white/90 font-semibold">{health.graph_nodes_count} Nodes</span>
            </div>
          )}
        </div>
      </aside>

      {/* Spacious Main Content Container (Shifted Left to Accommodate Vertical Right Dock) */}
      <main className="relative z-10 flex-1 max-w-[1440px] w-full mx-auto pl-6 sm:pl-12 pr-24 lg:pr-72 py-12 sm:py-16">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeScreen}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
            style={{ willChange: 'transform, opacity' }}
          >
        {/* SCREEN A: FRONT NEXUS STAGE + SCROLL-REVEAL MAIN FUNCTIONS */}
        {activeScreen === 'overview' && (
          <div className="space-y-28">
            {/* 1. FRONT NEXUS STAGE (Full-Height Initial Viewport before Scrolling Down) */}
            <section className="min-h-[84vh] flex flex-col justify-between pt-2 pb-6">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center my-auto">
                <div className="lg:col-span-6 space-y-6">
                  <div className="space-y-3">
                    <span className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-amber-400/15 border border-amber-300/35 text-xs font-semibold text-amber-200">
                      <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                      Self-Validating Graph & SQL Intelligence
                    </span>

                    <h1 className="nexus-title text-4xl sm:text-6xl leading-[1.08] tracking-tight">
                      Ask your data.
                      <span className="block font-medium mt-1">
                        Verify every answer.
                      </span>
                    </h1>
                  </div>

                  {/* Crisp, Eye-Catching Bullet Points Instead of Long Paragraphs */}
                  <ul className="space-y-3 text-base sm:text-lg text-slate-100/95">
                    <li className="flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-amber-300 shadow-[0_0_10px_#fde68a] shrink-0" />
                      <span>
                        <strong className="text-white font-semibold">Plain-English SQL & Graph:</strong> Query messy tables & relationships without code.
                      </span>
                    </li>
                    <li className="flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-sky-300 shadow-[0_0_10px_#7dd3fc] shrink-0" />
                      <span>
                        <strong className="text-white font-semibold">Evidence Path Replay:</strong> Inspect every hop, row, and audit conflict.
                      </span>
                    </li>
                    <li className="flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-violet-300 shadow-[0_0_10px_#c4b5fd] shrink-0" />
                      <span>
                        <strong className="text-white font-semibold">Live Indian Corporate Hub:</strong> Pre-loaded with L&T, Adani, Reliance, TCS & custom data studio.
                      </span>
                    </li>
                  </ul>

                  <div className="flex flex-wrap items-center gap-3.5 pt-2">
                    <button
                      type="button"
                      onClick={() => setActiveScreen('ask')}
                      className="btn-nexus flex items-center gap-2.5"
                    >
                      <MessageSquare className="w-4 h-4" />
                      <span>Open Ask Workspace</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveScreen('studio')}
                      className="btn-nexus-outline flex items-center gap-2 !border-emerald-300/50 !text-emerald-100"
                    >
                      <PlusCircle className="w-4 h-4 text-emerald-300" />
                      <span>+ Add Your Data</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveScreen('graph')}
                      className="btn-nexus-outline flex items-center gap-2"
                    >
                      <GitBranch className="w-4 h-4 text-sky-300" />
                      <span>3D Knowledge Graph</span>
                    </button>
                  </div>

                  {health && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3">
                      <div className="p-3.5 rounded-2xl glass-panel">
                        <div className="font-display font-bold text-2xl text-white">
                          {health.connected_sources_count}
                        </div>
                        <div className="text-xs text-indigo-100/80 mt-0.5">Read-Only Databases</div>
                      </div>
                      <div className="p-3.5 rounded-2xl glass-panel">
                        <div className="font-display font-bold text-2xl text-amber-200">
                          {health.graph_nodes_count}
                        </div>
                        <div className="text-xs text-indigo-100/80 mt-0.5">Graph Entities</div>
                      </div>
                      <div className="p-3.5 rounded-2xl glass-panel">
                        <div className="font-display font-bold text-2xl text-sky-200">
                          {health.graph_confirmed_edges_count}+{health.graph_inferred_edges_count}
                        </div>
                        <div className="text-xs text-indigo-100/80 mt-0.5">Verified Links</div>
                      </div>
                      <div className="p-3.5 rounded-2xl glass-panel">
                        <div className="font-display font-bold text-2xl text-emerald-300">
                          ≤8.0B
                        </div>
                        <div className="text-xs text-indigo-100/80 mt-0.5">Model Benchmark</div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Live Front Nexus with Autonomous Random Acts */}
                <div className="lg:col-span-6">
                  <Hero3DCore />
                </div>
              </div>

              {/* Scroll Down Indicator to Reveal Main Platform Functions */}
              <div className="pt-8 flex justify-center">
                <a
                  href="#main-functions"
                  className="inline-flex items-center gap-3 px-6 py-3 rounded-full bg-white/10 hover:bg-white/15 border border-white/25 text-xs font-semibold text-amber-200 shadow-lg transition hover:translate-y-0.5"
                >
                  <span>Scroll Down to Main Functions</span>
                  <span className="animate-bounce">↓</span>
                </a>
              </div>
            </section>

            {/* 2. SCROLL-REVEALED MAIN WEBPAGE FUNCTIONS (Bullet-Point Cards) */}
            <motion.section
              id="main-functions"
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, amount: 0.15 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="space-y-8 scroll-mt-10"
            >
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div className="space-y-1.5">
                  <span className="eye-label block">Platform Capabilities</span>
                  <h2 className="text-2xl sm:text-4xl font-display font-bold text-white">
                    Main Workspace Functions
                  </h2>
                </div>
                <span className="text-xs text-indigo-200/85">
                  Click any module to launch directly
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {PLATFORM_FUNCTIONS.map((fn) => (
                  <button
                    key={fn.id}
                    type="button"
                    onClick={() => setActiveScreen(fn.id)}
                    className="text-left p-7 rounded-3xl glass-panel spotlight-card group flex flex-col justify-between gap-5"
                  >
                    <div className="space-y-3.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="px-3 py-1 rounded-full text-xs font-semibold bg-white/10 text-amber-200 border border-white/20">
                          {fn.tag}
                        </span>
                        <ArrowRight className="w-4 h-4 text-indigo-200 group-hover:translate-x-1 transition-transform" />
                      </div>
                      <h3 className="text-xl font-display font-bold text-white group-hover:text-amber-200 transition">
                        {fn.title}
                      </h3>
                      <ul className="space-y-2 text-sm text-slate-200/90">
                        {fn.bullets.map((b, idx) => (
                          <li key={idx} className="flex items-start gap-2.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-300 mt-2 shrink-0" />
                            <span>{b}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </button>
                ))}
              </div>
            </motion.section>

            {/* 3. SCROLL-REVEALED LIVE VERIFICATION PROBES (Short Bullet Points) */}
            <motion.section
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, amount: 0.15 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="space-y-8"
            >
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div className="space-y-1.5">
                  <span className="eye-label block">One-Click Verification Probes</span>
                  <h2 className="text-2xl sm:text-4xl font-display font-bold text-white">
                    Interactive Evidence Scenarios
                  </h2>
                </div>
                <span className="text-xs text-indigo-200/85">
                  Runs live SQL + Graph verification
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {EXAMPLE_QUESTIONS.map((ex, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      setActiveSourceId(ex.source_id);
                      setQuestionInput(ex.question);
                      setScopedCommunityId(undefined);
                      setActiveScreen('ask');
                      handleRunAsk(ex.question, ex.source_id);
                    }}
                    className="text-left p-7 rounded-3xl glass-panel spotlight-card group flex flex-col justify-between gap-5"
                  >
                    <div className="space-y-3.5">
                      <span className="inline-block text-xs font-semibold px-3.5 py-1 rounded-full bg-indigo-500/20 text-sky-200 border border-white/20">
                        {ex.badge}
                      </span>
                      <p className="text-base font-semibold text-white group-hover:text-amber-200 transition leading-snug">
                        {ex.question}
                      </p>
                      <ul className="space-y-1.5 text-xs text-slate-200/85 pt-1">
                        {ex.bullets.map((b, bIdx) => (
                          <li key={bIdx} className="flex items-start gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-300 mt-1.5 shrink-0" />
                            <span>{b}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="text-xs font-semibold text-amber-200 flex items-center gap-2 pt-3 border-t border-white/15">
                      <span>Verify Answer</span>
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-1.5 transition-transform" />
                    </div>
                  </button>
                ))}
              </div>
            </motion.section>
          </div>
        )}

        {/* SCREEN B: SPACIOUS, CLEAN, READABLE ASK DATA WORKSPACE */}
        {activeScreen === 'ask' && (
          <div className="max-w-[1120px] mx-auto space-y-12">
            {/* 1. Spacious Question Input Box */}
            <div className="rounded-3xl glass-panel-elevated spotlight-card p-8 sm:p-10 space-y-7">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <span className="eye-label block">ASK YOUR DATA</span>
                  <div className="flex items-center gap-3">
                    <h2 className="text-2xl sm:text-3xl font-display font-bold text-white">
                      Natural-Language Intelligence
                    </h2>
                    {scopedCommunityId && (
                      <span className="px-3.5 py-1 rounded-full text-sm font-mono bg-violet-500/20 text-violet-200 border border-violet-400/40 flex items-center gap-2">
                        Community: {scopedCommunityId}
                        <button
                          type="button"
                          onClick={() => setScopedCommunityId(undefined)}
                          className="text-slate-300 hover:text-white"
                        >
                          ×
                        </button>
                      </span>
                    )}
                  </div>
                </div>

                {/* Clean Database Selector & Add Data Shortcut */}
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setActiveScreen('studio')}
                    className="px-4 py-3 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-400/40 text-xs font-mono text-emerald-200 flex items-center gap-2 transition"
                  >
                    <PlusCircle className="w-4 h-4 text-emerald-300" />
                    <span>+ Add Company / Node</span>
                  </button>
                  <select
                    value={activeSourceId}
                    onChange={(e) => setActiveSourceId(e.target.value)}
                    className="px-4 py-3 rounded-xl bg-[#041034] border border-blue-400/40 text-sm text-white font-mono"
                  >
                    <option value="enterprise_supply_ops">
                      Database: Indian Corporate Supply & Compliance
                    </option>
                    <option value="california_schools_bird_demo">
                      Database: Regional STEM Schools (BIRD)
                    </option>
                  </select>
                </div>
              </div>

              {/* Large, Comfortable Search Input */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleRunAsk(questionInput, activeSourceId, scopedCommunityId);
                }}
                className="flex flex-col sm:flex-row gap-4"
              >
                <input
                  type="text"
                  value={questionInput}
                  onChange={(e) => setQuestionInput(e.target.value)}
                  placeholder="Ask any question about your records, relationships, contracts, or schools..."
                  className="flex-1 px-6 py-4 rounded-2xl bg-[#030d2b] border border-blue-400/40 text-base sm:text-lg text-white focus:border-cyan-300 outline-none shadow-inner"
                />
                <button
                  type="submit"
                  disabled={askLoading}
                  className="btn-nexus flex items-center justify-center gap-3 !text-xs !px-8 !py-4 shrink-0"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{askLoading ? 'Verifying...' : 'Verify Answer'}</span>
                </button>
              </form>

              {/* Clean Sample Question Pills */}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <span className="text-sm font-mono text-blue-200/70 mr-1">Try an example:</span>
                {EXAMPLE_QUESTIONS.map((ex, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      setActiveSourceId(ex.source_id);
                      setQuestionInput(ex.question);
                      handleRunAsk(ex.question, ex.source_id, scopedCommunityId);
                    }}
                    className="px-4 py-2 rounded-xl bg-[#041034]/90 hover:bg-blue-900/50 border border-blue-400/25 hover:border-cyan-300/60 text-xs sm:text-sm text-blue-100 transition"
                  >
                    {ex.badge}
                  </button>
                ))}
              </div>

              {askError && (
                <div className="p-5 rounded-2xl bg-rose-950/35 border border-rose-500/40 text-sm font-mono text-rose-200">
                  {askError}
                </div>
              )}
            </div>

            {/* 2. Spacious Results Flow */}
            {askResult && (
              <div className="space-y-10">
                {/* Executive Verified Answer Card */}
                <div className="rounded-3xl glass-panel spotlight-card p-8 sm:p-10 space-y-6">
                  <div className="flex flex-wrap items-center justify-between gap-4 border-b border-blue-400/20 pb-5">
                    <div className="flex items-center gap-3.5">
                      <ShieldCheck className="w-7 h-7 text-cyan-300 shrink-0" />
                      <div>
                        <h3 className="text-xl sm:text-2xl font-display font-bold text-white">
                          Verified Answer
                        </h3>
                        <p className="text-sm font-mono text-[#88ccff] mt-0.5">
                          Strategy: {askResult.routing.strategy_label} · Evidence Coverage:{' '}
                          {Math.round(askResult.routing.evidence_coverage_score * 100)}%
                        </p>
                      </div>
                    </div>
                    <StatusBadge status={askResult.verification_status} />
                  </div>

                  {/* Bullet-Point Formatted Verified Answer */}
                  <ul className="space-y-3 text-base sm:text-lg text-slate-100 bg-[#030d2b]/90 p-7 rounded-2xl border border-blue-400/20">
                    {(askResult.answer.includes('\n')
                      ? askResult.answer.split(/\n+/)
                      : askResult.answer.split(/(?<=[.!?])\s+(?=[A-Z•-])/)
                    )
                      .map((line) => line.replace(/^[•\-*]\s*/, '').trim())
                      .filter(Boolean)
                      .map((point, idx) => (
                        <li key={idx} className="flex items-start gap-3 leading-relaxed">
                          <span className="w-2 h-2 rounded-full bg-amber-300 mt-2.5 shrink-0 shadow-[0_0_8px_#fde68a]" />
                          <span>{point}</span>
                        </li>
                      ))}
                  </ul>

                  {/* Interactive Clarification Options if Ambiguous */}
                  {askResult.clarification_choices?.length > 0 && (
                    <div className="p-6 rounded-2xl bg-violet-950/30 border border-violet-400/40 space-y-4">
                      <div className="text-base font-semibold text-violet-200 flex items-center gap-2.5">
                        <HelpCircle className="w-5 h-5 text-violet-300" />
                        {askResult.clarification_prompt || 'Select which entity you want to inspect:'}
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {askResult.clarification_choices.map((choice, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              setQuestionInput(choice);
                              handleRunAsk(choice, askResult.source_id);
                            }}
                            className="text-left p-5 rounded-xl bg-[#030d2b] hover:bg-blue-950/70 border border-violet-400/40 text-sm sm:text-base text-violet-100 flex items-center justify-between transition"
                          >
                            <span>{choice}</span>
                            <ArrowRight className="w-5 h-5 shrink-0 ml-3" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* 3. Full-Width Signature Evidence Path Replay */}
                {(askResult.evidence_paths?.length > 0 || askResult.claim_validations?.length > 0) && (
                  <EvidencePathReplayPanel
                    question={askResult.question}
                    answerClaim={askResult.answer}
                    verificationStatus={askResult.verification_status}
                    verificationRationale={askResult.verification_rationale}
                    paths={askResult.evidence_paths || []}
                    claims={askResult.claim_validations || []}
                    missingOrConflictingNotes={askResult.missing_or_conflicting_notes || []}
                    onNavigateToGraphEntity={(entityId) => {
                      setGraphTargetEntityId(entityId);
                      setActiveScreen('graph');
                    }}
                  />
                )}

                {/* 4. Full-Width Spacious SQL Query & Results Table */}
                {askResult.sql_result && (
                  <div className="rounded-3xl glass-panel spotlight-card p-8 sm:p-10 space-y-7">
                    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-blue-400/20 pb-5">
                      <div className="flex items-center gap-3">
                        <Terminal className="w-6 h-6 text-cyan-300" />
                        <div>
                          <h3 className="text-xl sm:text-2xl font-display font-bold text-white">
                            Database Query Results
                          </h3>
                          <p className="text-sm font-mono text-emerald-300 mt-0.5">
                            {askResult.sql_result.row_count} verified rows retrieved in{' '}
                            {askResult.sql_result.execution_time_ms} ms
                          </p>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => setShowSqlEditor((prev) => !prev)}
                        className="px-4 py-2 rounded-xl bg-[#041034] hover:bg-blue-900/50 border border-blue-400/35 text-sm font-mono text-cyan-200 flex items-center gap-2 transition"
                      >
                        <Code2 className="w-4 h-4" />
                        <span>{showSqlEditor ? 'Hide SQL Query' : 'Inspect / Edit SQL'}</span>
                      </button>
                    </div>

                    {/* Collapsible SQL Query Inspector */}
                    {showSqlEditor && (
                      <div className="space-y-3 p-6 rounded-2xl bg-[#030d2b] border border-blue-400/30">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono uppercase tracking-wider text-blue-200/70">
                            Executed Read-Only SQL Query
                          </span>
                          <button
                            type="button"
                            disabled={sqlReexecLoading}
                            onClick={handleInspectAndRerunSql}
                            className="px-4 py-1.5 rounded-lg bg-blue-500/25 hover:bg-blue-500/40 text-cyan-200 border border-cyan-400/40 text-xs font-mono font-semibold transition"
                          >
                            {sqlReexecLoading ? 'Running...' : 'Re-Run SQL'}
                          </button>
                        </div>
                        <textarea
                          rows={3}
                          value={editableSql}
                          onChange={(e) => setEditableSql(e.target.value)}
                          className="w-full p-4 rounded-xl bg-[#020c28] border border-blue-400/25 font-mono text-sm text-cyan-200 focus:border-cyan-300 outline-none"
                        />
                      </div>
                    )}

                    {/* Spacious, Readable Results Table */}
                    {askResult.sql_result.rows.length > 0 && (
                      <div className="overflow-x-auto rounded-2xl border border-blue-400/25 bg-[#030d2b]">
                        <table className="w-full text-left border-collapse text-sm sm:text-base font-mono">
                          <thead>
                            <tr className="border-b border-blue-400/25 bg-blue-950/60 text-cyan-200">
                              {askResult.sql_result.columns.map((c) => (
                                <th key={c} className="py-4 px-5 whitespace-nowrap font-semibold">
                                  {c}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-blue-400/15">
                            {askResult.sql_result.rows.map((r, rIdx) => (
                              <tr key={rIdx} className="hover:bg-blue-900/25 transition">
                                {askResult.sql_result!.columns.map((c) => (
                                  <td
                                    key={c}
                                    className="py-4 px-5 whitespace-nowrap text-slate-100 tabular-nums"
                                  >
                                    {r[c] === null || r[c] === undefined ? (
                                      <span className="text-rose-300">NULL</span>
                                    ) : typeof r[c] === 'number' &&
                                      (c.toLowerCase().includes('usd') ||
                                        c.toLowerCase().includes('budget')) ? (
                                      `$${r[c].toLocaleString()}`
                                    ) : (
                                      String(r[c])
                                    )}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* Spacious Chart when applicable */}
                    {askResult.sql_result.chart_suggestion &&
                      askResult.sql_result.rows.length > 1 && (
                        <div className="pt-2 space-y-3">
                          <h4 className="text-sm font-mono uppercase tracking-wider text-blue-200/75">
                            Visual Comparison — {askResult.sql_result.chart_suggestion.title}
                          </h4>
                          <div className="h-72 w-full bg-[#030d2b]/90 p-6 rounded-2xl border border-blue-400/20">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={askResult.sql_result.rows}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#152C69" />
                                <XAxis
                                  dataKey={askResult.sql_result.chart_suggestion.x_key}
                                  stroke="#88CCFF"
                                  fontSize={12}
                                />
                                <YAxis stroke="#88CCFF" fontSize={12} />
                                <Tooltip
                                  contentStyle={{
                                    backgroundColor: '#041034',
                                    borderColor: '#3b82f6',
                                    fontSize: '13px',
                                  }}
                                />
                                {askResult.sql_result.chart_suggestion.y_keys.map((yk, idx) => (
                                  <Bar
                                    key={yk}
                                    dataKey={yk}
                                    fill={idx === 0 ? '#38BDF8' : '#A78BFA'}
                                    radius={[6, 6, 0, 0]}
                                  />
                                ))}
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}
                  </div>
                )}

                {/* 5. Supporting Documents (Clean & Readable) */}
                {askResult.semantic_evidence?.length > 0 && (
                  <div className="rounded-3xl glass-panel spotlight-card p-8 sm:p-10 space-y-5">
                    <h3 className="text-xl font-display font-bold text-white flex items-center gap-3">
                      <FileText className="w-5 h-5 text-violet-300" />
                      Supporting Compliance & Policy Documents
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      {askResult.semantic_evidence.slice(0, 2).map((doc: any, idx: number) => (
                        <div
                          key={idx}
                          className="p-6 rounded-2xl bg-[#030d2b]/90 border border-blue-400/20 space-y-2.5"
                        >
                          <div className="font-mono text-sm text-[#88ccff] font-semibold">
                            {doc.id} — {doc.title}
                          </div>
                          <p className="text-sm sm:text-base text-blue-100/90 leading-relaxed font-light">
                            “{doc.excerpt}”
                          </p>
                          {doc.conflicts?.length > 0 && (
                            <div className="rounded-xl border border-amber-400/35 bg-amber-950/30 p-3 space-y-2">
                              <div className="text-xs font-semibold uppercase tracking-wide text-amber-200">
                                Conflicting claims · review both sources
                              </div>
                              {doc.conflicts.flatMap((group: any) => group.claims).map((claim: any, claimIdx: number) => (
                                <div key={`${claim.document_id}-${claim.value}-${claimIdx}`} className="text-xs text-amber-100/90">
                                  <span className="font-semibold">{claim.subject}: {claim.value}</span>
                                  <span className="block text-amber-100/60">{claim.document_id} · {claim.title}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* SCREEN B2: ADD / MANAGE DATA STUDIO */}
        {activeScreen === 'studio' && (
          <DataStudioView
            onDataUpdated={() => {
              api.getHealth().then(setHealth).catch(console.error);
              api
                .getSources()
                .then((res) => setSources(res.sources || []))
                .catch(console.error);
            }}
            onAskAboutCompany={(q) => {
              setActiveSourceId('enterprise_supply_ops');
              setQuestionInput(q);
              setScopedCommunityId(undefined);
              setActiveScreen('ask');
              handleRunAsk(q, 'enterprise_supply_ops');
            }}
          />
        )}

        {/* SCREEN C: KNOWLEDGE GRAPH EXPLORER */}
        {activeScreen === 'graph' && (
          <GraphExplorerView
            activeSourceId={activeSourceId}
            initialSelectedEntityId={graphTargetEntityId}
          />
        )}

        {/* SCREEN D: COMMUNITY EXPLORER */}
        {activeScreen === 'communities' && (
          <CommunityExplorerView
            activeSourceId={activeSourceId}
            onAskCommunityQuestion={(q, commId, srcId) => {
              setActiveSourceId(srcId);
              setScopedCommunityId(commId);
              setQuestionInput(q);
              setActiveScreen('ask');
              handleRunAsk(q, srcId, commId);
            }}
          />
        )}

        {/* SCREEN E: ROUTING INSPECTOR */}
        {activeScreen === 'routing' && (
          <RoutingInspectorView
            activeSourceId={activeSourceId}
            onExecuteInAskWorkspace={(q, srcId) => {
              setActiveSourceId(srcId);
              setQuestionInput(q);
              setScopedCommunityId(undefined);
              setActiveScreen('ask');
              handleRunAsk(q, srcId);
            }}
          />
        )}

        {/* SCREEN F: DATABASE EXPLORER */}
        {activeScreen === 'database' && (
          <DatabaseExplorerView
            activeSourceId={activeSourceId}
            onSourceChange={(srcId) => setActiveSourceId(srcId)}
          />
        )}

        {/* SCREEN G: EVALUATION DASHBOARD */}
        {activeScreen === 'evaluation' && <EvaluationDashboardView />}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Spacious Footer */}
      <footer className="relative z-10 border-t border-white/15 bg-white/[0.03] backdrop-blur-xl py-7 pl-6 sm:pl-12 pr-24 lg:pr-72 mt-20">
        <div className="max-w-[1440px] mx-auto flex flex-wrap items-center justify-between gap-4 text-xs text-indigo-100/75 font-medium">
          <div>
            DataTrust AI — Ask your data. Verify every answer.
          </div>
          <div className="flex items-center gap-4">
            <span>Read-Only SQLite Guard</span>
            <span>•</span>
            <span>3D Knowledge Graph</span>
            <span>•</span>
            <span>≤8B Benchmark Ready</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
