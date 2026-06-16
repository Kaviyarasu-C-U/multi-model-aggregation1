// ── Particle canvas ─────────────────────────────────────────────────────────
(function() {
  const c = document.getElementById('canvas'), ctx = c.getContext('2d');
  let W, H, P = [];
  function resize() { W = c.width = innerWidth; H = c.height = innerHeight; }
  resize(); addEventListener('resize', resize);
  for (let i = 0; i < 70; i++) P.push({
    x: Math.random()*W, y: Math.random()*H,
    r: Math.random()*1.4+.3, vx: (Math.random()-.5)*.25, vy: (Math.random()-.5)*.25,
    a: Math.random()*.4+.08
  });
  (function draw() {
    ctx.clearRect(0,0,W,H);
    P.forEach(p => {
      p.x+=p.vx; p.y+=p.vy;
      if(p.x<0)p.x=W; if(p.x>W)p.x=0; if(p.y<0)p.y=H; if(p.y>H)p.y=0;
      ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle=`rgba(99,102,241,${p.a})`; ctx.fill();
    });
    requestAnimationFrame(draw);
  })();
})();

// ── State ────────────────────────────────────────────────────────────────────
const MODELS = [
  { name:'Gemini 2.5 Flash',     icon:'🌟', fill:'#06b6d4', provider:'Google'   },
  { name:'Gemini 2.5 Flash-Lite',icon:'⚡', fill:'#14b8a6', provider:'Google'   },
  { name:'Llama 3.3 70B',        icon:'🔷', fill:'#6366f1', provider:'Groq'     },
  { name:'Llama 3.1 8B',         icon:'🧠', fill:'#a855f7', provider:'Cerebras' },
  { name:'Command A',            icon:'🌀', fill:'#f43f5e', provider:'Cohere'   },
];

let historyItems = [], activeHistId = null;
let accountData  = {};
let conversationContext = [];
let currentConvId = 'conv-' + Date.now();
let turnNum = 0;
let convNum = 1;

// ── Sidebar ──────────────────────────────────────────────────────────────────
let sidebarVisible = window.innerWidth > 700;
function toggleSidebar() {
  sidebarVisible = !sidebarVisible;
  const sidebar = document.querySelector('.sidebar');
  if (sidebarVisible) {
    sidebar.classList.remove('hidden');
    document.body.classList.remove('sidebar-hidden');
  } else {
    sidebar.classList.add('hidden');
    document.body.classList.add('sidebar-hidden');
  }
}
document.querySelector('.sidebar-overlay').addEventListener('click', toggleSidebar);

// ── New Conversation ─────────────────────────────────────────────────────────
function newConversation() {
  convNum++;
  conversationContext = [];
  currentConvId = 'conv-' + Date.now();
  turnNum = 0;
  document.getElementById('conv-thread').innerHTML = '';
  document.getElementById('conv-header').style.display = 'none';
  document.getElementById('empty-state').style.display = 'block';
  document.getElementById('loading-turn').style.display = 'none';
  const inp = document.getElementById('query-input');
  inp.value = ''; inp.style.height = 'auto'; inp.focus();
  window.scrollTo({top: 0, behavior:'smooth'});
}

// ── Account ──────────────────────────────────────────────────────────────────
async function loadAccount() {
  const r = await fetch('/api/account'); accountData = await r.json();
  const av = document.getElementById('user-avatar');
  av.textContent = (accountData.name||'?')[0].toUpperCase();
  av.style.background = accountData.avatar_color||'#6366f1';
  document.getElementById('acc-name').value  = accountData.name||'';
  document.getElementById('acc-email').value = accountData.email||'';
  document.getElementById('acc-org').value   = accountData.organization||'';
  document.querySelectorAll('.color-opt').forEach(el => {
    el.classList.toggle('selected', el.dataset.color === (accountData.avatar_color||'#6366f1'));
    el.addEventListener('click', () => {
      document.querySelectorAll('.color-opt').forEach(e => e.classList.remove('selected'));
      el.classList.add('selected');
    });
  });
  const s = await (await fetch('/api/stats')).json();
  document.getElementById('stat-total').textContent = s.total||0;
  document.getElementById('stat-avg-time').textContent = s.avg_time ? s.avg_time.toFixed(1)+'s' : '--';
  document.getElementById('stat-since').textContent = accountData.created_at
    ? new Date(accountData.created_at).toLocaleDateString() : '--';
}
function openAccountModal()  { document.getElementById('account-modal').classList.add('show'); }
function closeAccountModal() { document.getElementById('account-modal').classList.remove('show'); }
async function saveAccount() {
  const sel = document.querySelector('.color-opt.selected');
  await fetch('/api/account', {
    method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      name: document.getElementById('acc-name').value,
      email: document.getElementById('acc-email').value,
      organization: document.getElementById('acc-org').value,
      avatar_color: sel ? sel.dataset.color : accountData.avatar_color
    })
  });
  closeAccountModal(); loadAccount();
}

