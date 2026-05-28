/* POD-EXP — shared analysis card renderer */
function buildAnalysisHtml(d, a1, a2) {
  const el = document.createElement('div');
  const interactionPatterns = d.interaction_patterns || d.attack_patterns;
  const positionAsymmetries = d.position_asymmetries || d.defense_asymmetries;
  const relationStatus = d.relation_status || d.spore_status;

  function pill(text) { const s = document.createElement('span'); s.className = 'ana-pill'; s.textContent = text; return s; }
  function list(items) {
    const ul = document.createElement('ul'); ul.className = 'ana-ul';
    (items || []).forEach(i => { const li = document.createElement('li'); li.textContent = i; ul.appendChild(li); });
    return ul;
  }
  function sec(title) {
    const d = document.createElement('div'); d.className = 'ana-sec';
    d.innerHTML = `<div class="ana-sec-title">${title}</div>`;
    return d;
  }

  if (d.cartographer_position) {
    const p = document.createElement('p'); p.className = 'ana-cart-pos';
    p.textContent = '📍 ' + d.cartographer_position;
    el.appendChild(p);
  }

  if (d.interaction_pattern) {
    const s = sec('Układ relacji');
    const badge = document.createElement('span'); badge.className = 'ana-spore-type'; badge.textContent = d.interaction_pattern.type || '—';
    const p = document.createElement('p'); p.textContent = d.interaction_pattern.rationale || '';
    s.appendChild(badge);
    s.appendChild(p);
    if (d.interaction_pattern.exchange_refs?.length) {
      const refs = document.createElement('div'); refs.className = 'muted';
      refs.innerHTML = d.interaction_pattern.exchange_refs.map(n => `<span class="ana-xref">#${n}</span>`).join(' ');
      s.appendChild(refs);
    }
    el.appendChild(s);
  }

  if (d.mode_observation) {
    const s = sec('Tryb a przebieg');
    const badge = document.createElement('span'); badge.className = 'ana-spore-type'; badge.textContent = d.mode_observation.fit || '—';
    const p1 = document.createElement('p'); p1.textContent = `Tryb zadany: ${d.mode_observation.declared_mode || '—'}`;
    const p2 = document.createElement('p'); p2.className = 'muted'; p2.textContent = d.mode_observation.rationale || '';
    s.appendChild(badge);
    s.appendChild(p1);
    s.appendChild(p2);
    el.appendChild(s);
  }

  if (d.agent_1 || d.agent_2) {
    const cols = document.createElement('div'); cols.className = 'ana-cols';
    [['agent_1', a1, 's1'], ['agent_2', a2, 's2']].forEach(([key, name, cls]) => {
      const ag = d[key]; if (!ag) return;
      const card = document.createElement('div'); card.className = `ana-agent-card ${cls}`;
      card.innerHTML = `<div class="ana-agent-title">${name}</div>`;
      if (ag.core_position) { const p = document.createElement('p'); p.className = 'ana-core'; p.textContent = ag.core_position; card.appendChild(p); }
      if (ag.attractors?.length) { const w = document.createElement('div'); ag.attractors.forEach(a => w.appendChild(pill(a))); card.appendChild(w); }
      if (ag.declared_foundations?.length) { const lbl = document.createElement('div'); lbl.className = 'ana-lbl'; lbl.textContent = 'Deklarowane:'; card.appendChild(lbl); card.appendChild(list(ag.declared_foundations)); }
      if (ag.undeclared_foundations?.length) { const lbl = document.createElement('div'); lbl.className = 'ana-lbl muted'; lbl.textContent = 'Milczące:'; card.appendChild(lbl); card.appendChild(list(ag.undeclared_foundations)); }
      cols.appendChild(card);
    });
    el.appendChild(cols);
  }

  if (d.collision_points?.length) {
    const s = sec('Punkty styku i rozbieżności');
    d.collision_points.forEach(cp => {
      const item = document.createElement('div'); item.className = 'ana-cp';
      const refs = (cp.exchange_refs || []).map(n => `<span class="ana-xref">#${n}</span>`).join(' ');
      item.innerHTML = `<div class="ana-cp-head"><strong>${cp.name}</strong><span class="ana-incomm ${cp.incommensurability_type}">${cp.incommensurability_type}</span>${refs}</div><div class="ana-cp-claims"><span class="s1">${cp.agent_1_claim}</span><span class="vs">vs</span><span class="s2">${cp.agent_2_claim}</span></div>`;
      s.appendChild(item);
    });
    el.appendChild(s);
  }

  if (interactionPatterns) {
    const s = sec('Wzorce interakcji');
    const cols = document.createElement('div'); cols.className = 'ana-cols';
    [['agent_1', a1, 's1'], ['agent_2', a2, 's2']].forEach(([key, name, cls]) => {
      const col = document.createElement('div'); col.className = 'ana-attack-col';
      col.innerHTML = `<div class="ana-sub-title ${cls}">${name}</div>`;
      (interactionPatterns[key] || []).forEach(p => {
        const item = document.createElement('div'); item.className = 'ana-attack-item';
        const xrefs = (p.exchanges || []).map(n => `<span class="ana-xref">#${n}</span>`).join(' ');
        item.innerHTML = `<div><em>${p.type}</em> ${xrefs}</div><div class="muted">${p.description}</div>`;
        col.appendChild(item);
      });
      cols.appendChild(col);
    });
    s.appendChild(cols); el.appendChild(s);
  }

  if (positionAsymmetries) {
    const da = positionAsymmetries;
    const s = sec('Asymetrie pozycji');
    const grid = document.createElement('div'); grid.className = 'ana-asym-grid';
    [
      ['Najsłabszy gdy', da.agent_1_weakest_when, da.agent_2_weakest_when],
      ['Najsilniejszy gdy', da.agent_1_strongest_when, da.agent_2_strongest_when]
    ].forEach(([lbl, v1, v2]) => {
      const row = document.createElement('div'); row.className = 'asym-row';
      row.innerHTML = `<div class="asym-lbl">${lbl}</div><div class="asym-cell s1">${v1 || '—'}</div><div class="asym-cell s2">${v2 || '—'}</div>`;
      grid.appendChild(row);
    });
    s.appendChild(grid); el.appendChild(s);
  }

  if (d.translation_failures?.length) {
    const s = sec('Translation failures');
    d.translation_failures.forEach(tf => {
      const item = document.createElement('div'); item.className = 'ana-tf';
      item.innerHTML = `<div><strong>${tf.term}</strong> <span class="ana-xref">#${tf.exchange}</span></div><div class="ana-tf-reads"><span class="s1">${tf.agent_1_reading}</span><span class="vs">≠</span><span class="s2">${tf.agent_2_reading}</span></div><div class="muted">${tf.description}</div>`;
      s.appendChild(item);
    });
    el.appendChild(s);
  }

  if (d.max_tension_exchange) {
    const s = sec(`Moment maksymalnego napięcia lub przełomu <span class="ana-xref">#${d.max_tension_exchange.exchange}</span>`);
    s.classList.add('ana-tension');
    const p = document.createElement('p'); p.textContent = d.max_tension_exchange.why;
    s.appendChild(p); el.appendChild(s);
  }

  if (d.unspoken?.length) {
    const s = sec('Przemilczane'); s.appendChild(list(d.unspoken)); el.appendChild(s);
  }

  if (relationStatus) {
    const s = sec('Status relacji');
    const badge = document.createElement('span'); badge.className = 'ana-spore-type'; badge.textContent = relationStatus.type;
    const p = document.createElement('p'); p.textContent = relationStatus.rationale;
    s.appendChild(badge); s.appendChild(p); el.appendChild(s);
  }

  if (d.trajectory) {
    const tr = d.trajectory;
    const s = sec('Trajektoria');
    const badge = document.createElement('span'); badge.className = 'ana-spore-type'; badge.textContent = tr.convergence || '—';
    const p1 = document.createElement('p'); p1.textContent = tr.depth_progression || '';
    const p2 = document.createElement('p'); p2.className = 'muted'; p2.textContent = tr.exit_proximity || '';
    s.appendChild(badge); s.appendChild(p1); s.appendChild(p2); el.appendChild(s);
  }

  return el;
}
