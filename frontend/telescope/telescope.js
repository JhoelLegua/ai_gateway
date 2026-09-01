/**
 * AI Gateway Telescope — Frontend Engine
 * Vanilla JS, no external dependencies.
 *
 * Features:
 *   - Live metrics polling (2s interval)
 *   - Pipeline SVG animation with packet flow
 *   - HTTP status donut chart (native Canvas)
 *   - Latency percentile table (P50 / P95 / Max)
 *   - Configurable stress-test launcher with progress tracking
 *   - Rolling request event log (real-time feed)
 *   - Clean SVG icons, no raw emojis
 *   - Dark Gray / White Light Mode toggle
 *   - ES / EN i18n
 *   - Thesis-ready JSON & CSV export
 */

'use strict';

/* ══════════════════════════════════════════════════════════════
   i18n Dictionary (Pure Text, No Emoticons)
══════════════════════════════════════════════════════════════ */
const I18N = {
  es: {
    title: 'AI Gateway Telescope',
    subtitle: 'Monitor de Rendimiento & Stress Lab',
    live: 'EN VIVO',
    paused: 'PAUSADO',
    bwMode: 'Claro',
    colorMode: 'Oscuro',
    lang: 'EN',
    inputMonitor: 'MONITOR ENTRADA',
    outputMonitor: 'MONITOR SALIDA',
    pipelineLabel: 'PIPELINE DE SEGURIDAD — 5 CAPAS',
    totalReq: 'Total Requests',
    cleanPassed: 'Clean Passed',
    blocked: 'Bloqueados',
    uptime: 'Uptime',
    rps: 'Peticiones',
    http200: 'HTTP 200',
    http400: 'HTTP 400',
    http500: 'HTTP 500',
    latencyTable: 'Latencia por Capa',
    httpStatus: 'Distribución HTTP',
    layer: 'Capa',
    invocations: 'Invocaciones',
    p50: 'P50',
    p95: 'P95',
    max: 'Máx',
    avg: 'Prom',
    blockedCol: 'Bloq.',
    stressLab: 'Stress Lab',
    users: 'Usuarios Concurrentes',
    interval: 'Intervalo (ms)',
    iterations: 'Iteraciones',
    cleanTraffic: 'Tráfico Limpio',
    injectionTraffic: 'Inyecciones',
    fireBtn: 'LANZAR STRESS TEST',
    firingBtn: 'EJECUTANDO...',
    stopBtn: 'Detener',
    progressLabel: 'Progreso',
    success: 'Éxito',
    blockedRes: 'Bloqueadas',
    errors: 'Errores',
    avgMs: 'Prom ms',
    requestLog: 'Log de Requests',
    logTs: 'Timestamp',
    logUser: 'Usuario',
    logStatus: 'Status',
    logMs: 'ms',
    logLayer: 'Capa bloqueada',
    exportBtn: 'Exportar Reporte (JSON)',
    exportCsvBtn: 'Exportar CSV',
    noData: 'Sin datos aún...',
    layer1: 'L1 Heurística',
    layer2: 'L2 Vectorial',
    layer3: 'L3 Inteligencia',
    layer4: 'L4 Canario',
    layer5: 'L5 Egreso',
  },
  en: {
    title: 'AI Gateway Telescope',
    subtitle: 'Performance Monitor & Stress Lab',
    live: 'LIVE',
    paused: 'PAUSED',
    bwMode: 'Light',
    colorMode: 'Dark',
    lang: 'ES',
    inputMonitor: 'INPUT MONITOR',
    outputMonitor: 'OUTPUT MONITOR',
    pipelineLabel: 'SECURITY PIPELINE — 5 LAYERS',
    totalReq: 'Total Requests',
    cleanPassed: 'Clean Passed',
    blocked: 'Blocked',
    uptime: 'Uptime',
    rps: 'Requests',
    http200: 'HTTP 200',
    http400: 'HTTP 400',
    http500: 'HTTP 500',
    latencyTable: 'Latency by Layer',
    httpStatus: 'HTTP Distribution',
    layer: 'Layer',
    invocations: 'Invocations',
    p50: 'P50',
    p95: 'P95',
    max: 'Max',
    avg: 'Avg',
    blockedCol: 'Blk.',
    stressLab: 'Stress Lab',
    users: 'Concurrent Users',
    interval: 'Interval (ms)',
    iterations: 'Iterations',
    cleanTraffic: 'Clean Traffic',
    injectionTraffic: 'Injections',
    fireBtn: 'FIRE STRESS TEST',
    firingBtn: 'RUNNING...',
    stopBtn: 'Stop',
    progressLabel: 'Progress',
    success: 'Success',
    blockedRes: 'Blocked',
    errors: 'Errors',
    avgMs: 'Avg ms',
    requestLog: 'Request Log',
    logTs: 'Timestamp',
    logUser: 'User',
    logStatus: 'Status',
    logMs: 'ms',
    logLayer: 'Blocked Layer',
    exportBtn: 'Export Report (JSON)',
    exportCsvBtn: 'Export CSV',
    noData: 'No data yet...',
    layer1: 'L1 Heuristic',
    layer2: 'L2 Vectorial',
    layer3: 'L3 Intelligence',
    layer4: 'L4 Canary',
    layer5: 'L5 Egress',
  },
};