// ── History ──────────────────────────────────────────────────────────────────
async function loadHistory() {
  const d = await (await fetch('/api/history')).json();
  historyItems = d.items||[];
  renderHistory();
  const ns = document.getElementById('nav-stat');
  if (ns) ns.textContent = `${historyItems.length} queries`;
}
function renderHistory(filter='') {
  const list = document.getElementById('history-list');
  const items = filter
    ? historyItems.filter(i => i.query_text.toLowerCase().includes(filter.toLowerCase()))
    : historyItems;
  if (!items.length) { list.innerHTML = '<div class="empty-state">No history yet</div>'; return; }
  list.innerHTML = items.map(i => `
    <div class="history-item ${activeHistId===i.id?'active':''}" onclick="loadHistoryItem(${i.id})">
      <div class="hq">${escHtml(i.query_text)}</div>
      <div class="hm">
        <span>${timeAgo(i.timestamp)}</span>
        <span>✅ ${i.successful_models}/${i.total_models}</span>
        <button class="del-btn" onclick="event.stopPropagation();delHist(${i.id})">✕</button>
      </div>
    </div>`).join('');
}
async function loadHistoryItem(id) {
  activeHistId = id; renderHistory();
  const d = await (await fetch(`/api/history/${id}`)).json();
  // Show as a single-turn read-only thread
  newConversation();
  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('conv-header').style.display = 'flex';
  document.getElementById('conv-pill').textContent = 'History';
  document.getElementById('conv-title').textContent = d.query_text;
  appendTurn(d.query_text, 1,
    { broadcast: { responses: d.responses_json||[], total_broadcast_time_seconds: d.broadcast_time },
      consensus: { ranked_models: d.ranked_json||[], consensus_answer: d.consensus_answer||'' } }
  );
  if (window.innerWidth < 768) toggleSidebar();
}
async function delHist(id) {
  if (!confirm('Delete this entry?')) return;
  await fetch(`/api/history/${id}`, {method:'DELETE'});
  loadHistory();
}
document.getElementById('history-search').addEventListener('input', e => renderHistory(e.target.value));

// ── Input handling ───────────────────────────────────────────────────────────
document.getElementById('query-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitQuery(); }
});
document.getElementById('query-input').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 150) + 'px';
});

// ── Submit ───────────────────────────────────────────────────────────────────
async function submitQuery() {
  const inp = document.getElementById('query-input');
  const q   = inp.value.trim();
  if (!q) return;

  inp.value = ''; inp.style.height = 'auto'; inp.focus();

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.innerHTML = '<span style="display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite"></span> Querying…';

  // Activate engine panel
  if (typeof enginePanelActivate === 'function') enginePanelActivate();

  // Show conversation header on first query
  turnNum++;
  if (turnNum === 1) {
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('conv-header').style.display = 'flex';
    document.getElementById('conv-pill').textContent = `Conversation ${convNum}`;
    document.getElementById('conv-title').textContent = generateTitle(q);
  }

  // Show loading indicator (left-aligned)
  const loading = document.getElementById('loading-turn');
  document.getElementById('loading-sub').textContent = `Turn ${turnNum}`;
  loading.style.display = 'flex';
  loading.scrollIntoView({behavior:'smooth', block:'end'});

  try {
    const r = await fetch('/api/query', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        query: q,
        context: conversationContext,
        conversation_id: currentConvId
      })
    });
    if (!r.ok) {
      let msg = `Server error ${r.status}`;
      try { const e = await r.json(); msg = e.detail || JSON.stringify(e); } catch { msg = await r.text(); }
      throw new Error(msg.slice(0, 300));
    }
    const d = await r.json();
    loading.style.display = 'none';
    appendTurn(q, turnNum, d);

    // Push to conversation context
    const ans = d.consensus?.consensus_answer || '';
    if (ans) conversationContext.push({query: q, answer: ans});
    loadHistory();
  } catch(e) {
    loading.style.display = 'none';
    alert('Error: ' + e.message);
    turnNum--;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> Engage All';
  }
}

