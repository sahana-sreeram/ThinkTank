import React, { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  CheckCircle2,
  Circle,
  Loader2,
  ArrowRight,
  Zap,
  ChevronDown,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface StreamMessage {
  name: string;
  content: string;
  round?: number;
}

interface StepDef {
  id: string;
  label: string;
  keys: string[];
}

type StepStatus = 'idle' | 'active' | 'done';

interface LensTab {
  id: string;
  label: string;
  entries: StreamMessage[];
}

interface PolicySection {
  title: string;
  content: string;
  expanded: boolean;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const GRAPH_STEPS: StepDef[] = [
  { id: 'plan',        label: 'Policy Planning',       keys: ['plan_policy', 'director', 'planning'] },
  { id: 'research',    label: 'Evidence Research',      keys: ['research_agent', 'node_research', '# research'] },
  { id: 'stakeholder', label: 'Stakeholder Analysis',   keys: ['stakeholder', 'lens', 'equity', 'economic', 'operational'] },
  { id: 'synthesize',  label: 'Synthesis',              keys: ['synthes', 'synthesize_research'] },
  { id: 'recommend',   label: 'Recommendation',         keys: ['implement', 'recommend', 'policy_recommendation'] },
  { id: 'forecast',    label: 'Forecast',               keys: ['forecast', 'run_forecast'] },
  { id: 'finalize',    label: 'Finalizing',             keys: ['finaliz', 'finalize_result', '__end__'] },
];

const LENS_TABS: LensTab[] = [
  { id: 'all',         label: 'All',         entries: [] },
  { id: 'equity',      label: 'Equity',      entries: [] },
  { id: 'economic',    label: 'Economic',    entries: [] },
  { id: 'operational', label: 'Operations',  entries: [] },
  { id: 'research',    label: 'Research',    entries: [] },
];

const SCENARIOS = ['Baseline', 'Conservative', 'Expected', 'Optimistic'];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function classifyMessage(msg: StreamMessage): 'orchestrator' | 'briefing' | 'policy' | 'forecast' | 'system' {
  const n = msg.name.toLowerCase();
  if (n.includes('forecast') || n.includes('run_forecast'))                                          return 'forecast';
  if (n.includes('implement') || n.includes('recommend') || n.includes('synthes') || n.includes('final')) return 'policy';
  if (n.includes('research') || n.includes('stakeholder') || n.includes('retriev') || n.includes('context')) return 'briefing';
  if (n.includes('plan') || n.includes('director') || n.includes('system') || n.includes('starting')) return 'orchestrator';
  return 'system';
}

function detectLens(msg: StreamMessage): string {
  const text = (msg.name + ' ' + msg.content).toLowerCase();
  if (text.includes('equity') || text.includes('justice') || text.includes('access'))                     return 'equity';
  if (text.includes('economic') || text.includes('cost') || text.includes('revenue') || text.includes('fiscal')) return 'economic';
  if (text.includes('operational') || text.includes('transit') || text.includes('infrastructure'))         return 'operational';
  if (text.includes('research') || text.includes('evidence') || text.includes('study'))                   return 'research';
  return 'all';
}

function matchesStep(msg: StreamMessage, step: StepDef): boolean {
  const n = msg.name.toLowerCase();
  return step.keys.some(k => n.includes(k));
}

// ─── Sub-components ───────────────────────────────────────────────────────────

type AccentColor = 'blue' | 'emerald' | 'violet' | 'amber';

const ACCENT: Record<AccentColor, { dot: string; label: string; border: string; badge: string }> = {
  blue:    { dot: 'bg-blue-500',    label: 'text-blue-400',    border: 'border-blue-500/20',    badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20'    },
  emerald: { dot: 'bg-emerald-500', label: 'text-emerald-400', border: 'border-emerald-500/20', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  violet:  { dot: 'bg-violet-500',  label: 'text-violet-400',  border: 'border-violet-500/20',  badge: 'bg-violet-500/10 text-violet-400 border-violet-500/20'  },
  amber:   { dot: 'bg-amber-500',   label: 'text-amber-400',   border: 'border-amber-500/20',   badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20'   },
};

function CellHeader({
  color,
  num,
  label,
  badge,
  count,
}: {
  color: AccentColor;
  num: string;
  label: string;
  badge?: string;
  count?: number;
}) {
  const a = ACCENT[color];
  return (
    <div className="px-4 py-3 border-b border-[#141c2a] flex items-center gap-2.5 shrink-0">
      <span className={`text-[9px] font-mono font-bold ${a.label} opacity-50`}>{num}</span>
      <div className={`w-1.5 h-1.5 rounded-full ${a.dot}`} />
      <span className={`text-[10px] font-mono font-bold uppercase tracking-widest ${a.label}`}>{label}</span>
      <div className="flex-1" />
      {count !== undefined && count > 0 && (
        <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${a.badge}`}>{count}</span>
      )}
      {badge && (
        <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${a.badge}`}>{badge}</span>
      )}
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="h-full flex items-center justify-center">
      <p className="text-[10px] font-mono text-[#2d3f57] uppercase tracking-widest">{label}</p>
    </div>
  );
}

function StepPip({ status }: { status: StepStatus }) {
  if (status === 'done')   return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />;
  if (status === 'active') return <Loader2 className="h-3.5 w-3.5 text-blue-400 shrink-0 animate-spin" />;
  return <Circle className="h-3.5 w-3.5 text-[#1e2a3a] shrink-0" />;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function PolicyBriefing() {
  const [query, setQuery]           = useState('');
  const [running, setRunning]       = useState(false);
  const [status, setStatus]         = useState('Ready');
  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>(
    () => Object.fromEntries(GRAPH_STEPS.map(s => [s.id, 'idle']))
  );

  const [lenses, setLenses]         = useState<LensTab[]>(LENS_TABS.map(l => ({ ...l, entries: [] })));
  const [activeTab, setActiveTab]   = useState('all');
  const [policyDocs, setPolicyDocs] = useState<PolicySection[]>([]);
  const [rawPolicyStream, setRawPolicyStream] = useState<StreamMessage[]>([]);
  const [forecastMsgs, setForecastMsgs] = useState<StreamMessage[]>([]);
  const [orchLog, setOrchLog]           = useState<string[]>([]);

  const socketRef = useRef<WebSocket | null>(null);

  const handleMessage = useCallback((msg: StreamMessage) => {
    if (msg.name === '__end__') {
      setRunning(false);
      setStatus('Briefing complete');
      setStepStatuses(prev => {
        const next = { ...prev };
        GRAPH_STEPS.forEach(s => { next[s.id] = 'done'; });
        return next;
      });
      return;
    }

    setStepStatuses(prev => {
      const next = { ...prev };
      GRAPH_STEPS.forEach((step, idx) => {
        if (matchesStep(msg, step)) {
          GRAPH_STEPS.slice(0, idx).forEach(s => { next[s.id] = 'done'; });
          next[step.id] = 'active';
        }
      });
      return next;
    });

    const cls = classifyMessage(msg);

    if (cls === 'orchestrator' || cls === 'system') {
      setOrchLog(prev => [...prev, `[${msg.name}] ${msg.content.slice(0, 100)}`]);
    }

    if (cls === 'briefing') {
      const lens = detectLens(msg);
      setLenses(prev => prev.map(tab => {
        if (tab.id === 'all' || tab.id === lens) {
          return { ...tab, entries: [...tab.entries, msg] };
        }
        return tab;
      }));
    }

    if (cls === 'policy') {
      setRawPolicyStream(prev => [...prev, msg]);
      setPolicyDocs(prev => {
        const existing = prev.find(s => s.title === msg.name);
        if (existing) {
          return prev.map(s =>
            s.title === msg.name ? { ...s, content: s.content + '\n\n' + msg.content } : s
          );
        }
        return [...prev, { title: msg.name, content: msg.content, expanded: true }];
      });
    }

    if (cls === 'forecast') {
      setForecastMsgs(prev => [...prev, msg]);
    }
  }, []);

  const startAnalysis = useCallback(() => {
    if (!query.trim() || running) return;
    socketRef.current?.close();
    socketRef.current = null;

    setRunning(true);
    setStatus('Connecting…');
    setStepStatuses(Object.fromEntries(GRAPH_STEPS.map(s => [s.id, 'idle'])));
    setLenses(LENS_TABS.map(l => ({ ...l, entries: [] })));
    setActiveTab('all');
    setPolicyDocs([]);
    setRawPolicyStream([]);
    setForecastMsgs([]);
    setOrchLog([]);

    const ws = new WebSocket('ws://localhost:8000/ws/policy');
    socketRef.current = ws;

    ws.onopen  = () => { setStatus('Transmitting…'); ws.send(JSON.stringify({ query: query.trim() })); };
    ws.onmessage = (evt) => {
      try { handleMessage(JSON.parse(evt.data)); }
      catch (e) { console.error('WS parse error', e); }
    };
    ws.onerror = () => setStatus('Connection error — check server');
    ws.onclose = () => { setRunning(false); socketRef.current = null; };
  }, [query, running, handleMessage]);

  useEffect(() => () => { socketRef.current?.close(); }, []);

  const toggleSection = (idx: number) => {
    setPolicyDocs(prev => prev.map((s, i) => i === idx ? { ...s, expanded: !s.expanded } : s));
  };

  const activeLensEntries = lenses.find(l => l.id === activeTab)?.entries ?? [];
  const totalSources = lenses.find(l => l.id === 'all')?.entries.length ?? 0;

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen bg-[#07090e] flex flex-col overflow-hidden" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="h-14 border-b border-[#141c2a] flex items-center px-5 gap-4 shrink-0">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-7 h-7 bg-blue-500 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/30">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-white text-sm font-bold tracking-tight">ThinkTank</span>
        </div>
        <div className="w-px h-5 bg-[#1a2133]" />
        <span className="text-[10px] font-mono text-[#2d3f57] uppercase tracking-widest hidden lg:block">
          Policy Intelligence Platform
        </span>

        <div className="flex-1" />

        {/* Query input */}
        <div className="flex items-center gap-2 w-full max-w-xl">
          <input
            type="text"
            className="flex-1 bg-[#0c1018] border border-[#1a2133] rounded-lg px-3 py-2 text-[11px] text-slate-200 placeholder:text-[#2d3f57] focus:outline-none focus:border-blue-500/40 font-mono transition-colors"
            placeholder="e.g. Should Boston implement congestion pricing downtown?"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && startAnalysis()}
            disabled={running}
          />
          <button
            onClick={startAnalysis}
            disabled={running || !query.trim()}
            className="shrink-0 px-4 py-2 rounded-lg bg-blue-500 hover:bg-blue-400 active:bg-blue-600 disabled:bg-[#141c2a] disabled:text-[#2d3f57] disabled:cursor-not-allowed text-white text-[11px] font-bold tracking-wide transition-colors flex items-center gap-1.5"
          >
            {running
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing</>
              : <><ArrowRight className="w-3.5 h-3.5" /> Analyze</>}
          </button>
        </div>

        <div className="flex items-center gap-2 shrink-0 ml-2">
          <div className={`w-1.5 h-1.5 rounded-full transition-colors ${
            running ? 'bg-blue-400 animate-pulse' :
            status.includes('complete') ? 'bg-emerald-400' :
            'bg-[#1e2a3a]'
          }`} />
          <span className="text-[10px] font-mono text-[#3a4a60] hidden sm:block">{status}</span>
        </div>
      </header>

      {/* ── Bento Grid ─────────────────────────────────────────────────────── */}
      <div
        className="flex-1 p-3 gap-3 min-h-0 overflow-hidden"
        style={{
          display: 'grid',
          gridTemplateColumns: '256px 1fr 1.6fr',
          gridTemplateRows: '1fr 200px',
        }}
      >

        {/* ── Cell 1: Policy Director ─────────────────────────────────────── */}
        <div className="rounded-2xl border border-[#141c2a] bg-[#0a0d14] flex flex-col overflow-hidden">
          <CellHeader color="blue" num="01" label="Policy Director" />

          <div className="flex-1 overflow-y-auto p-4">
            <ol className="space-y-1">
              {GRAPH_STEPS.map((step, idx) => {
                const st = stepStatuses[step.id];
                return (
                  <li key={step.id} className="flex items-start gap-3">
                    <div className="flex flex-col items-center shrink-0 pt-0.5">
                      <StepPip status={st} />
                      {idx < GRAPH_STEPS.length - 1 && (
                        <div
                          className={`w-px mt-1 mb-1 ${st === 'done' ? 'bg-emerald-500/30' : 'bg-[#141c2a]'}`}
                          style={{ minHeight: 14 }}
                        />
                      )}
                    </div>
                    <span className={`text-[11px] leading-tight py-0.5 ${
                      st === 'active' ? 'text-white font-semibold' :
                      st === 'done'   ? 'text-emerald-400/80'      :
                                        'text-[#2d3f57]'
                    }`}>
                      {step.label}
                    </span>
                  </li>
                );
              })}
            </ol>
          </div>

          {orchLog.length > 0 && (
            <div className="border-t border-[#141c2a] p-3 max-h-28 overflow-y-auto shrink-0">
              <div className="text-[9px] font-mono text-[#2d3f57] uppercase tracking-widest mb-1.5">Activity</div>
              {orchLog.slice(-6).map((line, i) => (
                <p key={i} className="text-[9px] font-mono text-[#3a4a60] leading-relaxed truncate">{line}</p>
              ))}
            </div>
          )}
        </div>

        {/* ── Cell 2: Stakeholder Research ────────────────────────────────── */}
        <div className="rounded-2xl border border-[#141c2a] bg-[#0a0d14] flex flex-col overflow-hidden">
          <CellHeader color="emerald" num="02" label="Stakeholder Research" count={totalSources} />

          {/* Lens tabs */}
          <div className="flex border-b border-[#141c2a] px-3 gap-0 shrink-0">
            {lenses.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-2.5 py-2 text-[9px] font-mono font-bold uppercase tracking-wider transition-colors relative ${
                  activeTab === tab.id ? 'text-emerald-400' : 'text-[#2d3f57] hover:text-slate-500'
                }`}
              >
                {tab.label}
                {activeTab === tab.id && (
                  <span className="absolute bottom-0 left-0 right-0 h-px bg-emerald-500" />
                )}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            {activeLensEntries.length === 0 ? (
              <EmptyState label={running ? 'Gathering intelligence…' : 'No sources yet'} />
            ) : (
              <div className="space-y-2">
                {activeLensEntries.map((msg, i) => (
                  <div key={i} className="rounded-xl border border-[#141c2a] bg-[#07090e] p-3">
                    <div className="flex items-start gap-2">
                      <span className="text-[9px] font-mono text-[#2d3f57] shrink-0 mt-0.5 tabular-nums">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[11px] font-semibold text-slate-300 leading-tight truncate">{msg.name}</p>
                        <p className="text-[10px] text-[#3a4a60] mt-1 line-clamp-2 leading-relaxed">
                          {msg.content.slice(0, 160)}{msg.content.length > 160 ? '…' : ''}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Cell 3: Recommendation Engine (spans 2 rows) ────────────────── */}
        <div
          className="rounded-2xl border border-[#141c2a] bg-[#0a0d14] flex flex-col overflow-hidden"
          style={{ gridRow: '1 / 3' }}
        >
          <CellHeader
            color="violet"
            num="03"
            label="Recommendation Engine"
            badge={rawPolicyStream.length > 0 ? 'LIVE' : undefined}
          />

          <div className="flex-1 overflow-y-auto p-4">
            {policyDocs.length === 0 ? (
              <EmptyState label={running ? 'Building recommendation…' : 'Awaiting policy document'} />
            ) : (
              <div className="space-y-2.5">
                {policyDocs.map((section, i) => (
                  <div key={i} className="rounded-xl border border-[#1a2133] overflow-hidden">
                    <button
                      onClick={() => toggleSection(i)}
                      className="w-full flex items-center justify-between px-4 py-2.5 bg-[#07090e] hover:bg-[#0d1120] transition-colors text-left"
                    >
                      <span className="text-[10px] font-mono font-bold text-violet-400 uppercase tracking-wider">
                        {section.title}
                      </span>
                      <ChevronDown
                        className={`w-3.5 h-3.5 text-[#2d3f57] transition-transform duration-200 ${
                          section.expanded ? '' : '-rotate-90'
                        }`}
                      />
                    </button>
                    {section.expanded && (
                      <div className="px-4 py-3 text-[11px] text-slate-400 leading-relaxed border-t border-[#141c2a]
                        [&_h1]:text-sm [&_h1]:font-bold [&_h1]:text-slate-200 [&_h1]:mb-2 [&_h1]:mt-3
                        [&_h2]:text-xs [&_h2]:font-bold [&_h2]:text-slate-300 [&_h2]:mb-1.5 [&_h2]:mt-2.5
                        [&_h3]:text-[11px] [&_h3]:font-bold [&_h3]:text-slate-300 [&_h3]:mb-1
                        [&_p]:mb-2 [&_p]:last:mb-0
                        [&_ul]:pl-4 [&_ul]:mb-2 [&_ul]:space-y-0.5
                        [&_ol]:pl-4 [&_ol]:mb-2 [&_ol]:space-y-0.5
                        [&_li]:text-slate-400
                        [&_strong]:text-slate-200 [&_strong]:font-semibold
                        [&_code]:bg-[#141c2a] [&_code]:text-violet-300 [&_code]:px-1 [&_code]:rounded [&_code]:text-[10px] [&_code]:font-mono
                      ">
                        <ReactMarkdown>{section.content}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Cell 4: Forecast Engine (cols 1–2, row 2) ───────────────────── */}
        <div
          className="rounded-2xl border border-[#141c2a] bg-[#0a0d14] flex flex-col overflow-hidden"
          style={{ gridColumn: '1 / 3' }}
        >
          <CellHeader color="amber" num="04" label="Deterministic Forecast Engine" badge="LLM-FREE" />

          <div className="flex-1 p-3 overflow-hidden">
            {forecastMsgs.length === 0 ? (
              <div className="h-full grid grid-cols-4 gap-3">
                {SCENARIOS.map(s => (
                  <div
                    key={s}
                    className="rounded-xl border border-[#141c2a] bg-[#07090e] flex flex-col items-center justify-center gap-1.5"
                  >
                    <span className="text-[9px] font-mono text-[#2d3f57] uppercase tracking-widest">{s}</span>
                    <span className="text-xl font-bold text-[#1a2133] font-mono">—</span>
                    {running && stepStatuses['forecast'] === 'active' && (
                      <div className="w-8 h-0.5 bg-[#1a2133] rounded-full overflow-hidden">
                        <div className="h-full bg-amber-500 rounded-full animate-pulse" style={{ width: '60%' }} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-full grid grid-cols-2 gap-3 overflow-auto">
                {forecastMsgs.map((msg, i) => (
                  <div key={i} className="rounded-xl border border-[#1a2133] bg-[#07090e] p-3">
                    <div className="text-[9px] font-mono text-amber-500 uppercase tracking-widest mb-2">{msg.name}</div>
                    <pre className="text-[10px] text-slate-400 whitespace-pre-wrap leading-relaxed overflow-auto max-h-24 font-mono">
                      {msg.content}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
