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
     (fotos do cluster KOMBI em github.com/fatihcesur/bmw-f30-cluster-simhub e o preview v06_fpk_* do próprio
     firmware): velocímetro grande à esquerda (0–260 km/h, ou 0–160 mph no carro americano) com números âmbar ao
     longo do arco; conta-giros à direita com a zona vermelha e DENTRO dele, na base, o mostrador do consumo
     instantâneo (0/10/20 l/100km) com o READY/OFF do start-stop; combustível (0 · 1/2 · 1, com a bomba) como
     mostrador pequeno fora do velocímetro e temperatura do motor (50/100/150, com o bujão) fora do conta-giros;
     o MID embaixo no centro, em duas linhas de LCD: relógio, caixinha da marcha e autonomia em cima e, embaixo
     da régua, temperatura exterior, modo (Comfort/Sport…) e odômetro; setas de
     direção verdes ao lado do MID. Com units=imperial o velocímetro vem em milhas. */
  function analogSvg(variant, units) {
    const imp = units === 'imperial';
    const txt = '#e6ebf2', sub = '#8d96a5';
    const or = '#ff8a3c';                                   // âmbar do painel aceso (o KOMBI também tem tema branco)
    const scrFill = '#0a0e14', scrStroke = '#2c333d';
    const ang = (t, a0, a1, v0, v1) => a0 + (a1 - a0) * (t - v0) / (v1 - v0);
    /* mostrador no estilo do KOMBI: escala âmbar com traço grande retangular por marca, números ao longo do
       arco, ponteiro âmbar fino com cubo; redFrom desenha a zona vermelha (o desenho antigo tinha um aro
       branco inteiro que o painel real não tem) */
    function kombiDial(cx, cy, r, max, labStep, tickStep, redFrom, name) {
      const w = Math.max(5, r * 0.075), gap = r * 0.2, lr = r - gap - 4, degLab = 270 * labStep / max, fs = Math.round(Math.min(r * 0.125, degLab * lr * 0.0349 * 0.62));
      let s = `<circle cx="${cx}" cy="${cy}" r="${f1(r + w + 6)}" fill="#05070b" stroke="#20262f" stroke-width="2"/>`;
      if (redFrom != null) s += `<path d="${arc(cx, cy, r, ang(redFrom, START, -START, 0, max), -START)}" fill="none" stroke="#d6281c" stroke-width="${f1(w)}"/>`;
      for (let v = tickStep; v < max; v += tickStep) {                     /* traço miúdo entre as marcas numeradas */
        if (v % labStep === 0) continue;
        const d = ang(v, START, -START, 0, max);
        const [x0, y0] = pol(cx, cy, r - w, d), [x1, y1] = pol(cx, cy, r + w * 0.45, d);
        s += `<line x1="${f1(x0)}" y1="${f1(y0)}" x2="${f1(x1)}" y2="${f1(y1)}" stroke="${or}" stroke-width="2"/>`;
      }
      for (let v = 0; v <= max; v += labStep) {                            /* marca grande + número (só nos valores da régua, como o painel real) */
        const d = ang(v, START, -START, 0, max);
        const [x0, y0] = pol(cx, cy, r - w, d), [x1, y1] = pol(cx, cy, r + w, d), [x2, y2] = pol(cx, cy, r + w, d + 2.4), [x3, y3] = pol(cx, cy, r - w, d + 2.4);
        s += `<polygon points="${f1(x0)},${f1(y0)} ${f1(x1)},${f1(y1)} ${f1(x2)},${f1(y2)} ${f1(x3)},${f1(y3)}" fill="${or}"/>`;
        const [tx, ty] = pol(cx, cy, lr, d);
        s += `<text x="${f1(tx)}" y="${f1(ty + 5)}" text-anchor="middle" font-size="${fs}" font-weight="600" fill="${or}">${Math.round(v)}</text>`;
      }
      return s + `<g class="needle" data-needle="${name}" data-pivot="${cx} ${cy}"><polygon points="${f1(cx - 2.6)},${f1(cy + 16)} ${f1(cx + 2.6)},${f1(cy + 16)} ${f1(cx + 1.3)},${f1(cy - r + gap + 16)} ${f1(cx - 1.3)},${f1(cy - r + gap + 16)}" fill="${or}"/></g><circle cx="${cx}" cy="${cy}" r="${Math.max(5, Math.round(r * 0.045))}" fill="#0a0e14" stroke="${or}" stroke-width="2"/>`;
    }
    /* mostrador pequeno fora dos mostradores grandes (combustível de um lado, temperatura do outro): aro claro
       fino como o do carro, escala âmbar, ícone embaixo do ponteiro */
    function mini(id, cx, cy, r, ticks, icon) {
      let s = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="#05070b" stroke="#cfd6df" stroke-width="3"/>`;
      for (const [lab, t] of ticks) {
        const d = ang(t, START, -START, 0, 100);
        const [x0, y0] = pol(cx, cy, r - 6, d), [x1, y1] = pol(cx, cy, r - 13, d), [tx, ty] = pol(cx, cy, r - 25, d);
        s += `<line x1="${f1(x0)}" y1="${f1(y0)}" x2="${f1(x1)}" y2="${f1(y1)}" stroke="${or}" stroke-width="3"/>`;
        s += `<text x="${f1(tx)}" y="${f1(ty + 4)}" text-anchor="middle" font-size="12" fill="${or}">${lab}</text>`;
      }
      return s + `<circle cx="${cx}" cy="${cy}" r="4.5" fill="#0a0e14" stroke="${or}" stroke-width="2"/>${icon}<g class="needle" data-needle="${id}" data-pivot="${cx} ${cy}"><polygon points="${f1(cx - 2)},${f1(cy + 12)} ${f1(cx + 2)},${f1(cy + 12)} ${f1(cx + 1)},${f1(cy - r + 16)} ${f1(cx - 1)},${f1(cy - r + 16)}" fill="${or}"/></g>`;
    }
    const fuelIcon = `<g transform="translate(58,292) scale(.36)" fill="${or}"><path d="M4 4h16v22H4zM20 10h5v11h-5M8 10h8"/></g>`;
    const tempIcon = `<g transform="translate(1188,292) scale(.36)" fill="${or}"><path d="M6 4v14a6 6 0 1 0 6 6V4"/></g>`;
    /* consumo instantâneo na base do conta-giros, como no carro: arco de traços 0…20+ com setinha própria, o
       "l/100km" no centro e o READY/OFF do start-stop na ponta esquerda do arco */
    const consMini = (() => {
      const cx = 980, cy = 206, r = 48;
      let s = `<text x="${cx}" y="${f1(cy - 20)}" text-anchor="middle" font-size="10" fill="${or}">l/100km</text>`;
      for (let i = 0; i <= 28; i++) {
        const d = ang(i, 140, 40, 0, 28), big = i % 10 === 0;
        const [x0, y0] = pol(cx, cy, r, d), [x1, y1] = pol(cx, cy, r - (big ? 9 : 5), d);
        s += `<line x1="${f1(x0)}" y1="${f1(y0)}" x2="${f1(x1)}" y2="${f1(y1)}" stroke="${i > 25 ? '#d6281c' : or}" stroke-width="${big ? 3 : 2}"/>`;
        if (i === 0 || i === 10 || i === 20) { const [tx, ty] = pol(cx, cy, r - 18, d); s += `<text x="${f1(tx)}" y="${f1(ty + 4)}" text-anchor="middle" font-size="11" fill="${or}">${i}</text>`; }
      }
      return s + `<circle cx="${cx}" cy="${cy}" r="3.5" fill="#0a0e14" stroke="${or}" stroke-width="1.5"/><g class="needle" data-needle="cons" data-pivot="${cx} ${cy}"><polygon points="${f1(cx - 1.8)},${f1(cy + 7)} ${f1(cx + 1.8)},${f1(cy + 7)} ${f1(cx + 1)},${f1(cy - r + 20)} ${f1(cx - 1)},${f1(cy - r + 20)}" fill="${or}"/></g><path d="${arc(cx, cy, r + 7, 146, 164)}" fill="none" stroke="${or}" stroke-width="2.5"/><text x="886" y="${cy - 2}" text-anchor="end" font-size="10" fill="${or}">READY</text><text x="886" y="${cy + 12}" text-anchor="end" font-size="10" fill="${or}">OFF</text>`;
    })();
    const scr = { x: 440, y: 336, w: 205, h: 96 };
    return `<svg viewBox="0 0 1280 480" xmlns="${SVGNS}" role="img" aria-label="Instrument cluster" class="cl-svg">
    <rect width="1280" height="480" rx="26" fill="#04060a"/>
    <rect x="3" y="3" width="1274" height="474" rx="24" fill="none" stroke="#1a2029" stroke-width="3"/>
    ${mini('fuel', 76, 262, 56, [['0', 0], ['1/2', 50], ['1', 100]], fuelIcon)}
    ${mini('temp', 1204, 262, 56, [['50', 8], ['100', 42], ['150', 92]], tempIcon)}
    ${kombiDial(300, 206, 150, imp ? 160 : 260, 40, 20, null, 'speed')}
    <text x="300" y="252" text-anchor="middle" font-size="14" fill="${or}">${imp ? 'mph' : 'km/h'}</text>
    ${kombiDial(980, 206, 146, 8, 1, 4, 6.4, 'tacho')}
    <text x="980" y="148" text-anchor="middle" font-size="12" fill="${or}">1/min x 1000</text>
    ${consMini}
    <text x="980" y="372" text-anchor="middle" font-size="12" fill="${or}">1/min x 1000</text>
    <g id="cl-tl" fill="#34c58a"><polygon id="cl-tl-l" points="414,372 398,385 414,398" class="tell"/><polygon id="cl-tl-r" points="670,372 686,385 670,398" class="tell"/></g>
    <g id="cl-pills"></g>
    <rect x="${scr.x}" y="${scr.y}" width="${scr.w}" height="${scr.h}" rx="8" fill="${scrFill}" stroke="${scrStroke}" stroke-width="1.5"/>
    <text id="cl-clock" x="${scr.x + 16}" y="${scr.y + 28}" text-anchor="start" font-size="20" font-weight="600" fill="${txt}">--:--</text>
    <rect id="cl-gear-box" x="${scr.x + 96}" y="${scr.y + 7}" width="28" height="24" rx="4" fill="none" stroke="${txt}" stroke-width="1.5"/>
    <text id="cl-gear" x="${scr.x + 110}" y="${scr.y + 25}" text-anchor="middle" font-size="17" font-weight="700" fill="${txt}">P</text>
    <text id="cl-range" x="${scr.x + scr.w - 14}" y="${scr.y + 26}" text-anchor="end" font-size="13" fill="${txt}"></text>
    <line x1="${scr.x + 8}" y1="${scr.y + 54}" x2="${scr.x + scr.w - 8}" y2="${scr.y + 54}" stroke="${or}" stroke-width="1.5"/>
    <text id="cl-out" x="${scr.x + 16}" y="${scr.y + 80}" text-anchor="start" font-size="14" fill="${txt}">--</text>
    <text id="cl-mode" x="${scr.x + 74}" y="${scr.y + 80}" text-anchor="start" font-size="11" font-weight="600" fill="${or}"></text>
    <text id="cl-odo" x="${scr.x + scr.w - 14}" y="${scr.y + 80}" text-anchor="end" font-size="12" fill="${txt}"></text>
    <g id="cl-nav" transform="translate(${scr.x + 26} ${scr.y + 8}) scale(.16)" style="display:none;color:${txt}"></g>
    <text id="cl-nav-t" style="display:none" x="${scr.x + 62}" y="${scr.y + 27}" text-anchor="start" font-size="17" font-weight="700" fill="${txt}"></text>
    <g id="cl-navinfo" style="display:none">
      <text id="cl-nav-src" x="${scr.x + scr.w / 2}" y="${scr.y + 46}" text-anchor="middle" font-size="10" fill="#7fd0ff"></text>
      <text id="cl-nav-street" x="${scr.x + scr.w / 2}" y="${scr.y + 68}" text-anchor="middle" font-size="13" font-weight="600" fill="${txt}"></text>
      <text id="cl-nav-dest" x="${scr.x + scr.w / 2}" y="${scr.y + 86}" text-anchor="middle" font-size="11" fill="${sub}"></text>
    </g>
  </svg>`;
  }
  const clusterSvg = (variant, units) => (variant === 'digital' ? DIGITAL_SVG : analogSvg(variant, units));

  /* HUD de 6,5" do F30, igual às camadas hud_* do próprio firmware (myv_displays/Headup_preview): a velocidade
     vive num painel escuro arredondado embaixo no centro (a "chapa" com topo em arco), o limite de velocidade
     num círculo branco com aro vermelho do lado esquerdo dele, e a navegação por cima: a rota laranja com a seta
     branca da manobra, a pílula escura da distância encostada na seta, a guia de faixas do lado direito (traço com
     uma seta laranja por faixa) e o cartucho azul da origem (A9) no topo. Sem marcha no HUD — o HUD do carro
     não mostra P/R/N/D. Os piscas são os triângulos verdes nas bordas. */
  const HUD_SVG = `<svg viewBox="0 0 800 300" xmlns="${SVGNS}" role="img" aria-label="Head-up display" class="hud-svg">
    <defs><linearGradient id="hud-bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0d1218"/><stop offset="1" stop-color="#010203"/></linearGradient>
    <linearGradient id="hud-panel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a4048"/><stop offset=".08" stop-color="#15181d"/><stop offset="1" stop-color="#05070a"/></linearGradient></defs>
    <rect width="800" height="300" rx="18" fill="url(#hud-bg)"/>
    <path d="M330 300L394 190M470 300L406 190" stroke="#141c26" stroke-width="3" fill="none"/>
    <g id="hud-nav" style="display:none">
      <rect id="hud-sign-bg" x="368" y="34" width="52" height="24" rx="5" fill="#2f6fd0" style="display:none"/><text id="hud-sign" x="394" y="51" text-anchor="middle" font-size="15" font-weight="700" fill="#fff" style="display:none"></text>
      <path id="hud-route" d="M400 196C400 150 400 128 436 106" fill="none" stroke="#ff7a1f" stroke-width="10" stroke-linecap="round" style="display:none"/>
      <g id="hud-arrow" transform="translate(400 168) scale(.62)" style="color:#f2f6fb"></g>
      <g id="hud-dist-pill" style="display:none"><rect x="452" y="128" width="96" height="36" rx="18" fill="#0b0e13" stroke="#e8eef6" stroke-width="1.5"/><text id="hud-dist" x="500" y="153" text-anchor="middle" font-size="22" font-weight="700" fill="#f2f6fb"></text></g>
      <g id="hud-lanes" style="display:none"><line x1="492" y1="244" x2="640" y2="244" stroke="#dfe6ee" stroke-width="2.5"/></g>
    </g>
    <g class="hud-ink">
      <g id="hud-sli" style="display:none"><circle cx="282" cy="186" r="27" fill="#fff"/><circle cx="282" cy="186" r="27" fill="none" stroke="#c4281d" stroke-width="7"/><text id="hud-sli-n" x="282" y="195" text-anchor="middle" font-size="26" font-weight="700" fill="#101318"></text></g>
      <path d="M318 284Q312 226 356 222H444Q488 226 482 284Z" fill="url(#hud-panel)" stroke="#39414c" stroke-width="1.5"/>
      <text id="hud-speed" x="398" y="266" text-anchor="middle" font-size="56" font-weight="700" fill="#f2f6fb">0</text>
      <text class="hud-unit" x="458" y="278" text-anchor="start" font-size="13" fill="#e8eef6" opacity=".85">km/h</text>
      <polygon id="hud-tl-l" points="64,236 30,256 64,276" fill="#34c58a" class="tell"/><polygon id="hud-tl-r" points="736,236 770,256 736,276" fill="#34c58a" class="tell"/>
    </g>
  </svg>`;

  const WARN = {
    belt_driver: ['Cinto', 'red'], belt_passenger: ['Cinto (passageiro)', 'red'], parking_brake: ['Freio de mão', 'red'], door: ['Porta aberta', 'red'], trunk: ['Porta-malas', 'red'], hood: ['Capô', 'red'],
    coolant_hot: ['Motor quente', 'red'], coolant_cold: ['Motor frio', 'info'], fuel_low: ['Combustível', 'amber'], tire_low: ['Pneus', 'amber'], high_beam: ['Farol alto', 'blue'], low_beam: ['Farol baixo', 'green'],
  };
  const PILL_FILL = { red: '#c4281d', amber: '#d89a1c', blue: '#2f7de1', green: '#2aa874', info: '#4a5565' };
  const GEAR = { 0: 'P', 1: 'R', 2: 'N', 3: 'D' };
  const NAVARROW = { left: '↰', right: '↱', uturn: '↩', straight: '↑', roundabout: '⟳', arrive: '⚑' };
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
        const dig = variant === 'digital';
        ws.slice(0, 8).forEach((w, i) => {          // digital: faixa no topo; ponteiros: lâmpadas na base, abaixo do combustível e da temperatura
          const [label, lvl] = WARN[w.id] || [w.id, w.level];
          const x = dig ? 340 + (i % 4) * 150 : 14 + (i % 2) * 154 + (i >= 4 ? 908 : 0), y = dig ? 12 + Math.floor(i / 4) * 36 : 392 + Math.floor(i / 2) * 30, wW = dig ? 140 : 140;
          const r = document.createElementNS(SVGNS, 'rect'); r.setAttribute('x', x); r.setAttribute('y', y); r.setAttribute('width', wW); r.setAttribute('height', 26); r.setAttribute('rx', 7); r.setAttribute('fill', PILL_FILL[lvl] || PILL_FILL.info);
          const t = document.createElementNS(SVGNS, 'text'); t.setAttribute('x', x + wW / 2); t.setAttribute('y', y + 18); t.setAttribute('text-anchor', 'middle'); t.setAttribute('font-size', 14); t.setAttribute('font-weight', 600); t.setAttribute('fill', '#fff');
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
        const setTxt = (id, s) => { const el = $(id); if (el) el.textContent = s; };
        const show = (id, vis) => { const el = $(id); if (el) el.style.display = vis ? '' : 'none'; };
        const imp = analog && units === 'imperial', spdD = imp ? spd * 0.621371 : spd, spdMax = imp ? 160 : 260;
        setNeedle('speed', START + SWEEP * Math.min(spdD, spdMax) / spdMax); setNeedle('tacho', START + SWEEP * Math.min(rpm / 1000, 8) / 8);
        setTxt('cl-speed', Math.round(spd));                                 // só o painel digital tem o número grande
        const gear = GEAR[Math.round(v.gear_position || 0)] || '-', mode = IDE.t(MODE[Math.round(v.driving_mode || 0)] || '');
        setTxt('cl-gear', gear); setTxt('cl-mode', mode);
        const gEl = $('cl-gear'); if (gEl) gEl.setAttribute('fill', gear === 'R' ? '#ff6b5e' : '#fff');
        const t = new Date(); setTxt('cl-clock', String(t.getHours()).padStart(2, '0') + ':' + String(t.getMinutes()).padStart(2, '0'));
        setTxt('cl-out', IDE.fmtNum(units === 'imperial' ? (v.outside_temp || 0) * 9 / 5 + 32 : (v.outside_temp || 0), 0) + ' °' + (units === 'imperial' ? 'F' : 'C'));
        const fp = Math.max(0, Math.min(100, d.fuel_pct || 0)), ct = Math.max(40, Math.min(160, v.coolant_temp || 0));
        if ($('cl-fuel')) {                          // digital: barras retangulares de combustível e temperatura
          const fEl = $('cl-fuel'), tEl = $('cl-temp');
          fEl.setAttribute('width', 160 * fp / 100); fEl.setAttribute('fill', fp < 12 ? '#e5502f' : '#f2b84b');
          tEl.setAttribute('width', 160 * (ct - 40) / 120); tEl.setAttribute('fill', ct >= 115 ? '#e5502f' : '#4aa8ff');
        } else {                                    // ponteiros: combustível e temperatura nos mostradores dos cantos + a setinha do consumo dentro do conta-giros (0…28, como no carro)
          setNeedle('fuel', START + SWEEP * fp / 100);
          setNeedle('temp', START + SWEEP * (ct - 40) / 120);
          const cons = units === 'imperial' ? Math.min(28, 235 / Math.max(0.5, v.fuel_consumption || 235)) : Math.max(0, v.fuel_consumption || 0);
          setNeedle('cons', 140 + (40 - 140) * Math.min(cons, 28) / 28);   // o arco do consumo vai de 140° a 40°
        }
        setTxt('cl-range', dist((d.range_km || 0) * 1000, units));
        setTxt('cl-odo', IDE.fmtNum(units === 'imperial' ? (v.odometer || 0) * 0.621371 : (v.odometer || 0), 0) + (units === 'imperial' ? ' mi' : ' km'));
        // orientação de navegação externa (plugin CarPlay Nav, POST /api/cluster/nav): toma a linha de conteúdo do MID, como o HMI faria no carro
        const nv = d.nav, dig = variant === 'digital';
        ['cl-clock', 'cl-gear', 'cl-gear-box', 'cl-mode', 'cl-range', 'cl-odo', 'cl-out'].forEach((id) => show(id, !nv));
        if (nv) {
          const arriving = nv.maneuver === 'arrive';
          if (dig) {                                                    // Live Cockpit: a navegação ocupa o centro, com a seta grande desenhada
            ['cl-clock', 'cl-gear', 'cl-gear-box', 'cl-mode', 'cl-range', 'cl-odo', 'cl-out'].forEach((id) => show(id, false));
            show('cl-nav', true); show('cl-navinfo', false);
            setTxt('cl-nav-src', nv.provider === 'carplay' ? 'Apple CarPlay' : nv.provider);
            const na = $('cl-nav-arrow'); if (na) na.innerHTML = arrowPath(arriving ? 'straight' : (NAVARROW[nv.maneuver] ? nv.maneuver : 'straight'));
            setTxt('cl-nav-dist', arriving ? '' : dist(nv.dist_m || 0, units));
            setTxt('cl-nav-street', (arriving ? nv.destination : nv.street) || '');
            setTxt('cl-nav-dest', nv.destination ? '→ ' + nv.destination + (nv.remaining_m != null ? '  ·  ' + dist(nv.remaining_m, units) : '') : '');
            setTxt('cl-nav-eta', nv.eta_min != null ? nv.eta_min + ' min' : '');
          } else {                                                      // KOMBI: a manobra entra na linha de conteúdo do MID
            show('cl-nav', true); show('cl-nav-t', true); show('cl-navinfo', true);
            const aa = $('cl-nav'); if (aa) aa.innerHTML = arrowPath(arriving ? 'straight' : (NAVARROW[nv.maneuver] ? nv.maneuver : 'straight'));
            setTxt('cl-nav-t', arriving ? IDE.t('Você chegou') : dist(nv.dist_m || 0, units));
            setTxt('cl-nav-src', nv.provider === 'carplay' ? 'Apple CarPlay' : nv.provider);
            setTxt('cl-nav-street', (arriving ? nv.destination : nv.street) || '');
            setTxt('cl-nav-dest', nv.destination ? '→ ' + nv.destination + (nv.remaining_m != null ? '  ·  ' + dist(nv.remaining_m, units) : '') : '');
          }
        } else {
          show('cl-nav', false); show('cl-nav-t', false); show('cl-navinfo', false);
        }
        const hz = !!v.hazard, tl = hz || !!v.turn_left, tr = hz || !!v.turn_right;
        ['cl-tl-l', 'hud-tl-l'].forEach((id) => { const el = $(id); if (el) el.classList.toggle('on', tl); }); ['cl-tl-r', 'hud-tl-r'].forEach((id) => { const el = $(id); if (el) el.classList.toggle('on', tr); });
        drawPills(d.warnings || []);
        // HUD (a seção já foi ligada/desligada no topo do render, pela codificação do carro)
        if (hasHud) {
          setTxt('hud-speed', units === 'imperial' ? Math.round(spd * 0.621371) : Math.round(spd));
          const hudLbl = box.querySelector('.hud-unit'); if (hudLbl) hudLbl.textContent = speedLabel(units);
          const sl = v.speed_limit || 0;                             // o HUD do carro só mostra o limite quando o SLI tem um valor
          show('hud-sli', sl > 0); if (sl > 0) setTxt('hud-sli-n', sl);
          const g = d.gps, tu = nv ? { dir: nv.maneuver === 'arrive' ? 'straight' : nv.maneuver, dist_m: nv.dist_m || 0, street: nv.street } : (g && g.turn);
          const navOn = !!tu || !!(g && g.route && g.remaining_m != null);
          show('hud-nav', navOn);
          const arrow = $('hud-arrow'), hdist = $('hud-dist');
          if (tu) {
            arrow.innerHTML = arrowPath(tu.dir);
            setTxt('hud-dist', dist(tu.dist_m, units)); show('hud-dist-pill', true);
            if (nv && nv.street) { const sEl = $('hud-sign'), bEl = $('hud-sign-bg'), txtS = nv.street.length > 7 ? nv.street.slice(0, 6) + '…' : nv.street; sEl.textContent = txtS; bEl.setAttribute('width', 14 * txtS.length + 16); sEl.setAttribute('x', 394); bEl.setAttribute('x', 394 - (7 * txtS.length + 8)); show('hud-sign', true); show('hud-sign-bg', true); }
            else { show('hud-sign', false); show('hud-sign-bg', false); }
          } else if (g && g.route && g.remaining_m != null) {
            arrow.innerHTML = ''; setTxt('hud-dist', dist(g.remaining_m, units)); show('hud-dist-pill', true); show('hud-sign', false); show('hud-sign-bg', false);
          } else { arrow.innerHTML = ''; show('hud-dist-pill', false); }
          show('hud-route', navOn); show('hud-lanes', navOn);
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