const LAYER_COLORS = ['#4f8ef7', '#a78bfa', '#22d3ee', '#fbbf24', '#34d399'];
const LAYER_NAMES_KEY = ['layer1', 'layer2', 'layer3', 'layer4', 'layer5'];
const LAYER_API_NAMES = [
  'layer_1_heuristics',
  'layer_2_vectorial',
  'layer_3_intelligence',
  'layer_4_canary',
  'layer_5_egress',
];

/* ══════════════════════════════════════════════════════════════
   App State
══════════════════════════════════════════════════════════════ */
let state = {
  lang: 'es',
  bw: false,   // true = light mode (white), false = dark gray
  live: true,
  metrics: null,
  history: [],
  stress: { running: false, progress: 0, total: 0, results: {} },
  pollTimer: null,
  stressTimer: null,
};

/* ══════════════════════════════════════════════════════════════
   Helpers
══════════════════════════════════════════════════════════════ */
const t = (key) => I18N[state.lang][key] ?? key;
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function fmtUptime(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

function fmtTs(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-GB', { hour12: false, fractionalSecondDigits: 2 });
}

/* ══════════════════════════════════════════════════════════════
   i18n apply
══════════════════════════════════════════════════════════════ */
function applyI18n() {
  $$('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    el.textContent = t(key);
  });
  $$('[data-i18n-ph]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPh);
  });
  // Update toggle button text labels
  const themeLabel = $('#label-theme');
  if (themeLabel) themeLabel.textContent = state.bw ? t('colorMode') : t('bwMode');
  const langLabel = $('#label-lang');
  if (langLabel) langLabel.textContent = t('lang');
}