// ── Build a conversation turn ─────────────────────────────────────────────────
function appendTurn(query, num, data) {
  const responses = data.broadcast?.responses || [];
  const ranked    = data.consensus?.ranked_models || [];
  const answer    = data.consensus?.consensus_answer || '';
  const time      = data.broadcast?.total_broadcast_time_seconds || 0;
  const ok        = responses.filter(r => r.status === 'success').length;
  const tid       = 'turn-' + Date.now() + '-' + num;

  const el = document.createElement('div');
  el.className = 'conv-turn';
  el.id = tid;
  el.innerHTML = `
    <!-- Query RIGHT -->
    <div class="turn-query">
      <div class="tq-bubble">
        <div class="tq-label">Query ${num}</div>
        <div class="tq-text">${escHtml(query)}</div>
      </div>
    </div>

    <!-- Answer LEFT -->
    <div class="turn-answer">
      <div class="ta-card">
        <div class="ta-hdr">
          <span class="ta-icon">◆</span>
          <span class="ta-lbl">Consensus Answer</span>
          <span class="ta-meta">${ok}/5 models · ${time.toFixed(1)}s</span>
          <button class="ta-toggle" onclick="toggleModels(this, '${tid}')">▾ Models</button>
        </div>
        <div class="ta-body">${renderMarkdown(answer || 'No answer synthesized.')}</div>
        <div class="ta-models" id="models-${tid}">
          <div class="mini-grid">${buildMiniCards(responses, ranked).replace(/__TID__/g, tid)}</div>
        </div>
      </div>
    </div>`;

  document.getElementById('conv-thread').appendChild(el);

  // Animate in
  requestAnimationFrame(() => {
    el.classList.add('visible');
    setTimeout(() => {
      el.scrollIntoView({behavior:'smooth', block:'start'});
      // Animate mini score bars
      ranked.forEach(r => {
        const fill = document.getElementById(`mf-${tid}-${r.rank}`);
        if (fill) fill.style.width = (r.consensus_score * 100) + '%';
      });
    }, 100);
  });

  // Update engine panel with results
  if (typeof enginePanelDone === 'function') {
    enginePanelDone(
      responses,
      ranked,
      time
    );
  }
}

function isSkippedError(err) {
  if (!err) return false;
  return /(credit|quota|balance|429|rate limit|billing|insufficient|exhausted|limit|unauthorized|401|403|exceeded)/i.test(err);
}

