/* POD-EXP — index page script */
// MODELS is injected inline by the template: const MODELS = {{ models | tojson }};

const THINKING_MODELS = new Set(['gpt-5.4', 'gpt-5.4-mini', 'gpt-5.5', 'gpt-5.5-mini']);
const STORAGE_KEYS = {
  chat: 'pod-exp.chat-settings',
  debate: 'pod-exp.debate-settings',
};
let defaultChatSettings = null;
let defaultDebateSettings = null;

let conversation = [];
let busy = false;
let liveNotes = null;

/* ── Boot ─────────────────────────────────────── */
(function () {
  defaultChatSettings = getDefaultChatSettings();
  defaultDebateSettings = getDefaultDebateSettings();
  restoreChatSettings();
  initDebateModels();
  restoreDebateSettings();
  bindPersistentSettings();
})();

/* ── Helpers ──────────────────────────────────── */
function provider() { return document.querySelector('input[name=provider]:checked').value; }
function model()    { return document.getElementById('sel-model').value; }
function agent()    { return document.getElementById('sel-agent').value; }
function thinking() { return document.getElementById('sel-thinking').value || null; }

function loadStoredJson(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function saveStoredJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {}
}

function clearStoredSettings() {
  try {
    localStorage.removeItem(STORAGE_KEYS.chat);
    localStorage.removeItem(STORAGE_KEYS.debate);
  } catch (_) {}
}

function getDefaultChatSettings() {
  const checkedProvider = document.querySelector('input[name=provider]:checked');
  return {
    agent: document.getElementById('sel-agent').value,
    provider: checkedProvider ? checkedProvider.value : 'openai',
    model: '',
    thinking_effort: document.getElementById('sel-thinking').value || null,
  };
}

function getDefaultDebateSettings() {
  return {
    agent1: document.getElementById('d-agent1').value,
    agent2: document.getElementById('d-agent2').value,
    provider1: debateProv(1),
    provider2: debateProv(2),
    model1: '',
    model2: '',
    thinking_effort1: document.getElementById('d-think1').value || null,
    thinking_effort2: document.getElementById('d-think2').value || null,
    max_tokens1: document.getElementById('d-maxtok1').value || '4096',
    max_tokens2: document.getElementById('d-maxtok2').value || '4096',
    topic: document.getElementById('d-topic').value.trim() || 'Czym jest prawda?',
    debate_mode: document.getElementById('d-mode').value,
    debate_mode_custom: document.getElementById('d-mode-custom').value || '',
    max_turns: parseInt(document.getElementById('d-turns').value, 10) || 33,
  };
}

function resetStoredSettings() {
  clearStoredSettings();
  if (defaultChatSettings) {
    const chatProvider = document.querySelector(`input[name=provider][value="${defaultChatSettings.provider || 'openai'}"]`);
    if (chatProvider) {
      chatProvider.checked = true;
    }
    document.getElementById('sel-agent').value = defaultChatSettings.agent;
    fillModels();
    document.getElementById('sel-thinking').value = defaultChatSettings.thinking_effort || '';
    onModelChange();
  }
  initDebateModels();
  if (defaultDebateSettings) {
    applyDebateConfig(defaultDebateSettings);
  }
  toggleDebateModeCustom();
}

function saveChatSettings() {
  saveStoredJson(STORAGE_KEYS.chat, {
    agent: agent(),
    provider: provider(),
    model: model(),
    thinking_effort: thinking(),
  });
}

function restoreChatSettings() {
  const stored = loadStoredJson(STORAGE_KEYS.chat) || defaultChatSettings || {};
  if (stored.agent) {
    document.getElementById('sel-agent').value = stored.agent;
  }
  const providerRadio = document.querySelector(`input[name=provider][value="${stored.provider || 'openai'}"]`);
  if (providerRadio) {
    providerRadio.checked = true;
  }
  fillModels();
  if (stored.model) {
    const modelSelect = document.getElementById('sel-model');
    if ([...modelSelect.options].some(option => option.value === stored.model)) {
      modelSelect.value = stored.model;
    }
  }
  onModelChange();
  if (stored.thinking_effort && THINKING_MODELS.has(model())) {
    document.getElementById('sel-thinking').value = stored.thinking_effort;
  }
  saveChatSettings();
}