/* ══════════════════════════════════════════════════════════════
   Pipeline SVG Builder
══════════════════════════════════════════════════════════════ */
function buildPipelineSVG() {
  const svg = $('#pipeline-svg');
  if (!svg) return;
  const W = svg.clientWidth || 700;
  const H = 175;
  const cx = (i) => 50 + i * ((W - 100) / 4);
  const cy = H / 2;
  const r = 26;

  svg.innerHTML = '';

  // Background connection lines
  for (let i = 0; i < 4; i++) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', cx(i) + r);
    line.setAttribute('y1', cy);
    line.setAttribute('x2', cx(i + 1) - r);
    line.setAttribute('y2', cy);
    line.setAttribute('stroke', getComputedStyle(document.documentElement).getPropertyValue('--border-bright').trim() || '#475569');
    line.setAttribute('stroke-width', '2');
    line.setAttribute('stroke-dasharray', '4 3');
    svg.appendChild(line);
  }

  // Animated packet track
  const track = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  track.id = 'packet-track';
  track.setAttribute('x1', cx(0) + r);
  track.setAttribute('y1', cy);
  track.setAttribute('x2', cx(4) - r);
  track.setAttribute('y2', cy);
  track.setAttribute('stroke', 'rgba(79,142,247,0.15)');
  track.setAttribute('stroke-width', '2');
  svg.appendChild(track);

  // Layer nodes
  const nodeFill = getComputedStyle(document.documentElement).getPropertyValue('--bg-card').trim() || '#272b35';

  for (let i = 0; i < 5; i++) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.id = `layer-node-${i}`;
    g.classList.add('layer-node');

    // Glow ring
    const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    ring.setAttribute('cx', cx(i));
    ring.setAttribute('cy', cy);
    ring.setAttribute('r', r + 6);
    ring.setAttribute('fill', 'none');
    ring.setAttribute('stroke', LAYER_COLORS[i]);
    ring.setAttribute('stroke-width', '1.5');
    ring.setAttribute('opacity', '0.25');
    ring.id = `ring-${i}`;
    g.appendChild(ring);

    // Main circle
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', cx(i));
    circle.setAttribute('cy', cy);
    circle.setAttribute('r', r);
    circle.setAttribute('fill', nodeFill);
    circle.setAttribute('stroke', LAYER_COLORS[i]);
    circle.setAttribute('stroke-width', '2');
    g.appendChild(circle);

    // Label
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', cx(i));
    label.setAttribute('y', cy - 5);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('fill', LAYER_COLORS[i]);
    label.setAttribute('font-size', '11');
    label.setAttribute('font-weight', '700');
    label.setAttribute('font-family', 'JetBrains Mono, monospace');
    label.textContent = `L${i + 1}`;
    g.appendChild(label);

    // Sub-label (Latency)
    const sub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    sub.setAttribute('x', cx(i));
    sub.setAttribute('y', cy + 10);
    sub.setAttribute('text-anchor', 'middle');
    sub.setAttribute('fill', '#94a3b8');
    sub.setAttribute('font-size', '8');
    sub.setAttribute('font-family', 'Inter, sans-serif');
    sub.id = `sub-${i}`;
    sub.textContent = '0ms';
    g.appendChild(sub);

    // Blocked count chip
    const chip = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    chip.setAttribute('x', cx(i) + 18);
    chip.setAttribute('y', cy - 18);
    chip.setAttribute('text-anchor', 'middle');
    chip.setAttribute('fill', '#ef4444');
    chip.setAttribute('font-size', '9');
    chip.setAttribute('font-family', 'JetBrains Mono, monospace');
    chip.setAttribute('font-weight', '700');
    chip.id = `chip-${i}`;
    chip.textContent = '';
    g.appendChild(chip);

    svg.appendChild(g);
  }

  // Packet element
  const pkt = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  pkt.id = 'packet';
  pkt.setAttribute('r', '6');
  pkt.setAttribute('fill', '#4f8ef7');
  pkt.setAttribute('opacity', '0');
  svg.appendChild(pkt);
}

/* ── Animate a packet through the pipeline ────────────────── */
let _packetAnim = null;

function animatePacket(blocked, blockedIdx) {
  const svg = $('#pipeline-svg');
  if (!svg) return;
  const W = svg.clientWidth || 700;
  const cx = (i) => 50 + i * ((W - 100) / 4);
  const cy = 87;
  const r = 26;
  const pkt = $('#packet');
  if (!pkt) return;

  const color = blocked ? '#f87171' : '#34d399';
  pkt.setAttribute('fill', color);
  pkt.setAttribute('cx', cx(0) + r);
  pkt.setAttribute('cy', cy);
  pkt.setAttribute('opacity', '1');

  const endIdx = blocked ? (blockedIdx ?? 4) : 4;
  const endX = cx(endIdx) - r;
  const startX = cx(0) + r;
  const duration = 1100;
  const start = performance.now();

  if (_packetAnim) cancelAnimationFrame(_packetAnim);

  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const x = startX + (endX - startX) * easeInOut(progress);
    pkt.setAttribute('cx', x);

    if (progress < 1) {
      _packetAnim = requestAnimationFrame(step);
    } else {
      pkt.setAttribute('opacity', '0');
      pulseNode(endIdx, blocked);
    }
  }

  requestAnimationFrame(step);
}

