import { useState, useEffect, useCallback } from 'react'

/* ───────────────── Inline styles (no external CSS deps) ───────────────── */

const COLORS = {
  bg: '#0a0a0f',
  surface: '#12121a',
  surfaceHover: '#1a1a2e',
  border: '#1e1e2e',
  accent: '#6c63ff',
  accentGlow: 'rgba(108,99,255,.35)',
  green: '#00e676',
  amber: '#ffab00',
  red: '#ff5252',
  text: '#e0e0e0',
  textDim: '#888',
  white: '#fff',
}

const fontStack = "'Inter','SF Pro Display',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"

/* ───────────────── Tiny animated particle background ───────────────── */

function ParticleBg() {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 0, overflow: 'hidden', pointerEvents: 'none' }}>
      {Array.from({ length: 30 }).map((_, i) => {
        const size = 2 + Math.random() * 3
        const x = Math.random() * 100
        const dur = 15 + Math.random() * 25
        const delay = Math.random() * -30
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              width: size,
              height: size,
              borderRadius: '50%',
              background: i % 3 === 0 ? COLORS.accent : i % 3 === 1 ? COLORS.green : COLORS.amber,
              opacity: 0.15 + Math.random() * 0.15,
              left: `${x}%`,
              top: '100%',
              animation: `floatUp ${dur}s ${delay}s linear infinite`,
            }}
          />
        )
      })}
      <style>{`
        @keyframes floatUp {
          0%   { transform: translateY(0) scale(1); opacity: .2 }
          100% { transform: translateY(-110vh) scale(.3); opacity: 0 }
        }
      `}</style>
    </div>
  )
}

/* ───────────────── Glowing card ───────────────── */

function Card({ children, style, glow }) {
  const [hover, setHover] = useState(false)
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? COLORS.surfaceHover : COLORS.surface,
        border: `1px solid ${hover && glow ? glow : COLORS.border}`,
        borderRadius: 16,
        padding: '28px 24px',
        transition: 'all .25s ease',
        boxShadow: hover && glow ? `0 0 30px ${glow}40` : 'none',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

/* ───────────────── Animated counter ───────────────── */

function AnimNum({ target, suffix = '' }) {
  const [val, setVal] = useState(0)
  useEffect(() => {
    let frame
    const start = performance.now()
    const dur = 1200
    const tick = (now) => {
      const t = Math.min((now - start) / dur, 1)
      const ease = 1 - Math.pow(1 - t, 3)
      setVal(Math.round(ease * target))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target])
  return <span>{val}{suffix}</span>
}

/* ───────────────── Live demo console ───────────────── */

const DEMO_LINES = [
  { type: 'cmd', text: '→ call_api("/v1/deals/update", {deal_id: "DEAL-001", stage: "closed-won"})' },
  { type: 'err', text: '✗ 404 — Endpoint deprecated. Deals API migrated to v2.' },
  { type: 'cmd', text: '→ read_docs("api_usage")' },
  { type: 'warn', text: '⚠ WARNING: Documentation reliability is degraded. Cross-reference before acting.' },
  { type: 'cmd', text: '→ ask_manager("How do I update deals?")' },
  { type: 'err', text: '✗ Manager unavailable — "I\'m in back-to-back meetings right now."' },
  { type: 'cmd', text: '→ check_policy("deal_approval")' },
  { type: 'ok', text: '✓ Policy v2: Deals > $25K require VP approval AND compliance review.' },
  { type: 'cmd', text: '→ call_api("/v2/compliance/generate", {deal_id: "DEAL-001"})' },
  { type: 'ok', text: '✓ 200 — compliance_id: COMP-A7F3E291' },
  { type: 'cmd', text: '→ call_api("/v2/deals/update", {deal_id: "DEAL-001", stage: "closed-won", compliance_id: "COMP-A7F3E291"})' },
  { type: 'ok', text: '✓ 200 — Deal DEAL-001 updated to closed-won' },
  { type: 'alert', text: '🔔 ALERT: Previous ticket resolution (refund) was incorrect. Client escalated — TKT-200 created.' },
]

function LiveConsole() {
  const [lines, setLines] = useState([])
  const [idx, setIdx] = useState(0)

  useEffect(() => {
    if (idx >= DEMO_LINES.length) {
      const t = setTimeout(() => { setLines([]); setIdx(0) }, 3000)
      return () => clearTimeout(t)
    }
    const delay = DEMO_LINES[idx].type === 'cmd' ? 1400 : 700
    const t = setTimeout(() => {
      setLines(prev => [...prev, DEMO_LINES[idx]])
      setIdx(i => i + 1)
    }, delay)
    return () => clearTimeout(t)
  }, [idx])

  const lineColor = {
    cmd: COLORS.textDim,
    ok: COLORS.green,
    err: COLORS.red,
    warn: COLORS.amber,
    alert: '#ff6e40',
  }

  return (
    <div style={{
      background: '#0d0d14',
      border: `1px solid ${COLORS.border}`,
      borderRadius: 12,
      padding: '16px 20px',
      fontFamily: "'JetBrains Mono','Fira Code',monospace",
      fontSize: 13,
      lineHeight: 1.7,
      height: 360,
      overflowY: 'auto',
      position: 'relative',
    }}>
      <div style={{ position: 'absolute', top: 12, right: 16, display: 'flex', gap: 6 }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: COLORS.red }} />
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: COLORS.amber }} />
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: COLORS.green }} />
      </div>
      <div style={{ color: COLORS.textDim, marginBottom: 8, fontSize: 11 }}>enterprise-arena / episode simulation</div>
      {lines.map((l, i) => (
        <div key={i} style={{ color: lineColor[l.type] || COLORS.text, opacity: 0, animation: 'fadeSlide .3s ease forwards' }}>
          {l.text}
        </div>
      ))}
      {idx < DEMO_LINES.length && (
        <span style={{ display: 'inline-block', width: 8, height: 16, background: COLORS.accent, animation: 'blink 1s step-end infinite', verticalAlign: 'middle' }} />
      )}
      <style>{`
        @keyframes fadeSlide { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:translateY(0) } }
        @keyframes blink { 50% { opacity: 0 } }
      `}</style>
    </div>
  )
}