function saveDebateSettings() {
  saveStoredJson(STORAGE_KEYS.debate, getDebateConfig());
}

function restoreDebateSettings() {
  const stored = loadStoredJson(STORAGE_KEYS.debate) || defaultDebateSettings;
  if (!stored) return;
  applyDebateConfig(stored);
  saveDebateSettings();
}

function bindPersistentSettings() {
  document.querySelectorAll('input[name=provider]')
    .forEach(r => r.addEventListener('change', () => { fillModels(); saveChatSettings(); }));
  document.getElementById('sel-model').addEventListener('change', () => { onModelChange(); saveChatSettings(); });
  document.getElementById('sel-agent').addEventListener('change', saveChatSettings);
  document.getElementById('sel-thinking').addEventListener('change', saveChatSettings);

  [
    'd-agent1', 'd-agent2', 'd-model1', 'd-model2', 'd-think1', 'd-think2',
    'd-maxtok1', 'd-maxtok2', 'd-topic', 'd-mode', 'd-mode-custom', 'd-turns',
  ].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('change', saveDebateSettings);
    el.addEventListener('input', saveDebateSettings);
  });

  document.querySelectorAll('input[name=prov1], input[name=prov2]')
    .forEach(r => r.addEventListener('change', saveDebateSettings));
}

function fillModels() {
  const sel = document.getElementById('sel-model');
  sel.innerHTML = (MODELS[provider()] || []).map(m => `<option value="${m}">${m}</option>`).join('');
  onModelChange();
}

function onModelChange() {
  const tf = document.getElementById('thinking-field');
  const st = document.getElementById('sel-thinking');
  if (THINKING_MODELS.has(model())) {
    tf.style.display = '';
  } else {
    tf.style.display = 'none';
    st.value = '';
  }
  saveChatSettings();
}

/* ── Chat management ──────────────────────────── */
function newChat() {
  conversation = [];
  const m = document.getElementById('messages');
  m.innerHTML = `<div class="empty" id="empty">
    <div class="empty-title">POD-EXP</div>
    <div class="empty-sub">Wybierz agenta i zadaj pytanie</div>
  </div>`;
  resetNotesPanel();
  hideContinueButton();
  debateContinuationState = null;
  lastDebateConfig = null;
  currentDebateSavedId = null;
}

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function addMessage(role, content, toolName) {
  const empty = document.getElementById('empty');
  if (empty) empty.remove();

  const wrap = document.createElement('div');
  wrap.className = `msg ${role}`;

  const labels = { user: 'Ty', assistant: 'Agent', tool: 'Tool', error: 'Błąd' };
  let bubble = '';

  if (role === 'assistant') {
    bubble = marked.parse(content);
  } else if (role === 'tool') {
    const chip = toolName ? `<div class="tool-chip">⚙ ${escHtml(toolName)}</div>` : '';
    bubble = chip + `<pre>${escHtml(content)}</pre>`;
  } else {
    bubble = `<p>${escHtml(content).replace(/\n/g, '<br>')}</p>`;
  }

  wrap.innerHTML = `
    <div class="msg-role">${labels[role] || role}</div>
    <div class="msg-bubble">${bubble}</div>
  `;

  const msgs = document.getElementById('messages');
  msgs.appendChild(wrap);
  msgs.scrollTop = msgs.scrollHeight;
}