function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

function pulseNode(idx, blocked) {
  const ring = $(`#ring-${idx}`);
  if (!ring) return;
  ring.setAttribute('opacity', '0.8');
  ring.setAttribute('stroke', blocked ? '#f87171' : '#34d399');
  setTimeout(() => {
    ring.setAttribute('opacity', '0.25');
    ring.setAttribute('stroke', LAYER_COLORS[idx] || '#4f8ef7');
  }, 450);
}

/* ══════════════════════════════════════════════════════════════
   Donut Chart (native Canvas)
══════════════════════════════════════════════════════════════ */
function drawDonut(counts) {
  const canvas = $('#status-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const size = canvas.width;
  const cx = size / 2;
  const cy = size / 2;
  const outer = cx - 10;
  const inner = outer * 0.60;

  ctx.clearRect(0, 0, size, size);

  const total = (counts[200] || 0) + (counts[400] || 0) + (counts[500] || 0) || 1;
  const slices = [
    { value: counts[200] || 0, color: '#34d399' },
    { value: counts[400] || 0, color: '#f87171' },
    { value: counts[500] || 0, color: '#fb923c' },
  ];

  let startAngle = -Math.PI / 2;
  for (const s of slices) {
    const sweep = (s.value / total) * 2 * Math.PI;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, outer, startAngle, startAngle + sweep);
    ctx.closePath();
    ctx.fillStyle = s.color;
    ctx.fill();
    startAngle += sweep;
  }

  // Hole — use current card background
  const holeFill = getComputedStyle(document.documentElement)
    .getPropertyValue('--bg-card').trim() || '#272b35';
  ctx.beginPath();
  ctx.arc(cx, cy, inner, 0, 2 * Math.PI);
  ctx.fillStyle = holeFill;
  ctx.fill();

  // Center text — use current text color
  const textColor = getComputedStyle(document.documentElement)
    .getPropertyValue('--text-primary').trim() || '#e2e8f0';
  ctx.fillStyle = textColor;
  ctx.font = `bold 22px JetBrains Mono, monospace`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(total === 1 && !counts[200] && !counts[400] ? 0 : total, cx, cy - 6);

  ctx.font = `10px Inter, sans-serif`;
  const mutedColor = getComputedStyle(document.documentElement)
    .getPropertyValue('--text-muted').trim() || '#64748b';
  ctx.fillStyle = mutedColor;
  ctx.fillText('TOTAL', cx, cy + 12);
}

/* ══════════════════════════════════════════════════════════════
   Render: KPI Cards
══════════════════════════════════════════════════════════════ */
function renderKPI(m) {
  const blocked = m.total_requests - m.clean_passed;
  $('#kpi-total').textContent = m.total_requests.toLocaleString();
  $('#kpi-clean').textContent = m.clean_passed.toLocaleString();
  $('#kpi-blocked').textContent = blocked.toLocaleString();
  $('#kpi-uptime').textContent = fmtUptime(m.uptime_s);
  $('#kpi-200').textContent = (m.http_status_counts[200] ?? 0).toLocaleString();
  $('#kpi-400').textContent = (m.http_status_counts[400] ?? 0).toLocaleString();
  $('#kpi-500').textContent = (m.http_status_counts[500] ?? 0).toLocaleString();

  const chip = $('#uptime-chip');
  if (chip) chip.textContent = fmtUptime(m.uptime_s);
}

