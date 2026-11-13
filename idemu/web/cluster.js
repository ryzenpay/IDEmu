'use strict';
/* IDEmu – aba "Cluster e HUD" (iDrive 5/6): painel de instrumentos e HUD desenhados com os sinais do CAN virtual, o GPS virtual e o que o HMI manda
   ao Kombi e ao HUD por MOST (GET /api/cluster, idemu/cluster.py). */
(function (IDE) {
  const { h, ic, api } = IDE;
  const SVGNS = 'http://www.w3.org/2000/svg';

  /* ---- geometria ---- */
  const SWEEP = 270, START = -135;                            // ângulo em graus, no sentido horário a partir do topo
  const pol = (cx, cy, r, deg) => { const a = (deg - 90) * Math.PI / 180; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
  const f1 = (n) => Math.round(n * 10) / 10;
  function arc(cx, cy, r, d0, d1) {
    const [x0, y0] = pol(cx, cy, r, d0), [x1, y1] = pol(cx, cy, r, d1);
    return ['M', f1(x0), ' ', f1(y0), 'A', r, ' ', r, ' 0 ', d1 - d0 > 180 ? 1 : 0, ' 1 ', f1(x1), ' ', f1(y1)].join('');
  }
  function dial(cx, cy, r, max, major, minorPer, labelFn, redFrom, col, name) {
    let s = `<circle cx="${cx}" cy="${cy}" r="${r + 14}" fill="#05070b" stroke="#2a313d" stroke-width="3"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#1b212b" stroke-width="2"/>`;
    if (redFrom != null) s += `<path d="${arc(cx, cy, r - 6, START + SWEEP * redFrom / max, START + SWEEP)}" fill="none" stroke="#d6281c" stroke-width="10"/>`;
    const n = Math.round(max / major) * minorPer;
    for (let i = 0; i <= n; i++) {
      const v = i * major / minorPer, d = START + SWEEP * v / max, big = i % minorPer === 0;
      const [x0, y0] = pol(cx, cy, r - (big ? 24 : 14), d), [x1, y1] = pol(cx, cy, r - 2, d);
      s += `<line x1="${f1(x0)}" y1="${f1(y0)}" x2="${f1(x1)}" y2="${f1(y1)}" stroke="${big ? '#f2f4f7' : '#8d96a5'}" stroke-width="${big ? 4 : 2}"/>`;
      if (big) { const [tx, ty] = pol(cx, cy, r - 50, d); s += `<text x="${f1(tx)}" y="${f1(ty + 9)}" text-anchor="middle" font-size="26" font-weight="600" fill="${col || '#e8ebf0'}">${labelFn(v)}</text>`; }
    }
    return s + `<g class="needle" data-needle="${name || cx}" data-pivot="${cx} ${cy}"><polygon points="${cx - 5},${cy + 28} ${cx + 5},${cy + 28} ${cx + 2},${cy - r + 8} ${cx - 2},${cy - r + 8}" fill="#ff5a1f"/></g><circle cx="${cx}" cy="${cy}" r="14" fill="#11151c" stroke="#ff5a1f" stroke-width="3"/>`;
  }
  const arrowPath = (kind) => ({
    left: '<path d="M0 64V0Q0 -30 -34 -30H-44" fill="none" stroke="currentColor" stroke-width="22" stroke-linecap="butt"/><polygon points="-40,-62 -86,-30 -40,2" fill="currentColor"/>',
    right: '<path d="M0 64V0Q0 -30 34 -30H44" fill="none" stroke="currentColor" stroke-width="22" stroke-linecap="butt"/><polygon points="40,-62 86,-30 40,2" fill="currentColor"/>',
    uturn: '<path d="M34 64V-12Q34 -52 0 -52Q-34 -52 -34 -12V20" fill="none" stroke="currentColor" stroke-width="22"/><polygon points="-62,16 -6,16 -34,64" fill="currentColor"/>',
    straight: '<path d="M0 64V-22" fill="none" stroke="currentColor" stroke-width="22"/><polygon points="-40,-18 40,-18 0,-70" fill="currentColor"/>',
  }[kind] || '');

  const DIGITAL_SVG = `<svg viewBox="0 0 1280 480" xmlns="${SVGNS}" role="img" aria-label="Instrument cluster" class="cl-svg">
    <rect width="1280" height="480" rx="26" fill="#020306"/>
    <rect x="3" y="3" width="1274" height="474" rx="24" fill="none" stroke="#202732" stroke-width="3"/>
    ${dial(325, 275, 185, 260, 20, 2, (v) => v, null, null, 'speed')}
    ${dial(955, 275, 185, 8, 1, 2, (v) => v, 6.5, null, 'tacho')}
    <text x="325" y="446" text-anchor="middle" font-size="19" fill="#8d96a5">km/h</text>
    <text x="955" y="446" text-anchor="middle" font-size="17" fill="#8d96a5">x1000 min⁻¹</text>
    <text id="cl-speed" x="325" y="412" text-anchor="middle" font-size="64" font-weight="700" fill="#fff">0</text>
    <g id="cl-tl" fill="#34c58a"><polygon id="cl-tl-l" points="60,52 28,76 60,100" class="tell"/><polygon id="cl-tl-r" points="1220,52 1252,76 1220,100" class="tell"/></g>
    <g id="cl-pills"></g>
    <text id="cl-clock" x="640" y="130" text-anchor="middle" font-size="40" font-weight="600" fill="#f2f4f7">--:--</text>
    <text id="cl-out" x="640" y="160" text-anchor="middle" font-size="22" fill="#8d96a5">--</text>
    <text id="cl-gear" x="640" y="268" text-anchor="middle" font-size="110" font-weight="700" fill="#fff">P</text>
    <text id="cl-mode" x="640" y="304" text-anchor="middle" font-size="22" fill="#ff8a4d"></text>
    <rect x="560" y="330" width="160" height="12" rx="6" fill="#161b24"/><rect id="cl-fuel" x="560" y="330" width="80" height="12" rx="6" fill="#f2b84b"/>
    <path d="M530 331h10v14h-10zM540 335l5 3v7" fill="none" stroke="#8d96a5" stroke-width="2"/>
    <rect x="560" y="356" width="160" height="12" rx="6" fill="#161b24"/><rect id="cl-temp" x="560" y="356" width="80" height="12" rx="6" fill="#4aa8ff"/>
    <path d="M532 372v-14M537 372v-14" stroke="#8d96a5" stroke-width="2" fill="none"/><circle cx="534.5" cy="373" r="4" fill="#8d96a5"/>
    <text id="cl-range" x="640" y="410" text-anchor="middle" font-size="22" fill="#e8ebf0"></text>
    <text id="cl-odo" x="640" y="444" text-anchor="middle" font-size="22" fill="#8d96a5"></text>
    <g id="cl-nav" style="display:none">
      <text id="cl-nav-src" x="640" y="188" text-anchor="middle" font-size="17" font-weight="600" fill="#ff8a4d"></text>
      <g id="cl-nav-arrow" transform="translate(566 236) scale(0.42)" style="color:#fff"></g>
      <text id="cl-nav-dist" x="604" y="256" text-anchor="start" font-size="54" font-weight="700" fill="#fff"></text>
      <text id="cl-nav-street" x="640" y="316" text-anchor="middle" font-size="32" font-weight="600" fill="#e8ebf0"></text>
      <text id="cl-nav-dest" x="640" y="412" text-anchor="middle" font-size="20" fill="#e8ebf0"></text>
      <text id="cl-nav-eta" x="640" y="440" text-anchor="middle" font-size="19" fill="#8d96a5"></text>
    </g>
  </svg>`;

  /* painel de ponteiros do F30 (o 'digital' acima é o Live Cockpit Professional), desenhado como o painel real
     (foto BimmerToday do 320d pré-LCI): dois mostradores grandes com aro branco e números laranja — velocímetro
     à esquerda (0–260 km/h, ou 0–160 mph no carro americano), conta-giros à direita com o '1/min x 1000' e o
     READY/OFF; MINI-MOSTRADORES redondos por fora embaixo: combustível (0 · 1/2 · 1, com a bomba) à esquerda e
     temperatura do arrefecimento (50/100/150, com o bulbo) à direita; a tela de informações BAIXA e larga entre
     os mostradores (temperatura exterior e relógio) com a FITA DO ODOMETRO ainda mais abaixo; e a barra de
     consumo segmentada (a "barra de mpg") no pé do conta-giros, com a marcha e o modo ao lado, como o 'S5
     SPORT+' da foto. Com units=imperial o velocímetro vem em milhas. */
  function analogSvg(variant, units) {
    const lo = variant === 'analog', imp = units === 'imperial';
    const scrFill = '#0c1016', scrStroke = '#39404c', txt = lo ? '#e6ebf2' : '#f2f4f7', sub = '#8d96a5';
    const or = '#ff6a2a';                                   // laranja dos números e das escalas
    const ang = (t, a0, a1, v0, v1) => a0 + (a1 - a0) * (t - v0) / (v1 - v0);
    const tickSvgs = (gx, ticks) => ticks.map((tk) => { const p = pol(gx, 330, 56, ang(tk[1], START, -START, 0, 100)); return '<text x="' + f1(p[0]) + '" y="' + f1(p[1] + 4) + '" text-anchor="middle" font-size="13" fill="' + or + '">' + tk[0] + '</text>'; }).join('');
    const mini = (id, gx, ticks, red, icon) => `
    <circle cx="${gx}" cy="330" r="66" fill="#05070b" stroke="#dfe5ec" stroke-width="4"/>
    <path d="${arc(gx, 330, 42, START, -START)}" fill="none" stroke="#39404c" stroke-width="3"/>
    ${red || ''}${tickSvgs(gx, ticks)}
    ${icon}
    <g class="needle" data-needle="${id}" data-pivot="${gx} 330"><polygon points="${f1(gx - 2.5)},342 ${f1(gx + 2.5)},342 ${f1(gx + 1)},290 ${f1(gx - 1)},290" fill="#ff5a1f"/></g>
    <circle cx="${gx}" cy="330" r="6" fill="#11151c" stroke="#ff5a1f" stroke-width="2"/>`;
    const fuelTicks = [['0', 0], ['1/2', 50], ['1', 100]];
    const tempTicks = [['50', 8], ['100', 42], ['150', 92]];
    const tempRed = `<path d="${arc(1172, 330, 42, ang(115, START, -START, 40, 160), -START)}" fill="none" stroke="#d6281c" stroke-width="4"/>`;
    const fuelIcon = `<g transform="translate(99,300) scale(.42)" fill="none" stroke="${or}" stroke-width="6"><path d="M4 4h16v22H4zM20 10h5v11h-5M8 10h8"/></g>`;
    const tempIcon = `<g transform="translate(1163,299) scale(.42)" fill="none" stroke="${or}" stroke-width="6"><path d="M6 4v14a6 6 0 1 0 6 6V4"/></g>`;
    const segBar = `<g id="cl-mpg">` + Array.from({ length: 12 }, (_, i) => `<rect x="${832 + i * 9}" y="362" width="6" height="8" rx="2" fill="#1b212b"/>`).join('') + '</g>';
    const screen = lo ? { x: 460, y: 255, w: 360, h: 135 } : { x: 455, y: 130, w: 370, h: 300 };
    return `<svg viewBox="0 0 1280 480" xmlns="${SVGNS}" role="img" aria-label="Instrument cluster" class="cl-svg">
    <rect width="1280" height="480" rx="26" fill="#05070b"/>
    <rect x="3" y="3" width="1274" height="474" rx="24" fill="none" stroke="#202732" stroke-width="3"/>
    <rect x="${screen.x}" y="${screen.y}" width="${screen.w}" height="${screen.h}" rx="8" fill="${scrFill}" stroke="${scrStroke}" stroke-width="2"/>
    <rect x="545" y="404" width="190" height="38" rx="6" fill="${scrFill}"/>
    <text x="595" y="420" text-anchor="middle" font-size="12" fill="${sub}">${imp ? 'mi' : 'km'}</text>
    <text id="cl-odo" x="640" y="438" text-anchor="middle" font-size="${lo ? 17 : 19}" fill="${txt}"></text>
    ${dial(360, 225, 168, imp ? 160 : 260, 20, 2, (v) => v, null, or, 'speed')}
    <circle cx="360" cy="225" r="181" fill="none" stroke="#dfe5ec" stroke-width="5" opacity=".85"/>
    ${dial(920, 225, 168, 8, 1, 2, (v) => v, 6.4, or, 'tacho')}
    <circle cx="920" cy="225" r="181" fill="none" stroke="#dfe5ec" stroke-width="5" opacity=".85"/>
    <text x="360" y="168" text-anchor="middle" font-size="16" fill="${or}">${imp ? 'mph' : 'km/h'}</text>
    <text x="920" y="150" text-anchor="middle" font-size="14" fill="${or}">1/min x 1000</text>
    <text x="872" y="258" text-anchor="middle" font-size="13" fill="#dfe5ec">READY</text>
    <text x="872" y="278" text-anchor="middle" font-size="11" fill="#dfe5ec">OFF</text>
    ${segBar}
    <text id="cl-gear" x="${lo ? 975 : screen.x + screen.w / 2}" y="${lo ? 372 : 296}" text-anchor="middle" font-size="${lo ? 20 : 66}" font-weight="700" fill="#eef2f7">P</text>
    <text id="cl-mode" x="${lo ? 975 : screen.x + screen.w / 2}" y="${lo ? 394 : 326}" text-anchor="middle" font-size="${lo ? 12 : 20}" fill="${or}"></text>
    <text x="858" y="416" font-size="11" fill="#2aa8a0" transform="rotate(-16 858 416)">EfficientDynamics</text>
    ${mini('fuel', 108, fuelTicks, '', fuelIcon)}
    ${mini('temp', 1172, tempTicks, tempRed, tempIcon)}
    <g id="cl-tl" fill="#34c58a"><polygon id="cl-tl-l" points="60,52 28,76 60,100" class="tell"/><polygon id="cl-tl-r" points="1220,52 1252,76 1220,100" class="tell"/></g>
    <g id="cl-pills"></g>
    <text id="cl-clock" x="640" y="${lo ? 330 : 172}" text-anchor="middle" font-size="${lo ? 24 : 34}" font-weight="600" fill="${txt}">--:--</text>
    <text id="cl-out" x="640" y="${lo ? 300 : 204}" text-anchor="middle" font-size="${lo ? 24 : 26}" fill="${txt}">--</text>
    <text id="cl-range" x="640" y="${lo ? 358 : 356}" text-anchor="middle" font-size="${lo ? 14 : 20}" fill="${txt}"></text>
    <g id="cl-nav" style="display:none">
      <text id="cl-nav-src" x="640" y="${lo ? 273 : 160}" text-anchor="middle" font-size="13" fill="#7fd0ff"></text>
      <g id="cl-nav-arrow" transform="translate(570 ${lo ? 318 : 250}) scale(${lo ? 0.4 : 0.5})" style="color:${txt}"></g>
      <text id="cl-nav-dist" x="670" y="${lo ? 326 : 258}" text-anchor="middle" font-size="${lo ? 26 : 40}" font-weight="700" fill="${txt}"></text>
      <text id="cl-nav-street" x="640" y="${lo ? 352 : 310}" text-anchor="middle" font-size="${lo ? 14 : 20}" fill="${txt}"></text>
      <text id="cl-nav-dest" x="640" y="${lo ? 368 : 336}" text-anchor="middle" font-size="13" fill="${sub}"></text>
      <text id="cl-nav-eta" x="640" y="${lo ? 382 : 360}" text-anchor="middle" font-size="13" fill="${sub}"></text>
    </g>
  </svg>`;
  }
  const clusterSvg = (variant, units) => (variant === 'digital' ? DIGITAL_SVG : analogSvg(variant, units));

  const HUD_SVG = `<svg viewBox="0 0 800 300" xmlns="${SVGNS}" role="img" aria-label="Head-up display" class="hud-svg">
    <defs><linearGradient id="hud-bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0d1218"/><stop offset="1" stop-color="#010203"/></linearGradient></defs>
    <rect width="800" height="300" rx="18" fill="url(#hud-bg)"/>
    <path d="M300 300L388 150M500 300L412 150" stroke="#16202b" stroke-width="3" fill="none"/><path d="M400 300V150" stroke="#16202b" stroke-width="2" stroke-dasharray="14 18" fill="none"/>
    <g class="hud-ink">
      <text id="hud-speed" x="190" y="170" text-anchor="middle" font-size="140" font-weight="700" fill="#a6ffd0">0</text>
      <text class="hud-unit" x="190" y="214" text-anchor="middle" font-size="26" fill="#a6ffd0" opacity=".75">km/h</text>
      <g id="hud-arrow" transform="translate(470 126)" style="color:#a6ffd0"></g>
      <text id="hud-dist" x="470" y="262" text-anchor="middle" font-size="36" font-weight="600" fill="#a6ffd0"></text>
      <text id="hud-gear" x="690" y="130" text-anchor="middle" font-size="84" font-weight="700" fill="#a6ffd0">P</text>
      <polygon id="hud-tl-l" points="640,205 612,225 640,245" fill="#a6ffd0" class="tell"/><polygon id="hud-tl-r" points="740,205 768,225 740,245" fill="#a6ffd0" class="tell"/>
    </g>
  </svg>`;

  const WARN = {
    belt_driver: ['Cinto', 'red'], belt_passenger: ['Cinto (passageiro)', 'red'], parking_brake: ['Freio de mão', 'red'], door: ['Porta aberta', 'red'], trunk: ['Porta-malas', 'red'], hood: ['Capô', 'red'],
    coolant_hot: ['Motor quente', 'red'], coolant_cold: ['Motor frio', 'info'], fuel_low: ['Combustível', 'amber'], tire_low: ['Pneus', 'amber'], high_beam: ['Farol alto', 'blue'], low_beam: ['Farol baixo', 'green'],
  };
  const PILL_FILL = { red: '#c4281d', amber: '#d89a1c', blue: '#2f7de1', green: '#2aa874', info: '#4a5565' };
  const GEAR = { 0: 'P', 1: 'R', 2: 'N', 3: 'D' };
  const MODE = { 0: 'Comfort', 1: 'Sport', 2: 'Eco Pro', 3: 'Sport+' };
  const km = (m) => (m >= 1000 ? IDE.fmtNum(m / 1000, m >= 10000 ? 0 : 1) + ' km' : Math.round(m / 10) * 10 + ' m');
  const dist = (m, units) => (units === 'imperial' ? IDE.fmtNum(m * 0.000621371, m >= 1600 ? 1 : 2) + ' mi' : km(m));
  const speedLabel = (units) => (units === 'imperial' ? 'mph' : 'km/h');

  IDE.tabDefs.cluster = {
    mount(host, ctx) {
      let stop = null, pillKey = '', last = null, variant = 'digital', unitsCur = '', errs = 0;
      const clWrap = h('div', { class: 'cl-wrap' }), hudWrap = h('div', { class: 'cl-wrap hud' });
      clWrap.innerHTML = DIGITAL_SVG; hudWrap.innerHTML = HUD_SVG;
      hudWrap.style.display = 'none';    // o HUD só aparece quando a codificação do carro diz que ele existe (render liga)
      const note = h('div', { class: 'note warn hidden' }, ic('alert', 16), h('span', { class: 'cl-note' }));
      const fsBtn = (el, label) => h('button', { class: 'btn sm', type: 'button', onclick: () => { try { el.requestFullscreen(); } catch (e) { /* sem tela cheia */ } } }, ic('expand', 14), label);
      const huList = h('pre', { class: 'logbox cl-hu' });
      const huSum = h('summary', null, 'Mensagens do HMI para o cluster e o HUD');
      const hudHead = h('div', { class: 'cl-head hud-head' }, h('b', null, 'HUD'), fsBtn(hudWrap, 'Tela cheia'));
      hudHead.style.display = 'none';    // idem: o render mostra quando o carro tem o opcional
      const box = h('div', { class: 'cluster' },
        h('p', { class: 'help' }, 'O cluster e o HUD mostram o carro virtual: velocidade, rotação, câmbio, luzes e alertas vêm do CAN; a posição vem do GPS. Mude os sinais na aba CAN e veja o painel reagir. A próxima curva é calculada pela rota do GPS virtual: o iDrive emulado não tem motor de navegação, então o HMI não manda manobras ao cluster. Quando um provedor externo publica orientação (o plugin CarPlay Nav), o centro do painel mostra a manobra, a rua e o destino.'),
        note,
        h('div', { class: 'cl-head' }, h('b', null, 'Cluster (Kombi)'), fsBtn(clWrap, 'Tela cheia')), clWrap,
        hudHead, hudWrap,
        h('details', { class: 'cl-det' }, huSum, huList));
      IDE.add(host, box);
      const $ = (id) => box.querySelector('#' + id);
      const needles = {};
      box.querySelectorAll('[data-needle]').forEach((g) => { needles[g.dataset.needle] = g; });
      const setNeedle = (key, deg) => { const g = needles[key]; if (!g) return; const p = (g.dataset.pivot || (g.dataset.needle + ' 275')).split(' '); g.setAttribute('transform', ['rotate(', f1(deg), ' ', p[0], ' ', p[1], ')'].join('')); };

      function drawPills(ws) {
        const key = ws.map((w) => w.id).join(',');
        if (key === pillKey) return;
        pillKey = key;
        const g = $('cl-pills'); g.textContent = '';
        const an = variant !== 'digital';
        ws.slice(0, 8).forEach((w, i) => {
          const [label, lvl] = WARN[w.id] || [w.id, w.level], an2 = an && variant === 'analog', x = an ? (an2 ? 480 : 465) + (i % 2) * (an2 ? 160 : 178) : 340 + (i % 4) * 150, y = (an ? (an2 ? 262 : 150) : 12) + (an ? Math.floor(i / 2) : Math.floor(i / 4)) * (an ? 30 : 36), wW = an ? (an2 ? 150 : 170) : 140;
          const r = document.createElementNS(SVGNS, 'rect'); r.setAttribute('x', x); r.setAttribute('y', y); r.setAttribute('width', wW); r.setAttribute('height', 28); r.setAttribute('rx', 8); r.setAttribute('fill', PILL_FILL[lvl] || PILL_FILL.info);
          const t = document.createElementNS(SVGNS, 'text'); t.setAttribute('x', x + wW / 2); t.setAttribute('y', y + 20); t.setAttribute('text-anchor', 'middle'); t.setAttribute('font-size', 16); t.setAttribute('font-weight', 600); t.setAttribute('fill', '#fff');
          t.textContent = IDE.t(label); g.appendChild(r); g.appendChild(t);
        });
      }
      function render(d) {
        const v = d.signals || {}, on = (v.terminal_state || 0) >= 65, spd = Math.max(0, v.vehicle_speed || 0), rpm = Math.max(0, v.engine_rpm || 0);
        const ci = d.cluster || {}, units = ci.units || 'metric', analog = ci.cluster && ci.cluster !== 'digital';
        const hasHud = ci.hud !== false;    // (logo no início: uma falha mais abaixo jamais deixaria o HUD de um carro sem HUD na tela)
        hudHead.style.display = hasHud ? '' : 'none'; hudWrap.style.display = hasHud ? '' : 'none';
        if (ci.cluster && (ci.cluster !== variant || units !== unitsCur)) {   // outro carro (painel ou unidades): trocar a desenharia e redesenhar
          variant = ci.cluster; unitsCur = units; clWrap.innerHTML = clusterSvg(variant, units);
          for (const k of Object.keys(needles)) delete needles[k];
          box.querySelectorAll('[data-needle]').forEach((g) => { needles[g.dataset.needle] = g; });
          pillKey = '\0'; last = d; return render(d);
        }
        const imp = analog && units === 'imperial', spdD = imp ? spd * 0.621371 : spd, spdMax = imp ? 160 : 260;
        setNeedle('speed', START + SWEEP * Math.min(spdD, spdMax) / spdMax); setNeedle('tacho', START + SWEEP * Math.min(rpm / 1000, 8) / 8);
        const spEl = $('cl-speed'); if (spEl) spEl.textContent = Math.round(spd);   // só o painel digital tem o número grande
        const gear = GEAR[Math.round(v.gear_position || 0)] || '-', mode = IDE.t(MODE[Math.round(v.driving_mode || 0)] || '');
        $('cl-gear').textContent = gear; $('cl-mode').textContent = mode;
        $('cl-gear').setAttribute('fill', gear === 'R' ? '#ff6b5e' : '#fff');
        const t = new Date(); $('cl-clock').textContent = String(t.getHours()).padStart(2, '0') + ':' + String(t.getMinutes()).padStart(2, '0');
        $('cl-out').textContent = IDE.fmtNum(units === 'imperial' ? (v.outside_temp || 0) * 9 / 5 + 32 : (v.outside_temp || 0), 0) + ' °' + (units === 'imperial' ? 'F' : 'C');
        const fp = Math.max(0, Math.min(100, d.fuel_pct || 0)), ct = Math.max(40, Math.min(160, v.coolant_temp || 0));
        if ($('cl-fuel')) {                          // digital: barras retangulares de combustível e temperatura
          const fEl = $('cl-fuel'), tEl = $('cl-temp');
          fEl.setAttribute('width', 160 * fp / 100); fEl.setAttribute('fill', fp < 12 ? '#e5502f' : '#f2b84b');
          tEl.setAttribute('width', 160 * (ct - 40) / 120); tEl.setAttribute('fill', ct >= 115 ? '#e5502f' : '#4aa8ff');
        } else {                                    // ponteiros: ponteiros dos mini-mostradores + a barra de consumo no pé do conta-giros (a "barra de mpg")
          setNeedle('fuel', START + SWEEP * fp / 100);
          setNeedle('temp', START + SWEEP * (ct - 40) / 120);
          const cons = Math.max(0, v.fuel_consumption || 0);   // l/100 km; nos EUA a barra enche com a eficiência (mpg), como no carro
          const frac = units === 'imperial' ? Math.min(1, (cons > 0.5 ? 235 / cons : 60) / 60) : Math.min(1, cons / 20);
          const segs = box.querySelectorAll('#cl-mpg rect'), lit = Math.round(frac * segs.length);
          segs.forEach((s, i) => s.setAttribute('fill', i < lit ? (frac > 0.8 ? '#e5502f' : '#ff7a33') : '#1b212b'));
        }
        $('cl-range').textContent = dist((d.range_km || 0) * 1000, units);
        $('cl-odo').textContent = IDE.fmtNum(units === 'imperial' ? (v.odometer || 0) * 0.621371 : (v.odometer || 0), 0) + (units === 'imperial' ? ' mi' : ' km');
        // orientação de navegação externa (plugin CarPlay Nav, POST /api/cluster/nav): toma o centro do painel, como o HMI faria no carro
        const nv = d.nav;
        ['cl-gear', 'cl-mode', 'cl-range', 'cl-odo'].forEach((id) => { $(id).style.display = nv ? 'none' : ''; });
        $('cl-nav').style.display = nv ? '' : 'none';
        if (nv) {
          const arriving = nv.maneuver === 'arrive';
          $('cl-nav-src').textContent = nv.provider === 'carplay' ? 'Apple CarPlay' : nv.provider;
          $('cl-nav-arrow').innerHTML = arrowPath(arriving ? 'straight' : nv.maneuver);
          $('cl-nav-dist').textContent = arriving ? '' : dist(nv.dist_m || 0, units);
          $('cl-nav-street').textContent = (arriving ? nv.destination : nv.street) || '';
          $('cl-nav-dest').textContent = nv.destination ? '→ ' + nv.destination : '';
          $('cl-nav-eta').textContent = nv.remaining_m != null ? dist(nv.remaining_m, units) + (nv.eta_min != null ? ' · ' + nv.eta_min + ' min' : '') : '';
        }
        const hz = !!v.hazard, tl = hz || !!v.turn_left, tr = hz || !!v.turn_right;
        ['cl-tl-l', 'hud-tl-l'].forEach((id) => $(id).classList.toggle('on', tl)); ['cl-tl-r', 'hud-tl-r'].forEach((id) => $(id).classList.toggle('on', tr));
        drawPills(d.warnings || []);
        // HUD (a seção já foi ligada/desligada no topo do render, pela codificação do carro)
        if (hasHud) {
          $('hud-speed').textContent = units === 'imperial' ? Math.round(spd * 0.621371) : Math.round(spd); $('hud-gear').textContent = gear;
          const hudLbl = box.querySelector('.hud-unit'); if (hudLbl) hudLbl.textContent = speedLabel(units);
          const g = d.gps, tu = nv ? { dir: nv.maneuver === 'arrive' ? 'straight' : nv.maneuver, dist_m: nv.dist_m || 0 } : (g && g.turn), arrow = $('hud-arrow'), hdist = $('hud-dist');
          if (tu) { arrow.innerHTML = arrowPath(tu.dir); hdist.textContent = dist(tu.dist_m, units); }
          else if (g && g.route && g.remaining_m != null) { arrow.innerHTML = arrowPath('straight'); hdist.textContent = dist(g.remaining_m, units); }
          else { arrow.innerHTML = ''; hdist.textContent = ''; }
        }
        const hu = d.hu || [];
        huList.textContent = hu.length ? hu.map((m) => m.dev + ' ' + m.name + '  op=' + m.op + '  x' + m.n + '  ' + IDE.t('há {s} s', { s: m.age }) + '  ' + m.hex).join('\n') : IDE.t('O HMI ainda não mandou nada ao cluster nem ao HUD.');
        huSum.textContent = IDE.t('Mensagens do HMI para o cluster e o HUD') + ' (' + hu.length + ')';
      }
      async function load() {
        if (ctx && ctx.booted && !ctx.booted()) {   // sem ambiente rodando: não martelar a API — o 409 a cada 200 ms alagava o console de erros de rede
          note.classList.remove('hidden'); note.querySelector('.cl-note').textContent = IDE.t('Nenhum ambiente em execução: inicie um carro para ver o cluster e o HUD.');
          return;
        }
        try { last = await api('/api/cluster'); errs = 0; note.classList.add('hidden'); render(last); }
        catch (e) { errs = 1; note.classList.remove('hidden'); note.querySelector('.cl-note').textContent = IDE.t(e.message); }
      }
      return { show() { stop = IDE.loop(load, () => (ctx && ctx.booted && !ctx.booted() ? 1000 : errs ? 800 : 200)); }, hide() { if (stop) stop(); stop = null; }, destroy() { if (stop) stop(); } };
    },
  };
})(window.IDE);
