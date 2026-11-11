/* ============================================================
 * lotto-rules.js — 选号规则引擎（与 Python 版规则严格一致）
 * 浏览器：依赖 lotto-core.js 先加载（全局 LOTTO）
 * Node：显式 require
 * ============================================================ */
'use strict';

const LOTTO_REF = (typeof LOTTO !== 'undefined') ? LOTTO : require('./lotto-core.js');

const RULES = (function (LOTTO) {

  // ---------- 区间定义 ----------
  const ZONES = [
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
    [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]
  ];

  // ---------- 对码映射（PAIR_MAP，与 Python 版逐项一致） ----------
  const PAIR_MAP = {
    1: [4], 2: [8], 3: [6], 4: [1, 7], 5: [10],
    6: [3, 9], 7: [4], 8: [2], 9: [6], 10: [5],
    11: [14], 12: [18], 13: [16], 14: [11, 17], 15: [20],
    16: [13, 19], 17: [14], 18: [12], 19: [16], 20: [15],
    21: [24], 22: [28], 23: [16], 24: [21, 27], 25: [30],
    26: [23, 29], 27: [24], 28: [22], 29: [26], 30: [25],
    31: [34], 32: [35], 33: [33], 34: [31], 35: [32]
  };

  // ---------- 遗漏分层 ----------
  const TIER_HOT = 2, TIER_WARM = 7, TIER_COLD = 14;

  function tierOf(omission) {
    if (omission <= TIER_HOT) return 'hot';
    if (omission <= TIER_WARM) return 'warm';
    if (omission <= TIER_COLD) return 'cold';
    return 'frozen';
  }

  const TIER_LABEL = { hot: '热', warm: '温', cold: '冷', frozen: '极冷' };

  // ---------- 遗漏值计算 ----------
  function computeOmission(records, maxNum = 35) {
    const om = {};
    for (let n = 1; n <= maxNum; n++) om[n] = records.length;
    // records[0] 为最新一期
    for (let i = 0; i < records.length; i++) {
      for (const n of records[i].front) {
        if (om[n] === records.length) om[n] = i;
      }
    }
    return om;
  }

  function tierNumbers(records) {
    const om = computeOmission(records, 35);
    const out = { hot: [], warm: [], cold: [], frozen: [] };
    for (let n = 1; n <= 35; n++) out[tierOf(om[n])].push(n);
    return out;
  }

  // ---------- 校验一注前区 ----------
  // relax: 0 全部；1 放宽度/连号/对码；2 仅和值+奇偶+跨度；3 仅和值+奇偶
  function validateFront(selected, opts = {}, relax = 0) {
    if (selected.length !== 5) return false;
    const o = {
      sumMin: 80, sumMax: 105, spanMin: 20, spanMax: 30,
      oddEven: null, zoneRatio: null,
      ...opts
    };
    const total = selected.reduce((a, b) => a + b, 0);
    if (total < o.sumMin || total > o.sumMax) return false;

    const odd = selected.filter(n => n % 2 === 1).length;
    if (o.oddEven) {
      if (odd !== o.oddEven[0]) return false;
    } else {
      if (odd !== 2 && odd !== 3) return false;
    }
    if (relax >= 3) return true;

    const span = Math.max(...selected) - Math.min(...selected);
    if (span < o.spanMin || span > o.spanMax) return false;
    if (relax >= 2) return true;

    // 三连号禁止（差值连续 2）
    const s = selected.slice().sort((a, b) => a - b);
    for (let i = 0; i + 2 < s.length; i++) {
      if (s[i + 1] - s[i] === 1 && s[i + 2] - s[i + 1] === 1) return false;
    }
    if (relax >= 1) return true;

    // 对码互斥：同一注内不得同时出现互为对码的两个号
    for (let i = 0; i < s.length; i++) {
      for (let j = i + 1; j < s.length; j++) {
        if ((PAIR_MAP[s[i]] || []).includes(s[j])) return false;
      }
    }

    // 区间比
    if (o.zoneRatio) {
      const zc = [0, 0, 0];
      for (const n of s) {
        if (n <= 12) zc[0]++;
        else if (n <= 24) zc[1]++;
        else zc[2]++;
      }
      if (zc[0] !== o.zoneRatio[0] || zc[1] !== o.zoneRatio[1] || zc[2] !== o.zoneRatio[2]) return false;
    }
    return true;
  }

  // ---------- 校验后区 ----------
  function validateBack(back, opts = {}) {
    if (back.length !== 2) return false;
    if (back[0] === back[1]) return false;
    const odd = back.filter(n => n % 2 === 1).length;
    if (odd !== 1) return false;
    const s = back[0] + back[1];
    if (s < 8 || s > 18) return false;
    if (back[0] % 10 === back[1] % 10) return false;
    return true;
  }

  // ---------- 生成器 ----------
  const TIER_WEIGHTS = { hot: 2.4, warm: 1.6, cold: 1.1, frozen: 1.5 };

  class Generator {
    constructor(cfg = {}) {
      this.records = cfg.records || [];
      this.killFront = cfg.killFront || [];
      this.killBack = cfg.killBack || [];
      this.brokenZones = cfg.brokenZones || [];
      this.oddEven = cfg.oddEven || null;
      this.zoneRatio = cfg.zoneRatio || null;
      this.frontPool = cfg.frontPool || null;
      this.tierWeights = cfg.tierWeights || TIER_WEIGHTS;
      this.sumMin = cfg.sumMin ?? 80;
      this.sumMax = cfg.sumMax ?? 105;
      this.spanMin = cfg.spanMin ?? 20;
      this.spanMax = cfg.spanMax ?? 30;
      this.rng = cfg.rng || LOTTO.makeRng(null);
      this._tiers = null;
    }

    tierWeightsMap() {
      const w = {};
      for (let n = 1; n <= 35; n++) w[n] = 1.0;
      if (!this.records.length) return w;
      if (!this._tiers) this._tiers = tierNumbers(this.records);
      for (const k of ['hot', 'warm', 'cold', 'frozen']) {
        const wv = this.tierWeights[k] ?? 1.0;
        for (const n of this._tiers[k]) w[n] = wv;
      }
      return w;
    }

    disabledSet() {
      const d = new Set(this.killFront);
      for (const zi of this.brokenZones) {
        if (ZONES[zi - 1]) ZONES[zi - 1].forEach(n => d.add(n));
      }
      return d;
    }

    validateOpts() {
      return {
        sumMin: this.sumMin, sumMax: this.sumMax,
        spanMin: this.spanMin, spanMax: this.spanMax,
        oddEven: this.oddEven, zoneRatio: this.zoneRatio
      };
    }

    weightedPickFront(pool, need) {
      const tw = this.tierWeightsMap();
      const pl = pool.slice();
      const wl = pl.map(n => Math.max(tw[n] ?? 1.0, 1e-9));
      const picked = [];
      for (let i = 0; i < need; i++) {
        let total = 0;
        for (const w of wl) total += w;
        let r = this.rng.next() * total;
        let idx = 0;
        for (let j = 0; j < wl.length; j++) {
          r -= wl[j];
          if (r <= 0) { idx = j; break; }
        }
        picked.push(pl.splice(idx, 1)[0]);
        wl.splice(idx, 1);
      }
      return picked;
    }

    pickFront() {
      const disabled = this.disabledSet();
      let pool = (this.frontPool || Array.from({ length: 35 }, (_, i) => i + 1))
        .filter(n => !disabled.has(n));
      if (pool.length < 5) {
        throw new Error(`号码池经杀号/断区过滤后不足 5 个（当前仅 ${pool.length} 个），请调整杀号或断区`);
      }
      const vo = this.validateOpts();

      // 第一轮：加权采样，严格校验
      for (let i = 0; i < 800; i++) {
        const s = this.weightedPickFront(pool, 5).sort((a, b) => a - b);
        if (validateFront(s, vo, 0)) return s;
      }
      // 第二轮：趋势排序滑窗
      const sorted = pool.slice().sort((a, b) => a - b);
      for (let i = 0; i + 5 <= sorted.length; i++) {
        const s = sorted.slice(i, i + 5);
        if (validateFront(s, vo, 0)) return s;
      }
      // 第三轮：逐级放宽
      for (let relax = 1; relax <= 3; relax++) {
        for (let i = 0; i < 600; i++) {
          const s = LOTTO.sample(pool, 5, this.rng).sort((a, b) => a - b);
          if (validateFront(s, vo, relax)) return s;
        }
      }
      throw new Error(`当前号码池（${pool.length} 个可用号）无法满足选号规则：和值 ${this.sumMin}-${this.sumMax}、奇数 2-3、跨度 ${this.spanMin}-${this.spanMax} 无解。请减少断区/杀号，或放宽规则后重试`);
    }

    pickBack() {
      let pool = Array.from({ length: 12 }, (_, i) => i + 1).filter(n => !this.killBack.includes(n));
      if (pool.length < 2) throw new Error(`后区号码不足 2 个（当前仅 ${pool.length} 个）`);
      for (let i = 0; i < 300; i++) {
        const b = LOTTO.sample(pool, 2, this.rng).sort((a, b) => a - b);
        if (validateBack(b)) return b;
      }
      // 放宽：仅要求不同且和为 8-18
      for (let i = 0; i < 400; i++) {
        const b = LOTTO.sample(pool, 2, this.rng).sort((a, b) => a - b);
        const s = b[0] + b[1];
        if (b[0] !== b[1] && s >= 8 && s <= 18) return b;
      }
      throw new Error('后区无法满足规则（奇偶/和值/尾数），请调整杀号');
    }

    generate() {
      return { front: this.pickFront(), back: this.pickBack() };
    }
  }

  return {
    ZONES, PAIR_MAP, TIER_LABEL,
    tierOf, computeOmission, tierNumbers,
    validateFront, validateBack, Generator
  };
})(LOTTO_REF);

if (typeof module !== 'undefined' && module.exports) module.exports = RULES;