function showThinking() {
  const el = document.createElement('div');
  el.className = 'thinking'; el.id = 'thinking';
  el.innerHTML = `<div class="dot"></div><div class="dot"></div><div class="dot"></div><span style="margin-left:5px">myśli…</span>`;
  const m = document.getElementById('messages');
  m.appendChild(el);
  m.scrollTop = m.scrollHeight;
}
function hideThinking() { const e = document.getElementById('thinking'); if (e) e.remove(); }

/* ── Send ─────────────────────────────────────── */
async function send() {
  if (busy) return;
  const inp = document.getElementById('input');
  const text = inp.value.trim();
  if (!text) return;

  inp.value = ''; inp.style.height = '';
  conversation.push({ role: 'user', content: text });
  addMessage('user', text);

  busy = true;
  document.getElementById('btn-send').disabled = true;
  showThinking();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent:           agent(),
        provider:        provider(),
        model:           model(),
        thinking_effort: thinking(),
        messages:        conversation,
      }),
    });
    const data = await res.json();
    hideThinking();

    if (data.error) {
      addMessage('error', data.error);
    } else {
      conversation.push({ role: 'assistant', content: data.content });
      addMessage('assistant', data.content);
    }
  } catch (e) {
    hideThinking();
    addMessage('error', `Błąd połączenia: ${e.message}`);
  } finally {
    busy = false;
    document.getElementById('btn-send').disabled = false;
    inp.focus();
  }
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
}
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 180) + 'px';
}

/* ═══════════════════════════════════════════════
   DEBATE MODE
   ═══════════════════════════════════════════════ */

let debateActive = false;
let dAgent1 = '', dAgent2 = '', dMaxTurns = 33;
let curThinkEl = null, curTextEl = null, curTextRaw = '';
let analyzerTextEl = null, analyzerRaw = '';
let summaryTextEl = null, summaryRaw = '';
let abortCtrl = null;
let debateContinuationState = null;
let lastDebateConfig = null;
let currentDebateSavedId = null;

function toggleDebateModeCustom() {
  const mode = document.getElementById('d-mode').value;
  const custom = document.getElementById('d-mode-custom');
  custom.style.display = mode === 'inne' ? '' : 'none';
}

/* ── Mode toggle ─────────────────────────────── */
function setMode(mode) {
  const isD = mode === 'debate';
  document.getElementById('chat-cfg').style.display    = isD ? 'none' : 'flex';
  document.getElementById('debate-cfg').style.display  = isD ? 'flex' : 'none';
  document.getElementById('input-area').style.display  = isD ? 'none' : '';
  document.getElementById('prog-row').style.display    = isD ? ''     : 'none';
  document.getElementById('notes-pane').classList.toggle('active', isD);
  document.getElementById('btn-chat-mode').classList.toggle('active', !isD);
  document.getElementById('btn-debate-mode').classList.toggle('active', isD);
  newChat();
  if (isD) {
    initDebateModels();
    toggleDebateModeCustom();
  }
}

/* ── Debate model selects ────────────────────── */
function debateProv(n) { return document.querySelector(`input[name=prov${n}]:checked`).value; }

function initDebateModels() {
  [1, 2].forEach(n => {
    fillDModel(n);
    document.querySelectorAll(`input[name=prov${n}]`)
      .forEach(r => {
        if (r.dataset.modelsBound === '1') return;
        r.addEventListener('change', () => { fillDModel(n); saveDebateSettings(); });
        r.dataset.modelsBound = '1';
      });
    const modelSelect = document.getElementById(`d-model${n}`);
    if (modelSelect.dataset.modelsBound !== '1') {
      modelSelect.addEventListener('change', () => { syncDThink(n); saveDebateSettings(); });
      modelSelect.dataset.modelsBound = '1';
    }
  });
}

function fillDModel(n) {
  const sel = document.getElementById(`d-model${n}`);
  sel.innerHTML = (MODELS[debateProv(n)] || []).map(m => `<option value="${m}">${m}</option>`).join('');
  syncDThink(n);
}

