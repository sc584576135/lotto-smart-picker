/* ============================================================
 * app.js — 主逻辑（普通 / 复式 / 胆拖 三模式）
 * ============================================================ */
'use strict';

(function () {

  // ---------- 注数档位 ----------
  const TICKET_OPTIONS = [
    { n: 1 }, { n: 2 }, { n: 3 }, { n: 5 }, { n: 8 }, { n: 10 },
    { n: 15 }, { n: 17 }, { n: 20 }, { n: 25 }, { n: 30 },
    { n: 34, tag: '高覆盖' }, { n: 40 }, { n: 50 }
  ];
  const DEFAULT_TICKETS = 10;
  const PRICE = 2;

  // 实测覆盖率对照（JS 引擎蒙特卡洛，每档 40000 次模拟 × 5 次重复取均值）
  const MEASURED = { 1: 6.7, 2: 13.2, 3: 19.5, 5: 31.9, 8: 46.0, 10: 55.3,
                     15: 69.1, 17: 74.6, 20: 78.7, 25: 85.8, 30: 89.8,
                     34: 92.6, 40: 95.2, 50: 97.5 };

  let state = {
    tickets: DEFAULT_TICKETS,
    result: null,
    mode: 'normal',
    tierOpt: true,
    pairOpt: true,
    optOpt: true,
    zones: new Set()
  };

  // ---------- DOM ----------
  const $ = id => document.getElementById(id);
  const toastEl = $('toast');
  let toastTimer = null;

  function toast(msg, isErr) {
    toastEl.textContent = msg;
    toastEl.className = 'toast show' + (isErr ? ' err' : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.className = 'toast' + (isErr ? ' err' : ''); }, 2800);
  }

  // ---------- 组合数 ----------
  function comb(n, k) {
    if (k < 0 || k > n) return 0;
    if (k === 0 || k === n) return 1;
    k = Math.min(k, n - k);
    let r = 1;
    for (let i = 1; i <= k; i++) r = r * (n - k + i) / i;
    return Math.round(r);
  }

  // ---------- 覆盖率 ----------
  function theoPct(n) { return (1 - Math.pow(1 - LOTTO.P_SINGLE_WIN, n)) * 100; }

  function measuredPct(n) {
    if (MEASURED[n] !== undefined) return MEASURED[n];
    const keys = Object.keys(MEASURED).map(Number).sort((a, b) => a - b);
    let lo = keys[0], hi = keys[keys.length - 1];
    for (const k of keys) { if (k <= n) lo = k; if (k >= n) { hi = k; break; } }
    if (lo === hi) return MEASURED[lo];
    return MEASURED[lo] + (MEASURED[hi] - MEASURED[lo]) * (n - lo) / (hi - lo);
  }

  // 一注中「命中 f 个前区、b 个后区」是否中奖（与 PRIZE_RULES 完全一致）
  function winByHits(f, b) {
    return Object.prototype.hasOwnProperty.call(LOTTO.PRIZE_RULES, f + ',' + b);
  }

  // 精确覆盖率：复式 = 前区 F 选 5 × 后区 B 选 2 的矩形结构。
  // 开奖命中数服从超几何分布，最大可命中 min(X,5) / min(Y,2)，可直接求和。
  function exactFuPct(F, B) {
    const TOT = comb(35, 5);
    const TOTB = comb(12, 2);
    const px = [];
    for (let k = 0; k <= 5; k++) px[k] = comb(F, k) * comb(35 - F, 5 - k) / TOT;
    const py = [];
    for (let k = 0; k <= 2; k++) py[k] = comb(B, k) * comb(12 - B, 2 - k) / TOTB;

    let p = 0;
    for (let x = 0; x <= 5; x++) {
      if (!px[x]) continue;
      for (let y = 0; y <= 2; y++) {
        if (!py[y]) continue;
        if (winByHits(Math.min(x, 5), Math.min(y, 2))) p += px[x] * py[y];
      }
    }
    return p * 100;
  }

  // 精确覆盖率：胆拖 = 固定胆码 + 拖码补位。
  // 前区最大命中 = 命中胆数 a + min(命中拖数 b, 5-d)；后区同理。
  function exactDanPct(dF, tF, dB, tB) {
    const needF = 5 - dF, needB = 2 - dB;
    const restF = 35 - dF - tF, restB = 12 - dB - tB;
    const TOT = comb(35, 5), TOTB = comb(12, 2);

    // 前区联合分布 P(a,b)
    const pf = [];
    for (let a = 0; a <= dF; a++) {
      for (let b = 0; b <= tF; b++) {
        const c = 5 - a - b;
        if (c < 0 || c > restF) continue;
        const w = comb(dF, a) * comb(tF, b) * comb(restF, c) / TOT;
        if (!w) continue;
        pf.push({ a, b, w, maxHit: a + Math.min(b, needF) });
      }
    }
    // 后区联合分布 P(a,b)
    const pb = [];
    for (let a = 0; a <= dB; a++) {
      for (let b = 0; b <= tB; b++) {
        const c = 2 - a - b;
        if (c < 0 || c > restB) continue;
        const w = comb(dB, a) * comb(tB, b) * comb(restB, c) / TOTB;
        if (!w) continue;
        pb.push({ a, b, w, maxHit: a + Math.min(b, needB) });
      }
    }

    let p = 0;
    for (const f of pf) {
      for (const b of pb) {
        if (winByHits(Math.min(f.maxHit, 5), Math.min(b.maxHit, 2))) p += f.w * b.w;
      }
    }
    return p * 100;
  }

  // 普通模式（含断区/杀号，号码经贪心优化，无解析结构）→ 蒙特卡洛
  const FRONT_ALL = [...Array(35).keys()].map(x => x + 1);
  const BACK_ALL = [...Array(12).keys()].map(x => x + 1);

  function measureTickets(tickets, draws) {
    const rng = LOTTO.makeRng(null);
    let hit = 0;
    for (let d = 0; d < draws; d++) {
      const df = LOTTO.sample(FRONT_ALL, 5, rng);
      const db = LOTTO.sample(BACK_ALL, 2, rng);
      for (let i = 0; i < tickets.length; i++) {
        const t = tickets[i];
        if (LOTTO.prizeLevel(t[0], t[1], df, db) > 0) { hit++; break; }
      }
    }
    return hit / draws * 100;
  }

  function canUseMeasured() {
    return state.mode === 'normal'
      && state.zones.size === 0
      && parseNums($('killFront').value, 35).length === 0
      && parseNums($('killBack').value, 12).length === 0;
  }

  function coverageOf(tickets, exact) {
    const n = tickets.length;
    if (exact) return { pct: exact, tag: '精确' };
    if (MEASURED[n] !== undefined && canUseMeasured()) {
      return { pct: MEASURED[n], tag: '实测' };
    }
    return { pct: measureTickets(tickets, Math.max(2000, Math.min(8000, Math.round(200000 / Math.max(n, 1))))), tag: '模拟' };
  }

  // ---------- 注数渲染 ----------
  function renderTickets() {
    const row = $('ticketRow');
    row.innerHTML = '';
    TICKET_OPTIONS.forEach(o => {
      const c = document.createElement('div');
      c.className = 'chip' + (o.n === state.tickets ? ' active' : '') + (o.tag ? ' hot' : '');
      c.textContent = o.n;
      if (o.tag) {
        const t = document.createElement('span');
        t.className = 'tag';
        t.textContent = o.tag;
        c.appendChild(t);
      }
      c.onclick = () => { state.tickets = o.n; renderTickets(); updateProb(); };
      row.appendChild(c);
    });
  }

  function updateProb() {
    const n = state.tickets;
    $('ticketCount').textContent = n;
    $('ticketAmt').textContent = (n * PRICE) + ' 元';

    const pct = measuredPct(n);
    $('probVal').textContent = pct.toFixed(1) + '%';
    $('probFill').style.width = Math.min(100, pct) + '%';
    $('ticketNote').textContent = n >= 34 ? '高覆盖档' : '';
    updateProbHint();
  }

  // 顶部概率条只反映「普通模式注数档位」的实测值；
  // 复式/胆拖/断区/杀号会改变实际覆盖，这里明确提示。
  function updateProbHint() {
    const n = state.tickets;
    let note = `覆盖率档位实测 ${measuredPct(n).toFixed(1)}% · 独立理论上限 ${theoPct(n).toFixed(1)}%`;

    const extra = [];
    if (state.zones.size) extra.push(`${state.zones.size} 个断区`);
    if (parseNums($('killFront').value, 35).length) extra.push('前区杀号');
    if (parseNums($('killBack').value, 12).length) extra.push('后区杀号');
    if (extra.length) note += ` · 已启用${extra.join('/')}，实际覆盖低于该档位`;
    if (state.mode !== 'normal') note += ' · 当前为' + (state.mode === 'fu' ? '复式' : '胆拖') + '模式，实际覆盖以结果区为准';

    $('probNote').textContent = note;
  }

  // ---------- 开关 ----------
  function bindSwitch(id, key) {
    const el = $(id);
    el.onclick = () => {
      state[key] = !state[key];
      el.classList.toggle('on', state[key]);
    };
  }

  // ---------- 模式切换 ----------
  function bindTabs() {
    const tabs = [...document.querySelectorAll('#modeTabs .tab')];
    tabs.forEach(t => {
      t.onclick = () => {
        tabs.forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        state.mode = t.dataset.mode;
        $('panelNormal').style.display = state.mode === 'normal' ? '' : 'none';
        $('panelFu').style.display = state.mode === 'fu' ? '' : 'none';
        $('panelDan').style.display = state.mode === 'dan' ? '' : 'none';
        updateModeInfo();
        updateProbHint();
      };
    });
  }

  // ---------- 断区 ----------
  function bindZones() {
    [...document.querySelectorAll('#zoneRow .zone-chip')].forEach(z => {
      z.onclick = () => {
        const v = parseInt(z.dataset.zone, 10);
        if (state.zones.has(v)) { state.zones.delete(v); z.classList.remove('active'); }
        else { state.zones.add(v); z.classList.add('active'); }
        updateProb();
      };
    });
  }

  // ---------- 解析 ----------
  function parseNums(str, max) {
    if (!str || !str.trim()) return [];
    return str.split(/[,，\s]+/).map(s => parseInt(s, 10))
      .filter(n => !isNaN(n) && n >= 1 && n <= max);
  }

  function parseRatio(str) {
    if (!str || !str.trim()) return null;
    const parts = str.split(/[:：,，\s]+/).map(s => parseInt(s, 10));
    if (parts.length !== 3 || parts.some(n => isNaN(n))) return null;
    if (parts.reduce((a, b) => a + b, 0) !== 5) return null;
    return parts;
  }

  // ---------- 复式/胆拖 注数提示 ----------
  function updateModeInfo() {
    if (state.mode === 'fu') {
      const f = parseInt($('fuFront').value, 10) || 5;
      const b = parseInt($('fuBack').value, 10) || 2;
      const n = comb(f, 5) * comb(b, 2);
      $('fuInfo').textContent = `前区 ${f} 选 5 × 后区 ${b} 选 2 = ${n} 注，共 ${n * PRICE} 元。`;
    } else if (state.mode === 'dan') {
      const df = parseNums($('danFront').value, 35).length;
      const dt = parseNums($('danTuo').value, 35).length;
      const db = parseNums($('danBack').value, 12).length;
      const dbt = parseNums($('danBackTuo').value, 12).length;
      const needF = Math.max(0, 5 - df);
      const needB = Math.max(0, 2 - db);
      const n = comb(dt, needF) * comb(dbt, needB);
      $('danInfo').textContent = `胆码 ${df}/${db} 个，拖码 ${dt}/${dbt} 个 → ${n} 注，共 ${n * PRICE} 元。`;
    }
  }

  // ---------- 普通模式生成 ----------
  function genNormal() {
    const killFront = parseNums($('killFront').value, 35);
    const killBack = parseNums($('killBack').value, 12);
    const oddEven = $('oddEven').value ? parseInt($('oddEven').value, 10) : null;
    const zoneRatio = parseRatio($('zoneRatio').value);

    const cfg = {
      killFront, killBack,
      brokenZones: [...state.zones],
      oddEven: oddEven ? [oddEven] : null,
      zoneRatio,
      sumMin: parseInt($('sumMin').value, 10) || 80,
      sumMax: parseInt($('sumMax').value, 10) || 105,
      spanMin: parseInt($('spanMin').value, 10) || 20,
      spanMax: parseInt($('spanMax').value, 10) || 30,
      tierWeights: state.tierOpt ? undefined : { hot: 1, warm: 1, cold: 1, frozen: 1 }
    };

    const gen = new RULES.Generator(cfg);

    const candTarget = Math.max(state.tickets * 30, 300);
    const pool = [];
    const seen = new Set();
    let tries = candTarget * 12;

    while (pool.length < candTarget && tries > 0) {
      tries--;
      let t;
      try { t = gen.generate(); } catch (e) {
        if (pool.length === 0) throw e;
        break;
      }
      const k = JSON.stringify([t.front, t.back]);
      if (!seen.has(k)) { seen.add(k); pool.push([t.front, t.back]); }
    }
    if (pool.length === 0) throw new Error('无法生成任何合规号码，请放宽规则或减少杀号/断区');

    if (state.optOpt && pool.length > state.tickets) {
      return LOTTO.optimize(pool, state.tickets);
    }
    return pool.slice(0, state.tickets);
  }

  // ---------- 复式生成 ----------
  function genFu() {
    const f = Math.max(5, Math.min(18, parseInt($('fuFront').value, 10) || 6));
    const b = Math.max(2, Math.min(12, parseInt($('fuBack').value, 10) || 2));
    const killFront = parseNums($('killFront').value, 35);
    const killBack = parseNums($('killBack').value, 12);

    // 前区可选号（去杀号、去断区）
    let fp = [];
    for (let n = 1; n <= 35; n++) {
      if (killFront.includes(n)) continue;
      const zi = n <= 12 ? 1 : (n <= 24 ? 2 : 3);
      if (state.zones.has(zi)) continue;
      fp.push(n);
    }
    if (fp.length < f) throw new Error(`前区可用号码仅 ${fp.length} 个，不足 ${f} 个`);

    let bp = [];
    for (let n = 1; n <= 12; n++) if (!killBack.includes(n)) bp.push(n);
    if (bp.length < b) throw new Error(`后区可用号码仅 ${bp.length} 个，不足 ${b} 个`);

    // 复式：从可用号中按分层权重挑 f 个前区、b 个后区
    const gen = new RULES.Generator({
      records: loadRecords(),
      tierWeights: state.tierOpt ? undefined : { hot: 1, warm: 1, cold: 1, frozen: 1 }
    });
    const tw = gen.tierWeightsMap();

    const rng = LOTTO.makeRng(null);
    const pickWeighted = (pool, need) => {
      const pl = pool.slice();
      const out = [];
      for (let i = 0; i < need; i++) {
        let total = 0;
        const wl = pl.map(n => Math.max(tw[n] || 1, 1e-9));
        for (const w of wl) total += w;
        let r = rng.next() * total, idx = 0;
        for (let j = 0; j < wl.length; j++) { r -= wl[j]; if (r <= 0) { idx = j; break; } }
        out.push(pl.splice(idx, 1)[0]);
      }
      return out;
    };

    const front = pickWeighted(fp, f).sort((a, b) => a - b);
    const back = pickWeighted(bp, b).sort((a, b) => a - b);

    // 展开为全部单注（复式 → 组合）
    const tickets = [];
    const fc = [];
    const enumerate = (start, chosen) => {
      if (chosen.length === 5) { fc.push(chosen.slice()); return; }
      for (let i = start; i < front.length; i++) {
        chosen.push(front[i]); enumerate(i + 1, chosen); chosen.pop();
      }
    };
    enumerate(0, []);

    const bc = [];
    for (let i = 0; i < back.length; i++)
      for (let j = i + 1; j < back.length; j++) bc.push([back[i], back[j]]);

    for (const fset of fc) for (const bset of bc) tickets.push([fset, bset]);
    return { tickets, fu: { front, back }, exact: exactFuPct(f, b) };
  }

  // ---------- 胆拖生成 ----------
  function genDan() {
    const danF = parseNums($('danFront').value, 35);
    const tuoF = parseNums($('danTuo').value, 35).filter(n => !danF.includes(n));
    const danB = parseNums($('danBack').value, 12);
    const tuoB = parseNums($('danBackTuo').value, 12).filter(n => !danB.includes(n));

    if (danF.length > 5) throw new Error('前区胆码最多 5 个');
    if (danB.length > 2) throw new Error('后区胆码最多 2 个');
    const needF = 5 - danF.length;
    const needB = 2 - danB.length;
    if (tuoF.length < needF) throw new Error(`前区拖码需至少 ${needF} 个（当前 ${tuoF.length} 个）`);
    if (tuoB.length < needB) throw new Error(`后区拖码需至少 ${needB} 个（当前 ${tuoB.length} 个）`);

    const fc = [];
    const rec = (start, chosen) => {
      if (chosen.length === needF) { fc.push(chosen.slice()); return; }
      for (let i = start; i < tuoF.length; i++) {
        chosen.push(tuoF[i]); rec(i + 1, chosen); chosen.pop();
      }
    };
    rec(0, []);
    if (needF === 0) fc.push([]);

    const bc = [];
    const rec2 = (start, chosen) => {
      if (chosen.length === needB) { bc.push(chosen.slice()); return; }
      for (let i = start; i < tuoB.length; i++) {
        chosen.push(tuoB[i]); rec2(i + 1, chosen); chosen.pop();
      }
    };
    rec2(0, []);
    if (needB === 0) bc.push([]);

    const tickets = [];
    for (const f of fc) for (const b of bc) {
      tickets.push([[...danF, ...f].sort((a, b) => a - b), [...danB, ...b].sort((a, b) => a - b)]);
    }
    return { tickets, dan: { danF, tuoF, danB, tuoB }, exact: exactDanPct(danF.length, tuoF.length, danB.length, tuoB.length) };
  }

  // ---------- 主生成入口 ----------
  function generate() {
    const btn = $('btnGen');
    btn.disabled = true;
    btn.textContent = '计算中…';

    setTimeout(() => {
      try {
        let tickets, extra = null, exact = null;

        if (state.mode === 'normal') {
          tickets = genNormal();
        } else if (state.mode === 'fu') {
          const r = genFu();
          tickets = r.tickets; extra = { type: 'fu', data: r.fu }; exact = r.exact;
        } else {
          const r = genDan();
          tickets = r.tickets; extra = { type: 'dan', data: r.dan }; exact = r.exact;
        }

        state.result = tickets;
        renderResult(tickets, extra, exact);
        renderTier();

        toast(`已生成 ${tickets.length} 注`);
      } catch (e) {
        toast(e.message || '生成失败', true);
      } finally {
        btn.disabled = false;
        btn.textContent = '开始选号';
      }
    }, 30);
  }

  // ---------- 渲染结果 ----------
  function renderResult(tickets, extra, exact) {
    const box = $('result');
    box.innerHTML = '';

    // 复式/胆拖：先展示母号
    if (extra) {
      const head = document.createElement('div');
      head.className = 'card-title';
      head.style.marginBottom = '10px';
      if (extra.type === 'fu') {
        head.innerHTML = `<span class="bar"></span>复式 前区 ${extra.data.front.length} 个 · 后区 ${extra.data.back.length} 个`;
      } else {
        head.innerHTML = `<span class="bar"></span>胆拖 胆 ${extra.data.danF.length}+${extra.data.danB.length} · 拖 ${extra.data.tuoF.length}+${extra.data.tuoB.length}`;
      }
      box.appendChild(head);

      const srcLine = document.createElement('div');
      srcLine.className = 'balls';
      srcLine.style.marginBottom = '12px';
      const src = extra.type === 'fu'
        ? [extra.data.front, extra.data.back]
        : [[...extra.data.danF, ...extra.data.tuoF], [...extra.data.danB, ...extra.data.tuoB]];
      src[0].forEach(n => {
        const b = document.createElement('div');
        b.className = 'ball front'; b.textContent = String(n).padStart(2, '0');
        srcLine.appendChild(b);
      });
      const sp = document.createElement('div'); sp.className = 'ball-sep'; srcLine.appendChild(sp);
      src[1].forEach(n => {
        const b = document.createElement('div');
        b.className = 'ball back'; b.textContent = String(n).padStart(2, '0');
        srcLine.appendChild(b);
      });
      box.appendChild(srcLine);
    }

    const wrap = document.createElement('div');
    tickets.forEach((t, i) => {
      const line = document.createElement('div');
      line.className = 'ticket-line';

      const idx = document.createElement('div');
      idx.className = 'ticket-idx';
      idx.textContent = String(i + 1).padStart(2, '0');
      line.appendChild(idx);

      const balls = document.createElement('div');
      balls.className = 'balls';

      t[0].forEach((n, k) => {
        const b = document.createElement('div');
        b.className = 'ball front';
        b.textContent = String(n).padStart(2, '0');
        b.style.animationDelay = (k * 0.04) + 's';
        balls.appendChild(b);
      });

      const sep = document.createElement('div');
      sep.className = 'ball-sep';
      balls.appendChild(sep);

      t[1].forEach((n, k) => {
        const b = document.createElement('div');
        b.className = 'ball back';
        b.textContent = String(n).padStart(2, '0');
        b.style.animationDelay = ((5 + k) * 0.04) + 's';
        balls.appendChild(b);
      });

      line.appendChild(balls);
      wrap.appendChild(line);
    });
    box.appendChild(wrap);

    // 统计
    const ov = LOTTO.totalOverlap(tickets);
    const cov = coverageOf(tickets, exact);
    const stats = document.createElement('div');
    stats.className = 'stat-row';
    stats.innerHTML = `
      <div class="stat"><div class="sv">${tickets.length}</div><div class="sl">注数</div></div>
      <div class="stat"><div class="sv">${cov.pct.toFixed(1)}%</div><div class="sl">覆盖率${cov.tag}</div></div>
      <div class="stat"><div class="sv">${Math.round(ov)}</div><div class="sl">注间重叠</div></div>
    `;
    box.appendChild(stats);

    const hint = document.createElement('div');
    hint.className = 'hint';
    hint.innerHTML = `<span class="hi">◈</span><span>覆盖率为「至少中一注」的概率，由本组号码对随机开奖号做蒙特卡洛模拟得出。返奖率约 50%，长期投 100 元期望回收约 50 元。</span>`;
    box.appendChild(hint);
  }

  // ========== 开奖数据 ==========
  function renderDrawList() {
    const recs = loadRecords();
    const box = $('drawList');
    $('dataStatus').textContent = recs.length ? `${recs.length} 期` : '未获取';

    // 期号下拉
    const sel = $('checkPeriod');
    const prev = sel.value;
    sel.innerHTML = recs.length
      ? recs.map(r => `<option value="${r.period}">${r.period} 期 · ${r.date}</option>`).join('')
      : '<option value="">— 先获取开奖数据 —</option>';
    if (prev && recs.some(r => r.period === prev)) sel.value = prev;

    if (!recs.length) {
      box.innerHTML = '<div class="mini-empty">尚未获取开奖数据。点「获取最新开奖」联网拉取最近 30 期，离线时可手动录入。</div>';
      return;
    }

    box.innerHTML = '';
    recs.slice(0, 30).forEach((r, i) => {
      const row = document.createElement('div');
      row.className = 'draw-row' + (i === 0 ? ' latest' : '');
      const nums = r.front.map(n => `<b class="df">${String(n).padStart(2, '0')}</b>`).join('')
                 + `<span class="ds">+</span>`
                 + r.back.map(n => `<b class="db">${String(n).padStart(2, '0')}</b>`).join('');
      row.innerHTML = `<div class="dl">
          <div class="dp">${r.period}${i === 0 ? '<i>最新</i>' : ''}</div>
          <div class="dd">${r.date}</div>
        </div>
        <div class="dn">${nums}</div>`;
      box.appendChild(row);
    });
  }

  function doFetchDraws() {
    const btn = $('btnFetch');
    if (btn.disabled) return;
    const old = btn.textContent;
    btn.disabled = true;
    btn.textContent = '获取中…';

    LOTTO_DATA.fetchDraws(30)
      .then(recs => {
        renderDrawList();
        renderTier();
        toast(`已更新 ${recs.length} 期开奖数据`);
      })
      .catch(e => {
        toast('获取失败：' + e.message + '（可手动录入）', true);
      })
      .then(() => { btn.disabled = false; btn.textContent = old; });
  }

  function doManualDraw() {
    const form = $('manualForm');
    const open = form.style.display !== 'none';
    form.style.display = open ? 'none' : '';
    if (!open) {
      $('mPeriod').value = ''; $('mFront').value = ''; $('mBack').value = '';
      $('mPeriod').focus();
    }
  }

  function doManualSave() {
    const p = $('mPeriod').value.trim();
    const front = parseNums($('mFront').value, 35).sort((a, c) => a - c);
    const back = parseNums($('mBack').value, 12).sort((a, c) => a - c);
    if (!p) { toast('请填写期号', true); return; }
    if (front.length !== 5) { toast('前区要 5 个号码（1-35，不重复）', true); return; }
    if (back.length !== 2) { toast('后区要 2 个号码（1-12，不重复）', true); return; }

    const dup = loadRecords().some(r => r.period === p);
    LOTTO_DATA.addRecord(p, new Date().toISOString().slice(0, 10), front, back);
    $('manualForm').style.display = 'none';
    renderDrawList();
    renderTier();
    toast(dup ? `已覆盖 ${p} 期` : `已录入 ${p} 期`);
  }

  function doClearDraw() {
    const btn = $('btnClearDraw');
    if (doClearDraw._armed) {
      clearTimeout(doClearDraw._armed);
      doClearDraw._armed = null;
      btn.textContent = '清空';
      localStorage.removeItem(LOTTO_DATA.K_RECORDS);
      renderDrawList();
      renderTier();
      toast('已清空开奖数据');
      return;
    }
    btn.textContent = '再点确认清空';
    doClearDraw._armed = setTimeout(() => {
      doClearDraw._armed = null;
      btn.textContent = '清空';
    }, 3000);
  }

  // ========== 选号记录 ==========
  function renderSavedList() {
    const arr = LOTTO_DATA.loadSaved();
    $('savedCount').textContent = `${arr.length} 组`;
    const box = $('savedList');
    if (!arr.length) {
      box.innerHTML = '<div class="mini-empty">每次生成的号码可点「保存这组」，之后在这里核对是否中奖。</div>';
      return;
    }

    box.innerHTML = '';
    arr.slice(0, 30).forEach(g => {
      const d = new Date(g.ts);
      const row = document.createElement('div');
      row.className = 'saved-row';
      row.innerHTML = `
        <div class="saved-head">
          <span class="saved-time">${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}</span>
          <span class="saved-tag">${g.mode === 'fu' ? '复式' : g.mode === 'dan' ? '胆拖' : '普通'} · ${g.tickets.length} 注</span>
          <span class="saved-del" data-id="${g.id}">删除</span>
        </div>
        <div class="saved-nums">${g.tickets.slice(0, 3).map(t =>
          t[0].map(n => String(n).padStart(2, '0')).join(' ') + ' + ' + t[1].map(n => String(n).padStart(2, '0')).join(' ')
        ).join('<br>')}${g.tickets.length > 3 ? `<br><i>…共 ${g.tickets.length} 注</i>` : ''}</div>
        <div class="saved-act"><button class="mini-btn ghost chk" data-id="${g.id}">核对这组</button></div>`;
      box.appendChild(row);
    });

    box.querySelectorAll('.saved-del').forEach(el => {
      el.onclick = () => {
        LOTTO_DATA.removeGroup(el.dataset.id);
        renderSavedList();
        toast('已删除');
      };
    });
    box.querySelectorAll('.chk').forEach(el => {
      el.onclick = () => checkSavedGroup(el.dataset.id);
    });
  }

  function doSaveGroup() {
    if (!state.result || !state.result.length) { toast('还没有号码', true); return; }
    const id = String(Date.now());
    const group = {
      id,
      ts: Date.now(),
      mode: state.mode,
      tickets: state.result.map(t => [t[0].slice(), t[1].slice()])
    };
    LOTTO_DATA.saveGroup(group);
    renderSavedList();
    toast(`已保存 ${state.result.length} 注`);
  }

  // ========== 中奖核对 ==========
  function currentDraw() {
    // 优先用手动输入的号码
    const fIn = parseNums($('drawFrontIn').value, 35);
    const bIn = parseNums($('drawBackIn').value, 12);
    if (fIn.length === 5 && bIn.length === 2) {
      return { period: '手动输入', front: fIn.sort((a, c) => a - c), back: bIn.sort((a, c) => a - c) };
    }
    const pid = $('checkPeriod').value;
    const recs = loadRecords();
    const rec = recs.find(r => r.period === pid);
    if (!rec) return null;
    return rec;
  }

  function renderCheck(res, draw, title) {
    const box = $('checkResult');
    if (!res) { box.innerHTML = ''; return; }

    const moneyTxt = res.floating
      ? `${res.money} 元 + ${res.floating} 注浮动奖`
      : `${res.money} 元`;

    const head = `
      <div class="chk-head">
        <div class="chk-title">${title}</div>
        <div class="chk-draw">${draw.period} 期 · ${draw.front.map(n => String(n).padStart(2, '0')).join(' ')}
          <span class="ds">+</span> ${draw.back.map(n => String(n).padStart(2, '0')).join(' ')}</div>
      </div>
      <div class="stat-row" style="margin-top:10px">
        <div class="stat"><div class="sv">${res.winCount}/${res.total}</div><div class="sl">中奖注数</div></div>
        <div class="stat"><div class="sv">${res.best ? res.best.name : '未中'}</div><div class="sl">最高奖级</div></div>
        <div class="stat"><div class="sv">${moneyTxt}</div><div class="sl">奖金合计</div></div>
      </div>`;

    const rows = res.rows.map(r => {
      const cls = r.level > 0 ? ' win' : '';
      const money = r.money === -1 ? '浮动' : (r.money > 0 ? r.money + ' 元' : '—');
      return `<div class="chk-row${cls}">
        <span class="cr-idx">${String(r.idx).padStart(2, '0')}</span>
        <span class="cr-nums">${r.front.map(n => String(n).padStart(2, '0')).join(' ')}
          <i>+</i> ${r.back.map(n => String(n).padStart(2, '0')).join(' ')}</span>
        <span class="cr-hit">${r.cond}</span>
        <span class="cr-prize">${r.level > 0 ? r.name : '—'}</span>
        <span class="cr-money">${money}</span>
      </div>`;
    }).join('');

    box.innerHTML = head + `<div class="chk-list">${rows}</div>`;
  }

  function checkNow() {
    if (!state.result || !state.result.length) { toast('先点「开始选号」生成号码', true); return; }
    const draw = currentDraw();
    if (!draw) { toast('请先选择期号，或手动输入开奖号码', true); return; }
    const res = LOTTO_DATA.checkGroup(state.result, draw);
    renderCheck(res, draw, '当前这组号码');
    toast(res.winCount ? `中 ${res.winCount} 注` : '这组没中');
  }

  function checkSavedGroup(id) {
    const draw = currentDraw();
    if (!draw) { toast('请先选择期号，或手动输入开奖号码', true); return; }
    const g = LOTTO_DATA.loadSaved().find(x => x.id === id);
    if (!g) { toast('找不到这组记录', true); return; }
    const res = LOTTO_DATA.checkGroup(g.tickets, draw);
    renderCheck(res, draw, '已保存的号码');
    toast(res.winCount ? `中 ${res.winCount} 注` : '这组没中');
  }

  function checkAllSaved() {
    const draw = currentDraw();
    if (!draw) { toast('请先选择期号，或手动输入开奖号码', true); return; }
    const arr = LOTTO_DATA.loadSaved();
    if (!arr.length) { toast('还没有保存的号码', true); return; }

    // 汇总所有组
    const all = [];
    let totalTickets = 0;
    for (const g of arr) {
      const r = LOTTO_DATA.checkGroup(g.tickets, draw);
      totalTickets += r.total;
      all.push(...r.rows.map(x => Object.assign({}, x, { group: g.id })));
    }
    const win = all.filter(r => r.level > 0);
    const fixed = win.reduce((s, r) => s + (r.money > 0 ? r.money : 0), 0);
    const floating = win.filter(r => r.money === -1).length;
    const best = win.length ? win.reduce((a, b) => (a.level < b.level ? a : b)) : null;

    renderCheck({ rows: all, winCount: win.length, total: totalTickets, money: fixed, floating, best },
                draw, `全部 ${arr.length} 组 / ${totalTickets} 注`);
    toast(win.length ? `共中 ${win.length} 注` : '全部没中');
  }

  // ---------- 渲染分层 ----------
  function renderTier() {
    const recs = loadRecords();
    if (!recs.length) { $('tierCard').style.display = 'none'; return; }

    const tiers = RULES.tierNumbers(recs);
    const grid = $('tierGrid');
    grid.innerHTML = '';
    const names = { hot: '热号 ≤2期', warm: '温号 ≤7期', cold: '冷号 ≤14期', frozen: '极冷号 >14期' };
    for (const k of ['hot', 'warm', 'cold', 'frozen']) {
      const it = document.createElement('div');
      it.className = 'tier-item ' + k;
      it.innerHTML = `<div class="tname">${names[k]}（${tiers[k].length}）</div>
                      <div class="tnums">${tiers[k].length ? tiers[k].map(n => String(n).padStart(2, '0')).join(' ') : '—'}</div>`;
      grid.appendChild(it);
    }
    $('tierCard').style.display = '';
  }

  // ---------- 历史数据 ----------
  function loadRecords() { return LOTTO_DATA.loadRecords(); }

  // ---------- 复制 ----------
  function copyResult() {
    if (!state.result || !state.result.length) { toast('还没有号码', true); return; }
    const text = state.result.map((t, i) =>
      `${String(i + 1).padStart(2, '0')}  ${t[0].map(n => String(n).padStart(2, '0')).join(' ')}  +  ${t[1].map(n => String(n).padStart(2, '0')).join(' ')}`
    ).join('\n');

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        () => toast('已复制到剪贴板'),
        () => fallbackCopy(text)
      );
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); toast('已复制到剪贴板'); }
    catch { toast('复制失败，请手动选择', true); }
    document.body.removeChild(ta);
  }

  // ========== 数据导出 ==========
  function doExport() {
    const arr = LOTTO_DATA.loadSaved();
    if (!arr.length) { toast('还没有可导出的记录，先保存几组号码', true); return; }
    const json = LOTTO_DATA.exportAll();
    const name = '大乐透数据_' + new Date().toISOString().slice(0, 10).replace(/-/g, '') + '.json';
    const r = LOTTO_DATA.downloadExport(json, name);
    if (r.ok) toast('已导出：' + r.path);
    else toast('导出失败：' + (r.error || '未知'), true);
  }

  function doExportDel() {
    const btn = $('btnExportDel');
    if (doExportDel._armed) {
      clearTimeout(doExportDel._armed);
      doExportDel._armed = null;
      btn.textContent = '清空记录';
      LOTTO_DATA.clearSaved();
      renderSavedList();
      toast('选号记录已清空（开奖数据保留）');
      return;
    }
    btn.textContent = '再点确认';
    doExportDel._armed = setTimeout(() => {
      doExportDel._armed = null;
      btn.textContent = '清空记录';
    }, 3000);
  }

  // ========== 顶部导航 ==========
  function switchPage(page) {
    document.querySelectorAll('.page').forEach(p => { p.style.display = 'none'; });
    const target = $('page-' + page);
    if (target) target.style.display = '';
    document.querySelectorAll('.nav-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.page === page);
    });
    // 选号页有底部操作栏，其他页隐藏
    $('dock').style.display = (page === 'picker') ? '' : 'none';
    // 切到开奖页时刷新列表
    if (page === 'data') renderDrawList();
    if (page === 'saved') renderSavedList();
    if (page === 'check') { renderDrawList(); }
    if (page === 'ai') renderAiCfg();
    window.scrollTo(0, 0);
  }

  function bindNav() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.onclick = () => switchPage(btn.dataset.page);
    });
  }

  // ========== AI 选号 ==========
  function renderAiCfg() {
    const cfg = LOTTO_AI.loadCfg();
    // 服务商下拉
    const prov = $('aiProvider');
    prov.innerHTML = '';
    Object.keys(LOTTO_AI.PROVIDER_PRESETS).forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name + (LOTTO_AI.PROVIDER_PRESETS[name].free ? '（免费/低价）' : '');
      prov.appendChild(opt);
    });
    prov.value = cfg.provider;
    $('aiKey').value = cfg.api_key;
    $('aiUrl').value = cfg.base_url;
    $('aiModel').value = cfg.model;
    $('swAI').classList.toggle('on', !!cfg.enabled);
  }

  function bindAi() {
    $('swAI').onclick = () => {
      $('swAI').classList.toggle('on');
    };
    // 切服务商自动填充 base_url / model
    $('aiProvider').onchange = () => {
      const name = $('aiProvider').value;
      const preset = LOTTO_AI.PROVIDER_PRESETS[name];
      if (preset) {
        $('aiUrl').value = preset.base_url;
        $('aiModel').value = preset.model;
      }
    };
    $('btnAiSave').onclick = () => {
      const cfg = LOTTO_AI.loadCfg();
      cfg.enabled = $('swAI').classList.contains('on');
      cfg.provider = $('aiProvider').value;
      cfg.base_url = $('aiUrl').value.trim() || cfg.base_url;
      cfg.model = $('aiModel').value.trim() || cfg.model;
      cfg.api_key = $('aiKey').value.trim();
      LOTTO_AI.saveCfg(cfg);
      toast('AI 配置已保存（仅存本机）');
    };
    $('btnAiGo').onclick = () => {
      const cfg = LOTTO_AI.loadCfg();
      if (!cfg.enabled || !cfg.api_key) {
        toast('请先填写 API Key 并启用 AI，再保存配置', true);
        renderAiCfg();
        return;
      }
      const box = $('aiResult');
      box.innerHTML = '<div class="mini-empty">✦ AI 正在思考，请稍候…</div>';
      const btn = $('btnAiGo');
      btn.disabled = true;
      const old = btn.textContent;
      btn.textContent = '思考中…';

      const recs = loadRecords();
      const last = state.result && state.result.length ? state.result[0] : null;
      const prompt = LOTTO_AI.buildPrompt(recs, last);

      LOTTO_AI.chatOnce(cfg, prompt).then(r => {
        btn.disabled = false;
        btn.textContent = old;
        if (!r.ok) {
          box.innerHTML = `<div class="mini-empty">❌ ${r.err || '调用失败'}（不影响其他功能）</div>`;
          return;
        }
        const parsed = LOTTO_AI.parseResult(r.text);
        const front = parsed.front;
        const back = parsed.back;
        // 校验合法性（与桌面版 _validate_llm_result 一致）
        const legal = front.length === 5 && back.length === 2
          && new Set(front).size === 5 && new Set(back).size === 2
          && front.every(n => n >= 1 && n <= 35) && back.every(n => n >= 1 && n <= 12);
        if (!legal) {
          box.innerHTML = '<div class="mini-empty">模型输出未能解析出合法号码，请再试一次</div>';
          return;
        }
        box.innerHTML = `
          <div class="ai-head">✦ AI 建议（仅供参考）</div>
          <div class="balls">
            ${front.map(n => `<div class="ball front">${String(n).padStart(2, '0')}</div>`).join('')}
            <div class="ball-sep"></div>
            ${back.map(n => `<div class="ball back">${String(n).padStart(2, '0')}</div>`).join('')}
          </div>
          <div class="data-actions" style="margin-top:12px;margin-bottom:0">
            <button class="mini-btn" id="btnAiUse">采用这组号码</button>
            <button class="mini-btn ghost" id="btnAiSave2">保存这组</button>
          </div>
          <div class="hint" style="margin-top:10px"><span class="hi">◈</span><span>模型输出仅为随机性参考，不构成中奖保证。</span></div>`;
        $('btnAiUse').onclick = () => {
          state.result = [[front.slice(), back.slice()]];
          renderResult(state.result, null, null);
          switchPage('picker');
          toast('已采用 AI 号码（1 注）');
        };
        $('btnAiSave2').onclick = () => {
          LOTTO_DATA.saveGroup({
            id: String(Date.now()),
            ts: Date.now(),
            mode: 'ai',
            tickets: [[front.slice(), back.slice()]]
          });
          renderSavedList();
          toast('已保存 AI 号码');
        };
      });
    };
  }

  // ---------- 初始化 ----------
  function init() {
    renderTickets();
    updateProb();
    bindSwitch('swTier', 'tierOpt');
    bindSwitch('swPair', 'pairOpt');
    bindSwitch('swOpt', 'optOpt');
    bindTabs();
    bindZones();
    bindNav();
    bindAi();
    $('btnGen').onclick = generate;
    $('btnCopy').onclick = copyResult;
    $('btnSave').onclick = doSaveGroup;

    // 开奖数据 / 选号记录 / 中奖核对
    $('btnFetch').onclick = doFetchDraws;
    $('btnManual').onclick = doManualDraw;
    $('btnManualSave').onclick = doManualSave;
    $('btnManualCancel').onclick = () => { $('manualForm').style.display = 'none'; };
    $('btnClearDraw').onclick = doClearDraw;
    $('btnCheckSaved').onclick = checkAllSaved;
    $('btnCheckNow').onclick = checkNow;
    $('btnExport').onclick = doExport;
    $('btnExportDel').onclick = doExportDel;
    ['drawFrontIn', 'drawBackIn'].forEach(id => { $(id).oninput = () => { $('checkResult').innerHTML = ''; }; });
    $('checkPeriod').onchange = () => { $('checkResult').innerHTML = ''; };
    renderDrawList();
    renderSavedList();

    ['fuFront', 'fuBack'].forEach(id => { $(id).oninput = updateModeInfo; });
    ['danFront', 'danTuo', 'danBack', 'danBackTuo'].forEach(id => { $(id).oninput = updateModeInfo; });
    ['killFront', 'killBack'].forEach(id => { $(id).oninput = updateProbHint; });
    updateModeInfo();

    if (loadRecords().length) renderTier();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