// ── Mini cards shown inside the collapsible ▾ Models section ────────────────
function buildMiniCards(responses, ranked) {
  const byModel = {};
  ranked.forEach(r => { byModel[r.model] = r; });
  return responses.map((resp, i) => {
    const m     = MODELS[i] || { icon:'🤖', fill:'#6366f1', name:resp.model, provider:'' };
    const rank  = byModel[resp.model];
    const ok    = resp.status === 'success';
    const skipped = !ok && isSkippedError(resp.error);
    const score = rank ? rank.consensus_score : null;
    const preview = ok ? truncate(resp.response, 120) : (skipped ? 'Skipped (Quota/Credits limit)' : (resp.error||'Failed').slice(0,100));
    const dotClass = ok ? 'dot-ok' : (skipped ? 'dot-skip' : 'dot-err');
    return `
      <div class="mini-card">
        <div class="mini-hdr">
          <span class="mini-icon">${m.icon}</span>
          <span class="mini-name">${resp.model}</span>
          <span class="mini-dot ${dotClass}"></span>
        </div>
        <div class="mini-preview">${escHtml(preview)}</div>
        ${score !== null ? `
        <div class="mini-bar"><div class="mini-fill" id="mf-__TID__-${rank.rank}" style="background:${m.fill};width:0"></div></div>
        <div class="mini-score">#${rank.rank} · ${score.toFixed(3)}</div>` : ''}
      </div>`;
  }).join('');
}

function buildFullCards(responses, ranked, tid) {
  const byModel = {};
  ranked.forEach(r => { byModel[r.model] = r; });
  return responses.map((resp, i) => {
    const m     = MODELS[i] || { icon:'🤖', fill:'#6366f1', name:resp.model, provider:'' };
    const rank  = byModel[resp.model];
    const ok    = resp.status === 'success';
    const skipped = !ok && isSkippedError(resp.error);
    const score = rank ? rank.consensus_score : null;
    const preview = ok ? truncate(resp.response, 180) : (skipped ? 'Skipped (Quota/Credits limit)' : (resp.error||'').slice(0,150));
    const fillId  = `sf-${tid}-${i}`;
    const scoreBar = ok && score !== null ? `
      <div class="score-row">
        <span class="score-label">#${rank.rank} rank</span>
        <div class="score-bar"><div class="score-fill" id="${fillId}" data-target="${(score*100).toFixed(1)}" style="background:${m.fill}"></div></div>
        <span class="score-val">${score.toFixed(2)}</span>
      </div>` : '';
    const cardClass = ok ? 'success' : (skipped ? 'skipped' : 'error');
    const dotClass = ok ? 'dot-success' : (skipped ? 'dot-skip' : 'dot-error');
    const txtClass = ok ? '' : (skipped ? 'skip-text' : 'error-text');
    return `
      <div class="model-card ${cardClass}" style="transition-delay:${i*80}ms">
        <div class="card-header">
          <div class="card-icon" style="background:${m.fill}22">${m.icon}</div>
          <div class="card-info">
            <div class="card-name">${resp.model}</div>
            <div class="card-provider">${resp.provider||m.provider} · ${resp.time_taken_seconds||0}s</div>
          </div>
          <div class="status-dot ${dotClass}"></div>
        </div>
        <div class="card-response ${txtClass}">${escHtml(preview)}</div>
        ${scoreBar}
      </div>`;
  }).join('');
}

function toggleModels(btn, tid) {
  const grid = document.getElementById('models-' + tid);
  if (!grid) return;
  const open = grid.classList.toggle('open');
  btn.textContent = open ? '\u25b4 Hide' : '\u25be Models';
  if (open) {
    // Animate mini score bars (IDs injected by buildMiniCards use tid)
    setTimeout(() => {
      grid.querySelectorAll('.mini-fill').forEach(f => {
        // width already set via data from appendTurn; trigger CSS transition
        const w = f.style.width;
        f.style.width = '0';
        requestAnimationFrame(() => { f.style.width = w; });
      });
    }, 50);
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function generateTitle(query) {
  const stop = new Set(['what','how','why','when','where','who','is','are','the','a','an',
    'and','or','of','in','to','do','does','can','could','would','should','will','with']);
  const words = query.trim().split(/\s+/)
    .filter(w => w.length > 2 && !stop.has(w.toLowerCase()))
    .slice(0, 5);
  return words.length > 0 ? words.join(' ') : truncate(query, 45);
}

function renderMarkdown(text) {
  if (!text) return '';
  // Code blocks first
  text = text.replace(/```[\s\S]*?```/g, m => {
    const code = m.replace(/^```\w*\n?/, '').replace(/```$/, '');
    return `<pre><code>${escHtml(code)}</code></pre>`;
  });
  return text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,  '<h2>$1</h2>')
    .replace(/^# (.+)$/gm,   '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')
    .replace(/`([^`]+)`/g,     '<code>$1</code>')
    .replace(/^[-*] (.+)$/gm,  '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>\n?)+/g, s => `<ul>${s}</ul>`)
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^([^<].*)$/gm, s => `<p>${s}</p>`)
    .replace(/<p><\/p>/g, '')
    .trim();
}

function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function truncate(s, n) {
  s = String(s||''); return s.length > n ? s.slice(0,n) + '…' : s;
}
function timeAgo(ts) {
  const diff = (new Date() - new Date(ts)) / 1000;
  if (diff < 60)   return Math.round(diff)+'s ago';
  if (diff < 3600) return Math.round(diff/60)+'m ago';
  if (diff < 86400) return Math.round(diff/3600)+'h ago';
  return new Date(ts).toLocaleDateString();
}

// ── Spin animation (inline for button) ───────────────────────────────────────
const style = document.createElement('style');
style.textContent = '@keyframes spin{to{transform:rotate(360deg)}}';
document.head.appendChild(style);

// ── Init ─────────────────────────────────────────────────────────────────────
loadAccount();
loadHistory();

// ── Engine Panel ──────────────────────────────────────────────────────────────
let epVisible = window.innerWidth > 700;

// Initialize on load
if (!sidebarVisible) {
  document.querySelector('.sidebar').classList.add('hidden');
  document.body.classList.add('sidebar-hidden');
}
if (!epVisible) {
  document.getElementById('engine-panel').classList.add('hidden');
  document.body.classList.add('ep-hidden');
}

function toggleEnginePanel() {
  epVisible = !epVisible;
  const panel = document.getElementById('engine-panel');
  if (epVisible) {
    panel.classList.remove('hidden');
    document.body.classList.remove('ep-hidden');
  } else {
    panel.classList.add('hidden');
    document.body.classList.add('ep-hidden');
  }
}

function epSetStatus(state) {
  const badge = document.getElementById('ep-status-badge');
  badge.className = 'ep-status-badge';
  if (state === 'active') { badge.classList.add('active'); badge.textContent = 'ENGAGING'; }
  else if (state === 'done') { badge.classList.add('done'); badge.textContent = 'COMPLETE'; }
  else { badge.textContent = 'IDLE'; }
}

function epResetModels() {
  for (let i = 0; i < 5; i++) {
    const row = document.getElementById('epm-' + i);
    const stat = document.getElementById('eps-' + i);
    if (row) { row.className = 'ep-model'; }
    if (stat) stat.textContent = 'Standby';
  }
  const cr = document.getElementById('ep-consensus-ring');
  const cs = document.getElementById('ep-consensus-stat');
  if (cr) { cr.className = 'ep-consensus-ring'; }
  if (cs) cs.textContent = 'Waiting for models\u2026';
}

function enginePanelActivate() {
  epResetModels();
  epSetStatus('active');
  // Stagger each model's "engaging" animation
  for (let i = 0; i < 5; i++) {
    setTimeout(() => {
      const row = document.getElementById('epm-' + i);
      const stat = document.getElementById('eps-' + i);
      if (row) row.classList.add('engaging');
      if (stat) stat.textContent = 'Querying\u2026';
    }, i * 120);
  }
  // After models start, activate consensus ring
  setTimeout(() => {
    const cr = document.getElementById('ep-consensus-ring');
    const cs = document.getElementById('ep-consensus-stat');
    if (cr) cr.classList.add('active');
    if (cs) cs.textContent = 'Awaiting responses\u2026';
  }, 700);
}

function enginePanelDone(responses, ranked, broadcastTime) {
  epSetStatus('done');

  // Build lookup: model name -> {score, time, status}
  const byModel = {};
  (ranked || []).forEach(r => { byModel[r.model] = r; });

  (responses || []).forEach((resp, i) => {
    const row  = document.getElementById('epm-' + i);
    const stat = document.getElementById('eps-' + i);
    if (!row) return;
    row.classList.remove('engaging');
    const ok = resp.status === 'success';
    const skipped = !ok && isSkippedError(resp.error);
    row.classList.add(ok ? 'done-ok' : (skipped ? 'done-skip' : 'done-err'));
    if (stat) {
      if (ok) {
        const rk = byModel[resp.model];
        const score = rk ? rk.consensus_score.toFixed(3) : '';
        const t = (resp.time_taken_seconds || 0).toFixed(1);
        stat.textContent = score ? `#${rk.rank} · ${score} · ${t}s` : `${t}s`;
      } else if (skipped) {
        stat.textContent = 'Skipped';
      } else {
        stat.textContent = 'Error';
      }
    }
  });

  // Consensus done
  setTimeout(() => {
    const cr = document.getElementById('ep-consensus-ring');
    const cs = document.getElementById('ep-consensus-stat');
    if (cr) { cr.classList.remove('active'); cr.classList.add('done'); }
    if (cs) cs.textContent = 'Synthesis complete';
  }, 400);

  // Update footer time
  const td = document.getElementById('ep-time-display');
  if (td && broadcastTime) td.textContent = broadcastTime.toFixed(2) + 's';
}