function syncDThink(n) {
  const m = document.getElementById(`d-model${n}`).value;
  document.getElementById(`d-think${n}`).style.display = THINKING_MODELS.has(m) ? '' : 'none';
}

function applyDebateConfig(cfg) {
  if (!cfg) return;
  document.getElementById('d-agent1').value = cfg.agent1 || document.getElementById('d-agent1').value;
  document.getElementById('d-agent2').value = cfg.agent2 || document.getElementById('d-agent2').value;
  document.getElementById('d-topic').value = cfg.topic || document.getElementById('d-topic').value;
  document.getElementById('d-turns').value = cfg.max_turns || document.getElementById('d-turns').value;
  document.getElementById('d-mode').value = cfg.debate_mode || 'dialog';
  document.getElementById('d-mode-custom').value = cfg.debate_mode_custom || '';
  toggleDebateModeCustom();

  const p1 = document.querySelector(`input[name=prov1][value="${cfg.provider1 || 'openai'}"]`);
  const p2 = document.querySelector(`input[name=prov2][value="${cfg.provider2 || 'openai'}"]`);
  if (p1) p1.checked = true;
  if (p2) p2.checked = true;

  fillDModel(1);
  fillDModel(2);

  if (cfg.model1) document.getElementById('d-model1').value = cfg.model1;
  if (cfg.model2) document.getElementById('d-model2').value = cfg.model2;
  syncDThink(1);
  syncDThink(2);

  document.getElementById('d-think1').value = cfg.thinking_effort1 || '';
  document.getElementById('d-think2').value = cfg.thinking_effort2 || '';
  document.getElementById('d-maxtok1').value = String(cfg.max_tokens1 || '4096');
  document.getElementById('d-maxtok2').value = String(cfg.max_tokens2 || '4096');
  saveDebateSettings();
}

function hideContinueButton() {
  document.getElementById('btn-continue-debate').style.display = 'none';
}

function showContinueButton() {
  document.getElementById('btn-continue-debate').style.display = '';
}

function removeAnalysisFromView() {
  document.querySelectorAll('.adivider, .dmsg.analyzer, .dmsg.summariser').forEach(el => el.remove());
  analyzerTextEl = null;
  analyzerRaw = '';
  summaryTextEl = null;
  summaryRaw = '';
}

/* ── Debate config ───────────────────────────── */
function getDebateConfig() {
  const mode = document.getElementById('d-mode').value;
  const customMode = document.getElementById('d-mode-custom').value.trim();
  return {
    agent1:           document.getElementById('d-agent1').value,
    agent2:           document.getElementById('d-agent2').value,
    provider1:        debateProv(1),
    provider2:        debateProv(2),
    model1:           document.getElementById('d-model1').value,
    model2:           document.getElementById('d-model2').value,
    thinking_effort1: document.getElementById('d-think1').value || null,
    thinking_effort2: document.getElementById('d-think2').value || null,
    max_tokens1:      document.getElementById('d-maxtok1').value || '4096',
    max_tokens2:      document.getElementById('d-maxtok2').value || '4096',
    topic:            document.getElementById('d-topic').value.trim() || 'Czym jest prawda?',
    debate_mode:      mode,
    debate_mode_custom: mode === 'inne' ? customMode : '',
    max_turns:        parseInt(document.getElementById('d-turns').value) || 33,
  };
}

