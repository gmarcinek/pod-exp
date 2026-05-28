/* POD-EXP — debate view page script */
// debate, a1, a2 are injected inline by the template

function slot(name) { return name === a1 ? 's1' : 's2'; }

function renderBubble(md) {
  const el = document.createElement('div');
  el.className = 'dmsg-bubble';
  el.innerHTML = marked.parse(md || '');
  return el;
}

function renderThink(text) {
  if (!text || !text.trim()) return null;
  const d = document.createElement('details');
  d.className = 'think';
  const s = document.createElement('summary');
  s.textContent = '🧠 myśli agenta';
  const b = document.createElement('div');
  b.className = 'think-body';
  b.textContent = text;
  d.append(s, b);
  return d;
}

const container = document.getElementById('messages');

debate.transcript.forEach((t, i) => {
  const sl = slot(t.agent);
  const el = document.createElement('div');
  el.className = `dmsg ${sl}`;

  const hdr = document.createElement('div');
  hdr.className = 'dmsg-hdr';
  hdr.innerHTML = `<span class="agent-tag ${sl}">${t.agent}</span><span class="turn-num">${i + 1} / ${debate.transcript.length}</span>`;

  const think = renderThink(t.thinking);
  const bubble = renderBubble(t.content);

  el.append(hdr);
  if (think) el.append(think);
  el.append(bubble);
  container.appendChild(el);
});

// Analizator
if (debate.analysis || debate.analysis_json) {
  const div = document.createElement('div');
  div.className = 'adivider';
  div.innerHTML = '<span>ANALIZATOR</span>';
  container.appendChild(div);

  const el = document.createElement('div');
  el.className = 'dmsg analyzer';
  const hdr = document.createElement('div');
  hdr.className = 'dmsg-hdr';
  hdr.innerHTML = '<span class="agent-tag atag">🔬 ANALIZATOR</span>';

  const think = renderThink(debate.analysis_thinking);
  el.append(hdr);
  if (think) el.append(think);

  if (debate.analysis_json) {
    const card = buildAnalysisHtml(debate.analysis_json, a1, a2);
    card.className = 'analysis-card';
    el.appendChild(card);
  } else {
    const bubble = document.createElement('div');
    bubble.className = 'dmsg-bubble';
    bubble.innerHTML = marked.parse(debate.analysis || '');
    el.append(bubble);
  }

  container.appendChild(el);
}

if (debate.summary) {
  const div = document.createElement('div');
  div.className = 'adivider';
  div.innerHTML = '<span>SUMMARISER</span>';
  container.appendChild(div);

  const el = document.createElement('div');
  el.className = 'dmsg summariser';
  const hdr = document.createElement('div');
  hdr.className = 'dmsg-hdr';
  hdr.innerHTML = '<span class="agent-tag atag">🧩 SUMMARISER</span>';

  const think = renderThink(debate.summary_thinking);
  el.append(hdr);
  if (think) el.append(think);

  const bubble = document.createElement('div');
  bubble.className = 'dmsg-bubble';
  bubble.innerHTML = marked.parse(debate.summary || '');
  el.append(bubble);

  container.appendChild(el);
}