/* ══════════════════════════════════════════════════════════════
   Render: Input / Output Monitors
══════════════════════════════════════════════════════════════ */
function renderMonitors(m) {
  const total = m.total_requests;
  const blocked = total - m.clean_passed;
  const sc = m.http_status_counts;

  const inEl = $('#input-monitor-content');
  if (inEl) {
    inEl.innerHTML = `
      <div class="stat-row"><span class="stat-label">RPS est.</span><span class="stat-value cyan">${(total / Math.max(m.uptime_s, 1)).toFixed(2)}/s</span></div>
      <div class="stat-row"><span class="stat-label">Total</span><span class="stat-value blue">${total.toLocaleString()}</span></div>
      <div class="stat-row"><span class="stat-label">Clean</span><span class="stat-value green">${m.clean_passed.toLocaleString()}</span></div>
      <div class="stat-row"><span class="stat-label">Threats</span><span class="stat-value red">${blocked.toLocaleString()}</span></div>
    `;
  }

  const outEl = $('#output-monitor-content');
  if (outEl) {
    const total200 = sc[200] ?? 0;
    const total400 = sc[400] ?? 0;
    const total500 = sc[500] ?? 0;
    const tot = total200 + total400 + total500 || 1;
    outEl.innerHTML = `
      <div class="stat-row"><span class="stat-label">HTTP 200</span><span class="stat-value green">${total200}</span></div>
      <div class="mini-bar"><div class="mini-bar-fill" style="width:${(total200/tot*100).toFixed(1)}%;background:var(--accent-green)"></div></div>
      <div class="stat-row" style="margin-top:6px"><span class="stat-label">HTTP 400</span><span class="stat-value red">${total400}</span></div>
      <div class="mini-bar"><div class="mini-bar-fill" style="width:${(total400/tot*100).toFixed(1)}%;background:var(--accent-red)"></div></div>
      <div class="stat-row" style="margin-top:6px"><span class="stat-label">HTTP 500</span><span class="stat-value yellow">${total500}</span></div>
      <div class="mini-bar"><div class="mini-bar-fill" style="width:${(total500/tot*100).toFixed(1)}%;background:var(--accent-orange)"></div></div>
    `;
  }
}

/* ══════════════════════════════════════════════════════════════
   Render: Pipeline SVG latencies
══════════════════════════════════════════════════════════════ */
function updatePipelineStats(layers) {
  const layerMap = {};
  for (const l of layers) layerMap[l.layer_name] = l;

  LAYER_API_NAMES.forEach((apiName, i) => {
    const layer = layerMap[apiName];
    const sub = $(`#sub-${i}`);
    const chip = $(`#chip-${i}`);
    if (sub && layer) {
      sub.textContent = `${layer.avg_latency_ms}ms`;
    }
    if (chip && layer && layer.total_blocked > 0) {
      chip.textContent = `-${layer.total_blocked}`;
    }
  });
}

/* ══════════════════════════════════════════════════════════════
   Render: Latency Table
══════════════════════════════════════════════════════════════ */
function renderLatencyTable(layers) {
  const tbody = $('#latency-tbody');
  if (!tbody) return;

  const layerMap = {};
  for (const l of layers) layerMap[l.layer_name] = l;

  tbody.innerHTML = LAYER_API_NAMES.map((apiName, i) => {
    const l = layerMap[apiName] || {};
    const color = LAYER_COLORS[i];
    const name = t(LAYER_NAMES_KEY[i]);
    return `<tr>
      <td><span class="layer-tag">
        <span class="layer-dot" style="background:${color}"></span>
        ${name}
      </span></td>
      <td>${l.invocations ?? 0}</td>
      <td class="p50-val">${l.p50_ms ?? 0}ms</td>
      <td class="p95-val">${l.p95_ms ?? 0}ms</td>
      <td class="max-val">${l.max_ms ?? 0}ms</td>
      <td>${l.avg_latency_ms ?? 0}ms</td>
      <td><span class="blocked-badge">${l.total_blocked ?? 0}</span></td>
    </tr>`;
  }).join('');
}