/* ───────────────── Trust score bars ───────────────── */

function TrustBar({ label, value, color }) {
  const [width, setWidth] = useState(0)
  useEffect(() => { const t = setTimeout(() => setWidth(value * 100), 300); return () => clearTimeout(t) }, [value])
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
        <span style={{ color: COLORS.text }}>{label}</span>
        <span style={{ color, fontWeight: 600 }}>{Math.round(value * 100)}%</span>
      </div>
      <div style={{ height: 6, background: '#1a1a2e', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${width}%`, background: color, borderRadius: 3, transition: 'width 1s ease' }} />
      </div>
    </div>
  )
}

/* ───────────────── Architecture diagram ───────────────── */

function ArchDiagram() {
  const box = (label, sub, x, y, color) => (
    <g key={label}>
      <rect x={x} y={y} width={140} height={54} rx={10} fill={COLORS.surface} stroke={color} strokeWidth={1.5} />
      <text x={x + 70} y={y + 22} textAnchor="middle" fill={COLORS.white} fontSize={12} fontWeight={600} fontFamily={fontStack}>{label}</text>
      <text x={x + 70} y={y + 40} textAnchor="middle" fill={COLORS.textDim} fontSize={9} fontFamily={fontStack}>{sub}</text>
    </g>
  )
  const arrow = (x1, y1, x2, y2, color) => (
    <line key={`${x1}${y1}${x2}${y2}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={1.5} markerEnd="url(#arrowhead)" strokeDasharray="5,3" />
  )
  return (
    <svg viewBox="0 0 600 220" style={{ width: '100%', maxWidth: 600 }}>
      <defs>
        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill={COLORS.textDim} />
        </marker>
      </defs>
      {box('AI Agent', 'LLM / RL Policy', 30, 80, COLORS.accent)}
      {box('MCP Tools', '11 Enterprise Tools', 230, 10, COLORS.green)}
      {box('Drift Engine', 'Stochastic Chaos', 230, 80, COLORS.amber)}
      {box('Cascade Engine', 'Consequence Chains', 230, 150, COLORS.red)}
      {box('Grader', '5-Component Score', 430, 80, COLORS.accent)}

      {arrow(170, 95, 230, 37, COLORS.green)}
      {arrow(170, 107, 230, 107, COLORS.amber)}
      {arrow(170, 115, 230, 170, COLORS.red)}
      {arrow(370, 37, 430, 95, COLORS.green)}
      {arrow(370, 107, 430, 107, COLORS.amber)}
      {arrow(370, 177, 430, 115, COLORS.red)}
    </svg>
  )
}

/* ───────────────── Difficulty tiers ───────────────── */

const TIERS = [
  {
    id: 'easy', name: 'Easy', color: COLORS.green, icon: '🟢',
    desc: 'Close a deal. One API drift mid-task.',
    drifts: 1, sources: 0, cascades: 'None', steps: 40,
    deals: 1, tickets: 0,
  },
  {
    id: 'medium', name: 'Medium', color: COLORS.amber, icon: '🟡',
    desc: 'Deal + ticket. Manager lies, docs outdated.',
    drifts: 2, sources: 3, cascades: 'Escalation', steps: 60,
    deals: 2, tickets: 2,
  },
  {
    id: 'hard', name: 'Hard', color: COLORS.red, icon: '🔴',
    desc: 'Full audit. 3 drifts, cascading failures.',
    drifts: 3, sources: 5, cascades: 'Full chain', steps: 100,
    deals: 3, tickets: 3,
  },
]

/* ───────────────── Features ───────────────── */

const FEATURES = [
  {
    icon: '🌊', title: 'Stochastic Drift',
    desc: 'API schemas, policy thresholds, and required fields shift at unpredictable times within randomized windows. No two episodes are the same.',
    color: COLORS.amber,
  },
  {
    icon: '💥', title: 'Cascading Consequences',
    desc: 'Wrong decisions ripple forward. A bad ticket resolution triggers a client escalation 3 steps later. A compliance gap spawns an audit.',
    color: COLORS.red,
  },
  {
    icon: '🎭', title: 'Adversarial Information',
    desc: 'Your manager gives wrong advice. Documentation is outdated. Only the CRM and policy system are trustworthy — if you know which to check.',
    color: '#e040fb',
  },
  {
    icon: '📉', title: 'Functional Trust Scores',
    desc: 'Trust isn\'t decorative — it changes tool behavior. Low manager trust makes them unavailable. Low docs trust shows reliability warnings.',
    color: COLORS.accent,
  },
]

/* ───────────────── Episode Replay Timeline ───────────────── */

const REPLAY_STEPS = [
  { step: 1, tool: 'read_task_brief', result: 'ok', summary: 'Read objectives: close DEAL-001, resolve TKT-100, file reports', trust: { crm: 1, api: 1, docs: 1, mgr: 1, policy: 1 }, events: [] },
  { step: 2, tool: 'query_crm', args: 'DEAL-001', result: 'ok', summary: 'Acme Corp, $75K Enterprise Suite, stage: negotiation', trust: { crm: 1, api: 1, docs: 1, mgr: 1, policy: 1 }, events: [] },
  { step: 3, tool: 'read_docs', args: 'api_usage', result: 'ok', summary: 'Docs show v1 endpoints (outdated but no warning yet)', trust: { crm: 1, api: 1, docs: 1, mgr: 1, policy: 1 }, events: [] },
  { step: 4, tool: 'call_api', args: '/v1/deals/update', result: 'ok', summary: 'Deal updated via v1 — works (drift hasn\'t fired yet)', trust: { crm: 1, api: 1, docs: 1, mgr: 1, policy: 1 }, events: [] },
  { step: 5, tool: 'query_crm', args: 'TKT-100', result: 'ok', summary: 'Data export failing since API migration, priority: high', trust: { crm: 1, api: 1, docs: 1, mgr: 1, policy: 1 }, events: [] },
  { step: 6, tool: 'ask_manager', args: 'TKT-100 resolution?', result: 'warn', summary: '"Just process a refund. Data issues are client-side."', trust: { crm: 1, api: 1, docs: 1, mgr: 0.85, policy: 1 }, events: ['bad_advice'] },
  { step: 7, tool: 'check_policy', args: 'complaint_handling', result: 'ok', summary: 'Policy says: verify root cause. Valid: technical_fix, workaround, escalation, refund', trust: { crm: 1, api: 1, docs: 1, mgr: 0.85, policy: 1 }, events: ['cross_verify'] },
  { step: 8, tool: 'resolve_ticket', args: 'TKT-100, technical_fix', result: 'ok', summary: 'Resolved with technical_fix (ignored manager\'s "refund" advice)', trust: { crm: 1, api: 1, docs: 1, mgr: 0.7, policy: 1 }, events: [] },
  { step: 9, tool: 'call_api', args: '/v1/deals/update DEAL-002', result: 'err', summary: '404 — Endpoint deprecated. Deals API migrated to v2.', trust: { crm: 1, api: 0.7, docs: 0.8, mgr: 0.7, policy: 1 }, events: ['drift_api'] },
  { step: 10, tool: 'read_docs', args: 'api_usage', result: 'warn', summary: '⚠ Reliability warning shown. Now shows v2 endpoints.', trust: { crm: 1, api: 0.7, docs: 0.6, mgr: 0.7, policy: 1 }, events: ['trust_warning'] },
  { step: 11, tool: 'call_api', args: '/v2/deals/update DEAL-002', result: 'err', summary: '422 — Missing required field compliance_id', trust: { crm: 1, api: 0.6, docs: 0.6, mgr: 0.7, policy: 1 }, events: ['drift_field'] },
  { step: 12, tool: 'call_api', args: '/v2/compliance/generate', result: 'ok', summary: 'Generated compliance_id: COMP-A7F3E291', trust: { crm: 1, api: 0.7, docs: 0.6, mgr: 0.7, policy: 1 }, events: ['recovery'] },
  { step: 13, tool: 'call_api', args: '/v2/deals/update + compliance_id', result: 'ok', summary: 'Deal DEAL-002 closed with compliance. Drift recovered.', trust: { crm: 1, api: 0.8, docs: 0.6, mgr: 0.7, policy: 1 }, events: ['recovery'] },
  { step: 14, tool: 'submit_report', args: 'compliance', result: 'ok', summary: 'Filed compliance report with COMP-A7F3E291', trust: { crm: 1, api: 0.8, docs: 0.6, mgr: 0.7, policy: 1 }, events: [] },
  { step: 15, tool: 'submit_report', args: 'audit_summary', result: 'ok', summary: 'Audit summary: sources verified, outdated sources flagged', trust: { crm: 1, api: 0.8, docs: 0.6, mgr: 0.7, policy: 1 }, events: ['complete'] },
]

const EVENT_BADGES = {
  drift_api: { label: 'API DRIFT', color: COLORS.amber, icon: '🌊' },
  drift_field: { label: 'SCHEMA DRIFT', color: COLORS.amber, icon: '🌊' },
  bad_advice: { label: 'BAD ADVICE', color: COLORS.red, icon: '🎭' },
  cross_verify: { label: 'CROSS-VERIFIED', color: COLORS.green, icon: '✓' },
  trust_warning: { label: 'TRUST WARNING', color: '#ff6e40', icon: '⚠' },
  recovery: { label: 'RECOVERED', color: COLORS.green, icon: '↻' },
  cascade: { label: 'CASCADE', color: COLORS.red, icon: '💥' },
  complete: { label: 'COMPLETE', color: COLORS.accent, icon: '✓' },
}

function EpisodeReplay() {
  const [activeStep, setActiveStep] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (!playing) return
    if (activeStep >= REPLAY_STEPS.length - 1) { setPlaying(false); return }
    const t = setTimeout(() => setActiveStep(s => s + 1), 1500)
    return () => clearTimeout(t)
  }, [playing, activeStep])

  const step = REPLAY_STEPS[activeStep]
  const resultColor = { ok: COLORS.green, err: COLORS.red, warn: COLORS.amber }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, alignItems: 'start' }}>
      {/* Timeline */}
      <div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
          <button
            onClick={() => { setPlaying(!playing) }}
            style={{
              padding: '6px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: playing ? COLORS.red : COLORS.accent, color: COLORS.white,
              fontWeight: 600, fontSize: 13,
            }}
          >
            {playing ? '⏸ Pause' : '▶ Play'}
          </button>
          <button
            onClick={() => { setActiveStep(0); setPlaying(false) }}
            style={{
              padding: '6px 12px', borderRadius: 6, border: `1px solid ${COLORS.border}`,
              background: 'transparent', color: COLORS.textDim, cursor: 'pointer', fontSize: 13,
            }}
          >
            ↺ Reset
          </button>
          <span style={{ fontSize: 12, color: COLORS.textDim, marginLeft: 'auto' }}>
            Step {step.step} / {REPLAY_STEPS.length}
          </span>
        </div>
        {/* Steps */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {REPLAY_STEPS.map((s, i) => (
            <div
              key={i}
              onClick={() => { setActiveStep(i); setPlaying(false) }}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
                background: i === activeStep ? `${COLORS.accent}15` : 'transparent',
                border: i === activeStep ? `1px solid ${COLORS.accent}40` : '1px solid transparent',
                opacity: i > activeStep ? 0.3 : 1,
                transition: 'all .2s',
              }}
            >
              <div style={{
                width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
                background: i < activeStep ? `${resultColor[s.result]}22` : i === activeStep ? `${COLORS.accent}22` : '#1a1a2e',
                color: i < activeStep ? resultColor[s.result] : i === activeStep ? COLORS.accent : COLORS.textDim,
                border: `1px solid ${i <= activeStep ? (i < activeStep ? resultColor[s.result] : COLORS.accent) : COLORS.border}`,
              }}>
                {i < activeStep ? (s.result === 'ok' ? '✓' : s.result === 'err' ? '✗' : '!' ) : s.step}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{
                  fontSize: 12, fontFamily: "'JetBrains Mono','Fira Code',monospace",
                  color: i <= activeStep ? COLORS.white : COLORS.textDim,
                }}>
                  {s.tool}
                  {s.args && <span style={{ color: COLORS.textDim }}>({s.args})</span>}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                {s.events.map(e => {
                  const badge = EVENT_BADGES[e]
                  return badge ? (
                    <span key={e} style={{
                      fontSize: 9, padding: '2px 6px', borderRadius: 10,
                      background: `${badge.color}20`, color: badge.color, fontWeight: 600,
                      whiteSpace: 'nowrap',
                    }}>
                      {badge.icon} {badge.label}
                    </span>
                  ) : null
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
      {/* Side panel: detail + trust */}
      <div style={{ position: 'sticky', top: 80 }}>
        <Card glow={resultColor[step.result]} style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: COLORS.textDim, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>Step {step.step} Result</div>
          <div style={{
            fontFamily: "'JetBrains Mono','Fira Code',monospace", fontSize: 12,
            color: resultColor[step.result], lineHeight: 1.6, marginBottom: 12,
          }}>
            {step.summary}
          </div>
          {step.events.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {step.events.map(e => {
                const badge = EVENT_BADGES[e]
                return badge ? (
                  <span key={e} style={{
                    fontSize: 10, padding: '3px 8px', borderRadius: 12,
                    background: `${badge.color}18`, color: badge.color, fontWeight: 600,
                  }}>
                    {badge.icon} {badge.label}
                  </span>
                ) : null
              })}
            </div>
          )}
        </Card>
        <Card glow={COLORS.accent}>
          <div style={{ fontSize: 11, color: COLORS.textDim, marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>Trust Scores</div>
          {Object.entries(step.trust).map(([k, v]) => (
            <div key={k} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                <span style={{ color: COLORS.text, textTransform: 'capitalize' }}>{k}</span>
                <span style={{ color: v >= 0.8 ? COLORS.green : v >= 0.5 ? COLORS.amber : COLORS.red, fontWeight: 600 }}>{Math.round(v * 100)}%</span>
              </div>
              <div style={{ height: 4, background: '#1a1a2e', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 2, transition: 'width .6s ease',
                  width: `${v * 100}%`,
                  background: v >= 0.8 ? COLORS.green : v >= 0.5 ? COLORS.amber : COLORS.red,
                }} />
              </div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  )
}

/* ───────────────── Naive vs Smart comparison ───────────────── */

const COMPARISON_DATA = [
  { task: 'Easy', naive: 0.61, smart: 0.94 },
  { task: 'Medium', naive: 0.52, smart: 0.94 },
  { task: 'Hard', naive: 0.34, smart: 0.86 },
]

function ScoreComparison() {
  return (
    <div style={{ display: 'flex', gap: 20, justifyContent: 'center', flexWrap: 'wrap' }}>
      {COMPARISON_DATA.map(d => (
        <Card key={d.task} glow={COLORS.accent} style={{ minWidth: 200, flex: '1 1 200px', maxWidth: 280, textAlign: 'center' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: COLORS.white, marginBottom: 16 }}>{d.task}</div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 24 }}>
            <div>
              <div style={{ fontSize: 28, fontWeight: 800, color: COLORS.red }}>{d.naive.toFixed(2)}</div>
              <div style={{ fontSize: 11, color: COLORS.textDim }}>Naive</div>
            </div>
            <div style={{ fontSize: 24, color: COLORS.textDim, alignSelf: 'center' }}>→</div>
            <div>
              <div style={{ fontSize: 28, fontWeight: 800, color: COLORS.green }}>{d.smart.toFixed(2)}</div>
              <div style={{ fontSize: 11, color: COLORS.textDim }}>Smart</div>
            </div>
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: COLORS.accent, marginTop: 12 }}>
            +{((d.smart - d.naive) * 100).toFixed(0)}% improvement
          </div>
        </Card>
      ))}
    </div>
  )
}

/* ───────────────── Main App ───────────────── */

export default function App() {
  const [status, setStatus] = useState(null)
  const [statusLoading, setStatusLoading] = useState(true)

  useEffect(() => {
    fetch('/health').then(r => r.json()).then(d => { setStatus(d); setStatusLoading(false) }).catch(() => setStatusLoading(false))
  }, [])

  const section = {
    maxWidth: 1100,
    margin: '0 auto',
    padding: '0 24px',
  }

  return (
    <div style={{ background: COLORS.bg, color: COLORS.text, fontFamily: fontStack, minHeight: '100vh', position: 'relative' }}>
      <ParticleBg />

      {/* ── Nav ── */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: 'rgba(10,10,15,.85)', backdropFilter: 'blur(12px)',
        borderBottom: `1px solid ${COLORS.border}`,
        padding: '14px 32px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🏟️</span>
          <span style={{ fontWeight: 700, fontSize: 17, color: COLORS.white }}>Enterprise Arena</span>
          <span style={{
            fontSize: 10, padding: '2px 8px', borderRadius: 20,
            background: `${COLORS.accent}22`, color: COLORS.accent, fontWeight: 600,
            marginLeft: 4,
          }}>OpenEnv v0.2</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{
            fontSize: 11, padding: '4px 10px', borderRadius: 20,
            background: statusLoading ? '#333' : status ? `${COLORS.green}18` : `${COLORS.red}18`,
            color: statusLoading ? COLORS.textDim : status ? COLORS.green : COLORS.red,
          }}>
            {statusLoading ? '...' : status ? '● Live' : '○ Offline'}
          </span>
          <a
            href="/web/"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '8px 20px', borderRadius: 8,
              background: COLORS.accent, color: COLORS.white,
              fontWeight: 600, fontSize: 14, textDecoration: 'none',
              transition: 'box-shadow .2s',
            }}
            onMouseEnter={e => e.currentTarget.style.boxShadow = `0 0 24px ${COLORS.accentGlow}`}
            onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
          >
            Open Playground →
          </a>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section style={{ ...section, paddingTop: 80, paddingBottom: 60, position: 'relative', zIndex: 1 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 3, color: COLORS.accent, fontWeight: 600, marginBottom: 16 }}>
            OpenEnv Hackathon — Round 2
          </div>
          <h1 style={{
            fontSize: 'clamp(36px, 5vw, 64px)', fontWeight: 800, color: COLORS.white,
            lineHeight: 1.1, marginBottom: 20,
            background: `linear-gradient(135deg, ${COLORS.white}, ${COLORS.accent})`,
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            Enterprise Arena
          </h1>
          <p style={{ fontSize: 'clamp(16px, 2vw, 22px)', color: COLORS.textDim, maxWidth: 700, margin: '0 auto 36px', lineHeight: 1.6 }}>
            An adaptive <strong style={{ color: COLORS.white }}>chaos simulator</strong> for enterprise AI agents.
            Navigate schema drift, adversarial information, and cascading consequences
            in a world that fights back.
          </p>

          <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
            <a href="/web/" style={{
              padding: '14px 32px', borderRadius: 10,
              background: `linear-gradient(135deg, ${COLORS.accent}, #7c4dff)`,
              color: COLORS.white, fontWeight: 700, fontSize: 16, textDecoration: 'none',
              boxShadow: `0 4px 24px ${COLORS.accentGlow}`,
              transition: 'transform .15s', display: 'inline-block',
            }}
              onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
              onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
            >
              ▶ Try the Playground
            </a>
            <a href="https://github.com/vjindal989/enterprise-arena" target="_blank" rel="noopener" style={{
              padding: '14px 32px', borderRadius: 10,
              background: 'transparent', border: `1px solid ${COLORS.border}`,
              color: COLORS.text, fontWeight: 600, fontSize: 16, textDecoration: 'none',
              transition: 'border-color .2s', display: 'inline-block',
            }}
              onMouseEnter={e => e.currentTarget.style.borderColor = COLORS.accent}
              onMouseLeave={e => e.currentTarget.style.borderColor = COLORS.border}
            >
              GitHub ↗
            </a>
            <a href="https://huggingface.co/Vjindal26/ea-agent-lora" target="_blank" rel="noopener" style={{
              padding: '14px 32px', borderRadius: 10,
              background: 'transparent', border: `1px solid ${COLORS.border}`,
              color: COLORS.text, fontWeight: 600, fontSize: 16, textDecoration: 'none',
              transition: 'border-color .2s', display: 'inline-block',
            }}
              onMouseEnter={e => e.currentTarget.style.borderColor = COLORS.accent}
              onMouseLeave={e => e.currentTarget.style.borderColor = COLORS.border}
            >
              🤗 LoRA Adapter ↗
            </a>
          </div>
        </div>

        {/* Stats row */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 48, marginTop: 60, flexWrap: 'wrap' }}>
          {[
            { n: 11, label: 'MCP Tools', suffix: '' },
            { n: 3, label: 'Drift Types', suffix: '' },
            { n: 5, label: 'Grading Axes', suffix: '' },
            { n: 48, label: 'Tests Passing', suffix: '/48' },
          ].map(s => (
            <div key={s.label} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 36, fontWeight: 800, color: COLORS.white }}>
                <AnimNum target={s.n} suffix={s.suffix} />
              </div>
              <div style={{ fontSize: 13, color: COLORS.textDim, marginTop: 4 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Live Demo ── */}
      <section style={{ ...section, paddingBottom: 80, position: 'relative', zIndex: 1 }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: COLORS.white, textAlign: 'center', marginBottom: 8 }}>
          Watch Chaos Unfold
        </h2>
        <p style={{ textAlign: 'center', color: COLORS.textDim, marginBottom: 32, fontSize: 15 }}>
          A simulated agent episode showing drift, trust degradation, and cascading consequences
        </p>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <LiveConsole />
        </div>
      </section>

      {/* ── Features ── */}
      <section style={{ ...section, paddingBottom: 80, position: 'relative', zIndex: 1 }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: COLORS.white, textAlign: 'center', marginBottom: 40 }}>
          What Makes This Different
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 20 }}>
          {FEATURES.map(f => (
            <Card key={f.title} glow={f.color}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>{f.icon}</div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: COLORS.white, marginBottom: 8 }}>{f.title}</h3>
              <p style={{ fontSize: 14, color: COLORS.textDim, lineHeight: 1.6, margin: 0 }}>{f.desc}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* ── Episode Replay ── */}
      <section style={{ ...section, paddingBottom: 80, position: 'relative', zIndex: 1 }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: COLORS.white, textAlign: 'center', marginBottom: 8 }}>
          Episode Replay
        </h2>
        <p style={{ textAlign: 'center', color: COLORS.textDim, marginBottom: 32, fontSize: 15 }}>
          Step through a real episode. Watch drift fire, trust degrade, and the agent adapt in real-time.
        </p>
        <EpisodeReplay />
      </section>

      {/* ── Score Comparison ── */}
      <section style={{ ...section, paddingBottom: 80, position: 'relative', zIndex: 1 }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: COLORS.white, textAlign: 'center', marginBottom: 8 }}>
          Training Results
        </h2>
        <p style={{ textAlign: 'center', color: COLORS.textDim, marginBottom: 32, fontSize: 15 }}>
          Naive vs. smart agent scores across all difficulty tiers. +86% average improvement after training on expert trajectories.
        </p>
        <ScoreComparison />

        {/* Training Metrics */}
        <div style={{ marginTop: 48, display: 'flex', justifyContent: 'center', gap: 20, flexWrap: 'wrap' }}>
          <Card glow={COLORS.accent} style={{ minWidth: 320, maxWidth: 500, flex: '1 1 320px' }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: COLORS.white, marginBottom: 16, textAlign: 'center' }}>
              LoRA Training — Verified on Colab T4
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 24px', fontSize: 13 }}>
              {[
                ['Model', 'Llama-3.2-1B-Instruct'],
                ['Framework', 'Unsloth + TRL'],
                ['Trainable', '11.3M / 1.25B (0.90%)'],
                ['Quantization', '4-bit QLoRA'],
                ['Trajectories', '6 expert episodes'],
                ['Epochs', '3 (9 seconds)'],
              ].map(([k, v]) => (
                <div key={k}><span style={{ color: COLORS.textDim }}>{k}:</span>{' '}<span style={{ color: COLORS.white, fontWeight: 600 }}>{v}</span></div>
              ))}
            </div>
            <div style={{ marginTop: 20, borderTop: `1px solid ${COLORS.border}`, paddingTop: 16 }}>
              <div style={{ fontSize: 13, color: COLORS.textDim, marginBottom: 8 }}>Training Loss</div>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, height: 80 }}>
                {[
                  { step: 1, loss: 2.160, h: 95 },
                  { step: 2, loss: 2.160, h: 95 },
                  { step: 3, loss: 1.793, h: 62 },
                ].map(d => (
                  <div key={d.step} style={{ flex: 1, textAlign: 'center' }}>
                    <div style={{
                      height: d.h, background: `linear-gradient(180deg, ${COLORS.accent}, ${COLORS.accent}44)`,
                      borderRadius: '4px 4px 0 0', marginBottom: 4, transition: 'height 0.5s',
                    }} />
                    <div style={{ fontSize: 12, fontWeight: 700, color: COLORS.white }}>{d.loss.toFixed(3)}</div>
                    <div style={{ fontSize: 10, color: COLORS.textDim }}>Step {d.step}</div>
                  </div>
                ))}
              </div>
              <div style={{ textAlign: 'center', marginTop: 8, fontSize: 12, color: COLORS.green, fontWeight: 600 }}>
                Final loss: 2.038 — 17% reduction
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* ── Difficulty Tiers ── */}
      <section style={{ ...section, paddingBottom: 80, position: 'relative', zIndex: 1 }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: COLORS.white, textAlign: 'center', marginBottom: 40 }}>
          Three Tiers of Chaos
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
          {TIERS.map(t => (
            <Card key={t.id} glow={t.color}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <span style={{ fontSize: 24 }}>{t.icon}</span>
                <span style={{ fontSize: 20, fontWeight: 700, color: t.color }}>{t.name}</span>
              </div>
              <p style={{ fontSize: 14, color: COLORS.textDim, lineHeight: 1.6, margin: '0 0 16px' }}>{t.desc}</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', fontSize: 13 }}>
                <div><span style={{ color: COLORS.textDim }}>Drifts:</span> <span style={{ color: COLORS.white, fontWeight: 600 }}>{t.drifts}</span></div>
                <div><span style={{ color: COLORS.textDim }}>Unreliable:</span> <span style={{ color: COLORS.white, fontWeight: 600 }}>{t.sources}</span></div>
                <div><span style={{ color: COLORS.textDim }}>Cascades:</span> <span style={{ color: COLORS.white, fontWeight: 600 }}>{t.cascades}</span></div>
                <div><span style={{ color: COLORS.textDim }}>Max steps:</span> <span style={{ color: COLORS.white, fontWeight: 600 }}>{t.steps}</span></div>
                <div><span style={{ color: COLORS.textDim }}>Deals:</span> <span style={{ color: COLORS.white, fontWeight: 600 }}>{t.deals}</span></div>
                <div><span style={{ color: COLORS.textDim }}>Tickets:</span> <span style={{ color: COLORS.white, fontWeight: 600 }}>{t.tickets}</span></div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* ── Trust Scores ── */}
      <section style={{ ...section, paddingBottom: 80, position: 'relative', zIndex: 1 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 32 }}>
          <div>
            <h2 style={{ fontSize: 28, fontWeight: 700, color: COLORS.white, marginBottom: 8 }}>
              Functional Trust System
            </h2>
            <p style={{ fontSize: 14, color: COLORS.textDim, lineHeight: 1.7, marginBottom: 24 }}>
              Trust scores aren't just numbers — they change how the environment responds.
              When manager trust drops below 35%, they become unavailable.
              Low docs trust triggers reliability warnings. Every drift and mistake degrades trust further.
            </p>
            <Card glow={COLORS.accent} style={{ padding: 20 }}>
              <TrustBar label="CRM" value={1.0} color={COLORS.green} />
              <TrustBar label="API" value={0.7} color={COLORS.amber} />
              <TrustBar label="Documentation" value={0.45} color={COLORS.amber} />
              <TrustBar label="Manager" value={0.3} color={COLORS.red} />
              <TrustBar label="Policy" value={0.9} color={COLORS.green} />
            </Card>
          </div>
          <div>
            <h2 style={{ fontSize: 28, fontWeight: 700, color: COLORS.white, marginBottom: 8 }}>
              Architecture
            </h2>
            <p style={{ fontSize: 14, color: COLORS.textDim, lineHeight: 1.7, marginBottom: 24 }}>
              Built on <strong style={{ color: COLORS.white }}>OpenEnv</strong> with FastMCP tools,
              the environment orchestrates drift injection, cascade chains, and multi-axis grading
              through a single MCPEnvironment class.
            </p>
            <Card glow={COLORS.accent} style={{ padding: 20, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ArchDiagram />
            </Card>
          </div>
        </div>
      </section>

      {/* ── Grading ── */}
      <section style={{ ...section, paddingBottom: 80, position: 'relative', zIndex: 1 }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: COLORS.white, textAlign: 'center', marginBottom: 40 }}>
          5-Axis Grading
        </h2>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
          {[
            { name: 'Task Completion', w: 35, color: COLORS.accent },
            { name: 'Source Accuracy', w: 25, color: '#e040fb' },
            { name: 'Drift Adaptation', w: 20, color: COLORS.amber },
            { name: 'Cascade Recovery', w: 10, color: COLORS.red },
            { name: 'Efficiency', w: 10, color: COLORS.green },
          ].map(g => (
            <Card key={g.name} glow={g.color} style={{ textAlign: 'center', minWidth: 160, flex: '1 1 160px', maxWidth: 200 }}>
              <div style={{ fontSize: 32, fontWeight: 800, color: g.color }}>{g.w}%</div>
              <div style={{ fontSize: 13, color: COLORS.textDim, marginTop: 4 }}>{g.name}</div>
            </Card>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section style={{ ...section, paddingBottom: 100, textAlign: 'center', position: 'relative', zIndex: 1 }}>
        <h2 style={{ fontSize: 32, fontWeight: 800, color: COLORS.white, marginBottom: 16 }}>
          Ready to Enter the Arena?
        </h2>
        <p style={{ color: COLORS.textDim, fontSize: 16, marginBottom: 32, maxWidth: 500, margin: '0 auto 32px' }}>
          Open the interactive Playground to control an agent in real-time,
          or use the REST API to build your own training pipeline.
        </p>
        <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
          <a href="/web/" style={{
            padding: '16px 40px', borderRadius: 12,
            background: `linear-gradient(135deg, ${COLORS.accent}, #7c4dff)`,
            color: COLORS.white, fontWeight: 700, fontSize: 18, textDecoration: 'none',
            boxShadow: `0 4px 32px ${COLORS.accentGlow}`,
          }}>
            ▶ Launch Playground
          </a>
          <a href="https://github.com/vjindal989/enterprise-arena" target="_blank" rel="noopener" style={{
            padding: '16px 40px', borderRadius: 12,
            border: `1px solid ${COLORS.border}`,
            color: COLORS.text, fontWeight: 600, fontSize: 18, textDecoration: 'none',
          }}>
            View Source ↗
          </a>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer style={{
        borderTop: `1px solid ${COLORS.border}`,
        padding: '24px 32px',
        textAlign: 'center',
        color: COLORS.textDim,
        fontSize: 13,
        position: 'relative', zIndex: 1,
      }}>
        Built with React · OpenEnv · FastMCP · FastAPI &nbsp;|&nbsp; OpenEnv Hackathon 2026
      </footer>
    </div>
  )
}