/* ── Start / Stop ────────────────────────────── */
async function startDebate(options = {}) {
  if (debateActive) return;
  const isContinuation = options.continuation === true;
  const extraTurns = parseInt(document.getElementById('d-turns').value) || 10;
  const cfg = isContinuation && lastDebateConfig
    ? { ...lastDebateConfig, max_turns: extraTurns }
    : getDebateConfig();

  applyDebateConfig(cfg);
  lastDebateConfig = { ...cfg };
  dAgent1 = cfg.agent1;
  dAgent2 = cfg.agent2;
  dMaxTurns = cfg.max_turns;

  const completedTurns = isContinuation
    ? (debateContinuationState?.turns_completed || debateContinuationState?.transcript?.length || 0)
    : 0;
  const totalTurns = completedTurns + dMaxTurns;

  if (!isContinuation) {
    document.getElementById('messages').innerHTML = '';
    resetNotesPanel(cfg.topic);
    renderDebateTopic(cfg.topic);
    debateContinuationState = null;
    currentDebateSavedId = null;
  } else {
    removeAnalysisFromView();
    if (debateContinuationState?.live_notes) {
      liveNotes = debateContinuationState.live_notes;
      renderLiveNotes(completedTurns);
    }
  }

  document.getElementById('prog-fill').style.width = totalTurns ? `${(completedTurns / totalTurns) * 100}%` : '0%';
  document.getElementById('prog-label').textContent = `${completedTurns} / ${totalTurns}`;
  document.getElementById('btn-start-debate').disabled = true;
  hideContinueButton();
  document.getElementById('btn-stop-debate').style.display = '';
  debateActive = true;
  abortCtrl = new AbortController();

  const payload = isContinuation && debateContinuationState
    ? {
        ...cfg,
        history1: debateContinuationState.history1 || [],
        history2: debateContinuationState.history2 || [],
        transcript: debateContinuationState.transcript || [],
        live_notes: debateContinuationState.live_notes || null,
        continuation_of: currentDebateSavedId,
      }
    : cfg;

  try {
    const res = await fetch('/api/debate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal: abortCtrl.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const dec    = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try { onDebateEvent(JSON.parse(line.slice(6))); } catch (_) {}
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') addDebateError(e.message);
  } finally {
    debateActive = false;
    document.getElementById('btn-start-debate').disabled = false;
    document.getElementById('btn-stop-debate').style.display = 'none';
  }
}

function stopDebate() { abortCtrl?.abort(); }

function continueDebate() {
  if (!debateContinuationState || debateActive) return;
  startDebate({ continuation: true });
}

/* ── Event handlers ──────────────────────────── */
function onDebateEvent(ev) {
  switch (ev.type) {
    case 'turn_start':     onTurnStart(ev);      break;
    case 'thinking':       onThinking(ev);       break;
    case 'text':           onText(ev);           break;
    case 'turn_end':       onTurnEnd(ev);        break;
    case 'live_notes':     onLiveNotes(ev);      break;
    case 'live_notes_error': onLiveNotesError(ev); break;
    case 'analysis_start': onAnalysisStart();    break;
    case 'analysis_text':  onAnalysisText(ev);   break;
    case 'analysis_done':  onAnalysisDone();     break;
    case 'analysis_json':  onAnalysisJson(ev);   break;
    case 'summary_start':  onSummaryStart();     break;
    case 'summary_text':   onSummaryText(ev);    break;
    case 'summary_done':   onSummaryDone();      break;
    case 'summary_error':  onSummaryError(ev);   break;
    case 'saved':          onSaved(ev);          break;
    case 'error':          addDebateError(ev.message); break;
  }
}

function agentSlot(name) { return name === dAgent1 ? 's1' : 's2'; }

function onTurnStart(ev) {
  const empty = document.getElementById('empty');
  if (empty) empty.remove();

  const slot = agentSlot(ev.agent);
  const el   = document.createElement('div');
  el.className = `dmsg ${slot}`;

  const hdr = document.createElement('div');
  hdr.className = 'dmsg-hdr';
  hdr.innerHTML = `<span class="agent-tag ${slot}">${ev.agent}</span><span class="turn-num">${ev.turn} / ${ev.total}</span>`;

  const details = document.createElement('details');
  details.className = 'think'; details.open = true;
  const summary = document.createElement('summary');
  summary.textContent = '🧠 myśli...';
  const thinkBody = document.createElement('div');
  thinkBody.className = 'think-body';
  details.append(summary, thinkBody);

  const bubble = document.createElement('div');
  bubble.className = 'dmsg-bubble';

  el.append(hdr, details, bubble);
  const msgs = document.getElementById('messages');
  msgs.appendChild(el);
  scrollMsgs();

  document.getElementById('prog-fill').style.width = ((ev.turn - 1) / ev.total * 100) + '%';
  document.getElementById('prog-label').textContent = `${ev.turn} / ${ev.total}`;

  curThinkEl = thinkBody; curTextEl = bubble; curTextRaw = '';
}

function onThinking(ev) {
  if (!curThinkEl) return;
  curThinkEl.textContent += ev.delta;
  scrollMsgs();
}

function onText(ev) {
  if (!curTextEl) return;
  curTextRaw += ev.delta;
  curTextEl.textContent = curTextRaw;
  scrollMsgs();
}

function onTurnEnd(ev) {
  if (curTextEl && curTextRaw)
    curTextEl.innerHTML = marked.parse(curTextRaw);
  if (curThinkEl && !curThinkEl.textContent.trim()) {
    const d = curThinkEl.closest('details');
    if (d) d.style.display = 'none';
  }
  document.getElementById('prog-fill').style.width = (ev.turn / ev.total * 100) + '%';
  document.getElementById('prog-label').textContent = `${ev.turn} / ${ev.total}`;
  curThinkEl = null; curTextEl = null; curTextRaw = '';
}

function onLiveNotes(ev) {
  liveNotes = ev.data || null;
  renderLiveNotes(ev.turn);
}

function onLiveNotesError(ev) {
  const sub = document.getElementById('notes-subtitle');
  sub.textContent = `Notatki pominięte po turze ${ev.turn}: ${ev.message}`;
}

function onAnalysisStart() {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'adivider';
  div.innerHTML = '<span>ANALIZATOR</span>';
  msgs.appendChild(div);

  const el = document.createElement('div');
  el.className = 'dmsg analyzer';
  const hdr = document.createElement('div');
  hdr.className = 'dmsg-hdr';
  hdr.innerHTML = '<span class="agent-tag atag">🔬 ANALIZATOR</span>';
  const bubble = document.createElement('div');
  bubble.className = 'dmsg-bubble';
  el.append(hdr, bubble);
  msgs.appendChild(el);
  scrollMsgs();
  analyzerTextEl = bubble; analyzerRaw = '';
}

function onAnalysisText(ev) {
  if (!analyzerTextEl) return;
  analyzerRaw += ev.delta;
  analyzerTextEl.textContent = analyzerRaw;
  scrollMsgs();
}

function onAnalysisDone() {
}

function onAnalysisJson(ev) {
  if (!analyzerTextEl) return;
  const parent = analyzerTextEl.parentElement;
  analyzerTextEl.remove();
  const card = buildAnalysisHtml(ev.data, dAgent1, dAgent2);
  card.className = 'analysis-card';
  parent.appendChild(card);
  analyzerTextEl = null;
  scrollMsgs();
}

function onSummaryStart() {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'adivider';
  div.innerHTML = '<span>SUMMARISER</span>';
  msgs.appendChild(div);

  const el = document.createElement('div');
  el.className = 'dmsg summariser';
  const hdr = document.createElement('div');
  hdr.className = 'dmsg-hdr';
  hdr.innerHTML = '<span class="agent-tag atag">🧩 SUMMARISER</span>';
  const bubble = document.createElement('div');
  bubble.className = 'dmsg-bubble';
  el.append(hdr, bubble);
  msgs.appendChild(el);
  scrollMsgs();
  summaryTextEl = bubble;
  summaryRaw = '';
}

function onSummaryText(ev) {
  if (!summaryTextEl) return;
  summaryRaw += ev.delta;
  summaryTextEl.textContent = summaryRaw;
  scrollMsgs();
}

function onSummaryDone() {
  if (summaryTextEl && summaryRaw) {
    summaryTextEl.innerHTML = marked.parse(summaryRaw);
  }
  document.getElementById('prog-fill').style.width = '100%';
  document.getElementById('prog-label').textContent = 'Zakończono ✓';
}

function onSummaryError(ev) {
  addDebateError(`Summariser: ${ev.message}`);
}

function onSaved(ev) {
  currentDebateSavedId = ev.id;
  debateContinuationState = ev.continuation || null;
  if (ev.config) {
    lastDebateConfig = ev.config;
    applyDebateConfig(ev.config);
  }
  const label = document.getElementById('prog-label');
  label.textContent = 'Zapisano ✓';
  const link = document.createElement('a');
  link.href = `/debates/${ev.id}`;
  link.target = '_blank';
  link.textContent = '🔗 Zobacz zapis';
  link.style.cssText = 'margin-left:12px;font-size:11px;color:var(--accent);text-decoration:underline';
  label.appendChild(link);
  showContinueButton();
}

function addDebateError(message) {
  const wrap = document.createElement('div');
  wrap.className = 'msg error';
  wrap.innerHTML = `
    <div class="msg-role">Błąd</div>
    <div class="msg-bubble"><p>${escHtml(message)}</p></div>
  `;
  document.getElementById('messages').appendChild(wrap);
  scrollMsgs();
}

function resetNotesPanel(topic = '') {
  liveNotes = null;
  const sub = document.getElementById('notes-subtitle');
  sub.textContent = topic ? 'Aktualizowane po każdej turze debaty' : 'Po prawej pojawi się skrót sporu';
  const body = document.getElementById('notes-body');
  body.innerHTML = '<div class="notes-empty" id="notes-empty">Po prawej pojawią się krótkie notatki 1-3 zdania na turę oraz żółte fiszki z rzeczami do sprawdzenia.</div>';
}

function renderDebateTopic(topic) {
  const wrap = document.createElement('div');
  wrap.className = 'topic-card';
  wrap.innerHTML = `
    <div class="topic-kicker">Temat debaty</div>
    <div class="topic-text">${escHtml(topic)}</div>
  `;
  document.getElementById('messages').appendChild(wrap);
  scrollMsgs();
}

function renderLiveNotes(turn) {
  if (!liveNotes) return;
  const body = document.getElementById('notes-body');
  const entries = liveNotes.entries || [];
  const factCards = liveNotes.fact_cards || [];
  const noteCards = entries.map(entry => `
    <div class="notes-card">
      <div class="notes-kicker">Tura ${entry.turn} · ${escHtml(entry.agent || '')}</div>
      <div class="notes-essence">${escHtml(entry.note || '')}</div>
    </div>
  `).join('');
  const factGrid = factCards.map(card => `
    <div class="fact-card">
      <div class="notes-kicker">Tura ${card.turn} · ${escHtml(card.agent || '')}</div>
      <div class="fact-text">${escHtml(card.request || '')}</div>
    </div>
  `).join('');
  const factsError = liveNotes.facts_error ? `
    <div class="notes-meta">Fiszki faktów pominięte w ostatniej turze: ${escHtml(liveNotes.facts_error)}</div>
  ` : '';
  body.innerHTML = `
    <div class="notes-section">
      <div class="notes-section-title">Szybkie notatki</div>
      ${noteCards || '<div class="notes-empty">Brak notatek.</div>'}
    </div>
    <div class="notes-section">
      <div class="notes-section-title notes-section-title-facts">Fiszki faktów do sprawdzenia</div>
      ${factGrid ? `<div class="fact-grid">${factGrid}</div>` : '<div class="notes-empty">Brak nowych fiszek faktów.</div>'}
    </div>
    ${factsError}
    <div class="notes-meta">Ostatnia aktualizacja: tura ${turn}</div>
  `;
}

function scrollMsgs() {
  const m = document.getElementById('messages');
  m.scrollTop = m.scrollHeight;
}