/* ══════════════════════════════════════════════════════════════
   Render: Request Log
══════════════════════════════════════════════════════════════ */
function renderLog(events) {
  const wrap = $('#log-body');
  if (!wrap) return;

  if (!events.length) {
    wrap.innerHTML = `<div style="padding:16px;color:var(--text-muted);font-family:var(--font-mono);font-size:11px">${t('noData')}</div>`;
    return;
  }

  wrap.innerHTML = events.map(ev => {
    const sc = ev.http_status;
    const scClass = sc >= 500 ? 's500' : sc >= 400 ? 's400' : 's200';
    const layer = ev.blocked_layer ? ev.blocked_layer.replace('layer_', 'L').replace('_', ' ') : '—';
    return `<div class="log-row">
      <span class="log-ts">${fmtTs(ev.ts)}</span>
      <span class="log-user">${ev.user_id ?? '—'}</span>
      <span class="log-status ${scClass}">${sc}</span>
      <span class="log-ms">${ev.total_ms}ms</span>
      <span class="log-layer">${layer}</span>
    </div>`;
  }).join('');

  const latest = events[0];
  if (latest) {
    const blockedIdx = LAYER_API_NAMES.indexOf(latest.blocked_layer);
    animatePacket(latest.blocked, blockedIdx >= 0 ? blockedIdx : undefined);
  }
}

/* ══════════════════════════════════════════════════════════════
   Render: Status Legend
══════════════════════════════════════════════════════════════ */
function renderStatusLegend(counts) {
  const wrap = $('#status-legend');
  if (!wrap) return;
  const items = [
    { label: 'HTTP 200', color: '#34d399', count: counts[200] ?? 0 },
    { label: 'HTTP 400', color: '#f87171', count: counts[400] ?? 0 },
    { label: 'HTTP 500', color: '#fb923c', count: counts[500] ?? 0 },
  ];
  wrap.innerHTML = items.map(item => `
    <div class="legend-item">
      <div class="legend-label">
        <div class="legend-dot" style="background:${item.color}"></div>
        <span>${item.label}</span>
      </div>
      <span class="legend-count">${item.count.toLocaleString()}</span>
    </div>
  `).join('');
}

/* ══════════════════════════════════════════════════════════════
   API Calls
══════════════════════════════════════════════════════════════ */
async function fetchMetrics() {
  const r = await fetch('/v1/telescope/metrics');
  if (!r.ok) throw new Error('metrics fetch failed');
  return r.json();
}

async function fetchHistory(limit = 50) {
  const r = await fetch(`/v1/telescope/history?limit=${limit}`);
  if (!r.ok) throw new Error('history fetch failed');
  const data = await r.json();
  return data.events;
}

async function fireStress(params) {
  const r = await fetch('/v1/telescope/stress/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return r.json();
}

async function stopStress() {
  await fetch('/v1/telescope/stress/stop', { method: 'POST' });
}

async function fetchStressStatus() {
  const r = await fetch('/v1/telescope/stress/status');
  return r.json();
}

/* ══════════════════════════════════════════════════════════════
   Polling Loop
══════════════════════════════════════════════════════════════ */
async function poll() {
  if (!state.live) return;
  try {
    const [metrics, history] = await Promise.all([fetchMetrics(), fetchHistory(60)]);
    state.metrics = metrics;
    state.history = history;

    renderKPI(metrics);
    renderMonitors(metrics);
    updatePipelineStats(metrics.layers);
    renderLatencyTable(metrics.layers);
    drawDonut(metrics.http_status_counts);
    renderStatusLegend(metrics.http_status_counts);
    renderLog(history);
  } catch (e) {
    console.warn('[Telescope] Poll error:', e.message);
  }
}

/* ══════════════════════════════════════════════════════════════
   Stress Polling & State
══════════════════════════════════════════════════════════════ */
async function pollStress() {
  try {
    const s = await fetchStressStatus();
    renderStressStatus(s);
    if (!s.running && state.stressTimer) {
      clearInterval(state.stressTimer);
      state.stressTimer = null;
      setFireBtn(false);
    }
  } catch (e) { /* ignore */ }
}

function renderStressStatus(s) {
  const pct = s.percent ?? 0;
  const fill = $('#stress-progress-fill');
  const pctLabel = $('#stress-pct');
  const countLabel = $('#stress-count');
  if (fill) {
    fill.style.width = `${pct}%`;
    if (pct >= 100) fill.classList.add('complete');
    else fill.classList.remove('complete');
  }
  if (pctLabel) pctLabel.textContent = `${pct}%`;
  if (countLabel) countLabel.textContent = `${s.progress ?? 0} / ${s.total ?? 0}`;

  const r = s.results ?? {};
  $('#rc-success').textContent = r.success ?? 0;
  $('#rc-blocked').textContent = r.blocked ?? 0;
  $('#rc-errors').textContent  = r.errors  ?? 0;
  $('#rc-avgms').textContent   = r.avg_ms  ?? 0;
}

function setFireBtn(running) {
  const btn = $('#btn-fire');
  const stopBtn = $('#btn-stop');
  const fireText = $('#btn-fire-text');
  if (!btn) return;
  btn.disabled = running;
  if (fireText) {
    fireText.textContent = running ? t('firingBtn') : t('fireBtn');
  }
  const icon = btn.querySelector('.btn-icon');
  if (icon) {
    icon.innerHTML = running
      ? '<rect x="4" y="4" width="16" height="16" rx="2"></rect>'
      : '<polygon points="5 3 19 12 5 21 5 3"></polygon>';
  }
  if (stopBtn) stopBtn.style.display = running ? 'inline-flex' : 'none';
}

/* ══════════════════════════════════════════════════════════════
   Export
══════════════════════════════════════════════════════════════ */
function exportJSON() {
  const m = state.metrics;
  if (!m) return;
  const report = {
    generated_at: new Date().toISOString(),
    summary: {
      total_requests: m.total_requests,
      clean_passed: m.clean_passed,
      blocked: m.total_requests - m.clean_passed,
      success_rate_pct: m.total_requests > 0
        ? ((m.clean_passed / m.total_requests) * 100).toFixed(2)
        : '100.00',
      uptime_s: m.uptime_s,
      http_status: m.http_status_counts,
    },
    latency_by_layer: m.layers,
    recent_events: state.history.slice(0, 100),
  };
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `telescope_report_${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportCSV() {
  const rows = [
    ['timestamp', 'user_id', 'session_id', 'http_status', 'total_ms', 'blocked', 'blocked_layer'],
    ...state.history.map(ev => [
      new Date(ev.ts * 1000).toISOString(),
      ev.user_id,
      ev.session_id,
      ev.http_status,
      ev.total_ms,
      ev.blocked,
      ev.blocked_layer ?? '',
    ]),
  ];
  const csv = rows.map(r => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `telescope_log_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ══════════════════════════════════════════════════════════════
   Event Listeners
══════════════════════════════════════════════════════════════ */
function bindEvents() {
  // Theme toggle
  $('#btn-bw').addEventListener('click', () => {
    state.bw = !state.bw;
    document.body.classList.toggle('light', state.bw);
    const themeLabel = $('#label-theme');
    if (themeLabel) themeLabel.textContent = state.bw ? t('colorMode') : t('bwMode');
    
    // Update theme icon SVG
    const themeIcon = $('#icon-theme');
    if (themeIcon) {
      themeIcon.innerHTML = state.bw
        ? '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>'
        : '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
    }

    buildPipelineSVG();
    if (state.metrics) {
      updatePipelineStats(state.metrics.layers);
      drawDonut(state.metrics.http_status_counts);
    }
  });

  // Language toggle
  $('#btn-lang').addEventListener('click', () => {
    state.lang = state.lang === 'es' ? 'en' : 'es';
    applyI18n();
    renderLatencyTable(state.metrics?.layers ?? []);
    setFireBtn(state.stress.running);
  });

  // Live / Pause toggle
  $('#btn-live').addEventListener('click', () => {
    state.live = !state.live;
    const dot = $('#live-dot');
    const label = $('#live-label');
    const liveIcon = $('#icon-live');
    if (dot) dot.classList.toggle('paused', !state.live);
    if (label) label.textContent = state.live ? t('live') : t('paused');
    if (liveIcon) {
      liveIcon.innerHTML = state.live
        ? '<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>'
        : '<polygon points="5 3 19 12 5 21 5 3"></polygon>';
    }
    if (state.live) poll();
  });

  // Sliders
  const sliderDefs = [
    { id: 'slider-users',      valId: 'val-users',      suffix: '' },
    { id: 'slider-interval',   valId: 'val-interval',   suffix: 'ms' },
    { id: 'slider-iterations', valId: 'val-iterations', suffix: '' },
  ];
  sliderDefs.forEach(({ id, valId, suffix }) => {
    const sl = $(`#${id}`);
    const vl = $(`#${valId}`);
    if (sl && vl) {
      sl.addEventListener('input', () => { vl.textContent = sl.value + suffix; });
    }
  });

  // Mix sliders
  const mixClean = $('#slider-mix-clean');
  const mixInj   = $('#slider-mix-inject');

  if (mixClean && mixInj) {
    const updateMixBar = () => {
      const cleanPct = Number(mixClean.value);
      const injPct   = 100 - cleanPct;
      if (mixInj) mixInj.value = injPct;
      $('#val-mix-clean').textContent  = `${cleanPct}%`;
      $('#val-mix-inject').textContent = `${injPct}%`;
      const cleanBar = $('#mix-bar-clean');
      const injBar   = $('#mix-bar-inject');
      if (cleanBar) cleanBar.style.width = `${cleanPct}%`;
      if (injBar)   injBar.style.width   = `${injPct}%`;
    };
    mixClean.addEventListener('input', updateMixBar);
    updateMixBar();
  }

  // Fire stress
  $('#btn-fire').addEventListener('click', async () => {
    const users      = Number($('#slider-users').value);
    const interval   = Number($('#slider-interval').value);
    const iterations = Number($('#slider-iterations').value);
    const cleanPct   = Number($('#slider-mix-clean').value) / 100;

    state.stress.running = true;
    setFireBtn(true);
    try {
      await fireStress({
        users,
        interval_ms: interval,
        iterations,
        traffic_mix: { clean: cleanPct, injection: 1 - cleanPct },
        token: 'test',
      });
      state.stressTimer = setInterval(pollStress, 800);
    } catch (e) {
      alert('Error launching stress test: ' + e.message);
      state.stress.running = false;
      setFireBtn(false);
    }
  });

  // Stop stress
  $('#btn-stop').addEventListener('click', async () => {
    await stopStress();
    if (state.stressTimer) { clearInterval(state.stressTimer); state.stressTimer = null; }
    state.stress.running = false;
    setFireBtn(false);
  });

  // Export
  $('#btn-export-json').addEventListener('click', exportJSON);
  $('#btn-export-csv').addEventListener('click',  exportCSV);
}

/* ══════════════════════════════════════════════════════════════
   Boot
══════════════════════════════════════════════════════════════ */
function init() {
  applyI18n();
  buildPipelineSVG();
  bindEvents();
  poll();
  state.pollTimer = setInterval(poll, 2000);

  window.addEventListener('resize', () => {
    buildPipelineSVG();
    if (state.metrics) updatePipelineStats(state.metrics.layers);
  });
}

document.addEventListener('DOMContentLoaded', init);
